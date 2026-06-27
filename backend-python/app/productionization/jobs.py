from datetime import datetime
from app.productionization.config import settings
from app.productionization.storage import LocalStore
from app.productionization.models import JobRecord, GenerateRequest
from app.productionization.pipeline.orchestrator import ShopDrawingOrchestrator

store = LocalStore(settings.data_dir)


class JobService:
    def create_and_run(self, request: GenerateRequest):
        job = JobRecord(request=request, status="running")
        store.save("jobs", job.id, job)

        try:
            response, stages = ShopDrawingOrchestrator().run(job.id, request)
            job.status = "completed"
            job.response = response
            job.stages = stages
        except Exception as e:
            job.status = "failed"
            job.error = str(e)

        job.updated_at = datetime.utcnow().isoformat()
        store.save("jobs", job.id, job)
        return job

    def get(self, job_id: str):
        return store.load("jobs", job_id, JobRecord)

    def list(self):
        return store.list("jobs", JobRecord)
