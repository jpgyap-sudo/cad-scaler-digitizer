from pydantic import BaseModel
from typing import List, Dict

class QualityIssue(BaseModel):
    severity: str
    code: str
    message: str
    fix: str = ""

class QualityReport(BaseModel):
    score: float
    passed: bool
    issues: List[QualityIssue] = []
    metrics: Dict = {}
