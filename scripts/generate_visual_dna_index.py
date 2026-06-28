"""Generate visual_dna_index.json from _registry.json by classifying each
template_family into Visual DNA categories."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REGISTRY_PATH = ROOT / "resources" / "product_catalog" / "_registry.json"
OUTPUT_PATH = ROOT / "resources" / "product_catalog" / "visual_dna_index.json"

# === FAMILY CLASSIFICATION RULES ===
# Each rule maps family_name keyword -> VisualDNA defaults

CATEGORY_RULES = {
    "sofa": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "sofa", "archetype_base": 0.45},
    "armchair": {"top_shape": "square", "base_type": "legs", "leg_type": "four_leg", "category_hint": "chair", "archetype_base": 0.60},
    "chair": {"top_shape": "square", "base_type": "legs", "leg_type": "four_leg", "category_hint": "chair", "archetype_base": 0.55},
    "table": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "table", "archetype_base": 0.50},
    "coffee_table": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "table", "archetype_base": 0.50},
    "dining_table": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "table", "archetype_base": 0.50},
    "side_table": {"top_shape": "round", "base_type": "legs", "leg_type": "four_leg", "category_hint": "table", "archetype_base": 0.50},
    "console_table": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "table", "archetype_base": 0.55},
    "pedestal": {"top_shape": "round", "base_type": "pedestal", "leg_type": "single_pedestal", "category_hint": "table", "archetype_base": 0.70},
    "sideboard": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "plinth", "category_hint": "storage", "archetype_base": 0.60},
    "cabinet": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "plinth", "category_hint": "storage", "archetype_base": 0.60},
    "chest": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "plinth", "category_hint": "storage", "archetype_base": 0.55},
    "ottoman": {"top_shape": "square", "base_type": "floor", "leg_type": "no_legs", "category_hint": "ottoman", "archetype_base": 0.40},
    "pouf": {"top_shape": "round", "base_type": "floor", "leg_type": "no_legs", "category_hint": "ottoman", "archetype_base": 0.35},
    "light": {"top_shape": "round", "base_type": "ceiling", "leg_type": "no_legs", "category_hint": "lighting", "archetype_base": 0.65},
    "pendant": {"top_shape": "round", "base_type": "ceiling", "leg_type": "no_legs", "category_hint": "lighting", "archetype_base": 0.70},
    "chandelier": {"top_shape": "round", "base_type": "ceiling", "leg_type": "no_legs", "category_hint": "lighting", "archetype_base": 0.80},
    "sconce": {"top_shape": "round", "base_type": "wall_mounted", "leg_type": "no_legs", "category_hint": "lighting", "archetype_base": 0.75},
    "lamp": {"top_shape": "round", "base_type": "floor", "leg_type": "cylindrical", "category_hint": "lighting", "archetype_base": 0.65},
    "fan": {"top_shape": "round", "base_type": "ceiling", "leg_type": "no_legs", "category_hint": "lighting", "archetype_base": 0.90},
    "ceiling_fan": {"top_shape": "round", "base_type": "ceiling", "leg_type": "no_legs", "category_hint": "fan", "archetype_base": 0.90},
    "stone": {"top_shape": "rectangular", "base_type": "floor", "leg_type": "no_legs", "category_hint": "material", "archetype_base": 0.90},
    "slab": {"top_shape": "rectangular", "base_type": "floor", "leg_type": "no_legs", "category_hint": "material", "archetype_base": 0.85},
    "rug": {"top_shape": "rectangular", "base_type": "floor", "leg_type": "no_legs", "category_hint": "rug", "archetype_base": 0.40},
    "pillow": {"top_shape": "square", "base_type": "floor", "leg_type": "no_legs", "category_hint": "pillow", "archetype_base": 0.35},
    "wall_panel": {"top_shape": "rectangular", "base_type": "wall_mounted", "leg_type": "no_legs", "category_hint": "panel", "archetype_base": 0.85},
    "bed": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "bed", "archetype_base": 0.60},
    "bench": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "seating", "archetype_base": 0.55},
    "stool": {"top_shape": "square", "base_type": "legs", "leg_type": "four_leg", "category_hint": "seating", "archetype_base": 0.55},
    "bar_stool": {"top_shape": "square", "base_type": "legs", "leg_type": "four_leg", "category_hint": "seating", "archetype_base": 0.60},
    "shelf": {"top_shape": "rectangular", "base_type": "wall_mounted", "leg_type": "no_legs", "category_hint": "storage", "archetype_base": 0.70},
    "seat": {"top_shape": "square", "base_type": "legs", "leg_type": "four_leg", "category_hint": "seating", "archetype_base": 0.55},
    "base": {"top_shape": "round", "base_type": "pedestal", "leg_type": "single_pedestal", "category_hint": "support", "archetype_base": 0.50},
    "glass": {"top_shape": "round", "base_type": "legs", "leg_type": "four_leg", "category_hint": "table", "archetype_base": 0.60},
    "lounge": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "chair", "archetype_base": 0.55},
    "chesterfield": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "sofa", "archetype_base": 0.75},
    "tufted": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "sofa", "archetype_base": 0.70},
    "club": {"top_shape": "square", "base_type": "legs", "leg_type": "four_leg", "category_hint": "chair", "archetype_base": 0.65},
    "modular": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "plinth", "category_hint": "sofa", "archetype_base": 0.50},
    "sectional": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "plinth", "category_hint": "sofa", "archetype_base": 0.55},
    "curved": {"top_shape": "irregular", "base_type": "legs", "leg_type": "plinth", "category_hint": "sofa", "archetype_base": 0.65},
    "round": {"top_shape": "round", "base_type": "pedestal", "leg_type": "single_pedestal", "category_hint": "table", "archetype_base": 0.60},
    "oval": {"top_shape": "oval", "base_type": "pedestal", "leg_type": "single_pedestal", "category_hint": "table", "archetype_base": 0.65},
    "nesting": {"top_shape": "round", "base_type": "pedestal", "leg_type": "single_pedestal", "category_hint": "table", "archetype_base": 0.60},
    "sculptural": {"top_shape": "organic", "base_type": "legs", "leg_type": "single_pedestal", "category_hint": "table", "archetype_base": 0.75},
    "fluted": {"top_shape": "rectangular", "base_type": "wall_mounted", "leg_type": "no_legs", "category_hint": "panel", "archetype_base": 0.85},
    "midcentury": {"top_shape": "rectangular", "base_type": "legs", "leg_type": "four_leg", "category_hint": "sofa", "archetype_base": 0.60},
    "sintered": {"top_shape": "rectangular", "base_type": "floor", "leg_type": "no_legs", "category_hint": "material", "archetype_base": 0.90},
    "marble": {"top_shape": "rectangular", "base_type": "floor", "leg_type": "no_legs", "category_hint": "material", "archetype_base": 0.85},
}

# === COMPONENT GRAPHS PER CATEGORY ===
COMPONENT_GRAPHS = {
    "sofa": ["seat_base", "seat_cushions", "backrest", "armrests", "legs_or_plinth"],
    "chair": ["seat", "backrest", "armrests", "legs"],
    "table": ["tabletop", "base_support_or_legs"],
    "lighting": ["fixture_body", "mounting_or_cord", "bulb_or_led"],
    "storage": ["body_carcass", "doors_or_drawers", "shelves", "base_or_plinth"],
    "material": ["slab_body"],
    "rug": ["rug_body"],
    "pillow": ["pillow_body", "filling"],
    "panel": ["panel_body"],
    "fan": ["motor_body", "blades", "light_kit", "mounting"],
    "ottoman": ["seat_cushion", "base_or_legs"],
    "seating": ["seat", "backrest", "legs"],
    "bed": ["bed_frame", "headboard", "footboard"],
    "support": ["column", "base_plate", "mounting_plate"],
}

# === SVG SKELETONS ===
SVG_SKELETONS = {
    "rectangular_sofa": {"top": "M 0,40 L 200,40 L 200,80 L 0,80 Z", "front": "M 0,0 L 200,0 L 200,100 L 0,100 Z", "side": "M 0,0 L 80,0 L 80,100 L 0,100 Z"},
    "square_chair": {"top": "M 10,10 L 90,10 L 90,90 L 10,90 Z", "front": "M 10,0 L 90,0 L 90,120 L 10,120 Z", "side": "M 0,0 L 90,0 L 90,120 L 0,120 Z"},
    "round_table": {"top": "M 50,0 A 50,50 0 1,1 50,100 A 50,50 0 1,1 50,0 Z", "front": "M 0,0 L 100,0 L 100,80 L 0,80 Z", "side": "M 0,0 L 100,0 L 100,80 L 0,80 Z"},
    "rectangular_table": {"top": "M 0,20 L 160,20 L 160,80 L 0,80 Z", "front": "M 0,0 L 160,0 L 160,80 L 0,80 Z", "side": "M 0,0 L 80,0 L 80,80 L 0,80 Z"},
    "oval_table": {"top": "M 20,0 Q 100,-20 180,0 Q 100,20 20,0", "front": "M 0,0 L 180,0 L 180,80 L 0,80 Z", "side": "M 0,0 L 120,0 L 120,80 L 0,80 Z"},
    "round_lighting": {"top": "M 50,0 A 30,30 0 1,1 50,60 A 30,30 0 1,1 50,0 Z", "front": "M 20,0 L 80,0 L 80,40 L 20,40 Z", "side": "M 20,0 L 80,0 L 80,40 L 20,40 Z"},
    "rectangular_panel": {"top": "M 0,0 L 180,0 L 180,200 L 0,200 Z", "front": "M 0,0 L 180,0 L 180,200 L 0,200 Z", "side": "M 0,0 L 10,0 L 10,200 L 0,200 Z"},
    "square_rug": {"top": "M 0,0 L 100,0 L 100,100 L 0,100 Z", "front": "M 0,0 L 0,5 Z", "side": "M 0,0 L 0,5 Z"},
    "round_rug": {"top": "M 50,0 A 50,50 0 1,1 50,100 A 50,50 0 1,1 50,0 Z", "front": "M 0,0 L 0,3 Z", "side": "M 0,0 L 0,3 Z"},
    "square_pillow": {"top": "M 10,10 L 90,10 L 90,90 L 10,90 Z", "front": "M 10,0 L 90,0 L 90,60 L 10,60 Z", "side": "M 0,0 L 60,0 L 60,60 L 0,60 Z"},
    "ottoman": {"top": "M 10,10 L 90,10 L 90,90 L 10,90 Z", "front": "M 10,0 L 90,0 L 90,50 L 10,50 Z", "side": "M 0,0 L 80,0 L 80,50 L 0,50 Z"},
    "pedestal": {"top": "M 40,0 L 60,0 L 60,100 L 40,100 Z", "front": "M 30,0 L 70,0 Q 50,50 40,100 L 60,100 Q 50,50 30,0 Z", "side": "M 30,0 L 70,0 Q 50,50 40,100 L 60,100 Q 50,50 30,0 Z"},
    "ceiling_fan": {"top": "M 50,10 A 5,5 0 1,1 50,20 A 5,5 0 1,1 50,10 Z M 10,15 L 40,15 L 40,16 L 10,16 Z M 60,15 L 90,15 L 90,16 L 60,16 Z", "front": "M 40,0 L 60,0 L 60,10 L 40,10 Z M 45,10 L 55,10 L 55,30 L 45,30 Z", "side": "M 40,0 L 60,0 L 60,10 L 40,10 Z M 45,10 L 55,10 L 55,30 L 45,30 Z"},
    "stone_slab": {"top": "M 0,0 L 120,0 L 120,80 L 0,80 Z", "front": "M 0,0 L 120,0 L 120,3 L 0,3 Z", "side": "M 0,0 L 80,0 L 80,3 L 0,3 Z"},
    "wall_panel": {"top": "M 0,0 L 180,0 L 180,200 L 0,200 Z", "front": "M 0,0 L 180,0 L 180,200 L 0,200 Z", "side": "M 0,0 L 8,0 L 8,200 L 0,200 Z"},
    "sideboard": {"top": "M 0,20 L 160,20 L 160,100 L 0,100 Z", "front": "M 0,0 L 160,0 L 160,80 L 0,80 Z", "side": "M 0,0 L 50,0 L 50,80 L 0,80 Z"},
    "midcentury": {"top": "M 0,30 L 160,30 L 160,80 L 0,80 Z", "front": "M 0,0 L 160,0 L 160,90 L 0,90 Z", "side": "M 0,0 L 85,0 L 85,90 L 0,90 Z"},
    "curved_sofa": {"top": "M 0,60 Q 100,-20 200,60 Q 100,40 0,60 Z", "front": "M 0,0 L 200,0 L 200,100 L 0,100 Z", "side": "M 0,0 L 100,0 L 100,100 L 0,100 Z"},
    "lamp": {"top": "M 45,0 A 5,5 0 1,1 55,0 A 5,5 0 1,1 45,0 Z M 30,15 A 20,20 0 1,1 70,15 L 60,15 L 40,15 Z", "front": "M 40,0 L 60,0 L 60,10 L 40,10 Z M 20,10 L 80,10 Q 50,30 40,40 L 60,40 Q 50,30 20,10 Z", "side": "M 40,0 L 60,0 L 60,10 L 40,10 Z M 30,10 L 70,10 Q 50,30 45,40 L 55,40 Q 50,30 30,10 Z"},
    "console_table": {"top": "M 0,10 L 120,10 L 120,40 L 0,40 Z", "front": "M 0,0 L 120,0 L 120,80 L 0,80 Z", "side": "M 0,0 L 40,0 L 40,80 L 0,80 Z"},
    "shelf": {"top": "M 0,0 L 100,0 L 100,20 L 0,20 Z", "front": "M 0,0 L 100,0 L 100,100 L 0,100 Z", "side": "M 0,0 L 20,0 L 20,100 L 0,100 Z"},
}


def classify_family(family: str) -> dict:
    """Classify a template_family string into visual DNA attributes."""
    f_lower = family.lower().replace("_", " ").replace("-", " ")
    tokens = f_lower.split()

    # Start with defaults
    result = {
        "top_shape": "rectangular",
        "base_type": "legs",
        "leg_type": "four_leg",
        "symmetry": "symmetric",
        "materials": ["wood", "fabric"],
        "category_hint": "furniture",
        "component_graph": ["body", "support"],
        "archetype_score": 0.5,
        "svg_skeleton": {},
    }

    # Apply rules from most specific to least
    matched_rules = []
    for keyword, rule in CATEGORY_RULES.items():
        if keyword in f_lower:
            matched_rules.append((keyword, rule))

    # Apply all matched rules (last match wins for overrides)
    for keyword, rule in matched_rules:
        for k, v in rule.items():
            if k == "archetype_base":
                result["archetype_score"] = v
            else:
                result[k] = v

    # Refine based on more specific patterns
    if "curved" in f_lower or "round" in f_lower:
        result["symmetry"] = "symmetric"
    if "asymmetric" in f_lower or "organic" in f_lower or "sculptural" in f_lower:
        result["symmetry"] = "asymmetric"
        result["archetype_score"] = max(result["archetype_score"], 0.65)
    if "nesting" in f_lower:
        result["symmetry"] = "symmetric"
        result["archetype_score"] = max(result["archetype_score"], 0.55)
    if "marble" in f_lower:
        result["materials"] = ["marble", "metal"]
        result["archetype_score"] = max(result["archetype_score"], 0.70)
    if "metal" in f_lower or "steel" in f_lower or "brass" in f_lower or "iron" in f_lower:
        if "metal" not in result["materials"]:
            result["materials"].append("metal")
    if "glass" in f_lower:
        if "glass" not in result["materials"]:
            result["materials"].append("glass")
        result["archetype_score"] = max(result["archetype_score"], 0.55)
    if "wood" in f_lower or "walnut" in f_lower or "oak" in f_lower:
        if "wood" not in result["materials"]:
            result["materials"].append("wood")
    if "leather" in f_lower:
        if "leather" not in result["materials"]:
            result["materials"].append("leather")
    if "fabric" in f_lower or "upholstered" in f_lower or "velvet" in f_lower:
        if "fabric" not in result["materials"]:
            result["materials"].append("fabric")
    if "stone" in f_lower or "sintered" in f_lower or "calacatta" in f_lower:
        result["materials"] = ["stone", "sintered"]
        result["archetype_score"] = max(result["archetype_score"], 0.80)

    # Component graph
    cat = result["category_hint"]
    for comp_cat, comps in COMPONENT_GRAPHS.items():
        if comp_cat in f_lower or comp_cat == cat:
            result["component_graph"] = comps
            break

    # SVG skeleton
    if cat == "sofa" and result["top_shape"] == "irregular":
        result["svg_skeleton"] = SVG_SKELETONS["curved_sofa"]
    elif cat == "sofa" and "midcentury" in f_lower:
        result["svg_skeleton"] = SVG_SKELETONS["midcentury"]
    elif cat == "sofa":
        result["svg_skeleton"] = SVG_SKELETONS["rectangular_sofa"]
    elif cat == "chair":
        result["svg_skeleton"] = SVG_SKELETONS["square_chair"]
    elif cat == "table" and result["top_shape"] == "round":
        result["svg_skeleton"] = SVG_SKELETONS["round_table"]
    elif cat == "table" and result["top_shape"] == "oval":
        result["svg_skeleton"] = SVG_SKELETONS["oval_table"]
    elif cat == "table" and "console" in f_lower:
        result["svg_skeleton"] = SVG_SKELETONS["console_table"]
    elif cat == "table":
        result["svg_skeleton"] = SVG_SKELETONS["rectangular_table"]
    elif cat == "lighting" and "pendant" in f_lower:
        result["svg_skeleton"] = SVG_SKELETONS["round_lighting"]
    elif cat == "lighting" and "lamp" in f_lower:
        result["svg_skeleton"] = SVG_SKELETONS["lamp"]
    elif cat == "lighting":
        result["svg_skeleton"] = SVG_SKELETONS["round_lighting"]
    elif cat == "material":
        result["svg_skeleton"] = SVG_SKELETONS["stone_slab"]
    elif cat == "panel":
        result["svg_skeleton"] = SVG_SKELETONS["wall_panel"]
    elif cat == "fan":
        result["svg_skeleton"] = SVG_SKELETONS["ceiling_fan"]
    elif cat == "rug":
        result["svg_skeleton"] = SVG_SKELETONS["round_rug"] if "oval" in f_lower or "round" in f_lower else SVG_SKELETONS["square_rug"]
    elif cat == "pillow":
        result["svg_skeleton"] = SVG_SKELETONS["square_pillow"]
    elif cat == "ottoman":
        result["svg_skeleton"] = SVG_SKELETONS["ottoman"]
    elif cat == "storage":
        result["svg_skeleton"] = SVG_SKELETONS["sideboard"]
    elif cat == "seating" and "bar" in f_lower:
        result["svg_skeleton"] = SVG_SKELETONS["square_chair"]
    elif cat == "support":
        result["svg_skeleton"] = SVG_SKELETONS["pedestal"]
    else:
        result["svg_skeleton"] = SVG_SKELETONS["rectangular_sofa"]

    return result


def main():
    registry = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))

    # Group by family
    families = {}
    for entry in registry:
        fam = entry["template_family"]
        if fam not in families:
            families[fam] = []
        families[fam].append(entry)

    dna_index = {}
    for family, members in sorted(families.items()):
        dna = classify_family(family)
        # Add items list
        dna["count"] = len(members)
        dna["items"] = [
            {
                "title": m["title"],
                "handle": m["handle"],
                "template_file": f"templates/{m['file']}",
                "category": m["product_type"],
            }
            for m in members
        ]
        dna_index[family] = dna

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(dna_index, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Visual DNA index written: {OUTPUT_PATH}")
    print(f"Families: {len(dna_index)}")
    # Show distribution of archetype scores
    scores = [d["archetype_score"] for d in dna_index.values()]
    print(f"Archetype scores: min={min(scores):.2f}, max={max(scores):.2f}, avg={sum(scores)/len(scores):.2f}")


if __name__ == "__main__":
    main()
