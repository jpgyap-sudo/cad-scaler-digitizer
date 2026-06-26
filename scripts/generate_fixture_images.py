"""
Generate realistic shop-drawing PNG images for benchmark fixtures.

Reads each fixture's spec.json, calls the appropriate DXF exporter with
the actual dimensions, then renders the DXF to a high-quality PNG using
ezdxf + matplotlib (the same pipeline as the /api/preview endpoint).

Output: fixtures/<name>/reference.jpg  (overwrites any placeholder).
"""

import json
import os
import sys
import tempfile
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend-python"))

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import ezdxf
from ezdxf.addons.drawing import RenderContext, Frontend
from ezdxf.addons.drawing.matplotlib import MatplotlibBackend

from app.backend.dxf_exporter import (
    save_round_pedestal_table,
    save_rectangular_table,
    save_cabinet,
    save_sofa,
    save_coffee_table,
    save_dining_chair,
    save_wardrobe,
    save_reception_counter,
    save_bed_headboard,
)

FIXTURES_DIR = Path(__file__).parent.parent / "fixtures"

# ── Dimension key → exporter parameter mapping ──────────────────────────

EXPORTER_MAP = {
    "round_pedestal_table": {
        "func": save_round_pedestal_table,
        "param_map": {
            "top_dia": "top_dia_cm",
            "height": "height_cm",
            "base_dia": "base_dia_cm",
            "neck_dia": "neck_dia_cm",
            "thickness": "top_thick_cm",
            "top_thickness": "top_thick_cm",
        },
        "defaults": {"top_dia_cm": 80, "height_cm": 70, "base_dia_cm": 44, "neck_dia_cm": 22, "top_thick_cm": 4},
    },
    "rectangular_table": {
        "func": save_rectangular_table,
        "param_map": {
            "width": "width_cm",
            "depth": "depth_cm",
            "height": "height_cm",
            "leg_thickness": "leg_thickness_cm",
        },
        "defaults": {"width_cm": 120, "depth_cm": 80, "height_cm": 70, "leg_thickness_cm": 6},
    },
    "sofa": {
        "func": save_sofa,
        "param_map": {
            "width": "width_cm",
            "depth": "depth_cm",
            "height": "height_cm",
            "seat_height": "seat_height_cm",
        },
        "defaults": {"width_cm": 200, "depth_cm": 80, "height_cm": 85, "seat_height_cm": 45},
    },
    "cabinet": {
        "func": save_cabinet,
        "param_map": {"width": "width_cm", "depth": "depth_cm", "height": "height_cm"},
        "defaults": {"width_cm": 100, "depth_cm": 50, "height_cm": 180},
    },
    "dining_chair": {
        "func": save_dining_chair,
        "param_map": {
            "width": "width_cm",
            "depth": "depth_cm",
            "height": "height_cm",
            "seat_height": "seat_height_cm",
        },
        "defaults": {"width_cm": 45, "depth_cm": 45, "height_cm": 90, "seat_height_cm": 45},
    },
    "chair": {  # alias for dining_chair
        "func": save_dining_chair,
        "param_map": {
            "width": "width_cm",
            "depth": "depth_cm",
            "height": "height_cm",
            "seat_height": "seat_height_cm",
        },
        "defaults": {"width_cm": 45, "depth_cm": 45, "height_cm": 90, "seat_height_cm": 45},
    },
    "coffee_table": {
        "func": save_coffee_table,
        "param_map": {"width": "width_cm", "depth": "depth_cm", "height": "height_cm"},
        "defaults": {"width_cm": 100, "depth_cm": 60, "height_cm": 45},
    },
    "wardrobe": {
        "func": save_wardrobe,
        "param_map": {"width": "width_cm", "depth": "depth_cm", "height": "height_cm"},
        "defaults": {"width_cm": 120, "depth_cm": 60, "height_cm": 200},
    },
    "reception_counter": {
        "func": save_reception_counter,
        "param_map": {"width": "width_cm", "depth": "depth_cm", "height": "height_cm"},
        "defaults": {"width_cm": 180, "depth_cm": 80, "height_cm": 110},
    },
    "bed_headboard": {
        "func": save_bed_headboard,
        "param_map": {"width": "width_cm", "height": "height_cm"},
        "defaults": {"width_cm": 160, "height_cm": 120},
    },
}


