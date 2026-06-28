"""
Furniture Grammar Engine — composes DrawingModel from grammar definitions.

USAGE:
    from app.backend.grammar import FurnitureGrammar
    grammar = FurnitureGrammar()

    # Look up a template
    template = grammar.get_template("dining_table_rectangular_4_leg")
    # template.family = "table", template.builder_fn = build_rectangular_table_model

    # Generate a DrawingModel (delegates to builder or composes from primitives)
    model = grammar.generate("dining_table_rectangular_4_leg", {
        "width_cm": 180, "depth_cm": 90, "height_cm": 75, ...
    })

    # Check if a type is supported
    if grammar.supports("novel_bench"):
        model = grammar.generate("novel_bench", params)

    # Get inherited family for a type
    family = grammar.get_family_for_type("coffee_table_rectangular_4_leg")
    # returns "table" (inherited from coffee_table → table)
"""

from __future__ import annotations

import logging
from typing import Any

from app.backend.drawing_model import DrawingModel

from .definitions import GrammarFamily, GrammarTemplate, get_grammar

logger = logging.getLogger("grammar_engine")


class FurnitureGrammar:
    """Grammar engine that maps furniture types to builder functions.

    WRAPPER PATTERN: When a known template exists, delegates to the existing
    builder function. When a template has NO builder (new type), falls back
    to generic geometry composition from grammar primitives.

    KEY INSIGHT: This is additive. All existing builder functions continue
    to work. The grammar just provides a unified interface + fallback.
    """

    def __init__(self):
        self._grammar = get_grammar()
        # Build reverse lookup: template name → family name
        self._template_to_family: dict[str, str] = {}
        for fname, family in self._grammar.items():
            for tname in family.templates:
                self._template_to_family[tname] = fname

    # ─── Lookup ─────────────────────────────────────────────────────

    def get_template(self, furniture_type: str) -> GrammarTemplate | None:
        """Look up a template by furniture type name.

        Searches all families. Returns None if not found.
        """
        for family in self._grammar.values():
            if furniture_type in family.templates:
                return family.templates[furniture_type]
        return None

    def get_family(self, family_name: str) -> GrammarFamily | None:
        """Get a family definition by name."""
        return self._grammar.get(family_name)

    def get_family_for_type(self, furniture_type: str) -> GrammarFamily | None:
        """Get the family that contains this furniture type."""
        fname = self._template_to_family.get(furniture_type)
        if fname:
            return self._grammar.get(fname)
        return None

    def supports(self, furniture_type: str) -> bool:
        """Check if a furniture type is known to the grammar."""
        return furniture_type in self._template_to_family

    def get_known_types(self) -> list[str]:
        """List all known furniture types across all families."""
        return list(self._template_to_family.keys())

    def get_families(self) -> list[str]:
        """List all family names."""
        return list(self._grammar.keys())

    def get_types_by_family(self, family_name: str) -> list[str]:
        """Get all template names in a family."""
        family = self._grammar.get(family_name)
        if family:
            return list(family.templates.keys())
        return []

    # ─── Generation ─────────────────────────────────────────────────

    def generate(self, furniture_type: str, params: dict[str, Any]) -> DrawingModel:
        """Generate a DrawingModel for the given furniture type.

        Delegates to existing builder function when available.
        Falls back to generic composition when no builder exists.

        Args:
            furniture_type: e.g. "dining_table_rectangular_4_leg"
            params: dimension parameters matching the builder's signature
                    e.g. {"width_cm": 180, "depth_cm": 90, "height_cm": 75, ...}

        Returns:
            DrawingModel ready for SVG/DXF export
        """
        template = self.get_template(furniture_type)

        if template and template.builder_fn:
            return self._delegate_to_builder(template, params)

        family = self.get_family_for_type(furniture_type)
        if family is None:
            # Try family name as fallback
            family = self._grammar.get(furniture_type)

        if family:
            return self._compose_from_primitives(furniture_type, family, params)

        # Last resort: generic fallback
        logger.warning(f"[Grammar] No definition for {furniture_type}, using generic")
        return self._generic_fallback(params)

    # ─── Builder delegation ─────────────────────────────────────────

    def _delegate_to_builder(self, template: GrammarTemplate, params: dict[str, Any]) -> DrawingModel:
        """Call the existing builder function with the right parameters.

        This is how the grammar stays backward compatible. The builder
        function doesn't know it's being called from the grammar.
        """
        logger.info(f"[Grammar] Delegating {template.name} to builder function")

        # Map common parameter names to builder function parameter names
        known_params = self._normalize_params(params)

        # Filter to only parameters the builder accepts
        import inspect
        sig = inspect.signature(template.builder_fn)
        valid_params = {}
        for key in sig.parameters:
            if key in known_params:
                valid_params[key] = known_params[key]
            elif key == "materials":
                valid_params[key] = known_params.get("materials", None)
            elif key == "client":
                valid_params[key] = known_params.get("client", "")
            elif key == "project":
                valid_params[key] = known_params.get("project", "Furniture Shop Drawing")

        try:
            return template.builder_fn(**valid_params)
        except Exception as e:
            logger.error(f"[Grammar] Builder error for {template.name}: {e}")
            raise

    def _normalize_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """Normalize common parameter names to what builders expect.

        Maps user-facing dimension names → builder function parameter names.
        Identity entries (like length_cm→length_cm) are kept for clarity
        even though they're no-ops — they document the canonical names.
        """
        # MAPPINGS: user-facing_key → builder parameter_key
        # Remove entries where key == value to eliminate no-ops
        mapping = {
            "overall_height_cm": "overall_height_cm",
            "top_diameter_cm": "top_dia_cm",
            "base_diameter_cm": "base_dia_cm",
            "collar_diameter_cm": "collar_dia_cm",
            "neck_diameter_cm": "neck_dia_cm",
            "top_thickness_cm": "top_thick_cm",
            "base_thickness_cm": "base_thick_cm",
            "seat_height_cm": "seat_height_cm",
            "leg_thickness_cm": "leg_thick_cm",
            "pedestal_diameter_cm": "pedestal_dia_cm",
            "material": "materials",
            "materials_json": "materials",
        }

        result = {}
        for k, v in params.items():
            # First check explicit mapping
            mapped = mapping.get(k)
            if mapped:
                result[mapped] = v
            else:
                # Keep original key (builders may accept it directly)
                result[k] = v
        return result

    # ─── Generic composition fallback ────────────────────────────────

    def _compose_from_primitives(
        self, furniture_type: str, family: GrammarFamily, params: dict[str, Any]
    ) -> DrawingModel:
        """Compose a DrawingModel from grammar primitives when no builder exists.

        Uses the family definition to determine what components to create
        and how to arrange them geometrically.

        This is how you add furniture type #26 without writing a builder function.
        """
        logger.info(f"[Grammar] Composing {furniture_type} from {family.name} primitives")

        from app.backend.drawing_model import (
            DimensionComponent,
            EntityMetadata,
            PolygonComponent,
            TextComponent,
        )
        from app.backend.drawing_model import (
            DrawingModel as DM,
        )
        from app.backend.drawing_model import (
            Point as DP,
        )
        from app.backend.drawing_model import (
            View as DV,
        )

        # Extract dimensions
        w = float(params.get("width_cm", params.get("length_cm", 100.0)))
        d = float(params.get("depth_cm", 60.0))
        h = float(params.get("height_cm", 75.0))
        sc = 2.0  # scale factor for DXF space

        model = DM(
            furniture_type=furniture_type,
            page_width=420.0,
            page_height=297.0,
            scale=0.5,
        )

        # FRONT VIEW
        front = DV(name="FRONT VIEW")

        # Main body (rectangle)
        body_h = h * sc
        body_w = w * sc
        floor_y = 30.0
        top_y = floor_y + body_h

        meta = EntityMetadata(source="grammar_composed", confidence=0.50)
        front.polygons.append(PolygonComponent(
            points=[
                DP(x=200 - body_w/2, y=top_y),
                DP(x=200 + body_w/2, y=top_y),
                DP(x=200 + body_w/2, y=floor_y),
                DP(x=200 - body_w/2, y=floor_y),
            ],
            layer="OBJECT",
            name="main_body",
            metadata=meta,
        ))

        # Overall dimension
        front.dimensions.append(DimensionComponent(
            p1=DP(x=200 - body_w/2, y=floor_y),
            p2=DP(x=200 + body_w/2, y=floor_y),
            label=f"{w:.0f}cm",
            layer="DIMENSION",
        ))
        front.dimensions.append(DimensionComponent(
            p1=DP(x=200 - body_w/2 - 20, y=floor_y),
            p2=DP(x=200 - body_w/2 - 20, y=top_y),
            label=f"{h:.0f}cm",
            layer="DIMENSION",
        ))

        model.views.append(front)

        # TOP VIEW
        top = DV(name="TOP VIEW")
        tv_w = w * 0.6
        tv_d = d * 0.6
        tv_x, tv_y = 60.0, top_y - tv_d * 0.5

        top.polygons.append(PolygonComponent(
            points=[
                DP(x=tv_x - tv_w/2, y=tv_y - tv_d/2),
                DP(x=tv_x + tv_w/2, y=tv_y - tv_d/2),
                DP(x=tv_x + tv_w/2, y=tv_y + tv_d/2),
                DP(x=tv_x - tv_w/2, y=tv_y + tv_d/2),
            ],
            layer="OBJECT",
            name="top_view",
            metadata=meta,
        ))
        top.dimensions.append(DimensionComponent(
            p1=DP(x=tv_x - tv_w/2, y=tv_y + tv_d/2 + 5),
            p2=DP(x=tv_x + tv_w/2, y=tv_y + tv_d/2 + 5),
            label=f"{w:.0f}cm",
            layer="DIMENSION",
        ))
        top.texts.append(TextComponent(
            content="TOP VIEW",
            position=DP(x=tv_x - 12, y=tv_y - tv_d/2 - 8),
            height=2.5,
            layer="MTEXT",
        ))
        model.views.append(top)

        # SIDE VIEW
        side = DV(name="SIDE VIEW")
        side_w = d * sc
        sx, sy = 200.0, top_y  # align with front view

        side.polygons.append(PolygonComponent(
            points=[
                DP(x=sx - side_w/2, y=sy),
                DP(x=sx + side_w/2, y=sy),
                DP(x=sx + side_w/2, y=floor_y),
                DP(x=sx - side_w/2, y=floor_y),
            ],
            layer="OBJECT",
            name="side_view",
            metadata=meta,
        ))
        side.dimensions.append(DimensionComponent(
            p1=DP(x=sx - side_w/2 - 15, y=floor_y),
            p2=DP(x=sx - side_w/2 - 15, y=sy),
            label=f"{h:.0f}cm",
            layer="DIMENSION",
        ))
        model.views.append(side)

        return model

    def _generic_fallback(self, params: dict[str, Any]) -> DrawingModel:
        """Last-resort generic fallback when nothing is known about the type."""
        logger.warning("[Grammar] Using generic fallback — no type or family match")
        return self._compose_from_primitives("generic", GrammarFamily(name="generic"), params)


# ─── Convenience functions ──────────────────────────────────────────

_engine: FurnitureGrammar | None = None

def get_grammar_engine() -> FurnitureGrammar:
    """Get singleton grammar engine."""
    global _engine
    if _engine is None:
        _engine = FurnitureGrammar()
    return _engine
