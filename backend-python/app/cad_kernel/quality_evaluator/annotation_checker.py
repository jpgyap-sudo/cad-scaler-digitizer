from .models import QualityIssue

class AnnotationChecker:
    def check(self, annotations):
        issues=[]
        if len(annotations.get("annotations",[])) < 3:
            issues.append(QualityIssue(severity="warning",code="ANNO-LOW",message="Too few annotations.",fix="Add material notes, leaders, and BOM balloons."))
        return issues
