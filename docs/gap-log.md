# Gap Log — AI CAD Drafter

Running list of known gaps between "what the chat agent can talk about"
and "what actually changes in the drawing." Add to this list as new gaps
are found; check items off (with commit hash) as they're closed.

See `docs/architecture-ai-cad-drafter.md` for the design that closes the
items below.

## Open gaps

### 1. Materials are parsed but never applied — PARTIALLY CLOSED (a7d7190)
~~`chat_agent.py`'s `process_message()` extracts `materials: {component: description}`
from a user message (e.g. "the base is hammered brass") and stores it on
`DrawingState`. **Nothing reads `state.materials` back into the actual
drawing.**~~ Closed for `round_pedestal_table` only: `build_round_pedestal_model`
and `save_round_pedestal_table` now accept a `materials` dict that overrides
the per-component leader text and title-block notes; `POST /api/material/edit`
sets/overrides it directly, persisted in the `.json` sidecar; `ChatBox.tsx`
now forwards `state.materials` to that endpoint when chat returns `action:
"render"`. **Still open for the other 8 furniture types** — `save_cabinet`,
`save_sofa`, `save_coffee_table`, `save_dining_chair`, `save_wardrobe`,
`save_reception_counter`, `save_bed_headboard` (and their `drawing_builders.py`
counterparts) have no `materials` parameter at all; `/api/material/edit`
explicitly 400s for any `furniture_type != 'round_pedestal_table'`.
Hatch-pattern-by-material-keyword (the second half of the original design in
`architecture-ai-cad-drafter.md` §1) is also still unimplemented — only the
leader/title-block text changes, not the fill pattern.

### 1b. `/adjust` (dimensions) is also round_pedestal_table/rectangular_table-only
Same shape of gap as #1, for dimensions instead of materials. `_dispatch_furniture`
and `_build_svg_model` in `routes.py` have a full branch per furniture type
(cabinet, sofa, coffee_table, dining_chair, wardrobe, reception_counter,
bed_headboard all generate correctly on *first* digitize), but `POST /adjust`
only has two branches — `rectangular_table` and a hardcoded-default
`round_pedestal_table` fallback for everything else. A user who digitizes a
sofa and then says "make it wider" via chat: `chat_agent` will happily
extract `{width_cm: 220}`, `ChatBox.tsx` will POST it to `/adjust`, and
`/adjust` will silently reinterpret the sofa as a round pedestal table and
regenerate a completely unrelated shape. This is a worse failure mode than a
silent no-op — it's a silent wrong-output. See "Generalizing /adjust and
/material/edit" in `architecture-ai-cad-drafter.md` for the fix (build the
furniture-type dispatch generically from `_component_schema` instead of as a
hand-written if/elif per endpoint).

### 1c. `furniture_type`, `visibility`, and `notes` from chat are captured but never applied
`DrawingState.furniture_type` / `.visibility` / `.notes` are parsed and
stored by `chat_agent.py` and surfaced in `App.tsx`'s `handleChatRender`
(`App.tsx:309`), but that handler only bumps a cache-busting counter — it
never calls any endpoint. A user saying "actually this is a cabinet, not a
table" or "hide the base plate" or "note: client wants matte finish" gets a
friendly LLM response and zero effect on the drawing. Visibility has an
existing closeable mechanism (gap #2 below); furniture_type correction needs
a full re-dispatch (re-run `_dispatch_furniture`/`_build_svg_model` with the
corrected type against the same source dimensions); notes needs threading
into `TitleBlockData.general_notes`.

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

### 4. Chat agent's vocabulary is stale relative to `component_schema` — PARTIALLY CLOSED (a7d7190)
`chat_agent.py`'s `SYSTEM_PROMPT` now includes `neck_diameter_cm` and
`collar_diameter_cm` (it didn't before — this caused the "make the base a
different diameter than the pedestal column" no-op reported in this
session: the LLM had no key to express "pedestal column diameter" at all),
plus an explicit rule forcing it to resolve relational requests ("make X
different from Y") to a concrete number using session context instead of
silently doing nothing. `/chat` now also seeds that context from the
drawing's `.json` sidecar so the LLM can reason about values it was never
told via chat (e.g. neck/collar set at generation time, not by a prior
message). **Still not actually fixed**: the vocabulary is still a hardcoded
list, not generated from `_component_schema(furniture_type)` as originally
designed in this doc's §4 below — every furniture type still gets the same
fixed prompt, so chat about a cabinet's `width_cm`/`depth_cm` works (those
happen to be in the static list) but chat about anything schema-specific to
other types won't.

### 5. ChatBox only forwards dimension updates to the backend — PARTIALLY CLOSED (a7d7190)
`ChatBox.tsx` now also forwards `state.materials` to `POST /api/material/edit`
(previously: nothing). **Still open**: visibility, merge, furniture_type,
and notes updates from chat still reach no endpoint (see #1c, #2, #3).

### 6. No fallback for furniture types outside the fixed list of 9
`_component_schema(f_type)` (`routes.py:98`) is a hardcoded if/elif chain
covering exactly `round_pedestal_table, rectangular_table, sofa, cabinet,
dining_chair/chair, wardrobe, reception_counter, bed_headboard,
coffee_table` — anything else (an L-shaped sectional, a bunk bed, a
furniture type GPT-4o correctly identifies in `ai_result.furniture_type`
but that isn't in `KNOWN_TYPES`) falls through to `return None`, and the
frontend's slider panel has nothing to render. There's also no database
table to persist a schema once generated — `create_ml_tables.sql` has
`furniture_corrections`, `material_library`, `style_presets`,
`chat_sessions`, `drawing_history`, `component_proportions`, but nothing
like `furniture_templates`/`component_schemas`. See "Dynamic schema and
geometry generation for novel furniture types" in
`architecture-ai-cad-drafter.md` for the design — this is the harder of the
two problems (the schema/metadata can be LLM-generated fairly easily; the
*geometry* to actually draw a never-seen-before furniture type needs a new
generic renderer, since every current builder hand-codes its own polygon
math).

## Closed gaps
(none fully — #1, #4, #5 are partially closed; see commit a7d7190)
