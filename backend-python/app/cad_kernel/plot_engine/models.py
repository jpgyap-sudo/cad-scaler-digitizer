from pydantic import BaseModel
from typing import List, Dict

class SheetItem(BaseModel):
    kind: str
    name: str
    x: float
    y: float
    width: float
    height: float

class PlotSheet(BaseModel):
    size: str = "A1"
    title: str = "Shop Drawing"
    items: List[SheetItem] = []
    metadata: Dict = {}

class PlotManifest(BaseModel):
    dxf_path: str
    pdf_path: str
    sheet_size: str
    item_count: int
    warnings: List[str] = []
