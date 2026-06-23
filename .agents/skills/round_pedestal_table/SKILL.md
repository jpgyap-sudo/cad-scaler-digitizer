---
name: round_pedestal_table
description: Guide to identify and parametrically reconstruct round pedestal tables with wood grains and base dimensions.
---

# Round Pedestal Table Skill

## Identification Clues
- Top view contains a real circle entity (often annotated with "DIA" or "Ø").
- Front view elevation depicts a tabletop rectangle resting on a pedestal column and a wider bottom base.

## Parametric Reconstruction
- Top View: True CIRCLE at radius = `top_diameter / 2`. Draw radial wood rays (24 divisions). Add Ø top diameter DIMENSION.
- Front View: Tabletop rectangle (width = `top_diameter`, height = `top_thickness`). Hatch tabletop with diagonal ANSI31.
- Pedestal Neck: Width = `neck_diameter`, centered.
- Pedestal Base: Width = `base_diameter`, height = `base_height`. Hatch base with ANSI37/NET mesh.
- Dimensions: Add height dimension on side, and base diameter linear dimension at bottom.
