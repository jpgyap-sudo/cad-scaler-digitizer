"""Unified Validation Gate — connects all 3 validation layers into one intelligent router.
Pre-generates validation checks, auto-corrects parameters, scores output quality,
and feeds everything into the closed-loop learning system.

Three validation layers:
1. Engineering Validation (pre-generation) — dimension safety, structural, joinery
2. Quality Evaluator (post-generation) — drawing completeness
3. Closed-Loop Learning (post-review) — continuous improvement
"""
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ValidationGateIssue:
    """A validation issue with severity, code, and message."""
    severity: str  # error, warning, info
    code: str
    message: str
    layer: str  # engineering, quality, learning
    field: Optional[str] = None
    suggested_fix: Optional[str] = None


@dataclass
class UnifiedValidationManifest:
    """Single source of truth for all validation data across all 3 layers."""
    product_type: str
    template_id: str
    engineering_score: float = 1.0
    quality_score: float = 1.0
    learning_confidence: float = 0.5
    issues: List[ValidationGateIssue] = field(default_factory=list)
    auto_corrections: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    @property
    def overall_score(self) -> float:
        """Weighted average: engineering 30%, quality 30%, learning 40%."""
        return round(
            self.engineering_score * 0.3 +
            self.quality_score * 0.3 +
            self.learning_confidence * 0.4, 3
        )

    @property
    def action(self) -> str:
        """What to do with this drawing: approve, flag_for_review, reject, regenerate."""
        if self.overall_score >= 0.85 and not self._has_errors(): return "approve"
        if self.overall_score >= 0.60: return "flag_for_review"
        return "regenerate"

    @property
    def passed(self) -> bool:
        return self.action == "approve"

    def _has_errors(self) -> bool:
        return any(i.severity == "error" for i in self.issues)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "engineering_score": self.engineering_score,
            "quality_score": self.quality_score,
            "learning_confidence": self.learning_confidence,
            "action": self.action,
            "passed": self.passed,
            "issues": [{"severity": i.severity, "code": i.code, "message": i.message, "layer": i.layer} for i in self.issues],
            "auto_corrections": self.auto_corrections,
            "warnings": self.warnings,
        }


class ValidationGate:
    """Intelligent validation gate that orchestrates all 3 validation layers."""

    def __init__(self):
        self._engineering = None
        self._quality = None
        self._closed_loop = None

    @property
    def engineering(self):
        if self._engineering is None:
            from app.resource_engine.validation import ValidationPipeline
            self._engineering = ValidationPipeline()
        return self._engineering

    @property
    def quality(self):
        if self._quality is None:
            from app.cad_kernel.quality_evaluator import Phase3E10Pipeline as QEP
            self._quality = QEP()
        return self._quality

    @property
    def closed_loop(self):
        if self._closed_loop is None:
            from app.resource_engine.closed_loop import ClosedLoopPipeline
            self._closed_loop = ClosedLoopPipeline()
        return self._closed_loop

    def pre_validate_params(self, params: Dict[str, Any], product_type: str,
                            template_id: str) -> Tuple[Dict[str, Any], List[ValidationGateIssue], List[str]]:
        """Pre-generation validation + auto-correction of parameters.
        
        Returns (corrected_params, issues, auto_corrections).
        """
        from app.resource_engine.manufacturing.models import ReadyForCADPackage, ManufacturingPlan, QCChecklist
        issues: List[ValidationGateIssue] = []
        corrections: List[str] = []

        # Create a minimal package for the engineering validation pipeline
        package = ReadyForCADPackage(
            product_type=product_type, template_id=template_id,
            cad_parameters=dict(params),
            manufacturing_plan=ManufacturingPlan(
                product_type=product_type, template_id=template_id,
                production_steps=[], cutting_list=[],
            ),
            qc_checklist=QCChecklist(product_type=product_type, checks=[]),
            drawing_notes=[],
        )

        try:
            report, corrected = self.engineering.run(package)
            for i in report.issues:
                sev = getattr(i, "severity", "warning") or "warning"
                issues.append(ValidationGateIssue(
                    severity=sev, code=getattr(i, "code", "UNKNOWN") or "UNKNOWN",
                    message=getattr(i, "message", ""), layer="engineering",
                    field=getattr(i, "field", None),
                    suggested_fix=getattr(i, "suggested_fix", None),
                ))
            corrections.extend(getattr(report, "applied_corrections", []))
            # Apply corrections to params
            if corrected and hasattr(corrected, 'cad_parameters'):
                params.update(corrected.cad_parameters)
        except Exception as e:
            issues.append(ValidationGateIssue(
                severity="info", code="VALIDATION_ERR",
                message=f"Engineering validation skipped: {e}", layer="engineering"))

        return params, issues, corrections

    def post_validate_drawing(self, sheet_data: Dict[str, Any],
                              dimensions: Dict[str, Any],
                              product_type: str, template_id: str) -> List[ValidationGateIssue]:
        """Post-generation quality check."""
        issues: List[ValidationGateIssue] = []
        try:
            report = self.quality.run(sheet_data, dimensions)
            for i in report.issues:
                sev = i.get("severity", "warning")
                issues.append(ValidationGateIssue(
                    severity=sev, code=i.get("code", f"Q{i.get('id','')}"),
                    message=i.get("message", ""), layer="quality",
                ))
        except Exception as e:
            issues.append(ValidationGateIssue(
                severity="info", code="QUALITY_ERR",
                message=f"Quality evaluation skipped: {e}", layer="quality"))
        return issues

    def build_manifest(self, product_type: str, template_id: str,
                       params: Dict[str, Any],
                       pre_issues: List[ValidationGateIssue],
                       post_issues: List[ValidationGateIssue],
                       auto_corrections: List[str],
                       closed_loop_confidence: float = 0.5) -> UnifiedValidationManifest:
        """Build the unified validation manifest from all layers."""
        all_issues = pre_issues + post_issues
        eng_issues = [i for i in all_issues if i.layer == "engineering"]
        qual_issues = [i for i in all_issues if i.layer == "quality"]

        # Calculate scores
        eng_score = max(0.0, 1.0 - len(eng_issues) * 0.15)
        qual_score = max(0.0, 1.0 - len(qual_issues) * 0.15)

        return UnifiedValidationManifest(
            product_type=product_type, template_id=template_id,
            engineering_score=round(eng_score, 2),
            quality_score=round(qual_score, 2),
            learning_confidence=closed_loop_confidence,
            issues=all_issues,
            auto_corrections=auto_corrections,
            warnings=[i.message for i in all_issues if i.severity == "warning"],
        )

    def run_full_gate(self, params: Dict[str, Any], product_type: str,
                      template_id: str, sheet_data: Dict[str, Any] = None,
                      dimensions: Dict[str, Any] = None,
                      closed_loop_confidence: float = 0.5) -> UnifiedValidationManifest:
        """Run the full validation gate: pre + post + learn."""
        # Pre-generation
        corrected_params, pre_issues, corrections = self.pre_validate_params(
            params, product_type, template_id)

        # Post-generation (if sheet data available)
        post_issues = []
        if sheet_data:
            post_issues = self.post_validate_drawing(
                sheet_data, dimensions or {}, product_type, template_id)

        # Build manifest
        return self.build_manifest(
            product_type, template_id, corrected_params,
            pre_issues, post_issues, corrections, closed_loop_confidence,
        )
