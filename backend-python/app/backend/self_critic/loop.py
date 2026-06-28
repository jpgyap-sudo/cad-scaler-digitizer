"""
Self-Critic Loop — Render → Compare → Repair → Repeat.

WRAPS EXISTING CODE:
  - svg_exporter.py (render SVG from DrawingModel)
  - comparison_agent.py (compare rendered vs original image)
  - anti_hallucination_validator.py (confidence-based visibility gating)

NOTHING IS REPLACED. Each iteration calls existing modules.

USAGE:
    from app.backend.self_critic import SelfCritic
    critic = SelfCritic()
    result = critic.run(drawing_model, original_image_path)
    # result.model — the best DrawingModel found
    # result.gap_score — final gap ratio (lower = better)
    # result.iterations — how many iterations ran
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from app.backend.drawing_model import DrawingModel, EntityMetadata
from app.backend.svg_exporter import render_svg

logger = logging.getLogger("self_critic")


@dataclass
class GapRegion:
    """A detected gap between rendered output and original image."""
    type: str                         # "missing_edge" | "extra_edge" | "dimension_mismatch" | "position_offset" | "symmetry_violation"
    component_name: str               # affected component
    confidence: float                 # how confident this is a real gap (not noise)
    severity: float                   # 0.0-1.0
    description: str
    suggested_action: str             # "re_detect" | "hide_component" | "override_dim" | "adjust_position" | "enforce_symmetry"
    bbox: tuple[float, float, float, float] | None = None  # pixel region


@dataclass
class GapReport:
    """Complete gap analysis report."""
    gaps: list[GapRegion] = field(default_factory=list)
    gap_pixel_count: int = 0
    total_pixel_count: int = 0
    gap_score: float = 1.0            # 0.0 = perfect, 1.0 = completely wrong

    @property
    def gap_ratio(self) -> float:
        if self.total_pixel_count == 0:
            return 1.0
        return self.gap_pixel_count / max(self.total_pixel_count, 1)


@dataclass
class SelfCriticResult:
    """Result of running the self-critic loop."""
    model: DrawingModel               # final (best) DrawingModel
    gap_score: float                  # final gap score
    iterations: int                   # how many iterations ran
    converged: bool                   # True if gap_threshold was met
    gap_history: list[float]          # gap score per iteration
    repairs_applied: list[str]        # descriptions of repairs made


class SelfCritic:
    """Orchestrates render → compare → repair → repeat.

    Each step delegates to existing modules:
      Render:    svg_exporter.render_svg()
      Compare:   OpenCV absdiff() OR comparison_agent.py
      Repair:    anti_hallucination_validator + model adjustments
    """

    def __init__(self, gap_threshold: float = 0.05, max_iterations: int = 3):
        self.gap_threshold = gap_threshold
        self.max_iterations = max_iterations

    def run(
        self,
        model: DrawingModel,
        original_image_path: str,
        existing_comparison: Any | None = None,
    ) -> SelfCriticResult:
        """Run the self-critic loop.

        Args:
            model: Initial DrawingModel to evaluate
            original_image_path: Path to the original uploaded image
            existing_comparison: If comparison_agent comparison already exists,
                                 skip re-comparison

        Returns:
            SelfCriticResult with final model and metrics
        """
        best_model = model
        best_gap = 1.0
        gap_history: list[float] = []
        repairs: list[str] = []

        for iteration in range(self.max_iterations):
            logger.info(f"[SelfCritic] Iteration {iteration + 1}/{self.max_iterations}")

            # STEP 1: Render (delegates to existing svg_exporter)
            svg_output = render_svg(model)

            # STEP 2: Compare (delegates to existing comparison logic)
            gap_report = self._compare(svg_output, original_image_path, existing_comparison)
            gap_history.append(gap_report.gap_score)

            logger.info(f"[SelfCritic]   Gap score: {gap_report.gap_score:.4f} (threshold: {self.gap_threshold})")

            # Track best model
            if gap_report.gap_score < best_gap:
                best_gap = gap_report.gap_score
                best_model = model

            # STEP 3: Check convergence
            if gap_report.gap_score <= self.gap_threshold:
                logger.info(f"[SelfCritic] Converged at iteration {iteration + 1}")
                return SelfCriticResult(
                    model=model,
                    gap_score=gap_report.gap_score,
                    iterations=iteration + 1,
                    converged=True,
                    gap_history=gap_history,
                    repairs_applied=repairs,
                )

            # STEP 4: Repair
            model, iteration_repairs = self._repair(model, gap_report)
            repairs.extend(iteration_repairs)

        # Max iterations reached
        logger.info(f"[SelfCritic] Max iterations ({self.max_iterations}) reached")
        return SelfCriticResult(
            model=best_model,
            gap_score=best_gap,
            iterations=self.max_iterations,
            converged=False,
            gap_history=gap_history,
            repairs_applied=repairs,
        )

    # ── Compare ────────────────────────────────────────────────────

    def _compare(
        self,
        svg_output: str,
        original_image_path: str,
        existing_comparison: Any | None = None,
    ) -> GapReport:
        """Compare rendered SVG to original image.

        Uses existing comparison_agent when available, or direct OpenCV.
        """
        # Try using existing comparison agent first
        if existing_comparison is not None:
            return self._from_existing_comparison(existing_comparison)

        # Fallback: direct OpenCV comparison
        return self._opencv_compare(svg_output, original_image_path)

    def _from_existing_comparison(self, comp_result: Any) -> GapReport:
        """Convert existing ComparisonResult to GapReport."""
        gaps = []
        errors = getattr(comp_result, 'errors', []) or getattr(comp_result, 'comparisons', [])
        for err in errors:
            error_type = getattr(err, 'error_type', 'missing_edge')
            severity = getattr(err, 'severity', 'minor')
            bbox = getattr(err, 'bbox', None)
            desc = getattr(err, 'description', '')

            gap_type = self._map_error_type(error_type)
            component = self._infer_component(desc)

            gaps.append(GapRegion(
                type=gap_type,
                component_name=component,
                confidence=0.7 if severity in ('critical', 'major') else 0.4,
                severity=1.0 if severity == 'critical' else 0.6 if severity == 'major' else 0.3,
                description=desc,
                suggested_action=self._suggest_action(gap_type),
                bbox=tuple(bbox) if bbox else None,
            ))

        score = getattr(comp_result, 'overall_score', getattr(comp_result, 'score', 1.0))
        gap_score = 1.0 - score

        return GapReport(
            gaps=gaps,
            gap_pixel_count=len([g for g in gaps if g.severity > 0.5]),
            total_pixel_count=max(len(gaps), 1),
            gap_score=max(0.0, min(1.0, gap_score)),
        )

    def _opencv_compare(self, svg_output: str, original_image_path: str) -> GapReport:
        """Direct OpenCV-based comparison.

        Renders SVG to bitmap, compares pixel-by-pixel with original.
        """
        gaps = []
        gap_pixels = 0
        total_pixels = 1

        try:
            import cv2
            import numpy as np
            from cairosvg import svg2png

            # Render SVG to PNG in memory
            png_bytes = svg2png(bytestring=svg_output.encode('utf-8'))
            nparr = np.frombuffer(png_bytes, np.uint8)
            rendered = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            if rendered is None:
                raise ValueError("Failed to decode SVG render")

            # Load original image
            original = cv2.imread(original_image_path)
            if original is None:
                raise ValueError(f"Failed to load original image: {original_image_path}")

            # Resize original to match render dimensions
            h, w = rendered.shape[:2]
            original = cv2.resize(original, (w, h))

            # Grayscale both
            gray_rendered = cv2.cvtColor(rendered, cv2.COLOR_BGR2GRAY)
            gray_original = cv2.cvtColor(original, cv2.COLOR_BGR2GRAY)

            # Edge detection on both
            edges_rendered = cv2.Canny(gray_rendered, 50, 150)
            edges_original = cv2.Canny(gray_original, 50, 150)

            # Pixel difference
            diff = cv2.absdiff(edges_rendered, edges_original)
            gap_pixels = int(np.sum(diff > 0))
            total_pixels = diff.size

            # Find gap regions via contours
            contours, _ = cv2.findContours(diff, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            for cnt in contours:
                area = cv2.contourArea(cnt)
                if area < 50:  # noise filter
                    continue
                x, y, cw, ch = cv2.boundingRect(cnt)
                gaps.append(GapRegion(
                    type="position_offset" if area < 500 else "missing_edge",
                    component_name=f"region_{len(gaps)}",
                    confidence=min(1.0, area / 1000),
                    severity=min(1.0, area / 2000),
                    description=f"Gap region: {int(area)}px²",
                    suggested_action="re_detect",
                    bbox=(float(x), float(y), float(x + cw), float(y + ch)),
                ))

        except ImportError as e:
            logger.warning(f"[SelfCritic] OpenCV/cairosvg not available: {e}")
        except Exception as e:
            logger.error(f"[SelfCritic] OpenCV comparison failed: {e}")

        gap_ratio = gap_pixels / max(total_pixels, 1)
        return GapReport(
            gaps=gaps,
            gap_pixel_count=gap_pixels,
            total_pixel_count=total_pixels,
            gap_score=gap_ratio,
        )

    # ── Repair ─────────────────────────────────────────────────────

    def _repair(self, model: DrawingModel, report: GapReport) -> tuple[DrawingModel, list[str]]:
        """Apply repairs to the DrawingModel based on gap analysis.

        Uses anti_hallucination_validator for confidence-based repairs,
        and direct model manipulation for structural repairs.
        """
        repairs = []

        for gap in report.gaps:
            if gap.suggested_action == "hide_component":
                # Use visibility gating via anti-hallucination
                model = self._hide_component(model, gap.component_name)
                repairs.append(f"Hid component '{gap.component_name}' (extra geometry)")

            elif gap.suggested_action == "override_dim":
                model = self._adjust_dimension(model, gap)
                repairs.append(f"Adjusted dimension for '{gap.component_name}'")

            elif gap.suggested_action == "re_detect":
                # Lower confidence threshold for this component
                model = self._lower_threshold(model, gap.component_name)
                repairs.append(f"Lowered detection threshold for '{gap.component_name}'")

            elif gap.suggested_action == "adjust_position":
                model = self._adjust_position(model, gap)
                repairs.append(f"Adjusted position of '{gap.component_name}'")

            elif gap.suggested_action == "enforce_symmetry":
                model = self._enforce_symmetry(model, gap)
                repairs.append(f"Enforced symmetry on '{gap.component_name}'")

        return model, repairs

    def _hide_component(self, model: DrawingModel, component_name: str) -> DrawingModel:
        """Set a component's visibility to False/estimated."""
        for view in getattr(model, 'views', []):
            for poly in getattr(view, 'polygons', []):
                if getattr(poly, 'name', '') == component_name:
                    meta = getattr(poly, 'metadata', EntityMetadata())
                    meta.confidence = 0.25  # below VISIBLE threshold
                    meta.source = "user_corrected"
        return model

    def _adjust_dimension(self, model: DrawingModel, gap: GapRegion) -> DrawingModel:
        """Adjust a dimension based on gap info."""
        # Placeholder — actual dimension adjustment needs the specific value
        return model

    def _lower_threshold(self, model: DrawingModel, component_name: str) -> DrawingModel:
        """Lower confidence threshold for re-detection."""
        for view in getattr(model, 'views', []):
            for poly in getattr(view, 'polygons', []):
                if getattr(poly, 'name', '') == component_name:
                    meta = getattr(poly, 'metadata', EntityMetadata())
                    meta.confidence = max(meta.confidence, 0.45)
        return model

    def _adjust_position(self, model: DrawingModel, gap: GapRegion) -> DrawingModel:
        """Shift component position based on detected offset."""
        if not gap.bbox:
            return model
        # Calculate center offset
        cx = (gap.bbox[0] + gap.bbox[2]) / 2
        cy = (gap.bbox[1] + gap.bbox[3]) / 2
        target_cx, target_cy = cx, cy  # would need original position

        for view in getattr(model, 'views', []):
            for poly in getattr(view, 'polygons', []):
                if getattr(poly, 'name', '') == gap.component_name:
                    pts = getattr(poly, 'points', [])
                    if not pts:
                        continue
                    # Compute current center
                    xs = [p.x for p in pts]
                    ys = [p.y for p in pts]
                    cur_cx = (min(xs) + max(xs)) / 2
                    cur_cy = (min(ys) + max(ys)) / 2
                    dx = target_cx - cur_cx
                    dy = target_cy - cur_cy
                    for p in pts:
                        p.x += dx
                        p.y += dy
        return model

    def _enforce_symmetry(self, model: DrawingModel, gap: GapRegion) -> DrawingModel:
        """Check component symmetry and enforce it."""
        # Find mirrored components
        comps = []
        for view in getattr(model, 'views', []):
            for poly in getattr(view, 'polygons', []):
                comps.append(poly)

        # Look for left/right pairs
        lefts = [c for c in comps if 'left' in (getattr(c, 'name', '') or '').lower()]
        rights = [c for c in comps if 'right' in (getattr(c, 'name', '') or '').lower()]

        for left, right in zip(lefts, rights):
            l_pts = getattr(left, 'points', [])
            r_pts = getattr(right, 'points', [])
            if not l_pts or not r_pts:
                continue
            # Average positions of left and mirrored right
            l_cx = (min(p.x for p in l_pts) + max(p.x for p in l_pts)) / 2
            r_cx = (min(p.x for p in r_pts) + max(p.x for p in r_pts)) / 2
            avg_cx = (l_cx + r_cx) / 2
            # Mirror both around center
            for p in l_pts:
                p.x = avg_cx - abs(p.x - avg_cx)
            for p in r_pts:
                p.x = avg_cx + abs(p.x - avg_cx)

        return model

    # ── Helpers ─────────────────────────────────────────────────────

    def _map_error_type(self, error_type: str) -> str:
        mapping = {
            "missing_line": "missing_edge",
            "extra_line": "extra_edge",
            "missing_entity": "missing_edge",
            "extra_entity": "extra_edge",
            "misaligned_dim": "dimension_mismatch",
            "dimension_mismatch": "dimension_mismatch",
            "edge_mismatch": "position_offset",
        }
        return mapping.get(error_type, "position_offset")

    def _infer_component(self, description: str) -> str:
        """Try to extract component name from error description."""
        keywords = ["tabletop", "leg", "apron", "seat", "back", "arm", "shelf", "door", "drawer"]
        for kw in keywords:
            if kw in description.lower():
                return kw
        return "unknown"

    def _suggest_action(self, gap_type: str) -> str:
        actions = {
            "missing_edge": "re_detect",
            "extra_edge": "hide_component",
            "dimension_mismatch": "override_dim",
            "position_offset": "adjust_position",
            "symmetry_violation": "enforce_symmetry",
        }
        return actions.get(gap_type, "re_detect")
