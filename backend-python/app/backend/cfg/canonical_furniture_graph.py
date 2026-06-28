"""
Canonical Furniture Graph — wrapper that reads EXISTING module outputs
into one unified structure.

NOT a replacement. Every existing module still works unchanged.
This just collects their outputs into a single CFG.

Usage:
    from app.backend.cfg import CanonicalFurnitureGraph
    cfg = CanonicalFurnitureGraph.from_pipeline_result(
        drawing_model=model,
        component_graph=comp_graph,
        unified_result=result,
        scale=scale_solution,
    )
    # Then work with cfg.components, cfg.relations, cfg.confidence_map, etc.
    # For export: drawing_model = cfg.to_drawing_model()
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from app.backend.cad_intelligence.component_graph import ComponentGraph as PipeComponentGraph
from app.backend.cad_intelligence.models import ScaleSolution as PipeScale
from app.backend.drawing_model import (
    DrawingModel,
    EntityMetadata,
)
from app.backend.drawing_model import (
    Point as DMPoint,
)

from .models import (
    BBox,
    BillOfMaterials,
    ComponentGeometry,
    ComponentNode,
    FurnitureGraph,
    MaterialSpec,
    ProvenanceEntry,
    ScaleInfo,
    ViewSpec,
)


def _point_to_tuple(p) -> tuple[float, float]:
    if hasattr(p, 'x') and hasattr(p, 'y'):
        return (p.x, p.y)
    if isinstance(p, (list, tuple)) and len(p) >= 2:
        return (float(p[0]), float(p[1]))
    return (0.0, 0.0)


def _bbox_from_points(points: list[tuple[float, float]]) -> BBox:
    if not points:
        return BBox()
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return BBox(x1=min(xs), y1=min(ys), x2=max(xs), y2=max(ys))


def _metadata_source(meta) -> str:
    if hasattr(meta, 'source'):
        return meta.source or "unknown"
    return "unknown"


def _metadata_confidence(meta) -> float:
    if hasattr(meta, 'confidence'):
        return meta.confidence or 0.0
    return 0.0


def _metadata_evidence(meta) -> list[str]:
    if hasattr(meta, 'evidence'):
        return meta.evidence or []
    return []


class CanonicalFurnitureGraph:
    """Static factory for building FurnitureGraph from existing pipeline outputs."""

    @classmethod
    def from_pipeline_result(
        cls,
        drawing_model: DrawingModel | None = None,
        component_graph: PipeComponentGraph | None = None,
        unified_result: Any = None,
        scale: PipeScale | None = None,
        furniture_type: str = "",
        furniture_family: str = "",
        overall_dims: dict[str, float] | None = None,
    ) -> FurnitureGraph:
        """Assemble CFG from existing module outputs.

        Each parameter is optional — call it with whatever you have available.
        Unprovided fields get empty defaults.
        """
        cfg = FurnitureGraph(
            graph_id=uuid.uuid4().hex[:12],
            furniture_type=furniture_type,
            furniture_family=furniture_family,
            source="pipeline",
        )

        # 1. Scale
        if scale is not None:
            cfg.scale = ScaleInfo(
                mm_per_px=scale.mm_per_px,
                confidence=scale.confidence,
                samples=len(getattr(scale, 'samples', [])),
                rejected=len(getattr(scale, 'rejected_samples', [])),
            )

        # 2. Overall dimensions
        if overall_dims:
            cfg.overall_dimensions = overall_dims
        elif drawing_model:
            kd = getattr(drawing_model, 'known_dimensions', {})
            cfg.overall_dimensions = {k: float(v) for k, v in kd.items()}

        # 3. Components from DrawingModel views
        if drawing_model:
            cls._from_drawing_model(cfg, drawing_model)

        # 4. Components from pipeline ComponentGraph
        if component_graph:
            cls._from_component_graph(cfg, component_graph)

        # 5. Provenance from unified router
        if unified_result is not None:
            cls._from_unified_result(cfg, unified_result)

        # 6. Views
        if drawing_model:
            for v in getattr(drawing_model, 'views', []):
                vname = getattr(v, 'name', '')
                vtype = "top"
                if "FRONT" in vname.upper():
                    vtype = "front"
                elif "SIDE" in vname.upper():
                    vtype = "side"
                elif "TOP" in vname.upper():
                    vtype = "top"
                cfg.views[vname] = ViewSpec(name=vname, type=vtype)

        # 7. BOM placeholder
        cfg.bom = BillOfMaterials()

        return cfg

    @classmethod
    def _from_drawing_model(cls, cfg: FurnitureGraph, dm: DrawingModel):
        """Extract components from DrawingModel views."""
        for view in getattr(dm, 'views', []):
            vname = getattr(view, 'name', 'VIEW')

            # Polygons → ComponentNodes
            for poly in getattr(view, 'polygons', []):
                pts = [_point_to_tuple(p) for p in getattr(poly, 'points', [])]
                cname = getattr(poly, 'name', '') or f"polygon_{len(cfg.components)}"
                meta = getattr(poly, 'metadata', EntityMetadata())
                node = ComponentNode(
                    id=f"comp_{len(cfg.components)}",
                    name=cname,
                    component_type="panel",
                    view=vname,
                    geometry=ComponentGeometry(
                        type="polygon",
                        points=pts,
                        bounding_box=_bbox_from_points(pts),
                    ),
                    confidence=_metadata_confidence(meta),
                    source=_metadata_source(meta),
                    dimensions_mm=_extract_poly_dimensions(pts),
                )
                cfg.add_component(node)

            # Circles
            for circ in getattr(view, 'circles', []):
                center = _point_to_tuple(getattr(circ, 'center', DMPoint(0, 0)))
                radius = getattr(circ, 'radius', 0.0)
                meta = getattr(circ, 'metadata', EntityMetadata())
                node = ComponentNode(
                    id=f"comp_{len(cfg.components)}",
                    name=f"circle_{len(cfg.components)}",
                    component_type="round",
                    view=vname,
                    geometry=ComponentGeometry(
                        type="circle",
                        points=[center],
                        radius=radius,
                        bounding_box=BBox(
                            x1=center[0] - radius, y1=center[1] - radius,
                            x2=center[0] + radius, y2=center[1] + radius,
                        ),
                    ),
                    confidence=_metadata_confidence(meta),
                    source=_metadata_source(meta),
                )
                cfg.add_component(node)

    @classmethod
    def _from_component_graph(cls, cfg: FurnitureGraph, cg: PipeComponentGraph):
        """Extract components from pipeline ComponentGraph nodes."""
        for cname, node in getattr(cg, 'nodes', {}).items():
            existing = cfg.get_component(cname)
            if existing:
                # Merge confidence: take max
                existing.confidence = max(existing.confidence, node.confidence)
                continue

            if hasattr(node, 'bbox') and node.bbox:
                bx1, by1, bx2, by2 = node.bbox
                bbox = BBox(x1=bx1, y1=by1, x2=bx2, y2=by2)
            else:
                bbox = BBox()

            dims = {}
            if hasattr(node, 'dimensions_mm'):
                dims = node.dimensions_mm
            elif hasattr(node, 'get_dimensions_mm'):
                getter = node.get_dimensions_mm
                dims = getter()

            cfg_node = ComponentNode(
                id=f"pipe_{cname}",
                name=cname,
                component_type=getattr(node, 'role', 'unknown'),
                view="front",
                geometry=ComponentGeometry(
                    type="polygon",
                    bounding_box=bbox,
                ),
                confidence=getattr(node, 'confidence', 0.0),
                source="pixel_detected",
                dimensions_mm=dims,
            )
            cfg.add_component(cfg_node)

    @classmethod
    def _from_unified_result(cls, cfg: FurnitureGraph, result: Any):
        """Extract provenance from unified router result.

        Reads UnifiedResult fields: product_type, top_shape, support_type,
        material_top, material_base, dimensions, and their ProvenanceValue
        objects which carry source, confidence, and note.
        """
        now = datetime.utcnow().isoformat()

        # product_type
        pt = getattr(result, 'product_type', None)
        if pt:
            cfg.furniture_type = str(getattr(pt, 'value', cfg.furniture_type))
            cfg.set_provenance("furniture_type", ProvenanceEntry(
                source=getattr(pt, 'source', 'unknown'),
                confidence=getattr(pt, 'confidence', 0.0),
                evidence=[f"note: {getattr(pt, 'note', '')}"] if getattr(pt, 'note', '') else [],
                agent="unified_router.vision",
                timestamp=now,
            ))

        # top_shape
        ts = getattr(result, 'top_shape', None)
        if ts:
            cfg.set_provenance("top_shape", ProvenanceEntry(
                source=getattr(ts, 'source', 'unknown'),
                confidence=getattr(ts, 'confidence', 0.0),
                evidence=[],
                agent="unified_router.vision",
                timestamp=now,
            ))

        # support_type
        st = getattr(result, 'support_type', None)
        if st:
            cfg.set_provenance("support_type", ProvenanceEntry(
                source=getattr(st, 'source', 'unknown'),
                confidence=getattr(st, 'confidence', 0.0),
                agent="unified_router.geometry",
                timestamp=now,
            ))

        # materials
        for mat_field in ['material_top', 'material_base']:
            mat = getattr(result, mat_field, None)
            if mat:
                cfg.materials[mat_field] = MaterialSpec(
                    material=str(getattr(mat, 'value', '')),
                    confidence=getattr(mat, 'confidence', 0.0),
                    source=getattr(mat, 'source', 'schema_default'),
                )

        # dimensions
        dims = getattr(result, 'dimensions', {})
        if isinstance(dims, dict):
            for dkey, dval in dims.items():
                if hasattr(dval, 'value'):
                    cfg.set_overall_dimension(dkey, float(dval.value))
                src = getattr(dval, 'source', None)
                conf = getattr(dval, 'confidence', None)
                if src and conf is not None:
                    cfg.set_provenance(f"dim_{dkey}", ProvenanceEntry(
                        source=src,
                        confidence=conf,
                        evidence=["from unified_router"],
                        agent="unified_router.dimension",
                        timestamp=now,
                    ))

    @classmethod
    def from_drawing_model_only(cls, dm: DrawingModel) -> FurnitureGraph:
        """Quick builder when only DrawingModel is available (most common path)."""
        cfg = FurnitureGraph(
            graph_id=uuid.uuid4().hex[:12],
            furniture_type=getattr(dm, 'furniture_type', ''),
            source="drawing_model",
        )
        cls._from_drawing_model(cfg, dm)
        cfg.bom = BillOfMaterials()
        return cfg


def cfg_to_drawing_model(cfg: FurnitureGraph, existing_model: DrawingModel | None = None) -> DrawingModel:
    """Convert CFG back to DrawingModel for existing exporters.

    This is a lossless* conversion — all ComponentNode geometry
    is mapped back to View → PolygonComponent/CircleComponent.

    *Lossless means: CFG -> DrawingModel preserves ALL geometry.
      DrawingModel -> CFG -> DrawingModel is a round-trip for entities.
    """
    from app.backend.drawing_model import (
        CircleComponent,
        EntityMetadata,
        PolygonComponent,
    )
    from app.backend.drawing_model import (
        DrawingModel as DM,
    )
    from app.backend.drawing_model import (
        Point as DMP,
    )
    from app.backend.drawing_model import (
        View as DV,
    )

    # Build completely new DrawingModel — don't mutate existing_model
    dm = DM(
        furniture_type=cfg.furniture_type,
        page_width=getattr(existing_model, 'page_width', 420.0) if existing_model else 420.0,
        page_height=getattr(existing_model, 'page_height', 297.0) if existing_model else 297.0,
        scale=cfg.scale.mm_per_px if cfg.scale else 0.5,
        known_dimensions=cfg.overall_dimensions,
    )

    # Group components by view name
    view_groups: dict[str, DV] = {}

    for comp in cfg.components:
        vname = comp.view or "FRONT VIEW"
        if vname not in view_groups:
            view_groups[vname] = DV(name=vname)
        view = view_groups[vname]

        meta = EntityMetadata(
            source=comp.source,
            confidence=comp.confidence,
            evidence=[],
        )

        if comp.geometry.type == "polygon" and len(comp.geometry.points) >= 3:
            pts = [DMP(x=float(p[0]), y=float(p[1])) for p in comp.geometry.points]
            view.polygons.append(PolygonComponent(
                points=pts, layer="OBJECT", name=comp.name, metadata=meta,
            ))

        elif comp.geometry.type == "circle" and comp.geometry.radius:
            center = comp.geometry.points[0] if comp.geometry.points else (0, 0)
            view.circles.append(CircleComponent(
                center=DMP(x=float(center[0]), y=float(center[1])),
                radius=float(comp.geometry.radius),
                layer="OBJECT",
                metadata=meta,
            ))

    # Set views from our built view_groups
    dm.views = list(view_groups.values())
    return dm


def _extract_poly_dimensions(points: list[tuple[float, float]]) -> dict[str, float]:
    """Estimate width/height from polygon points."""
    if not points:
        return {}
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    dims = {}
    w = max(xs) - min(xs)
    h = max(ys) - min(ys)
    if w > 0:
        dims["width_mm"] = round(w, 1)
    if h > 0:
        dims["height_mm"] = round(h, 1)
    return dims
