from pathlib import Path
from app.cad_kernel.document import CADDocument


class JSONExporter:
    def export(self, document: CADDocument, path: str):
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(document.model_dump_json(indent=2), encoding="utf-8")
        return str(p)
