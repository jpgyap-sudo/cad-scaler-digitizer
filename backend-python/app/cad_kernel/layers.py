from pydantic import BaseModel
from typing import Dict


class Layer(BaseModel):
    name: str
    color: int = 7
    lineweight: int = 25
    visible: bool = True


class LayerManager:
    DEFAULTS = {
        "VISIBLE": 7,
        "HIDDEN": 8,
        "CENTERLINE": 3,
        "DIMENSIONS": 2,
        "TEXT": 7,
        "SECTION": 1,
        "DETAIL": 4,
        "BOM": 5,
        "CONSTRUCTION": 9,
        "TOP": 7,
        "BASE": 6,
        "JOINERY": 8,
    }

    def __init__(self):
        self.layers: Dict[str, Layer] = {}
        for name, color in self.DEFAULTS.items():
            self.add(name, color=color)

    def add(self, name: str, color: int = 7, lineweight: int = 25):
        self.layers[name] = Layer(name=name, color=color, lineweight=lineweight)
        return self.layers[name]

    def ensure(self, name: str):
        return self.layers.get(name) or self.add(name)
