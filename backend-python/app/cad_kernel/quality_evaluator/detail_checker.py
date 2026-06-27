from .models import QualityIssue

class DetailChecker:
    def check(self, details):
        issues=[]
        if not details.get("details"):
            issues.append(QualityIssue(severity="warning",code="DETAIL-MISSING",message="No detail views found.",fix="Generate key details."))
        return issues
