"""TemplateGraphLoader — loads all 18 furniture template graph JSON files."""
from __future__ import annotations
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

TEMPLATE_DIR = Path(__file__).resolve().parent.parent.parent / "resources" / "furniture_template_graphs"


class TemplateGraphLoader:
    """Loads and indexes all furniture template graphs from JSON files.

    Singleton-friendly — call load() once at startup, then use get/find methods.
    Thread-safe for reads after initialization.
    """

    def __init__(self, root: Optional[str] = None):
        self._root = Path(root) if root else TEMPLATE_DIR
        self._by_id: Dict[str, Dict[str, Any]] = {}
        self._by_product_type: Dict[str, List[Dict[str, Any]]] = {}
        self._by_family: Dict[str, List[Dict[str, Any]]] = {}
        self._loaded = False

    def load(self) -> TemplateGraphLoader:
        """Scan template directory and load all JSON files."""
        self._by_id.clear()
        self._by_product_type.clear()
        self._by_family.clear()

        if not self._root.exists():
            print(f"[TemplateGraphLoader] Directory not found: {self._root}")
            self._loaded = True
            return self

        for fpath in sorted(self._root.glob("*.json")):
            try:
                data = json.loads(fpath.read_text(encoding="utf-8"))
                tid = data.get("id")
                if not tid:
                    print(f"[TemplateGraphLoader] Skipping {fpath.name}: no 'id' field")
                    continue

                self._by_id[tid] = data

                # Index by product_type
                pt = data.get("product_type", "")
                if pt:
                    self._by_product_type.setdefault(pt, []).append(data)

                # Index by family
                family = data.get("family", "")
                if family:
                    self._by_family.setdefault(family, []).append(data)

            except (json.JSONDecodeError, OSError) as e:
                print(f"[TemplateGraphLoader] Skipping {fpath.name}: {e}")

        self._loaded = True
        print(f"[TemplateGraphLoader] Loaded {self.count} templates from {self._root}")
        return self

    def get(self, template_id: str) -> Optional[Dict[str, Any]]:
        """Lookup a template by its ID (e.g. 'table.rectangular_four_leg.v1')."""
        return self._by_id.get(template_id)

    def find_by_product_type(self, product_type: str) -> List[Dict[str, Any]]:
        """Find all templates matching a product type (e.g. 'rectangular_table')."""
        return list(self._by_product_type.get(product_type, []))

    def find_by_family(self, family: str) -> List[Dict[str, Any]]:
        """Find all templates in a family (e.g. 'table', 'cabinet', 'seating')."""
        return list(self._by_family.get(family, []))

    def get_default(self, product_type: str) -> Optional[Dict[str, Any]]:
        """Get the first/best match for a product type. Useful for single-match dispatch."""
        matches = self.find_by_product_type(product_type)
        if matches:
            return matches[0]
        return None

    def list_all(self) -> List[Dict[str, Any]]:
        """Return all loaded templates."""
        return list(self._by_id.values())

    def get_parameter(self, template_id: str, param_name: str) -> Optional[Dict[str, Any]]:
        """Get a specific parameter definition from a template."""
        tpl = self.get(template_id)
        if not tpl:
            return None
        for param in tpl.get("parameters", []):
            if param.get("name") == param_name:
                return param
        return None

    def resolve_and_override(self, product_type: str,
                             overrides: Dict[str, float]
                             ) -> Optional[Dict[str, Any]]:
        """Find the default template for product_type and apply dimension overrides.

        Returns a dict with the full template + 'resolved_parameters' containing
        the overridden (or default) values. overrides keys should match parameter names.
        """
        tpl = self.get_default(product_type)
        if not tpl:
            return None

        resolved = {}
        for param in tpl.get("parameters", []):
            pname = param["name"]
            raw = overrides.get(pname, param.get("default"))
            resolved[pname] = raw

        result = dict(tpl)
        result["resolved_parameters"] = resolved
        return result

    @property
    def count(self) -> int:
        return len(self._by_id)

    @property
    def is_loaded(self) -> bool:
        return self._loaded
