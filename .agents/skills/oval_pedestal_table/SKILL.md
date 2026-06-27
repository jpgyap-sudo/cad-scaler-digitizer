---
name: oval_pedestal_table
description: Guide to identify and parametrically reconstruct oval/elliptical pedestal tables with central pedestal support.
---

# Oval Pedestal Table Skill

## Identification Clues
- Top view shows an oval/elliptical shape (not a true circle, not a rectangle with corners).
- Single circle at center of oval (pedestal footprint).
- Front elevation shows a single central column.
- Stone/marble top with polished finish, smooth curved edges.
- No four legs visible.
- Label may show "oval" or "elliptical" in text.

## Parametric Reconstruction
- Top View: 36-segment LWPOLYLINE approximating an ellipse (width=length_cm, height=depth_cm). One CIRCLE at center for pedestal footprint on HIDDEN layer. Stone hatch. Centerlines. Dimensions W=length_mm, D=depth_mm.
- Front Elevation: Tabletop rectangle (width=length_cm) with central pedestal. Metal hatch ANSI37 on pedestal. Stone hatch on top. Dimensions: H=height_mm, Ø=pedestal_diameter_mm, T=top_thickness_mm.

## Standard Parameters (mm)
- length_mm: 1800 (min 800, max 3000)
- depth_mm: 1000 (min 600, max 1500)
- height_mm: 750 (min 720, max 780)
- top_thickness_mm: 30 (min 20, max 50)
- pedestal_diameter_mm: 400 (min 250, max 550)

## Generator Functions
- save_oval_pedestal_table() in backend-python/app/backend/dxf_exporter.py
- build_oval_pedestal_model() in backend-python/app/backend/drawing_builders.py