def dxf_to_png(dxf_path: Path, png_path: Path, dpi: int = 300) -> bool:
    """Render a DXF file to a high-res PNG image using ezdxf + matplotlib.
    
    Uses 300 DPI to make dimension text large enough for Tesseract OCR.
    Also saves the DXF alongside the image for DXF-based dimension extraction.
    """
    try:
        doc = ezdxf.readfile(str(dxf_path))
        fig = plt.figure(figsize=(20, 15), dpi=dpi)
        ax = fig.add_axes([0.02, 0.02, 0.96, 0.96])
        ctx = RenderContext(doc)
        backend = MatplotlibBackend(ax)
        Frontend(ctx, backend).draw_layout(doc.modelspace(), finalize=True)
        ax.set_aspect("equal")
        ax.axis("off")
        fig.savefig(str(png_path), dpi=dpi, facecolor="white", bbox_inches="tight", pad_inches=0.2)
        plt.close(fig)
        return True
    except Exception as e:
        print(f"  RENDER FAILED: {e}")
        return False


def build_params(spec: dict, mapping: dict, defaults: dict) -> dict:
    """Extract exporter keyword arguments from fixture dimensions."""
    kwargs = dict(defaults)
    dims = spec.get("dimensions", [])
    params = spec.get("parameters", {})

    # Try dimensions array first
    for d in dims:
        tag = d.get("tag", "").lower().strip()
        val = d.get("value_cm")
        if tag in mapping and val is not None:
            kwargs[mapping[tag]] = float(val)

    # Fallback to parameters dict
    for param_key, param_val in params.items():
        # e.g. "width_cm" -> "width"
        short = param_key.replace("_cm", "")
        if short in mapping:
            kwargs[mapping[short]] = float(param_val)

    return kwargs


def generate_all():
    """Generate reference images for all fixtures with spec.json."""
    if not FIXTURES_DIR.exists():
        print(f"Fixtures dir not found: {FIXTURES_DIR}")
        return

    generated = 0
    failed = 0

    for subdir in sorted(FIXTURES_DIR.iterdir()):
        if not subdir.is_dir():
            continue

        spec_path = subdir / "spec.json"
        if not spec_path.exists():
            continue

        with open(spec_path) as f:
            spec = json.load(f)

        ftype = spec.get("furniture_type", spec.get("type", ""))
        if not ftype:
            print(f"  SKIP {subdir.name} — no furniture_type")
            continue

        exporter_cfg = EXPORTER_MAP.get(ftype)
        if not exporter_cfg:
            print(f"  SKIP {subdir.name} — no exporter for type '{ftype}'")
            continue

        params = build_params(spec, exporter_cfg["param_map"], exporter_cfg["defaults"])

        with tempfile.TemporaryDirectory() as tmp:
            dxf_path = Path(tmp) / "output.dxf"
            png_path = Path(tmp) / "output.png"

            try:
                exporter_cfg["func"](str(dxf_path), **params)
            except Exception as e:
                print(f"  FAIL {subdir.name} — DXF export error: {e}")
                failed += 1
                continue

            if not dxf_path.exists():
                print(f"  FAIL {subdir.name} — DXF not generated")
                failed += 1
                continue

            if dxf_to_png(dxf_path, png_path):
                ref_jpg = subdir / "reference.jpg"
                ref_dxf = subdir / "reference.dxf"
                # Save DXF alongside image for dimension extraction
                import shutil
                shutil.copy2(str(dxf_path), str(ref_dxf))
                # Convert PNG to JPEG (matplotlib saves as PNG)
                from PIL import Image
                img = Image.open(png_path)
                img = img.convert("RGB")
                img.save(str(ref_jpg), "JPEG", quality=92)
                file_size_kb = ref_jpg.stat().st_size / 1024
                print(f"  OK  {subdir.name:35s} ({ftype:25s}) -> {file_size_kb:.0f} KB")
                generated += 1
            else:
                failed += 1

    print(f"\nDone: {generated} generated, {failed} failed")


if __name__ == "__main__":
    generate_all()
