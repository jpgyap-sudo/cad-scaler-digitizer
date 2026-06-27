from pathlib import Path
from .models import QualityIssue

class ExportChecker:
    def check(self, manifest):
        issues=[]
        for key in ["dxf_path","pdf_path"]:
            path=manifest.get(key)
            if not path:
                issues.append(QualityIssue(severity="error",code="EXPORT-MISSING",message=f"Missing {key}.",fix="Run plot engine."))
            elif not Path(path).exists():
                issues.append(QualityIssue(severity="warning",code="EXPORT-NOTFOUND",message=f"{path} does not exist in current runtime.",fix="Verify output path."))
        return issues
