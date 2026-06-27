---
name: resource-intelligence-engine
description: Use the Resource Intelligence Engine — Scene Graph, Resource Library, Constraint Solver, and Feedback system for intelligent CAD generation.
---

# Resource Intelligence Engine Skill

## Overview

The Resource Intelligence Engine transforms detected furniture features into a **Parametric Scene Graph** — a structured description of every component (top, support, joinery, materials) with confidence scores, evidence, and constraint validation.

## Pipeline

```
Detected features (furniture_type + dimensions_cm + materials)
  ↓
ResourceLibrary.load() — loads geometry/, supports/, joinery/, materials/, construction_rules/
  ↓
build_scene_graph(ftype, dims, materials, library) — maps type to resource IDs
  ↓
solve_constraints(scene) — validates height, overhang, thickness, ergonomics
  ↓
Scene graph returned with evidence, warnings, and component parameters in MM
```

## Resource Library Location

All resource JSON files live in `resources/`:
- `resources/geometry/` — top shapes (rectangular_top, oval_top)
- `resources/supports/` — base/support types (dual_cylindrical_pedestal, single_cylindrical_pedestal, four_legs_rectangular)
- `resources/joinery/` — connection methods (hidden_steel_frame)
- `resources/materials/` — materials with shop drawing notes (calacatta_marble, brushed_metal, solid_wood)
- `resources/construction_rules/` — safety/ergonomic rules (residential_safety, office_safety)
- `resources/dimension_styles/` — drawing style definitions (metric_a3)
- `resources/manufacturers/` — manufacturer preferences (home_u)

## Type Mapping

| furniture_type | geometry | support |
|---|---|---|
| asymmetric_pedestal_table | geometry.rectangular_top.v1 | supports.dual_cylindrical_pedestal.v1 |
| oval_pedestal_table | geometry.oval_top.v1 | supports.single_cylindrical_pedestal.v1 |
| round_pedestal_table | geometry.oval_top.v1 | supports.single_cylindrical_pedestal.v1 |
| rectangular_table | geometry.rectangular_top.v1 | supports.four_legs_rectangular.v1 |
| console_table | geometry.rectangular_top.v1 | supports.four_legs_rectangular.v1 |
| office_desk | geometry.rectangular_top.v1 | supports.four_legs_rectangular.v1 |

## Constraint Rules Applied

- Dining tables: total height clamped to 720-780mm
- Stone tops over 1200mm span: minimum 30mm thickness
- Overhang past support: minimum 100mm per side
- Office desks: minimum 500mm depth, 720-760mm height

## API Endpoints

- `GET /api/scene/generate?furniture_type=...&length_cm=...` — generate scene graph
- `GET /api/scene/library` — view all library resources
- `POST /api/scene/feedback` — submit approved/rejected feedback
- `GET /api/scene/feedback/stats` — aggregated feedback stats
- `GET /api/templates/suggest?furniture_type=...&width_cm=...` — fill missing dims from ratios

## Key Files

- `backend-python/app/resource_engine/__init__.py` — package root
- `backend-python/app/resource_engine/schema.py` — ParametricSceneGraph, SceneComponent, ResourceRef
- `backend-python/app/resource_engine/library.py` — ResourceLibrary loader with search_by_features() + find_compatible()
- `backend-python/app/resource_engine/matcher.py` — build_scene_graph() maps types to resources
- `backend-python/app/resource_engine/constraint_solver.py` — solve_constraints() validates parameters
- `backend-python/app/resource_engine/feedback.py` — save_feedback() + load_feedback_history() + get_feedback_stats()
- `backend-python/app/api/routes.py` — scene graph wiring in _dispatch_furniture() + dedicated endpoints
