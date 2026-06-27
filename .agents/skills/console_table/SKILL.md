---
name: console_table
description: Guide to identify and parametrically reconstruct console/sofa tables — narrow long tables with simple legs.
---

# Console / Sofa Table Skill

## Identification Clues
- Long narrow rectangle in top view (aspect ratio > 3:1).
- Two or four legs at corners in top view (as small hidden rectangles).
- Front view shows narrow depth relative to width.
- Side view shows very shallow depth (300-500mm).
- Typically positioned against a wall.
- No drawers, no pedestals, no modesty panel.

## Parametric Reconstruction
- Top View: LWPOLYLINE rectangle (width=length_cm, height=depth_cm). Four leg footprint rectangles at corners on HIDDEN layer. Centerlines. Dimensions W=length_mm, D=depth_mm.
- Front View: Tabletop rectangle + two front legs. Back legs as hidden lines. Dimensions H=height_mm, W=length_mm.
- Side View: Narrow tabletop profile + one leg. Dimensions H=height_mm, D=depth_mm.

## Standard Parameters (mm)
- length_mm: 1200 (min 800, max 2000)
- depth_mm: 400 (min 250, max 550)
- height_mm: 750 (min 700, max 800)
- top_thickness_mm: 25 (min 15, max 40)
- leg_thickness_mm: 40 (min 25, max 60)

## Generator Functions
- save_console_table() in backend-python/app/backend/dxf_exporter.py
- build_console_table_model() in backend-python/app/backend/drawing_builders.py
