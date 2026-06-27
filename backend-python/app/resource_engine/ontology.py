"""Furniture Ontology — defines component structure per product type."""
from __future__ import annotations
from typing import List, Optional
from pydantic import BaseModel


class OntologyNode(BaseModel):
    role: str
    type: str
    required: bool = True
    resource_candidates: List[str] = []


class FurnitureOntology(BaseModel):
    product_type: str
    subtype: Optional[str] = None
    nodes: List[OntologyNode]
    required_views: List[str] = ["top", "front", "side"]


class FurnitureOntologyBuilder:
    """Builds an ontology (component tree) for any furniture product type."""

    def build(self, product_type: str, subtype: str = "",
              top_shape: str = "", support_type: str = "",
              material_top: str = "", upholstery_type: str = "") -> FurnitureOntology:

        pt = product_type

        # === TABLES ===
        if pt in ("dining_table", "asymmetric_pedestal_table", "oval_pedestal_table",
                  "rectangular_table", "round_pedestal_table", "console_table",
                  "coffee_table", "side_table"):
            nodes = [
                OntologyNode(role="top", type=top_shape or "rectangular"),
                OntologyNode(role="support", type=support_type or "four_leg"),
                OntologyNode(role="joinery", type="table_joinery", required=False),
                OntologyNode(role="top_material", type=material_top or "unknown"),
                OntologyNode(role="base_material", type="metal", required=False),
            ]
            return FurnitureOntology(product_type=pt, subtype=subtype, nodes=nodes,
                                     required_views=["top", "front", "side"])

        # === SEATING ===
        if pt in ("sofa", "lounge_chair", "dining_chair", "chair"):
            nodes = [
                OntologyNode(role="seat", type="upholstered_seat"),
                OntologyNode(role="back", type="upholstered_back"),
                OntologyNode(role="arms", type="arms", required=False),
                OntologyNode(role="base", type="sofa_base", required=False),
                OntologyNode(role="upholstery", type=upholstery_type or "fabric"),
            ]
            return FurnitureOntology(product_type=pt, subtype=subtype, nodes=nodes,
                                     required_views=["top", "front", "side"])

        # === BEDS ===
        if pt in ("bed", "bed_headboard"):
            nodes = [
                OntologyNode(role="mattress_zone", type="bed_platform"),
                OntologyNode(role="headboard", type="headboard"),
                OntologyNode(role="base", type="bed_base", required=False),
                OntologyNode(role="upholstery", type=upholstery_type or "fabric", required=False),
            ]
            return FurnitureOntology(product_type=pt, subtype=subtype, nodes=nodes,
                                     required_views=["top", "front", "side"])

        # === STORAGE / CASEWORK ===
        if pt in ("sideboard", "tv_console", "nightstand", "cabinet", "wardrobe"):
            nodes = [
                OntologyNode(role="case", type="rectangular_case"),
                OntologyNode(role="doors", type="door_fronts", required=False),
                OntologyNode(role="drawers", type="drawer_fronts", required=False),
                OntologyNode(role="base", type="cabinet_base", required=False),
                OntologyNode(role="material", type="wood_or_lacquer"),
            ]
            return FurnitureOntology(product_type=pt, subtype=subtype, nodes=nodes,
                                     required_views=["front", "side", "top"])

        # === DESK / OFFICE ===
        if pt in ("office_desk", "desk", "reception_counter"):
            nodes = [
                OntologyNode(role="top", type="rectangular"),
                OntologyNode(role="support", type="four_leg"),
                OntologyNode(role="material", type="wood_or_lacquer"),
            ]
            return FurnitureOntology(product_type=pt, subtype=subtype, nodes=nodes,
                                     required_views=["top", "front", "side"])

        # Fallback generic
        return FurnitureOntology(product_type=pt, subtype=subtype, nodes=[],
                                 required_views=["top", "front"])
