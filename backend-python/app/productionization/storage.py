import json
from pathlib import Path
from typing import Type, TypeVar, List

T = TypeVar("T")


class LocalStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def save(self, collection: str, item_id: str, model):
        path = self.root / collection / f"{item_id}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        return str(path)

    def load(self, collection: str, item_id: str, cls: Type[T]) -> T:
        path = self.root / collection / f"{item_id}.json"
        return cls(**json.loads(path.read_text(encoding="utf-8")))

    def list(self, collection: str, cls: Type[T]) -> List[T]:
        folder = self.root / collection
        if not folder.exists():
            return []
        return [cls(**json.loads(p.read_text(encoding="utf-8"))) for p in folder.glob("*.json")]

    def exists(self, collection: str, item_id: str) -> bool:
        return (self.root / collection / f"{item_id}.json").exists()
