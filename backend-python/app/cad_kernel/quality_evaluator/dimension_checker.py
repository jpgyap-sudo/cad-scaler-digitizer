from .models import QualityIssue

class DimensionChecker:
    def check(self, dimensions):
        issues=[]
        kinds={d.get("kind") for d in dimensions.get("dimensions",[])}
        if "overall_length" not in kinds:
            issues.append(QualityIssue(severity="warning",code="DIM-LENGTH",message="Missing overall length dimension.",fix="Add overall length dimension."))
        if "overall_depth" not in kinds:
            issues.append(QualityIssue(severity="warning",code="DIM-DEPTH",message="Missing overall depth dimension.",fix="Add overall depth dimension."))
        return issues
