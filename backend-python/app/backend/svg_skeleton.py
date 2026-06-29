"""Lightweight SVG Skeleton Generator — preview geometry before DXF.

For each product family, generates a minimal SVG outline/contour drawing
based on the product DNA's bounding_ratio and component_list.

This is NOT a detailed DXF — it's a "validate the geometry before committing"
step, rendered directly in the browser.

Usage:
    svg = generate_skeleton("straight_modern_sofa", {"width_cm": 200, "depth_cm": 85, "height_cm": 80})
    svg = generate_skeleton_from_handle("aalto-modern-sofa", {"width_cm": 180, "depth_cm": 80})
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
CATALOG_DIR = Path(__file__).resolve().parents[2] / "resources" / "product_catalog"
DNA_PATH = CATALOG_DIR / "product_dna.json"
DNA_INDEX_PATH = CATALOG_DIR / "visual_dna_index.json"

# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------
_PRODUCT_DNA: Dict[str, Any] | None = None
_DNA_INDEX: Dict[str, Any] | None = None


def _load_product_dna() -> Dict[str, Any]:
    global _PRODUCT_DNA
    if _PRODUCT_DNA is not None:
        return _PRODUCT_DNA
    if DNA_PATH.exists():
        try:
            _PRODUCT_DNA = json.loads(DNA_PATH.read_text(encoding="utf-8"))
        except Exception:
            _PRODUCT_DNA = {}
    else:
        _PRODUCT_DNA = {}
    return _PRODUCT_DNA


def _load_dna_index() -> Dict[str, Any]:
    global _DNA_INDEX
    if _DNA_INDEX is not None:
        return _DNA_INDEX
    if DNA_INDEX_PATH.exists():
        try:
            _DNA_INDEX = json.loads(DNA_INDEX_PATH.read_text(encoding="utf-8"))
        except Exception:
            _DNA_INDEX = {}
    else:
        _DNA_INDEX = {}
    return _DNA_INDEX


# ---------------------------------------------------------------------------
# Bounding box / ratio helpers
# ---------------------------------------------------------------------------

def _parse_ratio(ratio_str: str) -> Tuple[float, float, float]:
    """Parse '2.5:1:0.8' → (2.5, 1.0, 0.8)."""
    parts = ratio_str.split(":")
    if len(parts) >= 3:
        try:
            return float(parts[0]), float(parts[1]), float(parts[2])
        except ValueError:
            pass
    return (1.65, 1.0, 0.42)


def _dimensions_to_svg_coords(
    ratio: Tuple[float, float, float],
    width_cm: float = 100,
    depth_cm: Optional[float] = None,
    height_cm: Optional[float] = None,
    svg_width: int = 400,
    svg_height: int = 300,
) -> Dict[str, float]:
    """Convert real dimensions to SVG viewport coordinates.

    Returns {svg_w, svg_h, scale, ox, oy} for the front view.
    Uses depth as the horizontal dimension, height as vertical.
    """
    rw, rd, rh = ratio

    # If real dimensions provided, use them; else derive from ratio
    if depth_cm and depth_cm > 0:
        real_w = depth_cm  # front view shows depth as width
    else:
        real_w = rw * 50  # default scale factor

    if height_cm and height_cm > 0:
        real_h = height_cm
    else:
        real_h = rh * 50

    # Scale to fit SVG viewport with margins
    margin = 40
    avail_w = svg_width - 2 * margin
    avail_h = svg_height - 2 * margin

    scale_w = avail_w / real_w if real_w > 0 else 1
    scale_h = avail_h / real_h if real_h > 0 else 1
    scale = min(scale_w, scale_h)

    # Center in viewport
    ox = (svg_width - real_w * scale) / 2
    oy = (svg_height - real_h * scale) / 2

    return {
        "svg_w": svg_width,
        "svg_h": svg_height,
        "scale": scale,
        "ox": ox,
        "oy": oy,
        "real_w": real_w,
        "real_h": real_h,
    }


# ---------------------------------------------------------------------------
# Component positional layouts (per family archetype)
# ---------------------------------------------------------------------------

def _get_component_layout(
    family: str,
    bounding_ratio: str,
    components: List[str],
) -> Dict[str, Dict[str, float]]:
    """Return relative positions for each component in [0..1] space.

    Returns dict of component_name → {x, y, w, h} as fractions.
    """
    ratio = _parse_ratio(bounding_ratio)
    family_lower = family.lower()
    layout: Dict[str, Dict[str, float]] = {}

    if any(k in family_lower for k in ["sofa", "bench", "sofa_bench"]):
        # Front view of a sofa
        layout = {
            "seat_base": {"x": 0.05, "y": 0.35, "w": 0.90, "h": 0.35},
            "seat_cushions": {"x": 0.15, "y": 0.35, "w": 0.70, "h": 0.20},
            "backrest": {"x": 0.05, "y": 0.02, "w": 0.90, "h": 0.33},
            "armrests": {"x": 0.02, "y": 0.15, "w": 0.10, "h": 0.55},
            "legs_or_plinth": {"x": 0.10, "y": 0.82, "w": 0.80, "h": 0.15},
        }
    elif any(k in family_lower for k in ["armchair", "lounge_chair"]):
        layout = {
            "seat": {"x": 0.10, "y": 0.40, "w": 0.80, "h": 0.30},
            "backrest": {"x": 0.10, "y": 0.02, "w": 0.80, "h": 0.38},
            "armrests": {"x": 0.02, "y": 0.15, "w": 0.12, "h": 0.50},
            "legs_or_frame": {"x": 0.15, "y": 0.80, "w": 0.70, "h": 0.18},
        }
    elif any(k in family_lower for k in ["dining_table", "table", "coffee_table"]):
        layout = {
            "tabletop": {"x": 0.05, "y": 0.05, "w": 0.90, "h": 0.25},
            "base_support_or_legs": {"x": 0.20, "y": 0.30, "w": 0.60, "h": 0.55},
            "legs_or_frame": {"x": 0.10, "y": 0.40, "w": 0.80, "h": 0.50},
        }
    elif any(k in family_lower for k in ["dining_chair", "chair"]):
        layout = {
            "seat": {"x": 0.10, "y": 0.40, "w": 0.80, "h": 0.25},
            "backrest": {"x": 0.10, "y": 0.02, "w": 0.80, "h": 0.38},
            "legs": {"x": 0.15, "y": 0.70, "w": 0.70, "h": 0.28},
        }
    elif any(k in family_lower for k in ["bar_stool", "stool"]):
        layout = {
            "seat": {"x": 0.10, "y": 0.05, "w": 0.80, "h": 0.15},
            "backrest": {"x": 0.10, "y": 0.02, "w": 0.80, "h": 0.05},
            "legs": {"x": 0.15, "y": 0.20, "w": 0.70, "h": 0.75},
        }
    elif any(k in family_lower for k in ["ottoman", "pouf"]):
        layout = {
            "main_body": {"x": 0.05, "y": 0.10, "w": 0.90, "h": 0.55},
            "support": {"x": 0.10, "y": 0.70, "w": 0.80, "h": 0.25},
        }
    elif any(k in family_lower for k in ["pendant", "light", "chandelier"]):
        layout = {
            "canopy_or_mount": {"x": 0.30, "y": 0.02, "w": 0.40, "h": 0.08},
            "support_rods_or_blades": {"x": 0.48, "y": 0.10, "w": 0.04, "h": 0.30},
            "body": {"x": 0.15, "y": 0.40, "w": 0.70, "h": 0.35},
            "diffuser_or_shade": {"x": 0.10, "y": 0.75, "w": 0.80, "h": 0.20},
        }
    elif any(k in family_lower for k in ["ceiling_fan", "fan"]):
        layout = {
            "canopy_or_mount": {"x": 0.35, "y": 0.02, "w": 0.30, "h": 0.08},
            "body": {"x": 0.40, "y": 0.10, "w": 0.20, "h": 0.20},
            "diffuser_or_shade": {"x": 0.30, "y": 0.30, "w": 0.40, "h": 0.15},
            "light_source": {"x": 0.35, "y": 0.45, "w": 0.30, "h": 0.10},
        }
    elif any(k in family_lower for k in ["cabinet", "wardrobe", "sideboard"]):
        layout = {
            "main_body": {"x": 0.05, "y": 0.05, "w": 0.90, "h": 0.80},
            "door_or_drawer": {"x": 0.10, "y": 0.10, "w": 0.35, "h": 0.60},
            "door_or_drawer_2": {"x": 0.55, "y": 0.10, "w": 0.35, "h": 0.60},
            "base_or_plinth": {"x": 0.05, "y": 0.85, "w": 0.90, "h": 0.12},
        }
    elif any(k in family_lower for k in ["wall_panel", "panel"]):
        layout = {
            "panel_body": {"x": 0.02, "y": 0.02, "w": 0.96, "h": 0.96},
        }
    elif any(k in family_lower for k in ["stone", "slab", "sintered"]):
        layout = {
            "surface": {"x": 0.02, "y": 0.02, "w": 0.96, "h": 0.96},
        }
    elif any(k in family_lower for k in ["rug", "carpet"]):
        layout = {
            "surface": {"x": 0.02, "y": 0.02, "w": 0.96, "h": 0.96},
        }
    elif any(k in family_lower for k in ["pillow", "throw"]):
        layout = {
            "fabric_shell": {"x": 0.05, "y": 0.05, "w": 0.90, "h": 0.90},
            "decorative_face": {"x": 0.10, "y": 0.10, "w": 0.80, "h": 0.80},
        }
    elif any(k in family_lower for k in ["lamp", "sconce"]):
        layout = {
            "base": {"x": 0.20, "y": 0.75, "w": 0.60, "h": 0.15},
            "body": {"x": 0.30, "y": 0.30, "w": 0.40, "h": 0.45},
            "shade": {"x": 0.15, "y": 0.02, "w": 0.70, "h": 0.28},
        }
    elif any(k in family_lower for k in ["bed", "headboard"]):
        layout = {
            "headboard": {"x": 0.02, "y": 0.02, "w": 0.96, "h": 0.40},
            "mattress_or_bed": {"x": 0.02, "y": 0.42, "w": 0.96, "h": 0.35},
            "base": {"x": 0.02, "y": 0.80, "w": 0.96, "h": 0.18},
        }
    elif any(k in family_lower for k in ["console", "sideboard"]):
        layout = {
            "tabletop": {"x": 0.02, "y": 0.02, "w": 0.96, "h": 0.15},
            "main_body_or_drawers": {"x": 0.02, "y": 0.17, "w": 0.96, "h": 0.65},
            "legs_or_plinth": {"x": 0.02, "y": 0.85, "w": 0.96, "h": 0.13},
        }
    else:
        # Generic bounding box
        layout = {
            "main_body": {"x": 0.05, "y": 0.05, "w": 0.90, "h": 0.90},
        }

    return layout


# ---------------------------------------------------------------------------
# SVG component builders
# ---------------------------------------------------------------------------

def _svg_rect(
    x: float, y: float, w: float, h: float,
    fill: str = "none", stroke: str = "#333",
    stroke_width: float = 1.5, rx: float = 0,
    label: str = "",
    dashed: bool = False,
) -> str:
    """Build an SVG rect element."""
    dash = 'stroke-dasharray="4,4"' if dashed else ""
    rx_attr = f'rx="{rx}"' if rx > 0 else ""
    el = (
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}" '
        f'{rx_attr} {dash}/>'
    )
    if label:
        cx = x + w / 2
        cy = y + h / 2
        el += (
            f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-family="sans-serif" '
            f'font-size="10" fill="#555">{label}</text>'
        )
    return el


def _svg_circle(
    cx: float, cy: float, r: float,
    fill: str = "none", stroke: str = "#333",
    stroke_width: float = 1.5, label: str = "",
) -> str:
    """Build an SVG circle element."""
    el = (
        f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r:.1f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>'
    )
    if label:
        el += (
            f'<text x="{cx:.1f}" y="{cy:.1f}" text-anchor="middle" '
            f'dominant-baseline="central" font-family="sans-serif" '
            f'font-size="10" fill="#555">{label}</text>'
        )
    return el


def _svg_centerline(
    x1: float, y1: float, x2: float, y2: float,
) -> str:
    """Build a centerline (dashed blue line)."""
    return (
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="#2563eb" stroke-width="1" stroke-dasharray="6,4"/>'
    )


def _svg_dimension(
    x1: float, y1: float, x2: float, y2: float,
    label: str, offset_y: float = 20,
) -> str:
    """Build a dimension line with arrows and text."""
    mid_x = (x1 + x2) / 2
    dim_y = min(y1, y2) - offset_y
    lines = (
        f'<line x1="{x1:.1f}" y1="{dim_y:.1f}" x2="{x2:.1f}" y2="{dim_y:.1f}" '
        f'stroke="#666" stroke-width="0.8" stroke-dasharray="2,2"/>'
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x1:.1f}" y2="{dim_y:.1f}" '
        f'stroke="#999" stroke-width="0.5"/>'
        f'<line x1="{x2:.1f}" y1="{y2:.1f}" x2="{x2:.1f}" y2="{dim_y:.1f}" '
        f'stroke="#999" stroke-width="0.5"/>'
        f'<text x="{mid_x:.1f}" y="{dim_y - 4:.1f}" text-anchor="middle" '
        f'font-family="sans-serif" font-size="9" fill="#666">{label}</text>'
    )
    return lines


# ---------------------------------------------------------------------------
# Family-specific skeleton builders
# ---------------------------------------------------------------------------

def _build_sofa_skeleton(c: Dict[str, float], vp: Dict[str, float], label: str) -> str:
    """Build sofa skeleton with seat, backrest, armrests, legs."""
    s = vp["scale"]
    ox, oy = vp["ox"], vp["oy"]
    els = ""

    # Backrest (top portion)
    br = c["backrest"]
    els += _svg_rect(ox + br["x"] * vp["real_w"] * s, oy + br["y"] * vp["real_h"] * s,
                     br["w"] * vp["real_w"] * s, br["h"] * vp["real_h"] * s,
                     fill="#f0f0f0", label="Backrest")
    # Seat
    st = c.get("seat_base", c.get("seat", {"x": 0.05, "y": 0.35, "w": 0.90, "h": 0.35}))
    els += _svg_rect(ox + st["x"] * vp["real_w"] * s, oy + st["y"] * vp["real_h"] * s,
                     st["w"] * vp["real_w"] * s, st["h"] * vp["real_h"] * s,
                     fill="#fafafa", label="Seat")
    # Legs
    legs = c.get("legs_or_plinth", {"x": 0.10, "y": 0.82, "w": 0.80, "h": 0.15})
    lx = ox + legs["x"] * vp["real_w"] * s
    ly = oy + legs["y"] * vp["real_h"] * s
    lw = legs["w"] * vp["real_w"] * s
    lh = legs["h"] * vp["real_h"] * s
    # Draw 4 individual leg blocks
    leg_w = lw * 0.08
    gap = (lw - 4 * leg_w) / 5
    for i in range(4):
        lx_i = lx + gap + i * (leg_w + gap)
        els += _svg_rect(lx_i, ly, leg_w, lh, fill="#ddd", label="", stroke="#999")

    # Centerline
    els += _svg_centerline(ox, oy + 0.5 * vp["real_h"] * s,
                           ox + vp["real_w"] * s, oy + 0.5 * vp["real_h"] * s)

    # Title
    els += f'<text x="{ox + vp["real_w"] * s / 2:.1f}" y="{oy - 10:.1f}" text-anchor="middle" font-family="sans-serif" font-size="12" font-weight="bold" fill="#333">{label}</text>'

    return els


def _build_table_skeleton(c: Dict[str, float], vp: Dict[str, float], label: str) -> str:
    """Build table skeleton with top and base/pedestal."""
    s = vp["scale"]
    ox, oy = vp["ox"], vp["oy"]
    els = ""

    # Tabletop
    top = c.get("tabletop", {"x": 0.05, "y": 0.05, "w": 0.90, "h": 0.25})
    els += _svg_rect(ox + top["x"] * vp["real_w"] * s, oy + top["y"] * vp["real_h"] * s,
                     top["w"] * vp["real_w"] * s, top["h"] * vp["real_h"] * s,
                     fill="#f5f5f5", label="Top")

    # Base/legs
    base = c.get("base_support_or_legs", c.get("legs_or_frame", {"x": 0.20, "y": 0.30, "w": 0.60, "h": 0.55}))
    bx = ox + base["x"] * vp["real_w"] * s
    by = oy + base["y"] * vp["real_h"] * s
    bw = base["w"] * vp["real_w"] * s
    bh = base["h"] * vp["real_h"] * s

    # Check if pedestal (single column) or legs
    if bw < vp["real_w"] * s * 0.3:
        # Pedestal — single column
        els += _svg_rect(bx, by, bw, bh, fill="#eee", label="Pedestal")
    else:
        # Four legs
        leg_w = bw * 0.08
        for i in range(4):
            lx_i = bx + i * (bw - leg_w) / 3
            if i == 0:
                lx_i = bx
            elif i == 3:
                lx_i = bx + bw - leg_w
            else:
                lx_i = bx + (bw - leg_w) * i / 3
            els += _svg_rect(lx_i, by, leg_w, bh, fill="#ddd", stroke="#999")

    # Centerline
    els += _svg_centerline(ox + 0.5 * vp["real_w"] * s, oy,
                           ox + 0.5 * vp["real_w"] * s, oy + vp["real_h"] * s)

    els += f'<text x="{ox + vp["real_w"] * s / 2:.1f}" y="{oy - 10:.1f}" text-anchor="middle" font-family="sans-serif" font-size="12" font-weight="bold" fill="#333">{label}</text>'
    return els


def _build_chair_skeleton(c: Dict[str, float], vp: Dict[str, float], label: str) -> str:
    """Build chair skeleton with seat, backrest, legs."""
    s = vp["scale"]
    ox, oy = vp["ox"], vp["oy"]
    els = ""

    # Backrest
    br = c.get("backrest", {"x": 0.10, "y": 0.02, "w": 0.80, "h": 0.38})
    els += _svg_rect(ox + br["x"] * vp["real_w"] * s, oy + br["y"] * vp["real_h"] * s,
                     br["w"] * vp["real_w"] * s, br["h"] * vp["real_h"] * s,
                     fill="#f0f0f0", label="Backrest")
    # Seat
    seat = c.get("seat", {"x": 0.10, "y": 0.40, "w": 0.80, "h": 0.25})
    els += _svg_rect(ox + seat["x"] * vp["real_w"] * s, oy + seat["y"] * vp["real_h"] * s,
                     seat["w"] * vp["real_w"] * s, seat["h"] * vp["real_h"] * s,
                     fill="#fafafa", label="Seat")
    # Legs
    legs = c.get("legs", {"x": 0.15, "y": 0.70, "w": 0.70, "h": 0.28})
    lx = ox + legs["x"] * vp["real_w"] * s
    ly = oy + legs["y"] * vp["real_h"] * s
    lw = legs["w"] * vp["real_w"] * s
    lh = legs["h"] * vp["real_h"] * s
    leg_w = lw * 0.08
    for i in range(4):
        lx_i = lx + i * (lw - leg_w) / 3
        els += _svg_rect(lx_i, ly, leg_w, lh, fill="#ddd", stroke="#999")

    # Centerline
    els += _svg_centerline(ox + 0.5 * vp["real_w"] * s, oy,
                           ox + 0.5 * vp["real_w"] * s, oy + vp["real_h"] * s)
    els += f'<text x="{ox + vp["real_w"] * s / 2:.1f}" y="{oy - 10:.1f}" text-anchor="middle" font-family="sans-serif" font-size="12" font-weight="bold" fill="#333">{label}</text>'
    return els


def _build_pendant_skeleton(c: Dict[str, float], vp: Dict[str, float], label: str) -> str:
    """Build pendant light skeleton with canopy, rod, shade."""
    s = vp["scale"]
    ox, oy = vp["ox"], vp["oy"]
    els = ""

    # Canopy
    canopy = c.get("canopy_or_mount", {"x": 0.30, "y": 0.02, "w": 0.40, "h": 0.08})
    els += _svg_rect(ox + canopy["x"] * vp["real_w"] * s, oy + canopy["y"] * vp["real_h"] * s,
                     canopy["w"] * vp["real_w"] * s, canopy["h"] * vp["real_h"] * s,
                     fill="#ddd", label="Canopy")
    # Rod
    rod = c.get("support_rods_or_blades", {"x": 0.48, "y": 0.10, "w": 0.04, "h": 0.30})
    els += _svg_rect(ox + rod["x"] * vp["real_w"] * s, oy + rod["y"] * vp["real_h"] * s,
                     rod["w"] * vp["real_w"] * s, rod["h"] * vp["real_h"] * s,
                     fill="#ccc", label="")
    # Body/shade
    body = c.get("body", {"x": 0.15, "y": 0.40, "w": 0.70, "h": 0.35})
    els += _svg_rect(ox + body["x"] * vp["real_w"] * s, oy + body["y"] * vp["real_h"] * s,
                     body["w"] * vp["real_w"] * s, body["h"] * vp["real_h"] * s,
                     fill="#ffeaa7", label="Shade")

    # Centerline
    els += _svg_centerline(ox + 0.5 * vp["real_w"] * s, oy,
                           ox + 0.5 * vp["real_w"] * s, oy + vp["real_h"] * s)
    els += f'<text x="{ox + vp["real_w"] * s / 2:.1f}" y="{oy - 10:.1f}" text-anchor="middle" font-family="sans-serif" font-size="12" font-weight="bold" fill="#333">{label}</text>'
    return els


def _build_generic_skeleton(c: Dict[str, float], vp: Dict[str, float], label: str) -> str:
    """Build generic bounding box with component labels."""
    s = vp["scale"]
    ox, oy = vp["ox"], vp["oy"]
    els = ""

    for comp_name, comp in c.items():
        x = ox + comp["x"] * vp["real_w"] * s
        y = oy + comp["y"] * vp["real_h"] * s
        w = comp["w"] * vp["real_w"] * s
        h = comp["h"] * vp["real_h"] * s
        els += _svg_rect(x, y, w, h, fill="#f8f8f8", label=comp_name.replace("_", " ").title())

    # Bounding box (dashed)
    els += _svg_rect(ox, oy, vp["real_w"] * s, vp["real_h"] * s,
                     stroke="#999", stroke_width=1, dashed=True)

    # Centerline
    els += _svg_centerline(ox + 0.5 * vp["real_w"] * s, oy,
                           ox + 0.5 * vp["real_w"] * s, oy + vp["real_h"] * s)
    els += f'<text x="{ox + vp["real_w"] * s / 2:.1f}" y="{oy - 10:.1f}" text-anchor="middle" font-family="sans-serif" font-size="12" font-weight="bold" fill="#333">{label}</text>'
    return els


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------

def generate_skeleton(
    family_name: str,
    dimensions: Optional[Dict[str, float]] = None,
) -> str:
    """Generate a lightweight SVG skeleton for a product family.

    Args:
        family_name: Template family name (e.g. "straight_modern_sofa")
        dimensions: Optional dict with width_cm, depth_cm, height_cm

    Returns:
        Complete SVG string
    """
    dimensions = dimensions or {}
    dna_index = _load_dna_index()
    product_dna = _load_product_dna()

    # Find family in DNA index
    family_entry = dna_index.get(family_name, {})

    # If not found directly, search product_dna for a match
    if not family_entry:
        for handle, entry in product_dna.items():
            if entry.get("template_family", "") == family_name:
                # Build synthetic family entry
                family_entry = {
                    "top_shape": entry.get("top_shape", ""),
                    "base_type": entry.get("base_type", ""),
                    "leg_type": entry.get("leg_type", ""),
                    "symmetry": entry.get("symmetry", "bilateral"),
                    "category_hint": entry.get("category_hint", ""),
                    "component_graph": entry.get("component_list", []),
                }
                break

    # Get bounding ratio
    bounding_ratio = family_entry.get("bounding_ratio", "")
    if not bounding_ratio:
        # Try from product_dna
        for handle, entry in product_dna.items():
            if entry.get("template_family", "") == family_name:
                bounding_ratio = entry.get("bounding_ratio", "1.65:1:0.42")
                break

    if not bounding_ratio:
        bounding_ratio = "1.65:1:0.42"

    # Get component layout
    components = family_entry.get("component_graph", family_entry.get("components", []))
    layout = _get_component_layout(family_name, bounding_ratio, components)

    # Compute viewport coordinates
    w = dimensions.get("width_cm", 100)
    d = dimensions.get("depth_cm", None)
    h = dimensions.get("height_cm", None)
    vp = _dimensions_to_svg_coords(
        _parse_ratio(bounding_ratio),
        width_cm=w,
        depth_cm=d,
        height_cm=h,
    )

    # Determine which archetype builder to use
    fl = family_name.lower()
    label = family_name.replace("_", " ").title()

    if any(k in fl for k in ["sofa", "bench", "sofa_bench"]):
        inner = _build_sofa_skeleton(layout, vp, label)
    elif any(k in fl for k in ["table"]):
        inner = _build_table_skeleton(layout, vp, label)
    elif any(k in fl for k in ["chair", "armchair", "lounge", "stool"]):
        inner = _build_chair_skeleton(layout, vp, label)
    elif any(k in fl for k in ["pendant", "chandelier"]):
        inner = _build_pendant_skeleton(layout, vp, label)
    else:
        inner = _build_generic_skeleton(layout, vp, label)

    # Assemble full SVG
    svg_w = vp["svg_w"]
    svg_h = vp["svg_h"]
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {svg_w} {svg_h}" '
        f'width="100%" height="100%" style="background:#fff;border:1px solid #eee;">\n'
        f'  <rect width="{svg_w}" height="{svg_h}" fill="white"/>\n'
        f'  {inner}\n'
        f'  <!-- Dimensions footer -->\n'
        f'  <text x="{svg_w - 10:.0f}" y="{svg_h - 10:.0f}" text-anchor="end" '
        f'font-family="sans-serif" font-size="8" fill="#999">'
        f'Preview | {family_name} | ratio {bounding_ratio}</text>\n'
        f'</svg>'
    )
    return svg


def generate_skeleton_from_handle(
    handle: str,
    dimensions: Optional[Dict[str, float]] = None,
) -> str:
    """Generate SVG skeleton from a product handle.

    Args:
        handle: Product handle (e.g. "aalto-modern-sofa")
        dimensions: Optional dimensions

    Returns:
        Complete SVG string
    """
    product_dna = _load_product_dna()
    entry = product_dna.get(handle)
    if not entry:
        # Try to find by handle prefix
        for h, e in product_dna.items():
            if h.startswith(handle) or handle.startswith(h):
                entry = e
                break
    if not entry:
        return f'<svg viewBox="0 0 400 200"><text x="200" y="100" text-anchor="middle">No DNA for: {handle}</text></svg>'

    family = entry.get("template_family", entry.get("visual_dna_family", "unknown"))
    return generate_skeleton(family, dimensions)


# ---------------------------------------------------------------------------
# Main / demo
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')  # type: ignore

    print("=== SVG Skeleton Demo ===")

    test_families = [
        ("straight_modern_sofa", {"width_cm": 200, "depth_cm": 85, "height_cm": 80}),
        ("round_pedestal_table", {"width_cm": 120, "depth_cm": 120, "height_cm": 75}),
        ("accent_chair", {"width_cm": 60, "depth_cm": 60, "height_cm": 90}),
        ("single_pendant_light", {"width_cm": 30, "depth_cm": 30, "height_cm": 100}),
        ("natural_stone_slab", {"width_cm": 240, "depth_cm": 120, "height_cm": 2}),
    ]

    for family, dims in test_families:
        svg = generate_skeleton(family, dims)
        print(f"\n--- {family} ({len(svg)} bytes) ---")
        # Show first 200 chars
        print(svg[:200])

    # Test from handle
    print("\n--- From handle: aalto-modern-sofa ---")
    svg = generate_skeleton_from_handle("aalto-modern-sofa", {"width_cm": 200, "depth_cm": 85})
    print(f"SVG OK: {len(svg)} bytes")
