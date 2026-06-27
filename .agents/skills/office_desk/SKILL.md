---
name: office_desk
description: Guide to identify and parametrically reconstruct office desks with modesty panels and leg supports.
---

# Office Desk with Modesty Panel Skill

## Identification Clues
- Rectangle in top view, moderate aspect ratio (2:1 to 2.5:1).
- Front view shows modesty panel between legs below the tabletop.
- No drawers visible (different from cabinet/wardrobe).
- Flat top with no hutch or riser.
- Four straight legs at corners.
- Depth typically 500-800mm for computer monitor clearance.

## Parametric Reconstruction
- Top View: LWPOLYLINE rectangle (width=length_cm, height=depth_cm). Four leg footprints on HIDDEN layer. Centerlines. Dimensions W=length_mm, D=depth_mm.
- Front View: Tabletop rectangle + two front legs + modesty panel rectangle between legs (hatched ANSI31). Dimensions H=height_mm, W=length_mm, MH=modesty_panel_height_mm.
- Side View: Desktop profile + one leg + side profile of modesty panel. Dimensions H=height_mm, D=depth_mm.

## Standard Parameters (mm)
- length_mm: 1400 (min 900, max 2000)
- depth_mm: 600 (min 500, max 800)
- height_mm: 750 (min 720, max 780)
- top_thickness_mm: 25 (min 15, max 40)
- leg_thickness_mm: 40 (min 30, max 60)
- modesty_panel_height_mm: 150 (min 100, max 300)

## Generator Functions
- save_office_desk() in backend-python/app/backend/dxf_exporter.py
- build_office_desk_model() in backend-python/app/backend/drawing_builders.py
