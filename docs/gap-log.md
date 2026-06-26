# Gap Log — AI CAD Drafter

Running list of known gaps between "what the chat agent can talk about"
and "what actually changes in the drawing." Add to this list as new gaps
are found; check items off (with commit hash) as they're closed.

See `docs/architecture-ai-cad-drafter.md` for the design that closes the
items below.

## Open gaps

### 1. Materials are parsed but never applied
`chat_agent.py`'s `process_message()` extracts `materials: {component: description}`
from a user message (e.g. "the base is hammered brass") and stores it on
`DrawingState`. `/chat` (`routes.py:1197`) records it to Central Brain
(`record_material`) and echoes it back in the response. **Nothing reads
`state.materials` back into the actual drawing** — `dxf_exporter.py` and
`drawing_model.py` use fixed hatch patterns and fixed leader-annotation
text per component (e.g. `"Black hammered textured- apply a layer of PU
coating for paint protection"` is a literal string in
`drawing_model.py:493`, not a template). Saying "make it brass" changes
nothing visible.

### 2. Visibility is parsed but never applied
Same shape of gap as #1. `state.visibility: {component: bool}` is parsed
and stored, but the renderers only have ONE visibility mechanism today —
confidence-based hide/dash via `anti_hallucination_validator.py`'s
`_visible()`/`_is_estimated()` helpers in `dxf_exporter.py`. There's no
path for a user's explicit "hide the base plate" to reach that logic.

### 3. "Merge sections" doesn't exist as a concept anywhere
No code path treats two adjacent named components (e.g. `neck_ring` +
`pedestal_body`) as a single continuous shape. Each furniture builder
(`build_round_pedestal_model`, `save_round_pedestal_table`, etc.) draws a
fixed sequence of independent polygons with hardcoded boundaries between
them. There's nothing to "merge" — this needs new geometry support, not
just a new chat intent.

### 4. Chat agent's vocabulary is stale relative to `component_schema`
`chat_agent.py`'s `SYSTEM_PROMPT` (line 65) hardcodes a dimension-key list
(`top_diameter_cm, overall_height_cm, base_diameter_cm, top_thickness_cm,
width_cm, depth_cm`) and a material-component list
(`tabletop, pedestal_base, neck_ring, legs, seat, backrest, frame,
drawer_front, base_foot`) that predates `_component_schema()`
(`routes.py:97`, added for the slider panel generalization). It doesn't
know about `collar_diameter_cm`, doesn't know component names are
supposed to match `data-component` / schema section names 1:1, and isn't
furniture-type-aware (every furniture type gets the same fixed prompt).

### 5. ChatBox only forwards dimension updates to the backend
`ChatBox.tsx:70-84` — when the LLM returns `action: "render"`, the
frontend only calls `/adjust` if `data.state.dimensions` is non-empty.
Materials/visibility/merge updates from chat never reach any endpoint,
even once #1-#3 are fixed backend-side, unless this is also updated.

## Closed gaps
(none yet)
