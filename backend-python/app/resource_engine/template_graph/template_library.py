"""Template Library — loads FurnitureTemplate JSON graph definitions."""
import json
from pathlib import Path
from typing import Dict, Optional
from .models import FurnitureTemplate, TemplateParameter, TemplateComponent, TemplateConstraint
from app.backend.resource_paths import resolve_resources_dir


class TemplateLibrary:
    def __init__(self, root: str = None):
        default = resolve_resources_dir(Path(__file__)) / "furniture_template_graphs"
        self.root = Path(root) if root else default
        self.templates: Dict[str, FurnitureTemplate] = {}

    def load(self) -> "TemplateLibrary":
        self.root.mkdir(parents=True, exist_ok=True)
        for fpath in self.root.glob("*.json"):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                tmpl = FurnitureTemplate(
                    id=data["id"], name=data.get("name", data["id"]),
                    product_type=data.get("product_type", ""), family=data.get("family", ""),
                    parameters=[TemplateParameter(**p) for p in data.get("parameters", [])],
                    components=[TemplateComponent(**c) for c in data.get("components", [])],
                    constraints=[TemplateConstraint(**c) for c in data.get("constraints", [])],
                    required_views=data.get("required_views", ["top", "front_elevation", "side_elevation"]),
                    required_details=data.get("required_details", []),
                    drawing_notes=data.get("drawing_notes", []),
                )
                self.templates[tmpl.id] = tmpl
            except Exception as e:
                print(f"[TemplateLibrary] Skipping {fpath}: {e}")
        return self

    def get(self, template_id: str) -> Optional[FurnitureTemplate]:
        return self.templates.get(template_id)

    def find_by_product(self, product_type: str) -> list:
        return [t for t in self.templates.values() if t.product_type == product_type]
