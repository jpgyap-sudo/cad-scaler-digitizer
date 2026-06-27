from pydantic import BaseModel
from typing import List, Dict

class Annotation(BaseModel):
    kind: str
    text: str
    anchor: Dict[str, float]
    layer: str = "TEXT"

class AnnotationSet(BaseModel):
    annotations: List[Annotation] = []
    score: float = 0
