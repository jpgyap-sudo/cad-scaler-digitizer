from app.cad_kernel.importers.scene_graph_importer import SceneGraphImporter
from app.cad_kernel.constraints import ConstraintEngine
from app.cad_kernel.evaluator import SceneEvaluator
from app.cad_kernel.exporters.json_exporter import JSONExporter
from app.cad_kernel.exporters.dxf_exporter import DXFExporter


class Phase3E1CADKernelPipeline:
    def run(self, scene_graph: dict, output_json: str, output_dxf: str):
        document = SceneGraphImporter().import_scene(scene_graph, name=f"{scene_graph.get('product_type', 'furniture')} CAD Kernel Document")
        ConstraintEngine().apply(document)
        SceneEvaluator().evaluate(document)
        JSONExporter().export(document, output_json)
        DXFExporter().export(document, output_dxf)
        return document
