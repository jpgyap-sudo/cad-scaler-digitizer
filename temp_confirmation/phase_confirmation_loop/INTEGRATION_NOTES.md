# Integration Notes for cad-scaler-digitizer

## Where to put files

Copy `furniture_intelligence/` into your backend source folder.

Suggested structure:

```text
backend/
  furniture_intelligence/
  app.py or main.py
```

## UI flow to add

### Screen 1 — Upload product photo
User uploads image.

### Screen 2 — AI Furniture Analysis
Show:
- category
- detected components
- proposed template
- confidence
- uncertain questions

Example:

```text
I think this is:
Oval Sculptural Pedestal Coffee Table

Detected:
✓ oval stone top
✓ recessed brass bowl
✓ tapered brass pedestal
✓ hidden mounting plate
```

### Screen 3 — User correction
Show only uncertain choices:

```text
Tabletop shape: oval / circle / rectangle
Base type: truncated cone / four legs / panel legs
Bowl: centered / offset
```

### Screen 4 — Preview
Generate SVG/PNG preview from approved JSON.

### Screen 5 — DXF
Generate DXF only after user approves.

## Important architecture

Bad:

```text
Photo -> AI image generator -> DXF
```

Good:

```text
Photo -> Vision JSON -> Template match -> User confirms -> Deterministic preview/DXF
```

## Why this works

AI is good at furniture understanding.
Code is good at exact geometry.
User feedback closes the loop.
