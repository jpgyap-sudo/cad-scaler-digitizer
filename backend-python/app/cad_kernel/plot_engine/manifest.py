import json
from pathlib import Path
from .models import PlotManifest

class PlotManifestWriter:
    def write(self, dxf_path, pdf_path, sheet, path):
        manifest = PlotManifest(
            dxf_path=dxf_path,
            pdf_path=pdf_path,
            sheet_size=sheet.size,
            item_count=len(sheet.items),
        )
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Path(path).write_text(manifest.model_dump_json(indent=2), encoding="utf-8")
        return manifest
