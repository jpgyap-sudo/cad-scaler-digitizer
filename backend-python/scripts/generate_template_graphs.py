"""Generate template graph JSON files for all 18 furniture product types."""
import json
import os
from pathlib import Path

# Resolve template directory — write to project root resources/, NOT backend-python/resources/
script_dir = Path(__file__).parent.resolve()
# script_dir is backend-python/scripts/. Go up one more level to project root.
TEMPLATE_DIR = script_dir.parent.parent / "resources" / "furniture_template_graphs"
TEMPLATE_DIR = TEMPLATE_DIR.resolve()
TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

templates = {
    "table.rectangular_four_leg.v1": {
        "id": "table.rectangular_four_leg.v1",
        "name": "Rectangular table with four legs",
        "product_type": "rectangular_table",
        "family": "table",
        "parameters": [
            {"name": "length_mm", "default": 1800, "min_value": 800, "max_value": 3200, "description": "Overall table length"},
            {"name": "depth_mm", "default": 900, "min_value": 500, "max_value": 1400, "description": "Overall table depth"},
            {"name": "height_mm", "default": 750, "min_value": 720, "max_value": 780, "description": "Table height"},
            {"name": "top_thickness_mm", "default": 30, "min_value": 12, "max_value": 60, "description": "Top slab thickness"},
            {"name": "leg_size_mm", "default": 50, "min_value": 25, "max_value": 100, "description": "Leg cross-section size"},
            {"name": "leg_inset_mm", "default": 20, "min_value": 5, "max_value": 60, "description": "Leg inset from edge"}
        ],
        "components": [
            {"id": "top", "role": "top", "shape": "rectangular_slab", "material_role": "top", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "thickness_mm": "top_thickness_mm"}},
            {"id": "legs", "role": "support", "shape": "rectangular_prism", "quantity": 4, "material_role": "base", "parameter_map": {"size_mm": "leg_size_mm", "inset_mm": "leg_inset_mm"}}
        ],
        "constraints": [
            {"id": "height_range", "description": "Table height must be between 720-780mm", "expression": "720 <= height_mm <= 780", "severity": "warning"}
        ],
        "required_views": ["top", "front_elevation", "side_elevation"],
        "required_details": ["leg_detail"],
        "drawing_notes": ["RECTANGULAR TABLE — SHOW LEG POSITIONS AND JOINT DETAILS."]
    },
    "table.single_pedestal_round.v1": {
        "id": "table.single_pedestal_round.v1",
        "name": "Round table with single pedestal",
        "product_type": "round_pedestal_table",
        "family": "table",
        "parameters": [
            {"name": "diameter_mm", "default": 1200, "min_value": 600, "max_value": 2000, "description": "Table top diameter"},
            {"name": "height_mm", "default": 750, "min_value": 720, "max_value": 780, "description": "Table height"},
            {"name": "top_thickness_mm", "default": 30, "min_value": 12, "max_value": 60, "description": "Top slab thickness"},
            {"name": "pedestal_diameter_mm", "default": 400, "min_value": 200, "max_value": 650, "description": "Pedestal column diameter"},
            {"name": "pedestal_height_mm", "default": 720, "min_value": 400, "max_value": 760, "description": "Pedestal column height"}
        ],
        "components": [
            {"id": "top", "role": "top", "shape": "round_slab", "material_role": "top", "parameter_map": {"diameter_mm": "diameter_mm", "thickness_mm": "top_thickness_mm"}},
            {"id": "pedestal", "role": "support", "shape": "cylinder", "material_role": "base", "parameter_map": {"diameter_mm": "pedestal_diameter_mm", "height_mm": "pedestal_height_mm"}}
        ],
        "constraints": [
            {"id": "height_range", "description": "Table height must be between 720-780mm", "expression": "720 <= height_mm <= 780", "severity": "warning"}
        ],
        "required_views": ["top", "front_elevation"],
        "required_details": ["pedestal_mounting_detail"],
        "drawing_notes": ["ROUND TABLE — SHOW PEDESTAL CENTER AND DIAMETER."]
    },
    "table.single_pedestal_oval.v1": {
        "id": "table.single_pedestal_oval.v1",
        "name": "Oval table with single pedestal",
        "product_type": "oval_pedestal_table",
        "family": "table",
        "parameters": [
            {"name": "length_mm", "default": 1800, "min_value": 1000, "max_value": 3200, "description": "Overall table length"},
            {"name": "depth_mm", "default": 1000, "min_value": 600, "max_value": 1500, "description": "Overall table depth"},
            {"name": "height_mm", "default": 750, "min_value": 720, "max_value": 780, "description": "Table height"},
            {"name": "top_thickness_mm", "default": 30, "min_value": 12, "max_value": 60, "description": "Top slab thickness"},
            {"name": "pedestal_diameter_mm", "default": 400, "min_value": 200, "max_value": 650, "description": "Pedestal column diameter"},
            {"name": "pedestal_height_mm", "default": 720, "min_value": 400, "max_value": 760, "description": "Pedestal column height"}
        ],
        "components": [
            {"id": "top", "role": "top", "shape": "oval_slab", "material_role": "top", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "thickness_mm": "top_thickness_mm"}},
            {"id": "pedestal", "role": "support", "shape": "cylinder", "material_role": "base", "parameter_map": {"diameter_mm": "pedestal_diameter_mm", "height_mm": "pedestal_height_mm"}}
        ],
        "constraints": [
            {"id": "height_range", "description": "Table height must be between 720-780mm", "expression": "720 <= height_mm <= 780", "severity": "warning"}
        ],
        "required_views": ["top", "front_elevation"],
        "required_details": ["edge_profile_detail"],
        "drawing_notes": ["OVAL TABLE — SHOW TOP CENTERLINES AND PEDESTAL POSITION."]
    },
    "table.console_four_leg.v1": {
        "id": "table.console_four_leg.v1",
        "name": "Console / sofa table",
        "product_type": "console_table",
        "family": "table",
        "parameters": [
            {"name": "length_mm", "default": 1200, "min_value": 600, "max_value": 2000, "description": "Table length"},
            {"name": "depth_mm", "default": 400, "min_value": 250, "max_value": 550, "description": "Table depth"},
            {"name": "height_mm", "default": 750, "min_value": 700, "max_value": 800, "description": "Table height"},
            {"name": "top_thickness_mm", "default": 25, "min_value": 15, "max_value": 40, "description": "Top thickness"},
            {"name": "leg_size_mm", "default": 40, "min_value": 20, "max_value": 70, "description": "Leg cross-section"}
        ],
        "components": [
            {"id": "top", "role": "top", "shape": "rectangular_slab", "material_role": "top", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "thickness_mm": "top_thickness_mm"}},
            {"id": "legs", "role": "support", "shape": "rectangular_prism", "quantity": 4, "material_role": "base", "parameter_map": {"size_mm": "leg_size_mm"}}
        ],
        "constraints": [],
        "required_views": ["top", "front_elevation", "side_elevation"],
        "required_details": [],
        "drawing_notes": ["CONSOLE TABLE — PLACE AGAINST WALL."]
    },
    "table.coffee_rectangular.v1": {
        "id": "table.coffee_rectangular.v1",
        "name": "Rectangular coffee table",
        "product_type": "coffee_table",
        "family": "table",
        "parameters": [
            {"name": "length_mm", "default": 1200, "min_value": 600, "max_value": 1800, "description": "Table length"},
            {"name": "depth_mm", "default": 600, "min_value": 400, "max_value": 1000, "description": "Table depth"},
            {"name": "height_mm", "default": 380, "min_value": 300, "max_value": 480, "description": "Table height"},
            {"name": "top_thickness_mm", "default": 25, "min_value": 12, "max_value": 50, "description": "Top thickness"}
        ],
        "components": [
            {"id": "top", "role": "top", "shape": "rectangular_slab", "material_role": "top", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "thickness_mm": "top_thickness_mm"}},
            {"id": "legs", "role": "support", "shape": "rectangular_prism", "quantity": 4, "material_role": "base", "parameter_map": {}}
        ],
        "constraints": [
            {"id": "height_range", "description": "Coffee table height must be between 300-480mm", "expression": "300 <= height_mm <= 480", "severity": "warning"}
        ],
        "required_views": ["top", "front_elevation"],
        "required_details": [],
        "drawing_notes": ["COFFEE TABLE — LOW HEIGHT."]
    },
    "table.side_rectangular.v1": {
        "id": "table.side_rectangular.v1",
        "name": "Side / end table",
        "product_type": "side_table",
        "family": "table",
        "parameters": [
            {"name": "length_mm", "default": 500, "min_value": 350, "max_value": 800, "description": "Table length"},
            {"name": "depth_mm", "default": 500, "min_value": 350, "max_value": 800, "description": "Table depth"},
            {"name": "height_mm", "default": 520, "min_value": 450, "max_value": 650, "description": "Table height"},
            {"name": "top_thickness_mm", "default": 25, "min_value": 12, "max_value": 40, "description": "Top thickness"}
        ],
        "components": [
            {"id": "top", "role": "top", "shape": "rectangular_slab", "material_role": "top", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "thickness_mm": "top_thickness_mm"}},
            {"id": "legs", "role": "support", "shape": "rectangular_prism", "quantity": 4, "material_role": "base", "parameter_map": {}}
        ],
        "constraints": [],
        "required_views": ["top", "front_elevation"],
        "required_details": [],
        "drawing_notes": ["SIDE TABLE — COMPACT DIMENSIONS."]
    },
    "desk.standard.v1": {
        "id": "desk.standard.v1",
        "name": "Office desk with modesty panel",
        "product_type": "office_desk",
        "family": "desk",
        "parameters": [
            {"name": "length_mm", "default": 1400, "min_value": 900, "max_value": 2000, "description": "Desk length"},
            {"name": "depth_mm", "default": 600, "min_value": 500, "max_value": 800, "description": "Desk depth"},
            {"name": "height_mm", "default": 750, "min_value": 720, "max_value": 780, "description": "Desk height"},
            {"name": "top_thickness_mm", "default": 25, "min_value": 15, "max_value": 40, "description": "Top thickness"},
            {"name": "leg_size_mm", "default": 40, "min_value": 25, "max_value": 60, "description": "Leg cross-section"},
            {"name": "modesty_panel_height_mm", "default": 150, "min_value": 100, "max_value": 300, "description": "Modesty panel height"}
        ],
        "components": [
            {"id": "top", "role": "top", "shape": "rectangular_slab", "material_role": "top", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "thickness_mm": "top_thickness_mm"}},
            {"id": "legs", "role": "support", "shape": "rectangular_prism", "quantity": 4, "material_role": "base", "parameter_map": {"size_mm": "leg_size_mm"}},
            {"id": "modesty_panel", "role": "modesty", "shape": "rectangular_panel", "material_role": "casework", "parameter_map": {"height_mm": "modesty_panel_height_mm"}}
        ],
        "constraints": [
            {"id": "depth_min", "description": "Desk depth must be at least 500mm", "expression": "depth_mm >= 500", "severity": "error"},
            {"id": "height_range", "description": "Desk height must be between 720-780mm", "expression": "720 <= height_mm <= 780", "severity": "warning"}
        ],
        "required_views": ["top", "front_elevation", "side_elevation"],
        "required_details": ["modesty_panel_detail"],
        "drawing_notes": ["OFFICE DESK — SHOW MODESTY PANEL AND CABLE MANAGEMENT."]
    },
    "cabinet.standard.v1": {
        "id": "cabinet.standard.v1",
        "name": "Standard sideboard",
        "product_type": "sideboard",
        "family": "cabinet",
        "parameters": [
            {"name": "length_mm", "default": 1800, "min_value": 600, "max_value": 2400, "description": "Cabinet length"},
            {"name": "depth_mm", "default": 450, "min_value": 350, "max_value": 650, "description": "Cabinet depth"},
            {"name": "height_mm", "default": 800, "min_value": 600, "max_value": 1000, "description": "Cabinet height"},
            {"name": "panel_thickness_mm", "default": 18, "min_value": 12, "max_value": 25, "description": "Panel thickness"},
            {"name": "door_count", "default": 4, "min_value": 2, "max_value": 8, "description": "Number of doors"}
        ],
        "components": [
            {"id": "case", "role": "case", "shape": "rectangular_box", "material_role": "casework", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "height_mm": "height_mm"}},
            {"id": "doors", "role": "doors_or_drawers", "shape": "rectangular_panels", "material_role": "casework", "parameter_map": {"count": "door_count"}},
            {"id": "base", "role": "base", "shape": "plinth_or_legs", "material_role": "base", "parameter_map": {}}
        ],
        "constraints": [
            {"id": "cabinet_span", "description": "Span over 1800mm needs center support or extra doors", "expression": "length_mm <= 1800 or door_count >= 4", "severity": "warning"}
        ],
        "required_views": ["front_elevation", "side_elevation", "top"],
        "required_details": ["hinge_detail"],
        "drawing_notes": ["SIDEBOARD — SHOW DOOR AND SHELF LAYOUT."]
    },
    "cabinet.tv_console.v1": {
        "id": "cabinet.tv_console.v1",
        "name": "TV console / media unit",
        "product_type": "tv_console",
        "family": "cabinet",
        "parameters": [
            {"name": "length_mm", "default": 1800, "min_value": 800, "max_value": 2400, "description": "Console length"},
            {"name": "depth_mm", "default": 450, "min_value": 350, "max_value": 600, "description": "Console depth"},
            {"name": "height_mm", "default": 600, "min_value": 450, "max_value": 750, "description": "Console height"},
            {"name": "panel_thickness_mm", "default": 18, "min_value": 12, "max_value": 25, "description": "Panel thickness"}
        ],
        "components": [
            {"id": "case", "role": "case", "shape": "rectangular_box", "material_role": "casework", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "height_mm": "height_mm"}},
            {"id": "doors", "role": "doors_or_drawers", "shape": "rectangular_panels", "material_role": "casework", "parameter_map": {}}
        ],
        "constraints": [],
        "required_views": ["front_elevation", "side_elevation", "top"],
        "required_details": ["cable_management_detail"],
        "drawing_notes": ["TV CONSOLE — SHOW CABLE MANAGEMENT PROVISIONS."]
    },
    "cabinet.nightstand.v1": {
        "id": "cabinet.nightstand.v1",
        "name": "Nightstand / bedside table",
        "product_type": "nightstand",
        "family": "cabinet",
        "parameters": [
            {"name": "length_mm", "default": 500, "min_value": 400, "max_value": 650, "description": "Nightstand width"},
            {"name": "depth_mm", "default": 420, "min_value": 350, "max_value": 500, "description": "Nightstand depth"},
            {"name": "height_mm", "default": 500, "min_value": 450, "max_value": 600, "description": "Nightstand height"},
            {"name": "panel_thickness_mm", "default": 18, "min_value": 12, "max_value": 25, "description": "Panel thickness"}
        ],
        "components": [
            {"id": "case", "role": "case", "shape": "rectangular_box", "material_role": "casework", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "height_mm": "height_mm"}},
            {"id": "drawers", "role": "drawers", "shape": "rectangular_panels", "material_role": "casework", "parameter_map": {}}
        ],
        "constraints": [],
        "required_views": ["front_elevation", "top", "side_elevation"],
        "required_details": ["drawer_detail"],
        "drawing_notes": ["NIGHTSTAND — COMPACT CABINET."]
    },
    "wardrobe.standard.v1": {
        "id": "wardrobe.standard.v1",
        "name": "Standard wardrobe",
        "product_type": "wardrobe",
        "family": "cabinet",
        "parameters": [
            {"name": "length_mm", "default": 1200, "min_value": 800, "max_value": 2500, "description": "Wardrobe width"},
            {"name": "depth_mm", "default": 600, "min_value": 500, "max_value": 750, "description": "Wardrobe depth"},
            {"name": "height_mm", "default": 2000, "min_value": 1800, "max_value": 2600, "description": "Wardrobe height"},
            {"name": "panel_thickness_mm", "default": 18, "min_value": 12, "max_value": 25, "description": "Panel thickness"}
        ],
        "components": [
            {"id": "case", "role": "case", "shape": "rectangular_box", "material_role": "casework", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "height_mm": "height_mm"}},
            {"id": "doors", "role": "doors_or_drawers", "shape": "rectangular_panels", "material_role": "casework", "parameter_map": {}}
        ],
        "constraints": [
            {"id": "height_check", "description": "Wardrobe height must be between 1800-2600mm", "expression": "1800 <= height_mm <= 2600", "severity": "warning"}
        ],
        "required_views": ["front_elevation", "top", "side_elevation"],
        "required_details": ["hinge_detail"],
        "drawing_notes": ["WARDROBE — SHOW HANGING RAIL AND SHELF LAYOUT."]
    },
    "bed.standard.v1": {
        "id": "bed.standard.v1",
        "name": "Standard platform bed",
        "product_type": "bed",
        "family": "bed",
        "parameters": [
            {"name": "length_mm", "default": 2030, "min_value": 1900, "max_value": 2200, "description": "Bed length"},
            {"name": "depth_mm", "default": 1830, "min_value": 1350, "max_value": 2000, "description": "Bed width"},
            {"name": "height_mm", "default": 1000, "min_value": 800, "max_value": 1200, "description": "Overall bed height (incl headboard)"},
            {"name": "platform_height_mm", "default": 300, "min_value": 200, "max_value": 500, "description": "Mattress platform height"}
        ],
        "components": [
            {"id": "platform", "role": "mattress_zone", "shape": "rectangular_platform", "material_role": "platform", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "height_mm": "height_mm"}},
            {"id": "headboard", "role": "headboard", "shape": "vertical_panel", "material_role": "headboard", "parameter_map": {}}
        ],
        "constraints": [
            {"id": "bed_min_size", "description": "Minimum bed size is 1900x1350mm", "expression": "length_mm >= 1900 and depth_mm >= 1350", "severity": "error"}
        ],
        "required_views": ["top", "front_elevation", "side_elevation"],
        "required_details": [],
        "drawing_notes": ["BED — SHOW MATTRESS ZONE AND PLATFORM HEIGHT."]
    },
    "bed.headboard.v1": {
        "id": "bed.headboard.v1",
        "name": "Upholstered bed headboard",
        "product_type": "bed_headboard",
        "family": "bed",
        "parameters": [
            {"name": "width_mm", "default": 1830, "min_value": 900, "max_value": 2200, "description": "Headboard width"},
            {"name": "height_mm", "default": 1000, "min_value": 600, "max_value": 1500, "description": "Headboard height"},
            {"name": "panel_thickness_mm", "default": 50, "min_value": 25, "max_value": 100, "description": "Panel thickness (upholstery build-up)"}
        ],
        "components": [
            {"id": "headboard_panel", "role": "headboard", "shape": "vertical_panel", "material_role": "upholstery", "parameter_map": {"width_mm": "width_mm", "height_mm": "height_mm"}},
            {"id": "mounting_frame", "role": "base", "shape": "rectangular_frame", "material_role": "base", "visible": False, "parameter_map": {}}
        ],
        "constraints": [],
        "required_views": ["front_elevation", "side_elevation"],
        "required_details": [],
        "drawing_notes": ["HEADBOARD — SHOW UPHOLSTERY BUILD-UP."]
    },
    "sofa.standard.v1": {
        "id": "sofa.standard.v1",
        "name": "Standard sofa / couch",
        "product_type": "sofa",
        "family": "seating",
        "parameters": [
            {"name": "length_mm", "default": 2200, "min_value": 1500, "max_value": 3200, "description": "Overall length"},
            {"name": "depth_mm", "default": 950, "min_value": 800, "max_value": 1100, "description": "Overall depth"},
            {"name": "height_mm", "default": 780, "min_value": 700, "max_value": 900, "description": "Overall height"},
            {"name": "seat_height_mm", "default": 420, "min_value": 380, "max_value": 460, "description": "Seat height from floor"},
            {"name": "arm_width_mm", "default": 150, "min_value": 80, "max_value": 250, "description": "Armrest width"},
            {"name": "seat_count", "default": 3, "min_value": 2, "max_value": 4, "description": "Number of seat modules"}
        ],
        "components": [
            {"id": "seat", "role": "seat", "shape": "upholstered_block", "material_role": "upholstery", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "height_mm": "seat_height_mm"}},
            {"id": "back", "role": "back", "shape": "upholstered_back", "material_role": "upholstery", "parameter_map": {}},
            {"id": "arms", "role": "arms", "shape": "rectangular_arm_block", "quantity": 2, "material_role": "upholstery", "parameter_map": {"width_mm": "arm_width_mm"}},
            {"id": "base", "role": "base", "shape": "low_plinth_or_legs", "material_role": "base", "parameter_map": {}}
        ],
        "constraints": [
            {"id": "seat_height_range", "description": "Seat height must be between 380-460mm", "expression": "380 <= seat_height_mm <= 460", "severity": "warning"}
        ],
        "required_views": ["top", "front_elevation", "side_elevation"],
        "required_details": ["upholstery_build_up_detail"],
        "drawing_notes": ["SOFA — CONFIRM FABRIC DIRECTION AND SEAM PLACEMENT."]
    },
    "chair.lounge.v1": {
        "id": "chair.lounge.v1",
        "name": "Lounge chair",
        "product_type": "lounge_chair",
        "family": "seating",
        "parameters": [
            {"name": "length_mm", "default": 800, "min_value": 650, "max_value": 1000, "description": "Chair width"},
            {"name": "depth_mm", "default": 850, "min_value": 700, "max_value": 1000, "description": "Chair depth"},
            {"name": "height_mm", "default": 780, "min_value": 700, "max_value": 900, "description": "Overall height"},
            {"name": "seat_height_mm", "default": 420, "min_value": 380, "max_value": 460, "description": "Seat height from floor"}
        ],
        "components": [
            {"id": "seat", "role": "seat", "shape": "upholstered_block", "material_role": "upholstery", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "height_mm": "seat_height_mm"}},
            {"id": "back", "role": "back", "shape": "upholstered_back", "material_role": "upholstery", "parameter_map": {}}
        ],
        "constraints": [],
        "required_views": ["top", "front_elevation", "side_elevation"],
        "required_details": [],
        "drawing_notes": ["LOUNGE CHAIR."]
    },
    "chair.standard.v1": {
        "id": "chair.standard.v1",
        "name": "Standard dining chair",
        "product_type": "dining_chair",
        "family": "seating",
        "parameters": [
            {"name": "length_mm", "default": 520, "min_value": 400, "max_value": 650, "description": "Seat width"},
            {"name": "depth_mm", "default": 560, "min_value": 450, "max_value": 650, "description": "Seat depth"},
            {"name": "seat_height_mm", "default": 450, "min_value": 400, "max_value": 500, "description": "Seat height from floor"},
            {"name": "overall_height_mm", "default": 820, "min_value": 750, "max_value": 900, "description": "Total chair height"},
            {"name": "leg_size_mm", "default": 30, "min_value": 20, "max_value": 50, "description": "Leg cross-section"}
        ],
        "components": [
            {"id": "seat", "role": "seat", "shape": "rectangular_slab", "material_role": "upholstery", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm"}},
            {"id": "back", "role": "back", "shape": "upholstered_back", "material_role": "upholstery", "parameter_map": {}},
            {"id": "legs", "role": "base", "shape": "rectangular_prism", "quantity": 4, "material_role": "base", "parameter_map": {"size_mm": "leg_size_mm"}}
        ],
        "constraints": [],
        "required_views": ["front_elevation", "side_elevation", "top"],
        "required_details": [],
        "drawing_notes": ["DINING CHAIR — SHOW LEG AND STRETCHER POSITIONS."]
    },
    "reception_counter.standard.v1": {
        "id": "reception_counter.standard.v1",
        "name": "Reception / transaction counter",
        "product_type": "reception_counter",
        "family": "counter",
        "parameters": [
            {"name": "length_mm", "default": 1800, "min_value": 800, "max_value": 4000, "description": "Counter length"},
            {"name": "depth_mm", "default": 800, "min_value": 500, "max_value": 1200, "description": "Counter depth"},
            {"name": "overall_height_mm", "default": 1100, "min_value": 900, "max_value": 1200, "description": "Total counter height"},
            {"name": "counter_height_mm", "default": 750, "min_value": 700, "max_value": 800, "description": "Transaction surface height"},
            {"name": "top_thickness_mm", "default": 25, "min_value": 15, "max_value": 50, "description": "Top slab thickness"}
        ],
        "components": [
            {"id": "top", "role": "top", "shape": "rectangular_slab", "material_role": "top", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "thickness_mm": "top_thickness_mm"}},
            {"id": "base", "role": "base", "shape": "rectangular_box", "material_role": "casework", "parameter_map": {"height_mm": "overall_height_mm"}}
        ],
        "constraints": [
            {"id": "counter_height", "description": "Transaction surface height should be 700-800mm", "expression": "700 <= counter_height_mm <= 800", "severity": "info"}
        ],
        "required_views": ["front_elevation", "side_elevation", "top"],
        "required_details": [],
        "drawing_notes": ["RECEPTION COUNTER — SHOW TRANSACTION HEIGHT."]
    },
    "table.asymmetric_pedestal.v1": {
        "id": "table.asymmetric_pedestal.v1",
        "name": "Asymmetric dual pedestal table",
        "product_type": "asymmetric_pedestal_table",
        "family": "table",
        "parameters": [
            {"name": "length_mm", "default": 1800, "min_value": 1200, "max_value": 3200, "description": "Table length"},
            {"name": "depth_mm", "default": 900, "min_value": 600, "max_value": 1500, "description": "Table depth"},
            {"name": "height_mm", "default": 750, "min_value": 720, "max_value": 780, "description": "Table height"},
            {"name": "top_thickness_mm", "default": 30, "min_value": 15, "max_value": 50, "description": "Top slab thickness"},
            {"name": "large_pedestal_diameter_mm", "default": 400, "min_value": 300, "max_value": 500, "description": "Large pedestal diameter"},
            {"name": "small_pedestal_diameter_mm", "default": 220, "min_value": 150, "max_value": 300, "description": "Small pedestal diameter"},
            {"name": "left_pedestal_x_mm", "default": -300, "min_value": -800, "max_value": 0, "description": "Left pedestal X offset from center"},
            {"name": "right_pedestal_x_mm", "default": 250, "min_value": 0, "max_value": 800, "description": "Right pedestal X offset from center"},
            {"name": "pedestal_height_mm", "default": 720, "min_value": 400, "max_value": 760, "description": "Pedestal column height"}
        ],
        "components": [
            {"id": "top", "role": "top", "shape": "rectangular_slab", "material_role": "top", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm", "thickness_mm": "top_thickness_mm"}},
            {"id": "large_pedestal", "role": "support", "shape": "cylinder", "material_role": "base", "parameter_map": {"diameter_mm": "large_pedestal_diameter_mm", "height_mm": "pedestal_height_mm", "x_mm": "left_pedestal_x_mm"}},
            {"id": "small_pedestal", "role": "support", "shape": "cylinder", "material_role": "base", "parameter_map": {"diameter_mm": "small_pedestal_diameter_mm", "height_mm": "pedestal_height_mm", "x_mm": "right_pedestal_x_mm"}},
            {"id": "hidden_frame", "role": "joinery", "shape": "rectangular_steel_frame", "visible": False, "material_role": "steel", "parameter_map": {"length_mm": "length_mm", "depth_mm": "depth_mm"}}
        ],
        "constraints": [
            {"id": "height_range", "description": "Table height must be between 720-780mm", "expression": "720 <= height_mm <= 780", "severity": "warning"},
            {"id": "pedestal_ratio", "description": "Large pedestal must be larger than small pedestal", "expression": "large_pedestal_diameter_mm > small_pedestal_diameter_mm", "severity": "error"}
        ],
        "required_views": ["top", "front_elevation", "side_elevation"],
        "required_details": ["pedestal_mounting_detail", "hidden_frame_detail"],
        "drawing_notes": [
            "SHOW ASYMMETRIC PEDESTAL POSITIONS.",
            "SHOW HIDDEN STEEL FRAME UNDER STONE TOP."
        ]
    },
}

# Write each template as a JSON file
for tid, data in templates.items():
    fname = f"{tid}.json"
    fpath = TEMPLATE_DIR / fname
    fpath.write_text(json.dumps(data, indent=2))
    print(f"Created: {fname}")

print(f"\nTotal templates created: {len(templates)}")
print(f"Total files in directory: {len(list(TEMPLATE_DIR.glob('*.json')))}")
