"""
Fixture Image Generator — create synthetic furniture drawings for the golden test set.

Generates clean reference images with dimension labels for each furniture type,
so the accuracy benchmark has actual images to test against (not just spec.json).
Each image mimics a real shop drawing: outlines, leader lines, dimension text.
"""

import json
import math
import os
from pathlib import Path
from typing import Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageOps


FIXTURES_ROOT = Path(__file__).parent.parent.parent.parent / "fixtures"
# Normalize: if the manifest is inside fixtures/ already, use it directly
if not (FIXTURES_ROOT / "manifest.json").exists():
    # Try the project root fixture directory
    alt = Path(__file__).parent.parent.parent / "fixtures"
    if (alt / "manifest.json").exists():
        FIXTURES_ROOT = alt

# Approximate pixel scale: 1cm = 2px for table-sized drawings
PX_PER_CM = 2.0
# Thicker lines for reliable OpenCV detection. Use pure black with no anti-aliasing.
LINE_WIDTH = 3
OUTLINE_FILL = (0, 0, 0)
TEXT_FILL = (0, 0, 0)
# Slightly off-white background for better edge detection contrast versus pure white.
BG_FILL = (248, 248, 248)


def _get_font(size: int = 16) -> ImageFont.FreeTypeFont:
    """Get a reasonable font, falling back to default."""
    font_paths = [
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/Calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _draw_dimension_line(
    draw: ImageDraw.ImageDraw,
    x1: float, y1: float, x2: float, y2: float,
    label: str, font, offset: float = 20,
):
    """Draw a dimension line with arrows and text label."""
    # Extension lines
    if abs(x2 - x1) > abs(y2 - y1):
        # Horizontal dimension
        draw.line([(x1, y1 - offset + 12), (x1, y1)], fill=OUTLINE_FILL, width=max(1, LINE_WIDTH - 1))
        draw.line([(x2, y2 - offset + 12), (x2, y2)], fill=OUTLINE_FILL, width=max(1, LINE_WIDTH - 1))
        draw.line([(x1, y1 - offset), (x2, y2 - offset)], fill=OUTLINE_FILL, width=LINE_WIDTH)
        # Arrows
        draw.polygon([(x1, y1 - offset), (x1 + 6, y1 - offset - 4), (x1 + 6, y1 - offset + 4)], fill=OUTLINE_FILL)
        draw.polygon([(x2, y2 - offset), (x2 - 6, y2 - offset - 4), (x2 - 6, y2 - offset + 4)], fill=OUTLINE_FILL)
        # Text
        mid_x = (x1 + x2) / 2
        mid_y = y1 - offset - 14
    else:
        # Vertical dimension
        draw.line([(x1 - offset + 12, y1), (x1, y1)], fill=OUTLINE_FILL, width=max(1, LINE_WIDTH - 1))
        draw.line([(x2 - offset + 12, y2), (x2, y2)], fill=OUTLINE_FILL, width=max(1, LINE_WIDTH - 1))
        draw.line([(x1 - offset, y1), (x2 - offset, y2)], fill=OUTLINE_FILL, width=LINE_WIDTH)
        draw.polygon([(x1 - offset, y1), (x1 - offset - 4, y1 + 6), (x1 - offset + 4, y1 + 6)], fill=OUTLINE_FILL)
        draw.polygon([(x2 - offset, y2), (x2 - offset - 4, y2 - 6), (x2 - offset + 4, y2 - 6)], fill=OUTLINE_FILL)
        mid_x = x1 - offset - 30
        mid_y = (y1 + y2) / 2

    draw.text((mid_x - 15, mid_y - 8), label, fill=TEXT_FILL, font=font)


def _center_canvas(w_cm: float, h_cm: float, margin_cm: float = 20) -> Tuple[float, float, float, float]:
    """Compute image dimensions with margin."""
    img_w = int((w_cm + 2 * margin_cm) * PX_PER_CM)
    img_h = int((h_cm + 2 * margin_cm) * PX_PER_CM)
    ox = margin_cm * PX_PER_CM
    oy = margin_cm * PX_PER_CM
    return img_w, img_h, ox, oy


def generate_round_table(dia_cm: float, height_cm: float, base_dia_cm: float = None,
                         neck_dia_cm: float = None) -> Image.Image:
    """Generate a round pedestal table drawing with dimension labels."""
    base_dia = base_dia_cm or dia_cm * 0.55
    neck_dia = neck_dia_cm or dia_cm * 0.28

    img_w, img_h, ox, oy = _center_canvas(dia_cm, height_cm, 25)
    img = Image.new("RGB", (int(img_w), int(img_h)), BG_FILL)
    draw = ImageDraw.Draw(img)
    font = _get_font(14)
    font_sm = _get_font(11)

    # Top view (circle)
    top_cx = ox + dia_cm * PX_PER_CM / 2
    top_cy = oy + dia_cm * PX_PER_CM / 2 + 10
    top_r = dia_cm * PX_PER_CM / 2
    draw.ellipse(
        [(top_cx - top_r, top_cy - top_r), (top_cx + top_r, top_cy + top_r)],
        outline="black", width=2,
    )
    draw.text((top_cx - 40, top_cy - top_r - 20), f"TOP VIEW", fill="black", font=font_sm)
    _draw_dimension_line(draw, top_cx - top_r, top_cy + top_r + 5,
                         top_cx + top_r, top_cy + top_r + 5,
                         f"{dia_cm} cm DIA", font_sm, offset=10)

    # Front view offset
    front_ox = ox
    front_oy = oy + dia_cm * PX_PER_CM + 60

    # Tabletop (rectangle from front)
    tt_left = front_ox
    tt_right = front_ox + dia_cm * PX_PER_CM
    tt_top = front_oy
    tt_h = 5 * PX_PER_CM
    tt_bot = tt_top + tt_h
    draw.rectangle([(tt_left, tt_top), (tt_right, tt_bot)], outline="black", width=2)
    # Wood hatch
    for hx in range(int(tt_left) + 5, int(tt_right), 10):
        draw.line([(hx, tt_top + 2), (hx, tt_bot - 2)], fill="gray", width=1)

    # Collar plate
    collar_top = tt_bot
    collar_h = 2 * PX_PER_CM
    collar_bot = collar_top + collar_h
    collar_w = neck_dia * PX_PER_CM + 10
    collar_left = front_ox + (dia_cm * PX_PER_CM - collar_w) / 2
    collar_right = collar_left + collar_w
    draw.rectangle([(collar_left, collar_top), (collar_right, collar_bot)], outline="black", width=2)

    # Pedestal body (trapezoid)
    ped_top = collar_bot
    ped_bot_y = ped_top + (height_cm - 7) * PX_PER_CM
    ped_top_w = neck_dia * PX_PER_CM
    ped_bot_w = base_dia * PX_PER_CM
    ped_top_left = front_ox + (dia_cm * PX_PER_CM - ped_top_w) / 2
    ped_bot_left = front_ox + (dia_cm * PX_PER_CM - ped_bot_w) / 2
    draw.polygon([
        (ped_top_left, ped_top),
        (ped_top_left + ped_top_w, ped_top),
        (ped_bot_left + ped_bot_w, ped_bot_y),
        (ped_bot_left, ped_bot_y),
    ], outline="black", width=2)
    # Hammere texture
    for hy in range(int(ped_top) + 5, int(ped_bot_y), 12):
        pw = ped_top_w + (ped_bot_w - ped_top_w) * (hy - ped_top) / (ped_bot_y - ped_top)
        pl = front_ox + (dia_cm * PX_PER_CM - pw) / 2
        draw.line([(pl + 3, hy), (pl + pw - 3, hy)], fill="gray", width=1)

    # Base plate
    base_top = ped_bot_y
    base_h = 4 * PX_PER_CM
    base_bot = base_top + base_h
    base_w = base_dia * PX_PER_CM
    base_left = front_ox + (dia_cm * PX_PER_CM - base_w) / 2
    draw.rectangle([(base_left, base_top), (base_left + base_w, base_bot)], outline="black", width=2)

    draw.text((front_ox + 5, front_oy - 18), f"FRONT VIEW", fill="black", font=font_sm)

    # Dimension labels
    _draw_dimension_line(draw, tt_left - 15, tt_top, tt_left - 15, base_bot,
                         f"H={int(height_cm)} cm", font_sm, offset=25)

    # Base dia label
    _draw_dimension_line(draw, base_left, base_bot + 5,
                         base_left + base_w, base_bot + 5,
                         f"BASE {int(base_dia)} cm DIA", font_sm, offset=10)

    return img


def generate_rectangular_table(w_cm: float, d_cm: float, h_cm: float,
                                leg_t_cm: float = 6.0) -> Image.Image:
    """Generate a rectangular table drawing."""
    img_w, img_h, ox, oy = _center_canvas(w_cm, h_cm, 30)
    img = Image.new("RGB", (int(img_w), int(img_h)), BG_FILL)
    draw = ImageDraw.Draw(img)
    font = _get_font(14)
    font_sm = _get_font(11)

    # Top view
    top_x = ox
    top_y = oy
    top_w = w_cm * PX_PER_CM
    top_d = d_cm * PX_PER_CM
    draw.rectangle([(top_x, top_y), (top_x + top_w, top_y + top_d)], outline="black", width=2)
    draw.text((top_x + 5, top_y - 18), "TOP VIEW", fill="black", font=font_sm)
    _draw_dimension_line(draw, top_x, top_y + top_d + 5, top_x + top_w, top_y + top_d + 5,
                         f"W={int(w_cm)} cm", font_sm, offset=10)
    _draw_dimension_line(draw, top_x + top_w + 5, top_y, top_x + top_w + 5, top_y + top_d,
                         f"D={int(d_cm)} cm", font_sm, offset=15)

    # Front view
    fv_oy = oy + d_cm * PX_PER_CM + 40
    tt_h = 4 * PX_PER_CM
    leg_w = leg_t_cm * PX_PER_CM
    leg_h = (h_cm - 4) * PX_PER_CM
    inset = 8 * PX_PER_CM

    # Tabletop front
    draw.rectangle([(ox, fv_oy), (ox + top_w, fv_oy + tt_h)], outline="black", width=2)
    # Wood hatch
    for hx in range(int(ox) + 5, int(ox + top_w), 10):
        draw.line([(hx, fv_oy + 2), (hx, fv_oy + tt_h - 2)], fill="gray", width=1)

    # Legs
    leg_top = fv_oy + tt_h
    leg_bot = leg_top + leg_h
    draw.rectangle([(ox + inset, leg_top), (ox + inset + leg_w, leg_bot)], outline="black", width=2)
    draw.rectangle([(ox + top_w - inset - leg_w, leg_top), (ox + top_w - inset, leg_bot)], outline="black", width=2)

    # Stretcher
    str_y = leg_top + leg_h * 0.55
    str_h = 3 * PX_PER_CM
    draw.rectangle([(ox + inset + leg_w, str_y), (ox + top_w - inset - leg_w, str_y + str_h)], outline="black", width=2)

    draw.text((ox + 5, fv_oy - 18), "FRONT VIEW", fill="black", font=font_sm)
    _draw_dimension_line(draw, ox + inset - 5, leg_top, ox + inset - 5, leg_bot,
                         f"H={int(h_cm)} cm", font_sm, offset=20)

    return img


def generate_sofa(w_cm: float, d_cm: float, h_cm: float, seat_h_cm: float = 45) -> Image.Image:
    """Generate a sofa drawing."""
    img_w, img_h, ox, oy = _center_canvas(w_cm, h_cm, 30)
    img = Image.new("RGB", (int(img_w), int(img_h)), BG_FILL)
    draw = ImageDraw.Draw(img)
    font_sm = _get_font(11)

    pw = w_cm * PX_PER_CM
    ph = h_cm * PX_PER_CM

    # Backrest
    back_h = (h_cm - seat_h_cm) * PX_PER_CM
    draw.rectangle([(ox, oy), (ox + pw, oy + back_h)], outline="black", width=2)
    # Upholstery texture (cross-hatch)
    for tx in range(int(ox) + 5, int(ox + pw), 15):
        draw.line([(tx, oy + 2), (tx + 5, oy + back_h - 2)], fill="gray", width=1)

    # Seat
    seat_top = oy + back_h
    seat_h = seat_h_cm * PX_PER_CM
    draw.rectangle([(ox, seat_top), (ox + pw, seat_top + seat_h)], outline="black", width=2)

    # Armrests
    arm_w = 12 * PX_PER_CM
    arm_h = (h_cm - 10) * PX_PER_CM
    draw.rectangle([(ox, oy + 10), (ox + arm_w, oy + arm_h)], outline="black", width=2)
    draw.rectangle([(ox + pw - arm_w, oy + 10), (ox + pw, oy + arm_h)], outline="black", width=2)

    # Legs
    leg_h = 8 * PX_PER_CM
    leg_w = 5 * PX_PER_CM
    for lx in [ox + arm_w + 10, ox + pw - arm_w - leg_w - 10]:
        draw.rectangle([(lx, oy + ph - leg_h), (lx + leg_w, oy + ph)], outline="black", width=2)

    draw.text((ox + 5, oy - 18), "FRONT VIEW", fill="black", font=font_sm)
    _draw_dimension_line(draw, ox - 15, oy, ox - 15, oy + ph,
                         f"H={int(h_cm)} cm", font_sm, offset=20)
    _draw_dimension_line(draw, ox, oy + ph + 5, ox + pw, oy + ph + 5,
                         f"W={int(w_cm)} cm", font_sm, offset=10)

    return img


def generate_cabinet(w_cm: float, d_cm: float, h_cm: float) -> Image.Image:
    """Generate a cabinet drawing."""
    img_w, img_h, ox, oy = _center_canvas(w_cm, h_cm, 30)
    img = Image.new("RGB", (int(img_w), int(img_h)), BG_FILL)
    draw = ImageDraw.Draw(img)
    font_sm = _get_font(11)

    pw = w_cm * PX_PER_CM
    ph = h_cm * PX_PER_CM

    # Carcass
    draw.rectangle([(ox, oy), (ox + pw, oy + ph)], outline="black", width=2)

    # Doors (2 doors)
    door_w = (pw - 6) / 2
    draw.rectangle([(ox + 3, oy + 3), (ox + 3 + door_w, oy + ph * 0.65)], outline="black", width=1)
    draw.rectangle([(ox + pw - 3 - door_w, oy + 3), (ox + pw - 3, oy + ph * 0.65)], outline="black", width=1)
    # Door knobs
    for dx in [ox + door_w - 8, ox + pw - door_w + 8]:
        draw.ellipse([(dx - 2, oy + ph * 0.32 - 2), (dx + 2, oy + ph * 0.32 + 2)], fill="black")

    # Drawers
    draw_y = oy + ph * 0.65
    draw_h = ph * 0.32 / 3
    for i in range(3):
        dy = draw_y + i * draw_h
        draw.rectangle([(ox + 3, dy + 2), (ox + pw - 3, dy + draw_h - 2)], outline="black", width=1)
        # Knob
        draw.ellipse([(ox + pw / 2 - 2, dy + draw_h / 2 - 2), (ox + pw / 2 + 2, dy + draw_h / 2 + 2)], fill="black")

    # Base
    base_h = 8 * PX_PER_CM
    draw.rectangle([(ox - 0, oy + ph), (ox + pw, oy + ph + base_h)], outline="black", width=2)

    draw.text((ox + 5, oy - 18), "FRONT VIEW", fill="black", font=font_sm)
    _draw_dimension_line(draw, ox - 15, oy, ox - 15, oy + ph,
                         f"H={int(h_cm)} cm", font_sm, offset=20)
    _draw_dimension_line(draw, ox, oy + ph + base_h + 5, ox + pw, oy + ph + base_h + 5,
                         f"W={int(w_cm)} cm", font_sm, offset=12)

    return img


def generate_dining_chair(w_cm: float, h_cm: float) -> Image.Image:
    """Generate a dining chair drawing."""
    img_w, img_h, ox, oy = _center_canvas(w_cm, h_cm, 30)
    img = Image.new("RGB", (int(img_w), int(img_h)), BG_FILL)
    draw = ImageDraw.Draw(img)
    font_sm = _get_font(11)

    pw = w_cm * PX_PER_CM
    ph = h_cm * PX_PER_CM
    seat_h = 45 * PX_PER_CM
    back_h = (h_cm - 45) * PX_PER_CM

    # Backrest
    draw.rectangle([(ox + 8, oy), (ox + pw - 8, oy + back_h)], outline="black", width=2)
    # Slats
    for sx in range(int(ox) + 15, int(ox + pw) - 15, 12):
        draw.line([(sx, oy + 5), (sx, oy + back_h - 5)], fill="gray", width=1)

    # Seat
    seat_y = oy + back_h
    draw.rectangle([(ox, seat_y), (ox + pw, seat_y + seat_h)], outline="black", width=2)
    # Upholstery
    for ux in range(int(ox) + 5, int(ox + pw), 10):
        draw.line([(ux, seat_y + 3), (ux, seat_y + seat_h - 3)], fill="gray", width=1)

    # Legs
    leg_w = 4 * PX_PER_CM
    leg_top = seat_y + seat_h
    leg_bot = oy + ph
    draw.rectangle([(ox + 6, leg_top), (ox + 6 + leg_w, leg_bot)], outline="black", width=2)
    draw.rectangle([(ox + pw - 6 - leg_w, leg_top), (ox + pw - 6, leg_bot)], outline="black", width=2)

    draw.text((ox + 5, oy - 18), "FRONT VIEW", fill="black", font=font_sm)
    _draw_dimension_line(draw, ox - 15, oy, ox - 15, oy + ph,
                         f"H={int(h_cm)} cm", font_sm, offset=25)
    _draw_dimension_line(draw, ox, oy + ph + 5, ox + pw, oy + ph + 5,
                         f"W={int(w_cm)} cm", font_sm, offset=10)

    return img


def generate_bed_headboard(w_cm: float, h_cm: float) -> Image.Image:
    """Generate a bed headboard drawing."""
    img_w, img_h, ox, oy = _center_canvas(w_cm, h_cm, 30)
    img = Image.new("RGB", (int(img_w), int(img_h)), BG_FILL)
    draw = ImageDraw.Draw(img)
    font_sm = _get_font(11)

    pw = w_cm * PX_PER_CM
    ph = h_cm * PX_PER_CM

    # Headboard panel
    draw.rectangle([(ox, oy + 20), (ox + pw, oy + ph)], outline="black", width=2)
    # Upholstery tufting
    for ux in range(int(ox) + 10, int(ox + pw), 20):
        for uy in range(int(oy) + 30, int(oy + ph) - 4, 20):
            draw.ellipse([(ux - 2, uy - 2), (ux + 2, uy + 2)], outline="gray", width=1)

    # Posts
    post_w = 8 * PX_PER_CM
    draw.rectangle([(ox, oy), (ox + post_w, oy + ph + 30)], outline="black", width=2)
    draw.rectangle([(ox + pw - post_w, oy), (ox + pw, oy + ph + 30)], outline="black", width=2)

    draw.text((ox + 5, oy - 18), "FRONT VIEW", fill="black", font=font_sm)
    _draw_dimension_line(draw, ox - 15, oy, ox - 15, oy + ph,
                         f"H={int(h_cm)} cm", font_sm, offset=25)
    _draw_dimension_line(draw, ox, oy + ph + 35, ox + pw, oy + ph + 35,
                         f"W={int(w_cm)} cm", font_sm, offset=12)

    return img


# Map furniture types to generators
GENERATORS = {
    "round_pedestal_table": generate_round_table,
    "rectangular_table": generate_rectangular_table,
    "sofa": generate_sofa,
    "cabinet": generate_cabinet,
    "dining_chair": generate_dining_chair,
    "bed_headboard": generate_bed_headboard,
}


def generate_fixture_images(manifest_path: Optional[Path] = None) -> Dict[str, str]:
    """Generate reference images for all fixtures in the manifest.

    Returns dict of {fixture_name: image_path} for all generated images.
    """
    if manifest_path is None:
        manifest_path = FIXTURES_ROOT / "manifest.json"

    if not manifest_path.exists():
        print(f"[FixtureGen] Manifest not found: {manifest_path}")
        return {}

    with open(manifest_path) as f:
        manifest = json.load(f)

    generated = {}

    for fixture in manifest.get("fixtures", []):
        name = fixture["name"]
        ftype = fixture["type"]
        # Manifest paths are relative to project root, may include "fixtures/" prefix
        raw_spec_path = fixture.get("path", f"{name}/spec.json")
        raw_ref_path = fixture.get("reference_image", f"{name}/reference.jpg")
        # Strip "fixtures/" prefix if present since FIXTURES_ROOT already points there
        spec_rel = raw_spec_path.replace("fixtures/", "").replace("fixtures\\", "")
        ref_rel = raw_ref_path.replace("fixtures/", "").replace("fixtures\\", "")
        spec_path = FIXTURES_ROOT / spec_rel
        ref_path = FIXTURES_ROOT / ref_rel

        if not spec_path.exists():
            print(f"[FixtureGen] Spec not found for {name}: {spec_path}")
            continue

        with open(spec_path) as f:
            spec = json.load(f)

        # Ensure parent directory exists
        ref_path.parent.mkdir(parents=True, exist_ok=True)

        # Get parameters from spec
        params = spec.get("parameters", {})
        dims = {d["tag"]: d["value_cm"] for d in spec.get("dimensions", [])}

        generator = GENERATORS.get(ftype)
        if not generator:
            print(f"[FixtureGen] No generator for type: {ftype}")
            continue

        try:
            if ftype == "round_pedestal_table":
                img = generator(
                    dia_cm=params.get("top_diameter_cm") or params.get("dia", dims.get("top_dia", 100)),
                    height_cm=params.get("height_cm") or params.get("h", dims.get("height", 75)),
                    base_dia_cm=dims.get("base_dia"),
                    neck_dia_cm=dims.get("neck_dia"),
                )
            elif ftype == "rectangular_table":
                img = generator(
                    w_cm=params.get("width_cm") or params.get("w", dims.get("width", 200)),
                    d_cm=params.get("depth_cm") or params.get("d", dims.get("depth", 100)),
                    h_cm=params.get("height_cm") or params.get("h", dims.get("height", 75)),
                    leg_t_cm=dims.get("leg_thickness", 6),
                )
            elif ftype == "sofa":
                img = generator(
                    w_cm=params.get("width_cm") or params.get("w", dims.get("width", 105)),
                    d_cm=params.get("depth_cm") or params.get("d", dims.get("depth", 92)),
                    h_cm=params.get("height_cm") or params.get("h", dims.get("height", 87)),
                    seat_h_cm=params.get("seat_height_cm") or params.get("sh", dims.get("seat_height", 45)),
                )
            elif ftype == "cabinet":
                img = generator(
                    w_cm=params.get("width_cm") or params.get("w", dims.get("width", 100)),
                    d_cm=params.get("depth_cm") or params.get("d", dims.get("depth", 50)),
                    h_cm=params.get("height_cm") or params.get("h", dims.get("height", 180)),
                )
            elif ftype == "dining_chair":
                img = generator(
                    w_cm=params.get("width_cm") or params.get("w", dims.get("width", 50)),
                    h_cm=params.get("height_cm") or params.get("h", dims.get("height", 85)),
                )
            elif ftype == "bed_headboard":
                img = generator(
                    w_cm=params.get("width_cm") or params.get("w", dims.get("width", 180)),
                    h_cm=params.get("height_cm") or params.get("h", dims.get("height", 120)),
                )
            else:
                continue

            # Post-process: sharpen edges for OpenCV detection and reduce JPEG
            # compression artifacts. PIL anti-aliased lines can confuse
            # Canny/Hough detectors, so we sharpen aggressively.
            from PIL import ImageFilter, ImageEnhance
            enh = ImageEnhance.Sharpness(img)
            sharpened = enh.enhance(3.0)
            # Increase contrast between lines and background
            cont = ImageEnhance.Contrast(sharpened)
            sharpened = cont.enhance(1.5)
            sharpened.save(str(ref_path), "JPEG", quality=92)
            generated[name] = str(ref_path)
            print(f"[FixtureGen] Generated: {ref_path} ({ftype})")

        except Exception as e:
            print(f"[FixtureGen] Failed to generate {name}: {e}")

    print(f"[FixtureGen] Done. Generated {len(generated)} reference images.")
    return generated


def generate_ground_truth_dxf(out_base: Optional[Path] = None) -> Dict[str, str]:
    """Generate ground-truth expected DXF files from ALL fixture spec dirs.
    Scans subdirectories containing spec.json (same as load_fixtures()).
    Saves `expected.dxf` + `ground_truth.json` in each fixture directory."""

    if out_base is None:
        out_base = FIXTURES_ROOT

    if not out_base.exists():
        print(f"[FixtureGT] Fixtures directory not found: {out_base}")
        return {}

    generated = {}

    for subdir in out_base.iterdir():
        if not subdir.is_dir():
            continue

        spec_path = subdir / "spec.json"
        if not spec_path.exists():
            continue

        name = subdir.name

        with open(spec_path) as f:
            spec = json.load(f)

        ftype = spec.get("furniture_type") or spec.get("type", "")
        if not ftype:
            print(f"[FixtureGT] No furniture_type in {name}/spec.json")
            continue

        params = spec.get("parameters", {})
        dims = {d["tag"]: d["value_cm"] for d in spec.get("dimensions", [])}

        # Build kwargs for the DXF builder
        kwargs = {}
        if ftype == "round_pedestal_table":
            kwargs['top_dia_cm'] = params.get("top_diameter_cm") or params.get("dia", dims.get("top_dia", 80))
            kwargs['height_cm'] = params.get("height_cm") or params.get("h", dims.get("height", 70))
            kwargs['base_dia_cm'] = params.get("base_dia_cm") or dims.get("base_dia", kwargs['top_dia_cm'] * 0.55)
            kwargs['neck_dia_cm'] = params.get("neck_dia_cm") or dims.get("neck_dia", kwargs['top_dia_cm'] * 0.28)
            kwargs['top_thick_cm'] = params.get("top_thickness_cm") or dims.get("thickness", 4.0)
            kwargs['collar_dia_cm'] = kwargs['top_dia_cm'] * 0.625
        elif ftype == "rectangular_table":
            kwargs['width_cm'] = params.get("width_cm") or params.get("w", dims.get("width", 120))
            kwargs['depth_cm'] = params.get("depth_cm") or params.get("d", dims.get("depth", 80))
            kwargs['height_cm'] = params.get("height_cm") or params.get("h", dims.get("height", 70))
            kwargs['leg_thickness_cm'] = params.get("leg_thickness_cm") or dims.get("leg_thickness", 6.0)
        elif ftype == "sofa":
            kwargs['width_cm'] = params.get("width_cm") or params.get("w", dims.get("width", 200))
            kwargs['depth_cm'] = params.get("depth_cm") or params.get("d", dims.get("depth", 80))
            kwargs['height_cm'] = params.get("height_cm") or params.get("h", dims.get("height", 85))
            kwargs['seat_height_cm'] = params.get("seat_height_cm") or params.get("sh", dims.get("seat_height", 45))
        elif ftype == "cabinet":
            kwargs['width_cm'] = params.get("width_cm") or params.get("w", dims.get("width", 100))
            kwargs['depth_cm'] = params.get("depth_cm") or params.get("d", dims.get("depth", 50))
            kwargs['height_cm'] = params.get("height_cm") or params.get("h", dims.get("height", 180))
        elif ftype in ("dining_chair", "chair"):
            kwargs['width_cm'] = params.get("width_cm") or params.get("w", dims.get("width", 50))
            kwargs['height_cm'] = params.get("height_cm") or params.get("h", dims.get("height", 85))
        elif ftype == "bed_headboard":
            kwargs['width_cm'] = params.get("width_cm") or params.get("w", dims.get("width", 180))
            kwargs['height_cm'] = params.get("height_cm") or params.get("h", dims.get("height", 120))
        else:
            print(f"[FixtureGT] No DXF builder for type '{ftype}'")
            continue

        # Generate the ground-truth DXF
        expected_dxf = subdir / "expected.dxf"

        try:
            if ftype == "round_pedestal_table":
                from app.backend.dxf_exporter import save_round_pedestal_table
                save_round_pedestal_table(str(expected_dxf), **kwargs)
            elif ftype == "rectangular_table":
                from app.backend.dxf_exporter import save_rectangular_table
                save_rectangular_table(str(expected_dxf), **kwargs)
            elif ftype == "sofa":
                from app.backend.dxf_exporter import save_sofa
                save_sofa(str(expected_dxf), **kwargs)
            elif ftype == "cabinet":
                from app.backend.dxf_exporter import save_cabinet
                save_cabinet(str(expected_dxf), **kwargs)
            elif ftype in ("dining_chair", "chair"):
                from app.backend.dxf_exporter import save_dining_chair
                save_dining_chair(str(expected_dxf), **kwargs)
            elif ftype == "bed_headboard":
                from app.backend.dxf_exporter import save_bed_headboard
                save_bed_headboard(str(expected_dxf), **kwargs)
            else:
                continue

            # Also save the ground-truth metadata as JSON
            gt_path = subdir / "ground_truth.json"
            with open(gt_path, 'w') as f:
                json.dump({
                    "name": name,
                    "furniture_type": ftype,
                    "parameters": kwargs,
                    "expected_dxf": str(expected_dxf),
                    "dimensions": [
                        {"tag": d["tag"], "value_cm": d["value_cm"],
                         "tolerance_pct": d.get("tolerance_pct", 10)}
                        for d in spec.get("dimensions", [])
                    ],
                }, f, indent=2)

            generated[name] = str(expected_dxf)
            print(f"[FixtureGT] Generated expected DXF: {expected_dxf} ({ftype})")

        except Exception as e:
            print(f"[FixtureGT] Failed to generate DXF for {name}: {e}")
            import traceback
            traceback.print_exc()

    print(f"[FixtureGT] Done. Generated {len(generated)} ground-truth DXF files.")
    return generated


# Allow running as script
if __name__ == "__main__":
    generate_fixture_images()
    # Uncomment to also generate ground-truth DXF files:
    # generate_ground_truth_dxf()
