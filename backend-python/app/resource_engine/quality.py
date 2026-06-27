"""Quality Validator — scores scene completeness and correctness."""
from .schema import ParametricSceneGraph


class QualityValidator:
    """Validates a scene graph and assigns a quality score 0.0-1.0."""

    def validate(self, scene: ParametricSceneGraph) -> ParametricSceneGraph:
        score = 100

        # Required components
        roles = {c.role for c in scene.components}
        if "top" not in roles:
            scene.warnings.append("Quality: missing tabletop component.")
            score -= 30
        if "support" not in roles:
            scene.warnings.append("Quality: missing support/base component.")
            score -= 30
        if "joinery" not in roles:
            scene.warnings.append("Quality: no joinery component.")
            score -= 10

        # Materials
        if not scene.materials:
            scene.warnings.append("Quality: no materials defined.")
            score -= 10

        # Dim consistency for dining tables
        if scene.product_type in ("dining_table", "asymmetric_pedestal_table",
                                  "oval_pedestal_table", "rectangular_table"):
            top = next((c for c in scene.components if c.role == "top"), None)
            if top:
                L = top.parameters.get("length_mm", top.parameters.get("length_cm", 0) * 10)
                D = top.parameters.get("depth_mm", top.parameters.get("depth_cm", 0) * 10)
                if L < D:
                    scene.warnings.append("Quality: length is smaller than depth (suspicious).")
                    score -= 10

        # Rules
        if not scene.rules:
            scene.warnings.append("Quality: no construction rules applied.")
            score -= 10

        # Resource hits (evidence)
        if not scene.resource_hits:
            scene.warnings.append("Quality: no resource evidence recorded.")
            score -= 5

        scene.quality_score = max(0.0, min(1.0, score / 100))
        return scene
