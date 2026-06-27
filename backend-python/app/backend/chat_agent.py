"""
Conversational Chat Agent — parse user messages into structured drawing state.

Primary: OpenAI GPT-4o (fast, reliable JSON output)
Fallback: Ollama Hermes 3 (local, no API key needed)

Supported intents:
- MATERIAL: component material/finish/color overrides
- DIMENSION: measurement corrections
- VISIBILITY: component confirm/deny
- NOTE: general annotations, workflow instructions
- FURNITURE_TYPE: type correction
"""

import json
import os
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional

OLLAMA_URL = "http://localhost:11434/api/generate"
CHAT_MODEL = "hermes3:3b"  # Ollama fallback
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")


@dataclass
class DrawingState:
    """Accumulated user corrections to the CAD drawing."""
    furniture_type: Optional[str] = None
    materials: Dict[str, str] = field(default_factory=dict)
    dimensions: Dict[str, float] = field(default_factory=dict)
    visibility: Dict[str, bool] = field(default_factory=dict)
    notes: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)

    def apply_to_template_params(self) -> dict:
        return {
            "furniture_type": self.furniture_type,
            "materials": dict(self.materials),
            "dimensions": dict(self.dimensions),
            "visibility": dict(self.visibility),
            "notes": list(self.notes),
        }

    def to_dict(self) -> dict:
        return {
            "furniture_type": self.furniture_type,
            "materials": self.materials,
            "dimensions": self.dimensions,
            "visibility": self.visibility,
            "notes": self.notes,
            "corrections": self.corrections,
        }


@dataclass
class ChatResponse:
    message: str
    state: DrawingState
    extracted: dict
    action: str = "continue"
    render_hint: Optional[str] = None


# All 18 furniture types supported by the template graph system:
FURNITURE_TYPES_LIST = (
    "round_pedestal_table, rectangular_table, cabinet, sofa, coffee_table, "
    "dining_chair, wardrobe, reception_counter, bed_headboard, "
    "asymmetric_pedestal_table, oval_pedestal_table, console_table, "
    "office_desk, side_table, lounge_chair, nightstand, bed, sideboard, tv_console"
)

# Editable dimension keys per furniture type:
DIMENSION_KEYS_BY_TYPE = {
    "round_pedestal_table": "top_diameter_cm, overall_height_cm, base_diameter_cm, neck_diameter_cm, collar_diameter_cm, top_thickness_cm",
    "rectangular_table": "width_cm, depth_cm, overall_height_cm, leg_thickness_cm, top_thickness_cm, leg_inset_cm",
    "cabinet": "width_cm, depth_cm, overall_height_cm, door_count, door_thickness_cm, drawer_count, base_height_cm",
    "sofa": "width_cm, depth_cm, overall_height_cm, seat_height_cm, armrest_width_cm, armrest_height_cm, backrest_height_cm, leg_height_cm",
    "coffee_table": "width_cm, depth_cm, overall_height_cm, top_thickness_cm, leg_thickness_cm, lower_shelf_height_cm",
    "dining_chair": "width_cm, overall_height_cm, seat_height_cm, seat_depth_cm, backrest_height_cm, leg_thickness_cm",
    "wardrobe": "width_cm, depth_cm, overall_height_cm, door_count, rail_height_cm, shelf_count, base_height_cm",
    "bed_headboard": "width_cm, overall_height_cm, panel_thickness_cm, post_width_cm, post_height_cm",
    "reception_counter": "width_cm, depth_cm, overall_height_cm, top_thickness_cm, base_height_cm, overhang_cm",
    "asymmetric_pedestal_table": "length_cm, depth_cm, overall_height_cm, top_thickness_cm, large_ped_dia_cm, small_ped_dia_cm, left_ped_x_cm, right_ped_x_cm, overhang_cm",
    "oval_pedestal_table": "length_cm, depth_cm, overall_height_cm, top_thickness_cm, pedestal_dia_cm",
    "console_table": "length_cm, depth_cm, overall_height_cm, top_thickness_cm, leg_thick_cm, leg_inset_cm",
    "office_desk": "length_cm, depth_cm, overall_height_cm, top_thickness_cm, leg_thick_cm, modesty_panel_h_cm",
}

