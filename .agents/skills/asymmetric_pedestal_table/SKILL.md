---
name: asymmetric_pedestal_table
description: Guide to identify and parametrically reconstruct asymmetric cylindrical pedestal dining tables with marble/stone tops and dual offset metal pedestals.
---

# Asymmetric Cylindrical Pedestal Dining Table Skill

## Identification Clues
- Rectangular tabletop in top view with TWO circles inside (pedestal footprints of different diameters).
- Front elevation shows two vertical cylinders of different widths at different horizontal offsets from center.
- No four legs visible — the support is two cylindrical pedestals at different positions.
- Thin stone/marble/sintered top (25-40mm thick) with polished surface.
- Pedestals are brushed metal cylinders, not tapered.
- Side elevation shows one pedestal closer (solid) and one further (hidden/dashed).

## Parametric Reconstruction
- Top View: LWPOLYLINE rectangle (width=length_cm, height=depth_cm). Two CIRCLE entities at pedestal footprint positions (center=left_ped_x_cm and right_ped_x_cm). Stone hatch ANSI31 at 45°. Centerlines horizontal + vertical. Dimensions W=length_mm, D=depth_mm.
- Front Elevation: Tabletop rectangle + two cylindrical pedestal rectangles at their offset positions. Large pedestal (large_ped_dia_cm) is wider. Small pedestal (small_ped_dia_cm) is narrower. Metal hatch ANSI37 on pedestals. Stone hatch on top. Dimensions: H=height_mm, Ø for each pedestal, OH=overhang_mm.
- Side Elevation: Tabletop depth profile. One pedestal solid (closer), one hidden/dashed on HIDDEN layer (further). Dimension D=depth_mm, H=height_mm.
- Title block: "Asymmetric Pedestal Dining Table LxWxH mm" with material notes (marble top + brushed metal pedestals).

## Standard Parameters (mm)
- length_mm: 1800 (min 1200, max 3000)
- depth_mm: 900 (min 600, max 1500)
- height_mm: 750 (min 720, max 780)
- top_thickness_mm: 30 (min 15, max 50)
- large_pedestal_diameter_mm: 400 (min 300, max 500)
- small_pedestal_diameter_mm: 220 (min 150, max 300)

## Generator Functions
- save_asymmetric_pedestal_table() in backend-python/app/backend/dxf_exporter.py
- build_asymmetric_pedestal_model() in backend-python/app/backend/drawing_builders.py
