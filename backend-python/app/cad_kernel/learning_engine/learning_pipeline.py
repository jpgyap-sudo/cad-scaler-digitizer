from .models import LearningReport,Improvement
from .diff_engine import DifferenceEngine
from .template_updater import TemplateUpdater
from .constraint_updater import ConstraintUpdater
from .confidence_calibrator import ConfidenceCalibrator

class Phase4LearningPipeline:
    def run(self,generated,corrected,approved=True):
        diffs=DifferenceEngine().compare(generated,corrected)
        t=TemplateUpdater().update(diffs)
        c=ConstraintUpdater().update(diffs)
        imps=[Improvement(area="template",recommendation=t[0],confidence=0.9),
              Improvement(area="constraints",recommendation=c[0],confidence=0.88)]
        return LearningReport(improvements=imps,next_confidence=ConfidenceCalibrator().calibrate(approved))
