"""Validation report builder."""
from statistics import mean
from typing import List
from .models import ValidationIssue, ValidationReport


class ValidationReportBuilder:
    def build(self, product_type: str, template_id: str,
              issues: List[ValidationIssue], applied_corrections: List[str]) -> ValidationReport:
        total = len(issues)
        errors = sum(1 for i in issues if i.severity == "error")
        warnings = sum(1 for i in issues if i.severity == "warning")

        score = max(0.0, 1.0 - (errors * 0.3 + warnings * 0.1))
        approved = errors == 0

        return ValidationReport(
            product_type=product_type, template_id=template_id,
            approved_for_drafting=approved, score=round(score, 3),
            issues=issues, applied_corrections=applied_corrections,
        )
