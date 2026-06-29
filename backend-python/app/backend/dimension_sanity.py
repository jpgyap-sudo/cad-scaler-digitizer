"""
dimension_sanity.py
───────────────────
Cross-checks AI-extracted furniture dimensions against known furniture standards.
Catches unit errors (mm/cm confusion), impossible values, and swapped dimensions.
Returns corrected dimensions + a list of human-readable flags.

Usage:
    from app.backend.dimension_sanity import check_and_correct_dimensions
    corrected, flags = check_and_correct_dimensions("rectangular_table", dims)
"""
from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple

_STANDARDS_PATH = Path(__file__).parent.parent.parent / ".agents" / "skills" / "dimension-sanity" / "resources" / "dimension_standards.json"
_standards_cache: dict | None = None


def _load_standards() -> dict:
    global _standards_cache
    if _standards_cache is None:
        # Try dynamic resolution: first check relative to this file, then project root
        paths_to_try = [
            _STANDARDS_PATH,
            Path(__file__).parent.parent.parent.parent / ".agents" / "skills" / "dimension-sanity" / "resources" / "dimension_standards.json",
            Path(os.getcwd()) / ".agents" / "skills" / "dimension-sanity" / "resources" / "dimension_standards.json"
        ]
        for path in paths_to_try:
            if path.exists():
                try:
                    with open(path, encoding="utf-8") as f:
                        _standards_cache = json.load(f)
                        print(f"[DimensionSanity] Loaded standards from {path}")
                        break
                except Exception as e:
                    print(f"[DimensionSanity] Failed to load from {path}: {e}")
        if _standards_cache is None:
            print("[DimensionSanity] WARNING: standards file not found. Fallback to empty defaults.")
            _standards_cache = {"furniture_types": {}}
    return _standards_cache


def check_and_correct_dimensions(
    furniture_type: str,
    dims: Dict[str, float],
) -> Tuple[Dict[str, float], List[str]]:
    """
    Validate and auto-correct furniture dimensions.

    Args:
        furniture_type: e.g. 'rectangular_table'
        dims: dict of {param_name: value_cm}

    Returns:
        (corrected_dims, flags) where flags is a list of human-readable notes
    """
    standards = _load_standards()
    ftype_std = standards.get("furniture_types", {}).get(furniture_type, {})
    ranges = ftype_std.get("ranges", {})
    rules = ftype_std.get("rules", [])

    corrected = dict(dims)
    flags: List[str] = []

    # ── Pass 1: mm → cm auto-correction ───────────────────────────────────────
    for param, spec in ranges.items():
        if param not in corrected:
            continue
        val = corrected[param]
        if val is None:
            continue
        try:
            val = float(val)
        except (TypeError, ValueError):
            continue

        mm_threshold = spec.get("mm_threshold", spec["max"] * 10)
        if val > mm_threshold:
            corrected_val = round(val / 10, 1)
            flags.append(
                f"{param}: {val} looks like mm input — auto-divided by 10 → {corrected_val} cm"
            )
            corrected[param] = corrected_val
            val = corrected_val

        # Range flag (don't auto-fix, just warn)
        if val < spec["min"] or val > spec["max"]:
            flags.append(
                f"{param}: {val} cm is outside expected range [{spec['min']}–{spec['max']}]"
            )

    # ── Pass 2: Structural rules ───────────────────────────────────────────────
    for rule in rules:
        rule_id = rule.get("id", "")
        auto_fix = rule.get("auto_fix")

        if rule_id == "rect_width_gt_depth" or rule_id == "oval_length_gt_depth":
            w = corrected.get("width_cm") or corrected.get("length_cm") or corrected.get("width")
            d = corrected.get("depth_cm") or corrected.get("depth")
            if w and d and float(w) < float(d):
                if auto_fix == "swap":
                    # Swap them
                    if "width_cm" in corrected:
                        corrected["width_cm"], corrected["depth_cm"] = float(d), float(w)
                    if "length_cm" in corrected:
                        corrected["length_cm"] = float(d)
                    if "width" in corrected:
                        corrected["width"], corrected["depth"] = float(d), float(w)
                    flags.append(f"width/length and depth swapped — width was < depth ({w} < {d})")

        elif rule_id == "pedestal_base_lt_top" or rule_id == "collar_lt_top":
            top = corrected.get("top_dia_cm") or corrected.get("top_dia")
            base_key = "base_dia_cm" if "base" in rule_id else "collar_dia_cm"
            if base_key not in corrected and base_key.replace("_cm", "") in corrected:
                base_key = base_key.replace("_cm", "")
            
            base = corrected.get(base_key)
            if top and base and float(base) > float(top):
                if auto_fix == "cap_at_top":
                    capped = round(float(top) * 0.85, 1)
                    corrected[base_key] = capped
                    flags.append(f"{base_key}: {base} > top_dia {top} — capped at 85% → {capped}")

        elif rule_id == "large_gt_small_ped":
            lg = corrected.get("large_ped_dia_cm") or corrected.get("large_ped_dia")
            sm = corrected.get("small_ped_dia_cm") or corrected.get("small_ped_dia")
            if lg and sm and float(lg) < float(sm):
                lg_key = "large_ped_dia_cm" if "large_ped_dia_cm" in corrected else "large_ped_dia"
                sm_key = "small_ped_dia_cm" if "small_ped_dia_cm" in corrected else "small_ped_dia"
                corrected[lg_key], corrected[sm_key] = float(sm), float(lg)
                flags.append(f"large_ped_dia and small_ped_dia swapped — large was < small ({lg} < {sm})")

    return corrected, flags


def get_typical_dimensions(furniture_type: str) -> Dict[str, float]:
    """Return typical/default dimension values for a furniture type."""
    standards = _load_standards()
    ftype_std = standards.get("furniture_types", {}).get(furniture_type, {})
    return {
        param: spec["typical"]
        for param, spec in ftype_std.get("ranges", {}).items()
    }
