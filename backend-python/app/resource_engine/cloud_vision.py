"""Cloud Vision API integration — OpenAI and Gemini for furniture feature extraction.
Extends the existing hybrid digitize pipeline with structured VLM analysis.

Usage:
    client = make_cloud_vision_client()  # reads AI_PROVIDER from env
    features = client.extract_furniture_features("photo.jpg")
    # features is CloudVisionFeatureSet with product_type, dimensions, materials, etc.
"""
import json
import os
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class CloudVisionFeatureSet(BaseModel):
    """Structured furniture features extracted by cloud VLM."""
    product_type: str = "unknown"
    subtype: Optional[str] = None
    top_shape: Optional[str] = None
    support_type: Optional[str] = None
    material_top: Optional[str] = None
    material_base: Optional[str] = None
    upholstery_type: Optional[str] = None
    visible_parts: List[str] = []
    inferred_hidden_parts: List[str] = []
    construction_notes: List[str] = []
    style_keywords: List[str] = []
    approximate_dimensions_mm: Dict[str, Any] = {}
    confidence: float = Field(default=0.0, ge=0, le=1)


FURNITURE_FEATURE_PROMPT = '''
You are a furniture shop drawing feature extractor.

Analyze the furniture photo and return ONLY JSON.

Do not create CAD.
Do not invent exact brand names.
Use approximate dimensions only when visible type allows standard furniture assumptions.

Required JSON schema:
{
  "product_type": "dining_table | coffee_table | side_table | sofa | lounge_chair | dining_chair | bed | sideboard | tv_console | nightstand | cabinet | unknown",
  "subtype": "short subtype",
  "top_shape": "rectangular | round | oval | racetrack | organic | none",
  "support_type": "dual_cylindrical_pedestal | single_pedestal | four_leg | sled | plinth | panel_base | unknown",
  "material_top": "white_stone | marble | travertine | walnut | oak | glass | fabric | leather | unknown",
  "material_base": "brushed_metal | matte_black_metal | wood | plinth | unknown",
  "upholstery_type": "fabric | leather | boucle | none | unknown",
  "visible_parts": ["part names"],
  "inferred_hidden_parts": ["likely hidden construction parts"],
  "construction_notes": ["practical manufacturing assumptions"],
  "style_keywords": ["minimalist", "modern", "luxury", "..."],
  "approximate_dimensions_mm": {
    "length_mm": 1800,
    "depth_mm": 900,
    "height_mm": 750,
    "top_thickness_mm": 30
  },
  "confidence": 0.0
}

For tables:
- estimate top shape, support type, overhang, leg/pedestal quantity.
- if stone top is long, infer hidden steel frame.

For sofas/chairs:
- estimate seat, back, arms, base, upholstery.

For cabinets:
- estimate case, doors, drawers, plinth, material.

Return JSON only.
'''


class CloudVisionClient:
    """Base class for cloud vision clients."""

    def extract_furniture_features(self, image_path: str) -> CloudVisionFeatureSet:
        raise NotImplementedError


class OpenAIVisionClient(CloudVisionClient):
    """OpenAI GPT-4 vision client."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("OPENAI_VISION_MODEL", "gpt-4.1-mini")

    def extract_furniture_features(self, image_path: str) -> CloudVisionFeatureSet:
        from openai import OpenAI
        import base64

        client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

        with open(image_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode("utf-8")

        ext = os.path.splitext(image_path)[1].lower()
        mime = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

        response = client.responses.create(
            model=self.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": FURNITURE_FEATURE_PROMPT},
                        {"type": "input_image", "image_url": f"data:{mime};base64,{b64}"},
                    ],
                }
            ],
        )

        text = response.output_text
        cleaned = text.strip()
        if cleaned.startswith("```"): cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(cleaned)
        return CloudVisionFeatureSet(**data)


class GeminiVisionClient(CloudVisionClient):
    """Google Gemini vision client."""

    def __init__(self, model: Optional[str] = None):
        self.model = model or os.getenv("GEMINI_VISION_MODEL", "gemini-2.5-flash")

    def extract_furniture_features(self, image_path: str) -> CloudVisionFeatureSet:
        from google import genai
        from google.genai import types

        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

        with open(image_path, "rb") as f:
            image_bytes = f.read()

        response = client.models.generate_content(
            model=self.model,
            contents=[
                FURNITURE_FEATURE_PROMPT,
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
            ],
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            ),
        )

        cleaned = response.text.strip()
        if cleaned.startswith("```"): cleaned = cleaned.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        data = json.loads(cleaned)
        return CloudVisionFeatureSet(**data)


def make_cloud_vision_client() -> CloudVisionClient:
    """Factory: returns the configured cloud vision client."""
    provider = os.getenv("AI_PROVIDER", "openai").lower().strip()
    if provider == "gemini":
        return GeminiVisionClient()
    return OpenAIVisionClient()
