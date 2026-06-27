"""Scene Graph Builder — maps detected features to library resources."""
from typing import Dict, Any, List, Optional
from .schema import ParametricSceneGraph, SceneComponent, ResourceHit, VisionFeatureSet
from .library import ResourceLibrary
from .quality import QualityValidator

# Map furniture_type -> geometry, support resource IDs
TYPE_GEOMETRY_MAP = {
    "asymmetric_pedestal_table": "geometry.rectangular_top.v1",
    "oval_pedestal_table": "geometry.oval_top.v1",
    "rectangular_table": "geometry.rectangular_top.v1",
    "round_pedestal_table": "geometry.round_top.v1",
    "console_table": "geometry.rectangular_top.v1",
    "office_desk": "geometry.rectangular_top.v1",
}

TYPE_SUPPORT_MAP = {
    "asymmetric_pedestal_table": "supports.dual_cylindrical_pedestal.v1",
    "oval_pedestal_table": "supports.single_pedestal.v1",
    "round_pedestal_table": "supports.single_pedestal.v1",
    "rectangular_table": "supports.four_leg.v1",
    "console_table": "supports.four_leg.v1",
    "office_desk": "supports.four_leg.v1",
}


class ResourceIntelligenceEngine:
    """Builds a scene graph from detected features."""

    def __init__(self, library: ResourceLibrary):
        self.library = library
        self.validator = QualityValidator()

    def build_scene(self, features: VisionFeatureSet) -> ParametricSceneGraph:
        """Build a scene graph from a VisionFeatureSet."""
        components = []
        hits = []

        # === Deterministic mapping ===
        geo_id = TYPE_GEOMETRY_MAP.get(features.product_type, "geometry.rectangular_top.v1")
        sup_id = TYPE_SUPPORT_MAP.get(features.product_type, "supports.four_leg.v1")

        geo_res = self.library.get(geo_id)
        sup_res = self.library.get(sup_id)

        # Top parameters from features or defaults
        top_params = self._top_params(features)
        components.append(SceneComponent(role="top", resource_id=geo_id, parameters=top_params, confidence=0.85))
        hits.append(ResourceHit(resource_id=geo_id, score=0.85, reason=f"Detected {features.product_type}"))

        # Support parameters
        sup_params = self._support_params(features)
        components.append(SceneComponent(role="support", resource_id=sup_id, parameters=sup_params, confidence=0.80))
        hits.append(ResourceHit(resource_id=sup_id, score=0.80, reason="Matched support type"))

        # Joinery
        joinery_params = {"frame_inset_mm": 120, "plate_thickness_mm": 8, "bolt_count": 8}
        components.append(SceneComponent(role="joinery", resource_id="joinery.hidden_steel_frame.v1", parameters=joinery_params, confidence=0.75))
        hits.append(ResourceHit(resource_id="joinery.hidden_steel_frame.v1", score=0.75, reason="Stone top needs hidden support frame"))

        # Materials
        materials = self._material_components(features)
        for m in materials:
            hits.append(ResourceHit(resource_id=m.resource_id, score=m.confidence, reason=f"Material: {m.role}"))

        # Rules
        rules = ["rules.dining_table.v1"]
        if features.product_type == "office_desk":
            rules = ["rules.office_desk.v1"]

        scene = ParametricSceneGraph(
            product_type=features.product_type,
            drawing_type="shopdrawing",
            style="homeu_modern",
            units="mm",
            components=components,
            materials=materials,
            rules=rules,
            resource_hits=hits,
        )

        # Run validation
        scene = self.validator.validate(scene)
        return scene

    def build_from_dims(self, ftype: str, dims_cm: Dict[str, float],
                        materials: Optional[Dict[str, str]] = None,
                        library: Optional[ResourceLibrary] = None) -> ParametricSceneGraph:
        """Build scene from existing classification + dimensions (backward compat)."""
        features = VisionFeatureSet(
            product_type=ftype,
            style_keywords=[ftype.replace("_", " ")],
            confidence=0.85,
        )
        # Fill top params from dims
        scene = self.build_scene(features)
        top = self._get(scene, "top")
        support = self._get(scene, "support")
        if top:
            l = dims_cm.get("length_cm", dims_cm.get("width_cm", 180))
            d = dims_cm.get("depth_cm", 90)
            t = dims_cm.get("top_thickness_cm", dims_cm.get("thickness_cm", 3))
            top.parameters["length_mm"] = int(l * 10)
            top.parameters["depth_mm"] = int(d * 10)
            top.parameters["thickness_mm"] = int(t * 10)
        if support:
            h = dims_cm.get("overall_height_cm", dims_cm.get("height_cm", 75))
            top_t = dims_cm.get("top_thickness_cm", 3)
            support.parameters["height_mm"] = int((h - top_t) * 10)
            if ftype == "asymmetric_pedestal_table":
                support.parameters["large_diameter_mm"] = int(dims_cm.get("large_ped_dia_cm", 40) * 10)
                support.parameters["small_diameter_mm"] = int(dims_cm.get("small_ped_dia_cm", 22) * 10)
                support.parameters["left_x_offset_mm"] = int(dims_cm.get("left_ped_x_cm", 30) * 10)
                support.parameters["right_x_offset_mm"] = int(dims_cm.get("right_ped_x_cm", -25) * 10)
        return scene

    # --- Private helpers ---

    def _get(self, scene: ParametricSceneGraph, role: str):
        for c in scene.components:
            if c.role == role:
                return c
        return None

    def _top_params(self, features: VisionFeatureSet) -> Dict[str, Any]:
        return {"length_mm": 1800, "depth_mm": 900, "thickness_mm": 30}

    def _support_params(self, features: VisionFeatureSet) -> Dict[str, Any]:
        return {"height_mm": 720}

    def _material_components(self, features: VisionFeatureSet) -> List[SceneComponent]:
        mats = []
        if features.material_top:
            mats.append(SceneComponent(role="top_material", resource_id="materials.stone.white_marble.v1", confidence=0.80, parameters={}))
        if features.material_base:
            mats.append(SceneComponent(role="base_material", resource_id="materials.metal.brushed_black.v1", confidence=0.75, parameters={}))
        if not mats:
            mats.append(SceneComponent(role="top_material", resource_id="materials.stone.white_marble.v1", confidence=0.60, parameters={}))
            mats.append(SceneComponent(role="base_material", resource_id="materials.metal.brushed_black.v1", confidence=0.55, parameters={}))
        return mats


# Backward compat function
def build_scene_graph(ftype: str, dims: Dict[str, float],
                      materials: Optional[Dict[str, str]] = None,
                      library: Optional[ResourceLibrary] = None) -> ParametricSceneGraph:
    lib = library or ResourceLibrary().load()
    engine = ResourceIntelligenceEngine(lib)
    return engine.build_from_dims(ftype, dims, materials, lib)
