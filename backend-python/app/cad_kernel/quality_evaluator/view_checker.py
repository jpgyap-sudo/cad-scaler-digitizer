from .models import QualityIssue
from .rules import REQUIRED_VIEWS

class ViewChecker:
    def check(self, sheet):
        issues=[]
        names=[i.get("name","").upper() for i in sheet.get("items",[])]
        for v in REQUIRED_VIEWS:
            if not any(v in n for n in names):
                issues.append(QualityIssue(severity="error",code="VIEW-MISSING",message=f"Missing {v}",fix=f"Add {v} to sheet."))
        return issues
