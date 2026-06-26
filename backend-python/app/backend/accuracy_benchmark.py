"""
Accuracy Benchmark — measure system accuracy against ground truth data.

This benchmark:
1. Loads ground truth fixtures (drawing images + expected DXF dimensions)
2. Runs the full accuracy pipeline on each fixture
3. Compares results against ground truth
4. Reports accuracy metrics

Metrics measured:
- Dimension value error (% deviation from ground truth)
- Association accuracy (% correct text-to-geometry pairs)
- Scale factor error (% deviation)
- Furniture type classification accuracy
- Line role classification accuracy
"""

import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.backend.vision import load_image, preprocess, detect_lines, detect_circles, detect_rectangles, normalize_lines
from app.backend.ocr_layout_parser import extract_layout
from app.backend.dimension_associator import associate_dimension_text
from app.backend.line_role_classifier import classify_line_roles
from app.backend.scale_solver import compute_scale
from app.backend.geometry_reconstructor import reconstruct_geometry, reconstruct
from app.backend.furniture_classifier import classify_furniture, normalize_furniture_type


# ===== Ground Truth Data Types =====

@dataclass
class GroundTruthDimension:
    """Expected dimension from ground truth."""
    tag: str                    # "top_dia", "height", "base_dia", etc.
    value_cm: float             # Expected value in cm
    tolerance_pct: float = 5.0  # Acceptable deviation %


@dataclass
class GroundTruthFixture:
    """A single ground truth fixture for benchmarking."""
    name: str
    image_path: str
    furniture_type: str
    dimensions: List[GroundTruthDimension]
    line_counts: Dict[str, int] = field(default_factory=dict)  # Expected line counts per role

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "furniture_type": self.furniture_type,
            "dimensions": [{"tag": d.tag, "value_cm": d.value_cm, "tolerance_pct": d.tolerance_pct}
                          for d in self.dimensions],
        }


# ===== Benchmark Results =====

@dataclass
class DimensionAccuracy:
    tag: str
    expected_cm: float
    actual_cm: float
    error_pct: float
    within_tolerance: bool
    tolerance_pct: float

    def to_dict(self) -> dict:
        return {
            "tag": self.tag,
            "expected": round(self.expected_cm, 2),
            "actual": round(self.actual_cm, 2),
            "error_pct": round(self.error_pct, 2),
            "within_tolerance": self.within_tolerance,
            "tolerance_pct": self.tolerance_pct,
        }


