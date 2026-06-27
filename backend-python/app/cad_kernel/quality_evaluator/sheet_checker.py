from .models import QualityIssue
from .rules import REQUIRED_SHEET_ITEMS

class SheetChecker:
    def check(self, sheet):
        issues=[]
        kinds=[i.get("kind") for i in sheet.get("items",[])]
        for k in REQUIRED_SHEET_ITEMS:
            if k not in kinds:
                issues.append(QualityIssue(severity="error",code="SHEET-MISSING",message=f"Missing sheet item: {k}",fix=f"Add {k}."))
        return issues
