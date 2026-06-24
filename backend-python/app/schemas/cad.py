"""Pydantic schemas for CAD digitizer API."""
from pydantic import BaseModel, Field
from typing import Optional, Literal


class DimensionSet(BaseModel):
    unit: Literal["cm", "mm"] = "cm"
    diameter: Optional[float] = None
    width: Optional[float] = None
    depth: Optional[float] = None
    height: Optional[float] = None
    base_diameter: Optional[float] = None
    neck_diameter: Optional[float] = None
    top_thickness: Optional[float] = None
    seat_height: Optional[float] = None


class FurnitureAnalysis(BaseModel):
    furniture_type: str
    confidence: float = Field(ge=0, le=1)
    dimensions: DimensionSet


class DigitizeResponse(BaseModel):
    job_id: str
    furniture_type: str
    confidence: float
    dimensions: dict
    download_url: str
    warnings: list[str] = []
