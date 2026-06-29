"""
Furniture Draft — The ONE unified workflow endpoint.

Replaces /digitize, /digitize/hybrid, /digitize/smart, /digitize/unified
with a SINGLE endpoint that does it all.

Workflow:
  1. Accept image (upload) OR product URL
  2. Run unified pipeline (OpenCV + OCR + AI Vision)
  3. Wrap in Canonical Furniture Graph
  4. Grammar Engine resolves template + generates DrawingModel
  5. SelfCritic auto-correction loop
  6. Return: component_schema, locked_components, confidence_review, SVG, DXF

Key features:
  - Component locking: lock/regen individual components
  - Linked views: one shared model → all views
  - Confidence review: per-component confidence with actionable warnings
  - Editable: every component returns its dimensions for slider panel
"""

from __future__ import annotations
import json
import os
import uuid
import logging
import tempfile
import shutil
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

logger = logging.getLogger("furniture_draft")

# Paths
OUT = Path(tempfile.gettempdir()) / "cad_digitizer_outputs"
OUT.mkdir(parents=True, exist_ok=True)
UPLOAD = Path(tempfile.gettempdir()) / "cad_digitizer_uploads"
UPLOAD.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------

@dataclass
class DraftComponent:
    """A single editable component in the draft."""
    id: str
    name: str
    label: str
    component_type: str         # "top", "leg", "seat", "back", "door", "shelf", etc.
    editable: bool = True
    locked: bool = False        # User can lock to prevent regen
    confidence: float = 0.0
    source: str = "auto"        # "measured", "ocr", "ratio", "schema_default", "user"
    dimensions: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "label": self.label,
            "component_type": self.component_type,
            "editable": self.editable,
            "locked": self.locked,
            "confidence": round(self.confidence, 3),
            "source": self.source,
            "dimensions": self.dimensions,
            "warnings": self.warnings,
            "needs_review": self.confidence < 0.60 and not self.locked,
        }


@dataclass
class ViewModel:
    """A 2D view generated from the shared model."""
    name: str                    # "TOP VIEW", "FRONT VIEW", "SIDE VIEW"
    type: str                    # "top", "front", "side"
    primitives: List[Dict] = field(default_factory=list)
    confidence: float = 0.0
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type,
            "primitive_count": len(self.primitives),
            "confidence": round(self.confidence, 3),
            "warnings": self.warnings,
        }


@dataclass
class ConfidenceReview:
    """Per-component confidence review data."""
    average_confidence: float = 0.0
    needs_review: List[str] = field(default_factory=list)  # component names
    critical_fields: List[str] = field(default_factory=list)
    self_critic_score: Optional[float] = None
    warnings: List[str] = field(default_factory=list)
    auto_generated: bool = False

    def to_dict(self) -> dict:
        return {
            "average_confidence": round(self.average_confidence, 3),
            "needs_review": self.needs_review,
            "critical_fields": self.critical_fields,
            "self_critic_score": round(self.self_critic_score, 3) if self.self_critic_score else None,
            "warnings": self.warnings,
            "auto_generated": self.auto_generated,
        }


@dataclass
class FurnitureDraftResult:
    """Complete result from the furniture-draft pipeline."""
    job_id: str
    furniture_type: str
    furniture_family: str
    components: List[DraftComponent]
    views: List[ViewModel]
    confidence_review: ConfidenceReview
    dxf_file: Optional[str] = None
    svg_preview: Optional[str] = None
    download_url: Optional[str] = None
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "job_id": self.job_id,
            "furniture_type": self.furniture_type,
            "furniture_family": self.furniture_family,
            "components": [c.to_dict() for c in self.components],
            "views": [v.to_dict() for v in self.views],
            "confidence_review": self.confidence_review.to_dict(),
            "dxf_file": self.dxf_file,
            "svg_preview": self.svg_preview,
            "download_url": self.download_url,
            "error_count": len(self.errors),
            "errors": self.errors[:5],
            "warnings": self.warnings[:10],
            "component_count": len(self.components),
        }


