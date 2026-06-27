"""Validation pipeline — runs 5 validators, applies corrections, builds report."""
from typing import Any, Tuple, List
from .validators import (DimensionValidator, StructuralValidator, JoineryValidator,
                          HardwareClearanceValidator, ManufacturingValidator)
from .correction_engine import CorrectionEngine
from .report_builder import ValidationReportBuilder
from .models import ValidationIssue, ValidationReport


class ValidationPipeline:
    def __init__(self):
        self.validators = [
            DimensionValidator(), StructuralValidator(),
            JoineryValidator(), HardwareClearanceValidator(),
            ManufacturingValidator(),
        ]
        self.corrector = CorrectionEngine()
        self.reporter = ValidationReportBuilder()

    def run(self, package: Any) -> Tuple[ValidationReport, Any]:
        issues = []
        for v in self.validators:
            issues.extend(v.validate(package))
        corrected, applied = self.corrector.apply(package, issues)
        report = self.reporter.build(
            package.product_type, package.template_id, issues, applied,
        )
        return report, corrected
