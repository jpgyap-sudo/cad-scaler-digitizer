from .models import QualityReport
from .view_checker import ViewChecker
from .dimension_checker import DimensionChecker
from .detail_checker import DetailChecker
from .annotation_checker import AnnotationChecker
from .sheet_checker import SheetChecker
from .export_checker import ExportChecker
from .scorer import QualityScorer

class Phase3E10QualityPipeline:
    def run(self, sheet, dimensions=None, details=None, annotations=None, manifest=None):
        dimensions=dimensions or {}
        details=details or {}
        annotations=annotations or {}
        manifest=manifest or {}

        issues=[]
        issues+=ViewChecker().check(sheet)
        issues+=DimensionChecker().check(dimensions)
        issues+=DetailChecker().check(details)
        issues+=AnnotationChecker().check(annotations)
        issues+=SheetChecker().check(sheet)
        issues+=ExportChecker().check(manifest)

        metrics={
            "sheet_items":len(sheet.get("items",[])),
            "dimension_count":len(dimensions.get("dimensions",[])),
            "detail_count":len(details.get("details",[])),
            "annotation_count":len(annotations.get("annotations",[])),
            "issue_count":len(issues),
        }
        score=QualityScorer().score(issues,metrics)
        return QualityReport(score=score,passed=score>=0.8 and not any(i.severity=="error" for i in issues),issues=issues,metrics=metrics)
