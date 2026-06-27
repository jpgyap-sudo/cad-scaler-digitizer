"""Phase 3C-4B — Engineering Validation. Validates ReadyForCADPackage before drafting.
5 validators: dimension, structural, joinery, hardware clearance, manufacturing.
Output: ValidationReport + corrected ReadyForCADPackage.
"""
from .validators import DimensionValidator, StructuralValidator, JoineryValidator, HardwareClearanceValidator, ManufacturingValidator
from .correction_engine import CorrectionEngine
from .report_builder import ValidationReportBuilder
from .pipeline import ValidationPipeline