# ---------------------------------------------------------------------------
# Lock/Unlock State (per-job, in-memory — replace with Redis for production)
# ---------------------------------------------------------------------------

_lock_state: Dict[str, Dict[str, bool]] = {}  # job_id → component_id → locked

def get_locked_components(job_id: str) -> Dict[str, bool]:
    return _lock_state.get(job_id, {})

def lock_component(job_id: str, component_id: str, locked: bool = True):
    if job_id not in _lock_state:
        _lock_state[job_id] = {}
    _lock_state[job_id][component_id] = locked

def unlock_component(job_id: str, component_id: str):
    lock_component(job_id, component_id, locked=False)

# ---------------------------------------------------------------------------
# Main Pipeline
# ---------------------------------------------------------------------------

def run_furniture_draft(
    image_path: str,
    furniture_type_override: Optional[str] = None,
    user_dimensions: Optional[Dict[str, float]] = None,
    locked_components: Optional[Dict[str, bool]] = None,
    run_self_critic: bool = True,
) -> FurnitureDraftResult:
    """Run the unified furniture draft pipeline.

    Args:
        image_path: Path to uploaded image
        furniture_type_override: Optional user-specified furniture type
        user_dimensions: Optional user-provided dimensions {width_cm: 180, ...}
        locked_components: Components to skip regenerating {component_id: True}
        run_self_critic: Whether to run auto-correction loop

    Returns:
        FurnitureDraftResult with components, views, confidence, download links
    """
    job_id = uuid.uuid4().hex[:12]
    logger.info(f"[FurnitureDraft] Starting job {job_id}")

    result = FurnitureDraftResult(
        job_id=job_id,
        furniture_type="",
        furniture_family="",
        components=[],
        views=[],
        confidence_review=ConfidenceReview(),
    )

    # ── Phase 1: Run unified pipeline ──────────────────────────────
    try:
        from app.backend.cad_intelligence.unified_router import run_unified_pipeline
        unified = run_unified_pipeline(
            image_path=image_path,
            furniture_type_override=furniture_type_override,
            user_dimensions_cm=user_dimensions,
        )
        result.furniture_type = unified.product_type.value if unified.product_type else "generic"
    except Exception as e:
        result.errors.append(f"Unified pipeline failed: {e}")
        logger.error(f"[FurnitureDraft] Phase 1 failed: {e}")
        return result

    # ── Phase 2: Wrap in CFG ──────────────────────────────────────
    cfg = None
    try:
        from app.backend.cfg import CanonicalFurnitureGraph
        cfg = CanonicalFurnitureGraph.from_pipeline_result(
            unified_result=unified,
            furniture_type=result.furniture_type,
        )
        # Extract furniture family from product_type provenance if available
        if hasattr(unified, 'product_type') and unified.product_type:
            result.furniture_family = unified.product_type.source or ""
    except Exception as e:
        result.errors.append(f"CFG wrapping failed: {e}")

    # ── Phase 3: Grammar Engine → DrawingModel ────────────────────
    model = None
    try:
        from app.backend.grammar import FurnitureGrammar
        grammar = FurnitureGrammar()
        
        # Build params from unified dimensions
        params = {}
        if hasattr(unified, 'dimensions'):
            for k, v in unified.dimensions.items():
                if hasattr(v, 'value'):
                    params[k] = v.value
        
        # Merge user dimensions (override AI detection)
        if user_dimensions:
            params.update(user_dimensions)
        
        # Generate DrawingModel from grammar
        ftype = result.furniture_type if grammar.supports(result.furniture_type) else "generic"
        model = grammar.generate(ftype, params)
    except Exception as e:
        result.errors.append(f"Grammar engine failed: {e}")

    # ── Phase 4: SelfCritic auto-correction ────────────────────────
    self_critic_gap = None
    if run_self_critic and model:
        try:
            from app.backend.self_critic import SelfCritic
            critic = SelfCritic(gap_threshold=0.05, max_iterations=3)
            sc_result = critic.run(model, image_path)
            self_critic_gap = 1.0 - sc_result.gap_score
            logger.info(f"[FurnitureDraft] SelfCritic: gap={sc_result.gap_score:.4f}, "
                        f"iterations={sc_result.iterations}, converged={sc_result.converged}")
            if not sc_result.converged:
                result.warnings.append(f"Self-critic loop did not fully converge "
                                       f"(final gap: {sc_result.gap_score:.2%})")
            for repair in sc_result.repairs_applied:
                result.warnings.append(f"Auto-repair: {repair}")
        except Exception as e:
            logger.warning(f"[FurnitureDraft] SelfCritic skipped: {e}")

    # ── Phase 5: Build component schema ────────────────────────────
    components = _build_component_schema(cfg, model)
    
    # Apply lock state — merge from both parameter and stored state
    locks = dict(locked_components or {})
    stored_locks = get_locked_components(job_id)
    if stored_locks:
        locks.update(stored_locks)
    
    for comp in components:
        if comp.id in locks:
            comp.locked = locks[comp.id]
    
    result.components = components

    # ── Phase 6: Build view models ─────────────────────────────────
    views = _build_view_models(model)
    result.views = views

    # ── Phase 7: Build confidence review ───────────────────────────
    confidences = [c.confidence for c in components if not c.locked]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
    
    review = ConfidenceReview(
        average_confidence=avg_conf,
        needs_review=[c.name for c in components if c.confidence < 0.60 and not c.locked],
        critical_fields=[c.name for c in components if c.confidence < 0.30],
        self_critic_score=self_critic_gap,
        auto_generated=avg_conf >= 0.50,
    )
    
    if review.needs_review:
        review.warnings.append(f"Components need review: {', '.join(review.needs_review[:3])}")
    if review.critical_fields:
        review.warnings.append(f"Critical low-confidence: {', '.join(review.critical_fields[:3])}")
    
    result.confidence_review = review

    # ── Phase 8: Generate SVG preview ──────────────────────────────
    if model:
        try:
            from app.backend.svg_exporter import render_svg
            svg_name = f"{job_id}_preview.svg"
            svg_path = OUT / svg_name
            svg_content = render_svg(model)
            svg_path.write_text(svg_content, encoding='utf-8')
            result.svg_preview = f"/api/preview/svg/{svg_name}"
            logger.info(f"[FurnitureDraft] SVG saved to {svg_path}")
        except Exception as e:
            result.errors.append(f"SVG generation failed: {e}")

        # ── Phase 9: Generate DXF ──────────────────────────────────
        try:
            from app.backend.dxf_exporter import (
                save_generic, save_round_pedestal_table, save_rectangular_table,
                save_cabinet, save_sofa, save_coffee_table, save_dining_chair,
                save_wardrobe, save_bed_headboard,
                setup_doc, _save,
            )
            dxf_name = f"{job_id}_draft.dxf"
            dxf_path = OUT / dxf_name
            
            # Build dimension list for dispatch
            dims_list = [{"tag": k, "value_cm": v} for k, v in params.items()]
            
            # Use the api route's dispatch if available, otherwise try direct
            try:
                from app.api.routes import _dispatch_furniture as api_dispatch
                api_dispatch(result.furniture_type, dxf_path, dims_list, None, None)
            except ImportError:
                # Fallback: generate generic DXF
                save_generic(dxf_path, [], [], [])
            
            result.dxf_file = dxf_name
            result.download_url = f"/api/download/{dxf_name}"
            logger.info(f"[FurnitureDraft] DXF saved to {dxf_path}")
        except Exception as e:
            result.errors.append(f"DXF generation failed: {e}")

    # ── Phase 10: Warnings ─────────────────────────────────────────
    if hasattr(unified, 'product_type') and (not unified.product_type or unified.product_type.source == "template_default"):
        result.warnings.append("Furniture type could not be auto-detected — verify the type in the editor")

    if not result.components:
        result.warnings.append("No components could be detected — the image may not contain recognizable furniture")

    logger.info(f"[FurnitureDraft] Job {job_id} complete: {len(components)} components, "
                f"{len(views)} views, avg confidence {avg_conf:.2%}")
    return result


