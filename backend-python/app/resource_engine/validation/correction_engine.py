"""Correction engine — applies auto-fixes for validation issues."""
from typing import Any, List
from .models import ValidationIssue


class CorrectionEngine:
    def apply(self, package: Any, issues: List[ValidationIssue]):
        corrected = package
        applied = []

        for issue in issues:
            if issue.severity == "error" and issue.field and issue.suggested_fix:
                field = issue.field
                if field in corrected.cad_parameters:
                    # Try numeric fix extraction
                    fix = issue.suggested_fix
                    import re
                    nums = re.findall(r'\d+', fix)
                    if nums and field in corrected.cad_parameters:
                        corrected.cad_parameters[field] = float(nums[0])
                        applied.append(f"Auto-fixed {field}: {issue.suggested_fix}")

        return corrected, applied
