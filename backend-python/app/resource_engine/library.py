"""Resource Library — loads all resource JSON files intelligently."""
import json
from pathlib import Path
from typing import Dict, Any, List, Optional, Set

RESOURCE_DIR = Path(__file__).parent.parent.parent.parent / "resources"


class ResourceLibrary:
    """Loads and searches the full resource taxonomy."""
    
    def __init__(self, root: str = str(RESOURCE_DIR)):
        self.root = Path(root)
        self.resources: Dict[str, Dict[str, Any]] = {}
        self.categories: Dict[str, List[str]] = {}
    
    def load(self) -> "ResourceLibrary":
        """Scan all resource subdirectories for JSON files."""
        subdirs = [
            "geometry", "supports", "joinery", "materials",
            "construction_rules", "dimension_styles", "manufacturers",
        ]
        for sub in subdirs:
            path = self.root / sub
            if not path.exists():
                continue
            for fpath in path.glob("*.json"):
                try:
                    data = json.loads(fpath.read_text(encoding="utf-8"))
                    rid = data.get("id")
                    if rid:
                        self.resources[rid] = data
                        cat = data.get("category", sub)
                        if cat not in self.categories:
                            self.categories[cat] = []
                        self.categories[cat].append(rid)
                except (json.JSONDecodeError, OSError) as e:
                    print(f"[ResourceLibrary] Skipping {fpath}: {e}")
        return self
    
    def get(self, resource_id: str) -> Optional[Dict[str, Any]]:
        return self.resources.get(resource_id)
    
    def search_by_features(self, wanted: List[str], category: Optional[str] = None, limit: int = 5):
        """Find resources matching desired features."""
        results = []
        wanted_set = set(f.lower() for f in wanted)
        for rid, res in self.resources.items():
            if category and res.get("category") != category:
                continue
            features = set(f.lower() for f in res.get("features", []))
            score = len(wanted_set & features) / max(1, len(wanted_set))
            if score > 0:
                results.append((score, rid, res))
        return sorted(results, reverse=True, key=lambda x: x[0])[:limit]
    
    def find_compatible(self, resource_id: str, role: str) -> List[Dict[str, Any]]:
        """Find resources compatible with a given resource."""
        res = self.resources.get(resource_id)
        if not res:
            return []
        compatible = res.get("compatible_with", [])
        if not compatible:
            return []
        results = []
        for pattern in compatible:
            cat, glob = pattern.rsplit(".", 1) if "." in pattern else (pattern, "*")
            for rid, r in self.resources.items():
                if rid.startswith(cat) and ("*" in glob or rid.endswith(glob.replace("*", ""))):
                    results.append(r)
        return results
    
    @property
    def count(self) -> int:
        return len(self.resources)
    
    def summary(self) -> Dict[str, int]:
        return {cat: len(ids) for cat, ids in self.categories.items()}