# ---------------------------------------------------------------------------
# Helper: Build component schema from CFG + DrawingModel
# ---------------------------------------------------------------------------

def _build_component_schema(
    cfg: Any,
    model: Any,
) -> List[DraftComponent]:
    """Build editable component list from CFG data and DrawingModel."""
    components: List[DraftComponent] = []

    # Try CFG first
    if cfg and hasattr(cfg, 'components'):
        for comp in cfg.components:
            dims = getattr(comp, 'dimensions_mm', {})
            if isinstance(dims, dict):
                dims = {k: round(v, 1) for k, v in dims.items()}
            
            comp_name = getattr(comp, 'name', '') or f"component_{len(components)}"
            components.append(DraftComponent(
                id=getattr(comp, 'id', f"comp_{len(components)}"),
                name=comp_name,
                label=comp_name.replace("_", " ").title(),
                component_type=getattr(comp, 'component_type', 'unknown'),
                confidence=getattr(comp, 'confidence', 0.0),
                source=getattr(comp, 'source', 'auto'),
                dimensions=dims,
            ))

    # If CFG produced no components, fall back to DrawingModel
    if not components and model and hasattr(model, 'views'):
        for view in getattr(model, 'views', []):
            for poly in getattr(view, 'polygons', []):
                pname = getattr(poly, 'name', '') or f"poly_{len(components)}"
                meta = getattr(poly, 'metadata', None)
                conf = getattr(meta, 'confidence', 0.5) if meta else 0.5
                src = getattr(meta, 'source', 'auto') if meta else 'auto'
                components.append(DraftComponent(
                    id=f"comp_{len(components)}",
                    name=pname,
                    label=pname.replace("_", " ").title(),
                    component_type="panel",
                    confidence=conf,
                    source=src,
                    dimensions={},
                ))

    return components