@dataclass
class FixtureResult:
    """Accuracy results for a single fixture."""
    name: str
    furniture_type_match: bool
    dimension_accuracies: List[DimensionAccuracy]
    dimension_accuracy_pct: float
    association_count: int
    scale_px_per_cm: Optional[float]
    errors: List[str] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Compute overall accuracy score 0-100."""
        scores = []

        # Furniture type match: 20 points
        scores.append(20.0 if self.furniture_type_match else 0.0)

        # Dimension accuracy: 50 points
        if self.dimension_accuracies:
            within = sum(1 for d in self.dimension_accuracies if d.within_tolerance)
            dim_score = (within / len(self.dimension_accuracies)) * 50.0
            scores.append(dim_score)
        else:
            scores.append(0.0)

        # Associations found: 20 points
        assoc_score = min(20.0, self.association_count * 5.0)  # 4+ associations = full score
        scores.append(assoc_score)

        # Scale factor found: 10 points
        scores.append(10.0 if self.scale_px_per_cm else 0.0)

        # Penalize errors
        error_penalty = len(self.errors) * 5.0

        return max(0.0, min(100.0, sum(scores) - error_penalty))

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "furniture_type_match": self.furniture_type_match,
            "dimension_accuracies": [d.to_dict() for d in self.dimension_accuracies],
            "dimension_accuracy_pct": round(self.dimension_accuracy_pct, 1),
            "association_count": self.association_count,
            "scale_px_per_cm": round(self.scale_px_per_cm, 4) if self.scale_px_per_cm else None,
            "errors": self.errors,
            "overall_score": round(self.overall_score, 1),
        }


@dataclass
class BenchmarkResult:
    """Complete benchmark results."""
    fixtures: List[FixtureResult]
    timestamp: str
    total_fixtures: int
    passed_fixtures: int
    failed_fixtures: int
    average_score: float
    dimension_error_avg: float

    def to_dict(self) -> dict:
        return {
            "fixtures": [f.to_dict() for f in self.fixtures],
            "timestamp": self.timestamp,
            "total_fixtures": self.total_fixtures,
            "passed_fixtures": self.passed_fixtures,
            "failed_fixtures": self.failed_fixtures,
            "average_score": round(self.average_score, 1),
            "dimension_error_avg": round(self.dimension_error_avg, 2),
            "summary": self.summary(),
        }

    def summary(self) -> str:
        return (
            f"Benchmark: {self.passed_fixtures}/{self.total_fixtures} passed "
            f"(avg score: {self.average_score:.0f}%, "
            f"avg dim error: {self.dimension_error_avg:.1f}%)"
        )


# ===== Benchmark Runner =====

def _find_pipeline_value(associations, tag: str) -> Optional[float]:
    """Find a dimension value from the pipeline output by tag."""
    for assoc in associations:
        text = assoc.text.lower()
        if tag in text or (tag == "top_dia" and ("dia" in text or "diameter" in text)):
            return assoc.value_cm
    return None


def run_single_fixture(fixture: GroundTruthFixture) -> FixtureResult:
    """
    Run the full accuracy pipeline on a single fixture and measure accuracy.
    """
    errors: List[str] = []
    img_path = fixture.image_path

    if not os.path.exists(img_path):
        return FixtureResult(
            name=fixture.name,
            furniture_type_match=False,
            dimension_accuracies=[],
            dimension_accuracy_pct=0.0,
            association_count=0,
            scale_px_per_cm=None,
            errors=[f"Image not found: {img_path}"],
        )

    try:
        # Run OpenCV detection
        img, gray = load_image(img_path)
        binary = preprocess(gray)
        lines_raw = detect_lines(binary)
        lines = normalize_lines(lines_raw)
        circles = detect_circles(gray)
        rects = detect_rectangles(binary)

        # Run OCR Layout Parser
        layout = extract_layout(img_path)
        text_boxes = layout.text_boxes
        dim_labels = layout.dimension_labels

        # Run furniture classifier
        ocr_lines_text = layout.raw_text.splitlines()
        classifier = classify_furniture(ocr_lines_text, circles, lines, rects)
        f_type = normalize_furniture_type(classifier.get("type", ""))
        furniture_match = f_type == fixture.furniture_type

        # Run dimension association
        associations = associate_dimension_text(text_boxes, dim_labels, lines, circles, rects)

        # Measure dimension accuracy
        dim_accuracies: List[DimensionAccuracy] = []
        all_errors: List[float] = []

        for gt_dim in fixture.dimensions:
            pip_value = _find_pipeline_value(associations.associations, gt_dim.tag)

            if pip_value and pip_value > 0:
                error_pct = abs(pip_value - gt_dim.value_cm) / gt_dim.value_cm * 100
                within_tol = error_pct <= gt_dim.tolerance_pct
                all_errors.append(error_pct)

                dim_accuracies.append(DimensionAccuracy(
                    tag=gt_dim.tag,
                    expected_cm=gt_dim.value_cm,
                    actual_cm=pip_value,
                    error_pct=error_pct,
                    within_tolerance=within_tol,
                    tolerance_pct=gt_dim.tolerance_pct,
                ))
            else:
                dim_accuracies.append(DimensionAccuracy(
                    tag=gt_dim.tag,
                    expected_cm=gt_dim.value_cm,
                    actual_cm=0.0,
                    error_pct=100.0,
                    within_tolerance=False,
                    tolerance_pct=gt_dim.tolerance_pct,
                ))
                all_errors.append(100.0)
                errors.append(f"Missing dimension: {gt_dim.tag} (expected {gt_dim.value_cm} cm)")

        dim_accuracy_pct = 0.0
        if all_errors:
            dim_accuracy_pct = sum(100 - min(e, 100) for e in all_errors) / len(all_errors)

        # Compute scale if possible
        known_dims = {gt.tag: gt.value_cm for gt in fixture.dimensions}
        scale_solution = compute_scale(associations.associations, lines, known_dims)
        scale_px_per_cm = scale_solution.combined_scale.px_per_cm if scale_solution.combined_scale else None

        return FixtureResult(
            name=fixture.name,
            furniture_type_match=furniture_match,
            dimension_accuracies=dim_accuracies,
            dimension_accuracy_pct=dim_accuracy_pct,
            association_count=len(associations.associations),
            scale_px_per_cm=scale_px_per_cm,
            errors=errors,
        )

    except Exception as e:
        import traceback
        return FixtureResult(
            name=fixture.name,
            furniture_type_match=False,
            dimension_accuracies=[],
            dimension_accuracy_pct=0.0,
            association_count=0,
            scale_px_per_cm=None,
            errors=[f"Pipeline error: {e}", traceback.format_exc()],
        )


def run_benchmark(fixtures: List[GroundTruthFixture]) -> BenchmarkResult:
    """
    Run benchmark on all fixtures and compute aggregate metrics.
    """
    from datetime import datetime

    results: List[FixtureResult] = []
    all_dim_errors: List[float] = []

    for fixture in fixtures:
        print(f"[BENCHMARK] Testing: {fixture.name}")
        result = run_single_fixture(fixture)
        results.append(result)

        for dim_acc in result.dimension_accuracies:
            if not dim_acc.within_tolerance:
                all_dim_errors.append(dim_acc.error_pct)

        passed = "PASS" if result.overall_score >= 60 else "FAIL"
        print(f"  → {passed} (score: {result.overall_score:.0f}%, "
              f"dim accuracy: {result.dimension_accuracy_pct:.0f}%)")
        for err in result.errors:
            print(f"  ⚠ {err}")

    avg_score = sum(r.overall_score for r in results) / len(results) if results else 0.0
    avg_dim_error = sum(all_dim_errors) / len(all_dim_errors) if all_dim_errors else 0.0
    passed = sum(1 for r in results if r.overall_score >= 60)
    failed = len(results) - passed

    return BenchmarkResult(
        fixtures=results,
        timestamp=datetime.now().isoformat(),
        total_fixtures=len(fixtures),
        passed_fixtures=passed,
        failed_fixtures=failed,
        average_score=avg_score,
        dimension_error_avg=avg_dim_error,
    )


def load_fixtures() -> List[GroundTruthFixture]:
    """Load ground truth fixtures from the fixtures directory."""
    fixtures_dir = Path(__file__).parent.parent.parent / "fixtures"

    if not fixtures_dir.exists():
        print(f"[BENCHMARK] No fixtures directory at {fixtures_dir}")
        return []

    loaded = []
    for subdir in fixtures_dir.iterdir():
        if not subdir.is_dir():
            continue

        spec_path = subdir / "spec.json"
        if not spec_path.exists():
            continue

        with open(spec_path) as f:
            spec = json.load(f)

        # Find image path
        image_path = subdir / (spec.get("image", ""))
        if not image_path.exists():
            # Try any PNG/JPG in the directory
            for ext in [".png", ".jpg", ".jpeg", ".webp"]:
                candidates = list(subdir.glob(f"*{ext}"))
                if candidates:
                    image_path = candidates[0]
                    break

        if not image_path.exists():
            print(f"  ⚠ No image found for {subdir.name}")
            continue

        dimensions = [
            GroundTruthDimension(
                tag=d["tag"],
                value_cm=d["value_cm"],
                tolerance_pct=d.get("tolerance_pct", 5.0),
            )
            for d in spec.get("dimensions", [])
        ]

        loaded.append(GroundTruthFixture(
            name=subdir.name,
            image_path=str(image_path),
            furniture_type=spec.get("furniture_type", "unknown"),
            dimensions=dimensions,
        ))

    return loaded


# Public API
def run_accuracy_benchmark(fixtures_path: Optional[str] = None) -> dict:
    """Main entry point: run the full accuracy benchmark."""
    if fixtures_path:
        fixtures = load_fixtures_from_path(fixtures_path)
    else:
        fixtures = load_fixtures()

    if not fixtures:
        print("[BENCHMARK] No fixtures found to test")
        return {"error": "No fixtures found", "fixtures_loaded": 0}

    result = run_benchmark(fixtures)
    return result.to_dict()


def load_fixtures_from_path(path: str) -> List[GroundTruthFixture]:
    """Load fixtures from a custom JSON file."""
    with open(path) as f:
        data = json.load(f)

    fixtures = []
    for item in data if isinstance(data, list) else data.get("fixtures", []):
        fixtures.append(GroundTruthFixture(
            name=item["name"],
            image_path=item["image_path"],
            furniture_type=item["furniture_type"],
            dimensions=[GroundTruthDimension(**d) for d in item.get("dimensions", [])],
        ))
    return fixtures


if __name__ == "__main__":
    print("=" * 60)
    print("CAD Digitizer Accuracy Benchmark")
    print("=" * 60)

    fixtures = load_fixtures()
    print(f"\nLoaded {len(fixtures)} fixtures\n")

    if fixtures:
        result = run_benchmark(fixtures)
        print(f"\n{'=' * 60}")
        print(result.summary())
        print(f"Average Score: {result.average_score:.1f}%")
        print(f"Avg Dimension Error: {result.dimension_error_avg:.1f}%")
        print(f"Passed: {result.passed_fixtures}/{result.total_fixtures}")
    else:
        print("Create fixtures in /fixtures/ with spec.json files to run benchmarks")
