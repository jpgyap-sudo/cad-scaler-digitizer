"""
Conversational Chat Agent — parse user messages into structured drawing state.

Uses Ollama (Hermes 3) to extract intent from natural language messages.
Maintains a DrawingState that accumulates corrections across conversation turns.

Supported intents:
- MATERIAL: component material/finish/color overrides
- DIMENSION: measurement corrections
- VISIBILITY: component confirm/deny
- NOTE: general annotations
- FURNITURE_TYPE: type correction
"""

import json
import urllib.request
from dataclasses import dataclass, field
from typing import Dict, List, Optional

OLLAMA_URL = "http://localhost:11434/api/generate"
CHAT_MODEL = "hermes3:3b"  # Fast, good at structured output


@dataclass
class DrawingState:
    """Accumulated user corrections to the CAD drawing."""
    furniture_type: Optional[str] = None
    materials: Dict[str, str] = field(default_factory=dict)   # component -> material desc
    dimensions: Dict[str, float] = field(default_factory=dict) # component -> value_cm
    visibility: Dict[str, bool] = field(default_factory=dict)  # component -> confirmed
    notes: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)       # history

    def apply_to_template_params(self) -> dict:
        """Return overrides suitable for passing to template functions."""
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
    """Result of processing a user chat message."""
    message: str                             # AI response text
    state: DrawingState                      # Updated drawing state
    extracted: dict                          # Raw extraction from LLM
    action: str = "continue"                 # "done", "render", "continue"
    render_hint: Optional[str] = None        # What to re-render


SYSTEM_PROMPT = """You are a furniture CAD assistant. Parse user messages about furniture drawings.

Return ONLY valid JSON with these fields:
{
  "response": "your helpful reply to the user",
  "action": "continue" or "render" or "done",
  "updates": {
    "furniture_type": null or corrected type (round_pedestal_table, rectangular_table, cabinet, sofa, coffee_table, dining_chair, wardrobe, reception_counter, bed_headboard),
    "materials": {"component_name": "material description"},
    "dimensions": {"component_name": value_in_cm},
    "visibility": {"component_name": true_or_false},
    "notes": ["note text"]
  }
}

Rules:
- If user specifies a material, add to materials dict. Keys: tabletop, pedestal_base, neck_ring, legs, seat, etc.
- If user gives a measurement, add to dimensions dict. Keys: top_diameter_cm, overall_height_cm, base_diameter_cm, top_thickness_cm, etc.
- If user confirms/denies a component, set visibility to true/false.
- If user corrects the furniture type, set furniture_type.
- If user asks to render/generate/show, set action to "render".
- Be conversational but concise.
- If you don't understand, ask a clarifying question.
"""


def _ollama_chat(prompt: str, context: Optional[str] = None) -> str:
    """Call Ollama Hermes 3 model for intent parsing."""
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
    # Strip markdown fences
    if text.startswith("```"):
        text = text.split("\n", 1)[-1] if "\n" in text else text[3:]
    if text.rstrip().endswith("```"):
        text = text.rstrip()[:-3]
    text = text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        # Try to find JSON object in text
        import re
        m = re.search(r'\{[\s\S]*\}', text)
        if m:
            try:
                return json.loads(m.group(0))
            except Exception:
                pass
    return None


def process_message(message: str, state: Optional[DrawingState] = None) -> ChatResponse:
    """
    Process a user chat message and update drawing state.

    Args:
        message: User's natural language message
        state: Current drawing state (None for first message)

    Returns:
        ChatResponse with AI reply and updated state
    """
    state = state or DrawingState()

    # Build context from current state
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

    # Call Ollama
    raw = _ollama_chat(message, context)
    extracted = _extract_json(raw) if raw else {}

    if not extracted:
        return ChatResponse(
            message=raw or "I didn't understand that. Could you rephrase?",
            state=state,
            extracted={},
            action="continue",
        )

    # Apply updates to state
    updates = extracted.get("updates", {})

    if updates.get("furniture_type"):
        state.furniture_type = updates["furniture_type"]
        state.corrections.append(f"Type corrected to {updates['furniture_type']}")

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


# Public API
def chat_with_agent(
    message: str,
    session_state: Optional[Dict] = None,
) -> dict:
    """
    Main entry point for the chat endpoint.

    Args:
        message: User's message
        session_state: Previous state dict (from state.to_dict())

    Returns:
        dict with "response", "state", "action", "render_hint"
    """
    # Reconstruct state from previous session
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