SYSTEM_PROMPT = """You are a furniture CAD assistant for a shop drawing generator app.

Your job: analyze user messages about furniture items and return structured JSON.

The app generates professional CAD drawings (DXF format) from uploaded furniture images. Users can chat with you to:
1. Describe the item (materials, finish, style)
2. Provide exact dimensions
3. Correct the AI's furniture type detection
4. Specify which components are visible or hidden
5. Teach you workflow preferences (e.g., 'always use brushed steel for modern pieces')

SUPPORTED FURNITURE TYPES (all 18):
{types_list}

EDITABLE DIMENSION KEYS BY TYPE:
{dim_keys}

Return ONLY valid JSON:
{{
  "response": "your concise, helpful reply to the user (1-2 sentences)",
  "action": "continue" or "render",
  "updates": {{
    "furniture_type": null or one of the types listed above,
    "materials": {{"component": "material description"}},
    "dimensions": {{"component": value_in_cm_number}},
    "visibility": {{"component": true_or_false}},
    "notes": ["note text for the drawing"]
  }}
}}

Material components per type:
- round_pedestal_table: tabletop, collar_plate, neck_ring, pedestal_body, base_foot
- rectangular_table/cabinet/wardrobe: tabletop/carcass, doors/legs, base
- sofa: body, seat, backrest, armrests, legs
- coffee_table/console_table/office_desk: tabletop, legs, lower_shelf/modesty_panel
- dining_chair: seat, backrest, legs
- bed_headboard: headboard, posts/posts, frame
- reception_counter: counter_top, front_panel, base
- asymmetric_pedestal_table/oval_pedestal_table: tabletop, large_pedestal/small_pedestal/pedestal
Dimension keys: top_diameter_cm, overall_height_cm, base_diameter_cm, neck_diameter_cm, collar_diameter_cm, top_thickness_cm, width_cm, depth_cm, leg_thickness_cm, length_cm, large_ped_dia_cm, small_ped_dia_cm, pedestal_dia_cm, modesty_panel_h_cm, seat_height_cm, backrest_height_cm, door_count, shelf_count
Visibility: set to false to hide a component, true to show it

The drawing state given as context (if any) shows the CURRENT value of every dimension already set — use it to resolve relative/relational requests.

Rules:
- Be conversational and helpful
- Extract ALL measurable details from user messages
- If the user gives a RELATIONAL instruction without an exact number (e.g. "make the base a different diameter than the pedestal/neck", "the legs should be thicker", "make it wider than the top") you MUST still compute and return a concrete number in updates.dimensions using the current state shown in context plus normal furniture proportions - never leave it unset or silently do nothing. State your reasoning briefly in the response (e.g. "neck is 50cm, so I set the base to 65cm").
- If a relational request references a component with no key in the dimension keys above, pick the closest matching key - do not skip the request.
- If user says 'render', 'generate', 'show me', or 'update drawing' → set action to "render"
- If user describes a workflow preference, store it in notes
- Default action is "continue" unless user explicitly asks for rendering
""".format(
    types_list=FURNITURE_TYPES_LIST,
    dim_keys="\\n".join(f"  {k}: {v}" for k, v in DIMENSION_KEYS_BY_TYPE.items())
)


def _openai_chat(prompt: str, context: Optional[str] = None) -> Optional[str]:
    """Call OpenAI GPT-4o for intent parsing."""
    if not OPENAI_API_KEY:
        return None

    system = SYSTEM_PROMPT
    user_msg = prompt
    if context:
        user_msg = f"Current drawing state:\n{context}\n\nUser message: {prompt}"

    payload = json.dumps({
        "model": "gpt-4o",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_msg},
        ],
        "max_tokens": 600,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }).encode()

    try:
        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OPENAI_API_KEY}",
            },
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            content = result["choices"][0]["message"]["content"]
            return content
    except Exception as e:
        print(f"[ChatAgent] OpenAI error: {e}")
        return None


