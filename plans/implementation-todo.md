# CAD Intelligence Layer — Implementation Todo

## Phase 1: CAD Types
- [ ] Rewrite `types.ts` — add CadPrimitive union (Circle, Arc, Rectangle, Polyline, Line, Dimension, Text)
- [ ] Add CadView, CadDocument, ParametricTemplate types
- [ ] Remove old AgentResponse/VerificationResult
- [ ] Keep Polyline/Calibration for backward compat during migration

## Phase 2: Gemini Prompt
- [ ] Rewrite `agent.ts` — CAD understanding prompt (TASK 1-4)
- [ ] Add runCadAgent() returning CadDocument
- [ ] Add runCadVerifier() checking primitive quality
- [ ] Add runCadCorrector() with feedback loop

## Phase 3: CadRenderer
- [ ] Create `components/CadCanvas.tsx` — draws circles, arcs, rectangles as REAL primitives
- [ ] Create `components/ViewPanel.tsx` — multi-view panel (top/front/side)
- [ ] Update `components/TechStackModal.tsx`

## Phase 4: Shape Reconstruction
- [ ] Create `services/cadCleanup.ts` — dedup, snap, merge, straighten, remove short
- [ ] Pipeline: raw primitives → cleaned primitives

## Phase 5: DXF Upgrade
- [ ] Rewrite `utils/dxf.ts` — export CIRCLE, ARC, LWPOLYLINE, TEXT, DIMENSION

## Phase 6: Parametric Templates
- [ ] Create `templates/` directory with JSON definitions
- [ ] Create `services/templateMatcher.ts` — match + fill parameters
- [ ] Templates: round_table, rect_table, sofa, cabinet, bed, chair

## Phase 7: Integration
- [ ] Rewrite `App.tsx` — wire CadDocument flow, multilple view panels
- [ ] Update PostgreSQL schema for CadDocument
- [ ] Remove old digitization flow

## Phase 8: Polish
- [ ] Add dimension preview overlays
- [ ] Add template selector override UI
- [ ] Add primitive type icons in sidebar
