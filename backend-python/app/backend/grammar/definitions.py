"""
Furniture Grammar Definitions — composition rules for all furniture types.

Every furniture type is defined by:
  - family (inherits rules from parent)
  - allowed parts (top, base, legs, apron, etc.)
  - allowed profiles (rectangle, round, oval, etc.)
  - proportions (ratios between dimensions)
  - view order
  - template instances (which builder function or geometry primitives)

KEY DESIGN: New types can be added WITHOUT writing builder functions.
If a type has no builder, the grammar engine composes from geometry primitives.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.backend.drawing_model import DrawingModel

# ─── Type alias for builder functions ───────────────────────────────
BuilderFn = Callable[..., DrawingModel]


# ─── Grammar definition structure ───────────────────────────────────
class GrammarTemplate:
    """A template instance within a grammar family."""
    def __init__(
        self,
        name: str,
        family: str,
        top_type: str = "rectangle",
        base_type: str = "four_leg",
        leg_count: int = 4,
        builder_fn: BuilderFn | None = None,
        description: str = "",
    ):
        self.name = name
        self.family = family
        self.top_type = top_type
        self.base_type = base_type
        self.leg_count = leg_count
        self.builder_fn = builder_fn
        self.description = description


class GrammarFamily:
    """A furniture family with inheritance, rules, and template instances."""
    def __init__(
        self,
        name: str,
        inherits: list[str] | None = None,
        top_types: list[str] | None = None,
        base_types: list[str] | None = None,
        proportions: dict[str, float] | None = None,
        view_order: list[str] | None = None,
        height_range: list[float] | None = None,
        overrides: dict[str, Any] | None = None,
    ):
        self.name = name
        self.inherits = inherits or []
        self.top_types = top_types or ["rectangle"]
        self.base_types = base_types or ["four_leg"]
        self.proportions = proportions or {}
        self.view_order = view_order or ["top", "front", "side"]
        self.height_range = height_range or [30, 110]
        self.overrides = overrides or {}
        self.templates: dict[str, GrammarTemplate] = {}


# ─── Grammar Definitions ────────────────────────────────────────────
# Each family defines what parts it can have, what profiles are allowed,
# and what proportion rules apply. Template instances map to builder
# functions OR fall back to generic composition.
#
# To add a NEW furniture type (e.g., "bench"):
#   1. Add to the appropriate family OR create a new family
#   2. If it needs custom geometry: assign a builder_fn
#   3. If it can be composed from primitives: skip builder_fn, grammar generates it

# ─── Families ───────────────────────────────────────────────────────

TABLE_FAMILY = GrammarFamily(
    name="table",
    top_types=["rectangle", "round", "oval", "boat", "organic"],
    base_types=["four_leg", "pedestal", "metal_frame", "trestle", "plinth"],
    proportions={
        "top_thickness_to_height": 0.04,
        "base_height_to_total": 0.92,
        "overhang_ratio": 0.10,
    },
    height_range=[50, 110],
    view_order=["top", "front", "side"],
)

SOFA_FAMILY = GrammarFamily(
    name="seating",
    top_types=["rectangle"],
    base_types=["four_leg", "plinth", "sled"],
    proportions={
        "seat_height_to_total": 0.55,
        "arm_height_to_total": 0.75,
        "back_height_to_total": 0.85,
    },
    height_range=[75, 100],
    view_order=["front", "side", "top"],
)

CHAIR_FAMILY = GrammarFamily(
    name="chair",
    inherits=["seating"],
    base_types=["four_leg", "sled", "swivel"],
    proportions={
        "seat_height_to_total": 0.52,
        "back_height_to_total": 0.88,
        "leg_height_to_total": 0.40,
    },
    height_range=[75, 110],
    view_order=["front", "side", "top"],
)

STORAGE_FAMILY = GrammarFamily(
    name="storage",
    top_types=["rectangle"],
    base_types=["plinth", "four_leg", "recessed"],
    proportions={
        "door_height_to_total": 0.80,
        "drawer_height_to_total": 0.15,
        "plinth_height_to_total": 0.05,
    },
    height_range=[50, 220],
    view_order=["front", "side", "top"],
)

BED_FAMILY = GrammarFamily(
    name="bed",
    top_types=["rectangle"],
    base_types=["platform", "frame"],
    proportions={
        "headboard_height_to_total": 0.40,
        "platform_height_to_total": 0.30,
    },
    height_range=[80, 120],
    view_order=["top", "front", "side"],
)


# ─── Master Grammar Dictionary ──────────────────────────────────────
# Maps family names to family objects with their template instances.

def _define_grammar() -> dict[str, GrammarFamily]:
    """Build the complete grammar with all template instances."""
    from app.backend.drawing_builders import (
        build_asymmetric_pedestal_model,
        build_bed_headboard_model,
        build_cabinet_model,
        build_coffee_table_model,
        build_console_table_model,
        build_dining_chair_model,
        build_office_desk_model,
        build_oval_pedestal_model,
        build_reception_counter_model,
        build_rectangular_table_model,
        build_round_pedestal_model,
        build_sofa_model,
        build_wardrobe_model,
    )

    grammar: dict[str, GrammarFamily] = {}

    # ── Table Family (8 templates + 5 generic) ──
    tables = GrammarFamily(
        name="table",
        inherits=[],
        top_types=TABLE_FAMILY.top_types,
        base_types=TABLE_FAMILY.base_types,
        proportions=TABLE_FAMILY.proportions,
        height_range=TABLE_FAMILY.height_range,
        view_order=TABLE_FAMILY.view_order,
    )
    tables.templates["dining_table_rectangular_4_leg"] = GrammarTemplate(
        name="dining_table_rectangular_4_leg", family="table",
        top_type="rectangle", base_type="four_leg", leg_count=4,
        builder_fn=build_rectangular_table_model,
    )
    tables.templates["dining_table_round_pedestal"] = GrammarTemplate(
        name="dining_table_round_pedestal", family="table",
        top_type="round", base_type="pedestal", leg_count=0,
        builder_fn=build_round_pedestal_model,
    )
    tables.templates["coffee_table_rectangular_4_leg"] = GrammarTemplate(
        name="coffee_table_rectangular_4_leg", family="table",
        top_type="rectangle", base_type="four_leg", leg_count=4,
        builder_fn=build_coffee_table_model,
    )
    tables.templates["oval_pedestal_table"] = GrammarTemplate(
        name="oval_pedestal_table", family="table",
        top_type="oval", base_type="pedestal", leg_count=0,
        builder_fn=build_oval_pedestal_model,
    )
    tables.templates["console_table_slim"] = GrammarTemplate(
        name="console_table_slim", family="table",
        top_type="rectangle", base_type="four_leg", leg_count=4,
        builder_fn=build_console_table_model,
    )
    tables.templates["office_desk"] = GrammarTemplate(
        name="office_desk", family="table",
        top_type="rectangle", base_type="four_leg", leg_count=4,
        builder_fn=build_office_desk_model,
    )
    tables.templates["asymmetric_pedestal_table"] = GrammarTemplate(
        name="asymmetric_pedestal_table", family="table",
        top_type="rectangle", base_type="pedestal", leg_count=0,
        builder_fn=build_asymmetric_pedestal_model,
    )
    tables.templates["reception_counter"] = GrammarTemplate(
        name="reception_counter", family="table",
        top_type="rectangle", base_type="pedestal", leg_count=0,
        builder_fn=build_reception_counter_model,
    )
    # Generic (no builder — grammar composes from primitives)
    tables.templates["coffee_table_round_nesting_set"] = GrammarTemplate(
        name="coffee_table_round_nesting_set", family="table",
        top_type="round", base_type="four_leg", leg_count=4,
    )
    tables.templates["coffee_table_organic_blob"] = GrammarTemplate(
        name="coffee_table_organic_blob", family="table",
        top_type="organic", base_type="pedestal", leg_count=0,
    )
    tables.templates["coffee_table_glass_wire_mesh"] = GrammarTemplate(
        name="coffee_table_glass_wire_mesh", family="table",
        top_type="rectangle", base_type="metal_frame", leg_count=0,
    )
    tables.templates["coffee_table_block_plinth"] = GrammarTemplate(
        name="coffee_table_block_plinth", family="table",
        top_type="rectangle", base_type="plinth", leg_count=0,
    )
    tables.templates["side_table_round"] = GrammarTemplate(
        name="side_table_round", family="table",
        top_type="round", base_type="four_leg", leg_count=3,
    )
    tables.templates["side_table_rectangular"] = GrammarTemplate(
        name="side_table_rectangular", family="table",
        top_type="rectangle", base_type="four_leg", leg_count=4,
    )
    grammar["table"] = tables

    # ── Seating Family (sofa + armchair + bench + ottoman) ──
    seating = GrammarFamily(
        name="seating",
        inherits=[],
        top_types=SOFA_FAMILY.top_types,
        base_types=SOFA_FAMILY.base_types,
        proportions={
            "seat_height_to_total": 0.55,
            "arm_height_to_total": 0.75,
            "back_height_to_total": 0.85,
        },
        height_range=[75, 100],
        view_order=["front", "side", "top"],
    )
    seating.templates["sofa_straight_2_3_seat"] = GrammarTemplate(
        name="sofa_straight_2_3_seat", family="seating",
        top_type="rectangle", base_type="four_leg", leg_count=4,
        builder_fn=build_sofa_model,
    )
    seating.templates["sofa_sectional_l_shape"] = GrammarTemplate(
        name="sofa_sectional_l_shape", family="seating",
        top_type="rectangle", base_type="four_leg", leg_count=6,
    )
    seating.templates["armchair_lounge"] = GrammarTemplate(
        name="armchair_lounge", family="seating",
        top_type="rectangle", base_type="four_leg", leg_count=4,
    )
    seating.templates["bench_chaise"] = GrammarTemplate(
        name="bench_chaise", family="seating",
        top_type="rectangle", base_type="four_leg", leg_count=4,
    )
    seating.templates["ottoman_pouf"] = GrammarTemplate(
        name="ottoman_pouf", family="seating",
        top_type="rectangle", base_type="four_leg", leg_count=4,
    )
    grammar["seating"] = seating

    # ── Chair Family ──
    chairs = GrammarFamily(
        name="chair",
        inherits=["seating"],
        top_types=["rectangle", "round"],
        base_types=["four_leg", "sled", "swivel"],
        proportions={
            "seat_height_to_total": 0.52,
            "back_height_to_total": 0.88,
            "leg_height_to_total": 0.40,
        },
        height_range=[75, 110],
        view_order=["front", "side", "top"],
    )
    chairs.templates["dining_chair"] = GrammarTemplate(
        name="dining_chair", family="chair",
        top_type="rectangle", base_type="four_leg", leg_count=4,
        builder_fn=build_dining_chair_model,
    )
    chairs.templates["bar_stool"] = GrammarTemplate(
        name="bar_stool", family="chair",
        top_type="round", base_type="four_leg", leg_count=4,
    )
    grammar["chair"] = chairs

    # ── Storage Family ──
    storage = GrammarFamily(
        name="storage",
        inherits=[],
        top_types=["rectangle"],
        base_types=["plinth", "four_leg", "recessed"],
        proportions={
            "door_height_to_total": 0.80,
            "drawer_height_to_total": 0.15,
            "plinth_height_to_total": 0.05,
        },
        height_range=[50, 220],
        view_order=["front", "side", "top"],
    )
    storage.templates["cabinet"] = GrammarTemplate(
        name="cabinet", family="storage",
        top_type="rectangle", base_type="plinth", leg_count=0,
        builder_fn=build_cabinet_model,
    )
    storage.templates["wardrobe"] = GrammarTemplate(
        name="wardrobe", family="storage",
        top_type="rectangle", base_type="plinth", leg_count=0,
        builder_fn=build_wardrobe_model,
    )
    storage.templates["sideboard_2_4_door"] = GrammarTemplate(
        name="sideboard_2_4_door", family="storage",
        top_type="rectangle", base_type="plinth", leg_count=0,
    )
    storage.templates["tv_cabinet_low"] = GrammarTemplate(
        name="tv_cabinet_low", family="storage",
        top_type="rectangle", base_type="plinth", leg_count=0,
    )
    storage.templates["nightstand_bedside_drawer"] = GrammarTemplate(
        name="nightstand_bedside_drawer", family="storage",
        top_type="rectangle", base_type="four_leg", leg_count=4,
    )
    grammar["storage"] = storage

    # ── Bed Family ──
    beds = GrammarFamily(
        name="bed",
        inherits=[],
        top_types=["rectangle"],
        base_types=["platform", "frame"],
        proportions={
            "headboard_height_to_total": 0.40,
            "platform_height_to_total": 0.30,
        },
        height_range=[80, 120],
        view_order=["top", "front", "side"],
    )
    beds.templates["bed_headboard"] = GrammarTemplate(
        name="bed_headboard", family="bed",
        top_type="rectangle", base_type="frame", leg_count=0,
        builder_fn=build_bed_headboard_model,
    )
    beds.templates["bed_frame_upholstered"] = GrammarTemplate(
        name="bed_frame_upholstered", family="bed",
        top_type="rectangle", base_type="platform", leg_count=0,
    )
    grammar["bed"] = beds

    # ── Decor Family (no builders — grammar composes) ──
    decor = GrammarFamily(
        name="decor",
        inherits=[],
        top_types=["rectangle", "round"],
        base_types=["none"],
        proportions={},
        height_range=[0, 10],
        view_order=["top", "front"],
    )
    decor.templates["rug_rectangle"] = GrammarTemplate(
        name="rug_rectangle", family="decor",
        top_type="rectangle", base_type="none", leg_count=0,
    )
    decor.templates["wall_panel_fluted"] = GrammarTemplate(
        name="wall_panel_fluted", family="decor",
        top_type="rectangle", base_type="none", leg_count=0,
    )
    decor.templates["stone_slab_rectangular"] = GrammarTemplate(
        name="stone_slab_rectangular", family="decor",
        top_type="rectangle", base_type="none", leg_count=0,
    )
    grammar["decor"] = decor

    return grammar


# ─── Singleton access ──────────────────────────────────────────────
_grammar_cache: dict[str, GrammarFamily] | None = None

def get_grammar() -> dict[str, GrammarFamily]:
    global _grammar_cache
    if _grammar_cache is None:
        _grammar_cache = _define_grammar()
    return _grammar_cache