def _ollama_chat(prompt: str, context: Optional[str] = None) -> Optional[str]:
    """Call Ollama Hermes 3 as fallback."""
    full_prompt = SYSTEM_PROMPT
    if context:
        full_prompt += f"\n\nCurrent drawing state:\n{context}\n\nUser message: {prompt}"
    else:
        full_prompt += f"\n\nUser message: {prompt}"

    payload = json.dumps({
        "model": CHAT_MODEL,
        "prompt": full_prompt,
        "stream": False,
        "options": {"temperature": 0.3, "num_predict": 512},
    }).encode()

    try:
        req = urllib.request.Request(OLLAMA_URL, data=payload,
                                      headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode())
            return result.get("response", "")
    except Exception as e:
        print(f"[ChatAgent] Ollama error: {e}")
        return None


def _extract_json(text: str) -> Optional[dict]:
    """Extract JSON object from LLM response, with markdown fence stripping."""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        import re
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None


def process_message(message: str, state: Optional[DrawingState] = None) -> ChatResponse:
    """Process a user chat message, trying OpenAI first, then Ollama."""
    state = state or DrawingState()

    # Build context
    context_parts = []
    if state.furniture_type:
        context_parts.append(f"Furniture type: {state.furniture_type}")
    if state.materials:
        context_parts.append(f"Materials: {json.dumps(state.materials)}")
    if state.dimensions:
        context_parts.append(f"Dimensions: {json.dumps(state.dimensions)}")
    if state.visibility:
        context_parts.append(f"Visibility: {json.dumps(state.visibility)}")
    if state.notes:
        context_parts.append(f"Notes: {'; '.join(state.notes)}")
    context = "\n".join(context_parts) if context_parts else None

    # Try OpenAI first, fall back to Ollama
    raw = _openai_chat(message, context)
    backend = "OpenAI"
    if raw is None:
        raw = _ollama_chat(message, context)
        backend = "Ollama"

    extracted = _extract_json(raw) if raw else {}

    if not extracted:
        return ChatResponse(
            message=raw or "I couldn't process that. Try describing the material or dimensions.",
            state=state,
            extracted={},
            action="continue",
        )

    # Apply updates
    updates = extracted.get("updates", {})

    if updates.get("furniture_type"):
        state.furniture_type = updates["furniture_type"]
        state.corrections.append(f"Type: {updates['furniture_type']}")

    if updates.get("materials"):
        state.materials.update(updates["materials"])
        for comp, mat in updates["materials"].items():
            state.corrections.append(f"Material: {comp} → {mat}")

    if updates.get("dimensions"):
        state.dimensions.update(updates["dimensions"])
        for comp, val in updates["dimensions"].items():
            state.corrections.append(f"Dimension: {comp} = {val} cm")

    if updates.get("visibility"):
        state.visibility.update(updates["visibility"])
        for comp, vis in updates["visibility"].items():
            state.corrections.append(f"Visibility: {comp} → {'visible' if vis else 'hidden'}")

    if updates.get("notes"):
        state.notes.extend(updates["notes"])
        state.corrections.extend(updates["notes"])

    return ChatResponse(
        message=extracted.get("response", "Updated."),
        state=state,
        extracted=extracted,
        action=extracted.get("action", "continue"),
        render_hint="all" if extracted.get("action") == "render" else None,
    )


def chat_with_agent(message: str, session_state: Optional[Dict] = None) -> dict:
    """Main entry point for the chat endpoint."""
    prev_state = None
    if session_state:
        prev_state = DrawingState(
            furniture_type=session_state.get("furniture_type"),
            materials=session_state.get("materials", {}),
            dimensions=session_state.get("dimensions", {}),
            visibility=session_state.get("visibility", {}),
            notes=session_state.get("notes", []),
            corrections=session_state.get("corrections", []),
        )

    result = process_message(message, prev_state)
    return {
        "response": result.message,
        "state": result.state.to_dict(),
        "action": result.action,
        "render_hint": result.render_hint,
    }
