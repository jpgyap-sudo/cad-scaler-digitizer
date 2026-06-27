from pydantic import BaseModel
from typing import List,Dict

class Feedback(BaseModel):
    product_id:str
    approved:bool
    comments:List[str]=[]

class Improvement(BaseModel):
    area:str
    recommendation:str
    confidence:float

class LearningReport(BaseModel):
    improvements:List[Improvement]
    next_confidence:float
