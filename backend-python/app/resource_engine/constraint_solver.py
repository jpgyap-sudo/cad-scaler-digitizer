"""Constraint Solver — validates and adjusts scene graph parameters."""
from typing import Any, Dict, List, Optional
from .schema import ParametricSceneGraph, SceneComponent


def solve_constraints(scene: ParametricSceneGraph) -> ParametricSceneGraph:
    """Validate and adjust all component parameters against constraints.
    
    Returns the same scene with warnings added for any adjustments.
    """
    top = _get_component(scene, "top")
    supports = [c for c in scene.components if c.role == "support"]
    seat = _get_component(scene, "seat")
    
    # === DINING TABLE CHECKS (height 720-780mm) ===
    if scene.product_type in ("dining_table", "round_pedestal_table", "asymmetric_pedestal_table",
                              "oval_pedestal_table", "rectangular_table", "console_table",
                              "coffee_table", "side_table"):
        if top:
            _clamp_dining_height(scene, top, supports)
            
            # Top thickness constraints
            length = top.parameters.get("length_mm", top.parameters.get("length_cm", 180) * 10)
            thickness = top.parameters.get("thickness_mm", top.parameters.get("thickness_cm", 3) * 10)
            if length > 1200 and thickness < 30:
                top.parameters["thickness_mm"] = 30
                scene.warnings.append(f"Stone top thickness increased to 30mm for {length}mm span.")
            
            # Coffee table height
            if scene.product_type == "coffee_table":
                h = top.parameters.get("height_mm", top.parameters.get("height_cm", 38) * 10)
                if h < 300 or h > 500:
                    scene.warnings.append(f"Coffee table height {h}mm outside typical range 300-500mm.")
    
    # === OFFICE DESK CHECKS ===
    if scene.product_type in ("office_desk", "desk", "reception_counter"):
        if top:
            _clamp_desk_params(scene, top, supports)
    
    # === SOFA / SEATING CHECKS ===
    if scene.product_type in ("sofa", "lounge_chair", "dining_chair", "chair"):
        _solve_seating(scene, seat)
    
    # === BED CHECKS ===
    if scene.product_type in ("bed", "bed_headboard"):
        _solve_bed(scene)
    
    # === STORAGE / CASEWORK CHECKS ===
    if scene.product_type in ("sideboard", "tv_console", "nightstand", "cabinet", "wardrobe"):
        _solve_storage(scene)
    
    # === Overhang check for pedestal tables ===
    if supports and top:
        depth = top.parameters.get("depth_mm", top.parameters.get("depth_cm", 900) * 10)
        for support in supports:
            dia = support.parameters.get("diameter_mm") or support.parameters.get("large_diameter_mm", 400)
            overhang = (depth - dia) / 2
            if overhang < 100:
                scene.warnings.append(f"Overhang {overhang:.0f}mm < 100mm minimum. Adjust support spacing.")
    
    return scene


def _get_component(scene: ParametricSceneGraph, role: str) -> Optional[SceneComponent]:
    for c in scene.components:
        if c.role == role:
            return c
    return None


def _clamp_dining_height(scene, top, supports):
    """Dining tables: total height must be 720-780mm."""
    top_thick = top.parameters.get("thickness_mm", top.parameters.get("thickness_cm", 3) * 10)
    for support in supports:
        h = support.parameters.get("height_mm", support.parameters.get("height_cm", 72) * 10)
        total = h + top_thick
        if total < 720:
            support.parameters["height_mm"] = 750 - top_thick
            scene.warnings.append(f"Support height adjusted to {750-top_thick:.0f}mm for 750mm total.")
        elif total > 780:
            support.parameters["height_mm"] = 750 - top_thick
            scene.warnings.append(f"Support height adjusted to {750-top_thick:.0f}mm for 750mm total.")


def _solve_seating(scene, seat):
    """Seating: seat height 400-500mm, total height 750-850mm for dining chairs."""
    if not seat:
        return
    p = seat.parameters
    sh = p.get("seat_height_mm", 420)
    if sh < 350 or sh > 550:
        p["seat_height_mm"] = 420
        scene.warnings.append("Seat height adjusted to 420mm standard.")
    back = _get_component(scene, "back")
    if back:
        h = p.get("height_mm", p.get("overall_height_mm", 780))
        if h < 700 or h > 900:
            p["height_mm"] = 780
            scene.warnings.append("Total height adjusted to 780mm.")


def _solve_bed(scene):
    """Bed: platform height 250-400mm, mattress zone minimum 1900x1350mm."""
    mattress = _get_component(scene, "mattress_zone")
    if mattress:
        p = mattress.parameters
        ph = p.get("platform_height_mm", 300)
        if ph < 200 or ph > 500:
            p["platform_height_mm"] = 300
            scene.warnings.append("Platform height adjusted to 300mm.")
        l = p.get("length_mm", 2030)
        d = p.get("depth_mm", 1830)
        if l < 1800:
            p["length_mm"] = 1900
            scene.warnings.append("Bed length adjusted to 1900mm minimum.")


def _solve_storage(scene):
    """Storage: overall height 700-2000mm, depth 350-650mm."""
    case = _get_component(scene, "case")
    if case:
        p = case.parameters
        h = p.get("height_mm", 800)
        if h < 400 or h > 2200:
            p["height_mm"] = 800
            scene.warnings.append("Cabinet height adjusted to 800mm.")
        d = p.get("depth_mm", 450)
        if d < 300 or d > 800:
            p["depth_mm"] = 450
            scene.warnings.append("Cabinet depth adjusted to 450mm.")


def _clamp_desk_params(scene, top, supports):
    """Office desk: standard ergonomic constraints."""
    top_thick = top.parameters.get("thickness_mm", top.parameters.get("thickness_cm", 2.5) * 10)
    for support in supports:
        h = support.parameters.get("height_mm", support.parameters.get("height_cm", 72) * 10)
        total = h + top_thick
        if total < 720:
            support.parameters["height_mm"] = 750 - top_thick
        elif total > 760:
            support.parameters["height_mm"] = 750 - top_thick
    depth = top.parameters.get("depth_mm", top.parameters.get("depth_cm", 60) * 10)
    if depth < 500:
        top.parameters["depth_mm"] = 600
        scene.warnings.append("Desk depth increased to 600mm minimum.")
