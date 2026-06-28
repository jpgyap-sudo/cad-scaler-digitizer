"""
CFG Router — API endpoints for the Canonical Furniture Graph pipeline.
Adds /api/cfg/* endpoints that integrate CFG, Grammar, and SelfCritic.

All existing endpoints continue to work unchanged. These are additive.
"""

from __future__ import annotations
import json
import os
import uuid
import logging
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, UploadFile, HTTPException
from fastapi.responses import JSONResponse

from app.backend.cfg import CanonicalFurnitureGraph, FurnitureGraph
from app.backend.cfg.canonical_furniture_graph import cfg_to_drawing_model
from app.backend.grammar import FurnitureGrammar
from app.backend.self_critic import SelfCritic

logger = logging.getLogger("cfg_router")

router = APIRouter(prefix="/api/cfg", tags=["cfg"])

UPLOAD_DIR = Path(os.environ.get("UPLOAD_DIR", "uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/health")
async def cfg_health():
    """Check CFG system health."""
    grammar = FurnitureGrammar()
    return JSONResponse({
        "ok": True,
        "grammar_types": len(grammar.get_known_types()),
        "grammar_families": len(grammar.get_families()),
        "has_self_critic": True,
        "has_cfg": True,
    })


@router.get("/evaluate")
async def cfg_evaluate():
    """Run self-diagnostics on all CFG components.
    
    Tests:
    1. Grammar can load all 25+ template types
    2. Each type generates a valid DrawingModel
    3. CFG wraps/rewraps correctly
    4. SelfCritic initializes
    5. Returns pass/fail per test
    """
    results = {}
    errors = []
    
    # Test 1: Grammar loading
    try:
        grammar = FurnitureGrammar()
        types = grammar.get_known_types()
        families = grammar.get_families()
        results["grammar_load"] = {
            "passed": len(types) > 0,
            "types_count": len(types),
            "families_count": len(families),
            "types": types[:5],  # first 5 for display
        }
    except Exception as e:
        results["grammar_load"] = {"passed": False, "error": str(e)}
        errors.append(f"Grammar load: {e}")
    
    # Test 2: Each type generates a DrawingModel
    if results.get("grammar_load", {}).get("passed"):
        generate_results = []
        for ftype in types[:10]:  # Test first 10 types
            try:
                model = grammar.generate(ftype, {"width_cm": 100, "depth_cm": 60, "height_cm": 75})
                view_count = len(getattr(model, 'views', []))
                generate_results.append({
                    "type": ftype,
                    "passed": True,
                    "views": view_count,
                })
            except Exception as e:
                generate_results.append({
                    "type": ftype,
                    "passed": False,
                    "error": str(e),
                })
                errors.append(f"Generate {ftype}: {e}")
        results["generate_types"] = {
            "passed": all(r["passed"] for r in generate_results),
            "tested": len(generate_results),
            "passed_count": sum(1 for r in generate_results if r["passed"]),
            "details": generate_results,
        }
    
    # Test 3: CFG round-trip
    try:
        model = grammar.generate(types[0], {"width_cm": 100, "height_cm": 75})
        cfg = CanonicalFurnitureGraph.from_drawing_model_only(model)
        roundtrip = cfg_to_drawing_model(cfg)
        rt_views = len(getattr(roundtrip, 'views', []))
        results["cfg_roundtrip"] = {
            "passed": rt_views > 0,
            "component_count": cfg.component_count,
            "views_after_roundtrip": rt_views,
        }
    except Exception as e:
        results["cfg_roundtrip"] = {"passed": False, "error": str(e)}
        errors.append(f"CFG roundtrip: {e}")
    
    # Test 4: SelfCritic initializes
    try:
        critic = SelfCritic(gap_threshold=0.05, max_iterations=3)
        results["self_critic_init"] = {
            "passed": True,
            "max_iterations": critic.max_iterations,
            "gap_threshold": critic.gap_threshold,
        }
    except Exception as e:
        results["self_critic_init"] = {"passed": False, "error": str(e)}
        errors.append(f"SelfCritic init: {e}")
    
    all_passed = all(r.get("passed", False) for r in results.values())
    return JSONResponse({
        "status": "healthy" if all_passed else "degraded",
        "all_tests_passed": all_passed,
        "error_count": len(errors),
        "errors": errors[:5],  # first 5 errors
        "results": results,
    })


@router.post("/generate")
async def cfg_generate(
    furniture_type: str = Form(...),
    params_json: str = Form("{}"),
    run_self_critic: bool = Form(False),
):
    """Generate a DrawingModel via the Grammar Engine, return CFG.

    Args:
        furniture_type: e.g. "dining_table_rectangular_4_leg"
        params_json: JSON string of dimension parameters
        run_self_critic: Whether to run self-critic loop

    Returns:
        CFG JSON with components, confidence, provenance
    """
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError:
        params = {}

    # Step 1: Grammar Engine generates DrawingModel
    grammar = FurnitureGrammar()
    model = grammar.generate(furniture_type, params)

    # Step 2: Wrap in CFG
    cfg = CanonicalFurnitureGraph.from_drawing_model_only(model)
    cfg.furniture_type = furniture_type

    # Step 3: SelfCritic — graceful no-image fallback
    if run_self_critic:
        try:
            critic = SelfCritic(gap_threshold=0.05, max_iterations=3)
            result = critic.run(model, "")
            cfg.confidence_map["self_critic_score"] = round(1.0 - result.gap_score, 3)
            cfg.confidence_map["self_critic_iterations"] = result.iterations
            cfg.confidence_map["self_critic_converged"] = 1.0 if result.converged else 0.0
        except Exception as e:
            logger.warning(f"SelfCritic skipped (no comparison image): {e}")

    return JSONResponse({
        "cfg": cfg.to_dict(),
        "grammar_supported": grammar.supports(furniture_type),
        "grammar_family": grammar.get_family_for_type(furniture_type).name
        if grammar.get_family_for_type(furniture_type) else None,
    })


@router.get("/types")
async def cfg_types():
    """List all known furniture types from the grammar."""
    grammar = FurnitureGrammar()
    types = grammar.get_known_types()
    families = grammar.get_families()
    by_family = {}
    for f in families:
        by_family[f] = grammar.get_types_by_family(f)
    return JSONResponse({
        "types": types,
        "families": families,
        "by_family": by_family,
        "count": len(types),
        "family_count": len(families),
    })


@router.get("/family/{family_name}")
async def cfg_family(family_name: str):
    """Get grammar family details."""
    grammar = FurnitureGrammar()
    family = grammar.get_family(family_name)
    if not family:
        raise HTTPException(status_code=404, detail=f"Family '{family_name}' not found")
    types = grammar.get_types_by_family(family_name)
    return JSONResponse({
        "family": family_name,
        "inherits": family.inherits,
        "top_types": family.top_types,
        "base_types": family.base_types,
        "proportions": family.proportions,
        "height_range": family.height_range,
        "view_order": family.view_order,
        "templates": [{
            "name": t.name,
            "top_type": t.top_type,
            "base_type": t.base_type,
            "leg_count": t.leg_count,
            "has_builder": t.builder_fn is not None,
        } for t in family.templates.values()],
    })


@router.post("/self-critic")
async def cfg_self_critic(
    params_json: str = Form(...),
    image_path: str = Form(""),
    image: Optional[UploadFile] = File(None),
):
    """Run self-critic loop on an existing DrawingModel.

    Args:
        params_json: JSON with furniture_type and dimension params
        image_path: Path to original image for comparison (alternative to uploading)
        image: Upload original image for comparison (alternative to path)

    Returns:
        SelfCriticResult with iterations, gaps, convergence
    """
    try:
        params = json.loads(params_json)
    except json.JSONDecodeError:
        params = {}

    # Resolve image path
    resolved_path = image_path
    if image and not resolved_path:
        safe_fn = f"sc_{uuid.uuid4().hex[:8]}_{image.filename}"
        save_path = UPLOAD_DIR / safe_fn
        content = await image.read()
        save_path.write_bytes(content)
        resolved_path = str(save_path)

    furniture_type = params.get("furniture_type", "generic")
    grammar = FurnitureGrammar()
    model = grammar.generate(furniture_type, params)

    critic = SelfCritic(gap_threshold=0.05, max_iterations=3)
    result = critic.run(model, resolved_path)

    return JSONResponse({
        "iterations": result.iterations,
        "gap_score": round(result.gap_score, 4),
        "converged": result.converged,
        "gap_history": [round(g, 4) for g in result.gap_history],
        "repairs_applied": result.repairs_applied,
        "furniture_type": furniture_type,
        "image_saved": bool(resolved_path),
    })