# ---------------------------------------------------------------------------
# Helper: Build view models
# ---------------------------------------------------------------------------

def _build_view_models(model: Any) -> List[ViewModel]:
    """Build view descriptors from DrawingModel."""
    views: List[ViewModel] = []

    if not model or not hasattr(model, 'views'):
        return views

    for view in getattr(model, 'views', []):
        vname = getattr(view, 'name', 'VIEW')
        if "FRONT" in vname.upper():
            vtype = "front"
        elif "SIDE" in vname.upper():
            vtype = "side"
        else:
            vtype = "top"

        poly_count = len(getattr(view, 'polygons', []))
        circ_count = len(getattr(view, 'circles', []))
        dim_count = len(getattr(view, 'dimensions', []))

        # Estimate confidence from metadata
        confs = []
        for poly in getattr(view, 'polygons', []):
            meta = getattr(poly, 'metadata', None)
            if meta and hasattr(meta, 'confidence'):
                confs.append(meta.confidence)
        avg_conf = sum(confs) / len(confs) if confs else 0.7

        warnings = []
        if poly_count == 0 and circ_count == 0:
            warnings.append("No geometry entities in this view")
        if dim_count == 0:
            warnings.append("No dimensions in this view")

        views.append(ViewModel(
            name=vname,
            type=vtype,
            primitives=[{"type": "polygon", "count": poly_count},
                       {"type": "circle", "count": circ_count},
                       {"type": "dimension", "count": dim_count}],
            confidence=avg_conf,
            warnings=warnings,
        ))

    return views
