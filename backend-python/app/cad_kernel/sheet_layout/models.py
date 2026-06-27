from pydantic import BaseModel
from typing import List,Dict

class SheetItem(BaseModel):
    kind:str
    name:str
    x:float
    y:float
    width:float
    height:float

class DrawingSheet(BaseModel):
    size:str
    title:str
    items:List[SheetItem]=[]
    metadata:Dict={}
