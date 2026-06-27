from fastapi import FastAPI, HTTPException
from app.productionization.models import GenerateRequest, ReviewActionRequest
from app.productionization.jobs import JobService
from app.productionization.review.review_service import ReviewService
from app.productionization.registry import TemplateRegistry, ResourceRegistry

app = FastAPI(title="HomeU Shopdrawing AI", version="6.0.0")


@app.get("/")
def root():
    return {"name": "HomeU Shopdrawing AI", "version": "6.0.0", "status": "ok"}


@app.post("/api/generate-shopdrawing")
def generate_shopdrawing(request: GenerateRequest):
    job = JobService().create_and_run(request)
    if job.status == "failed":
        raise HTTPException(status_code=500, detail=job.error)
    return job.response


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    return JobService().get(job_id)


@app.get("/api/jobs")
def list_jobs():
    return JobService().list()


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    case = ReviewService().get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/api/cases/{case_id}/accept")
def accept_case(case_id: str, action: ReviewActionRequest):
    return ReviewService().accept(case_id, reviewer=action.reviewer, comments=action.comments)


@app.post("/api/cases/{case_id}/reject")
def reject_case(case_id: str, action: ReviewActionRequest):
    return ReviewService().reject(case_id, reviewer=action.reviewer, comments=action.comments)


@app.post("/api/cases/{case_id}/corrections")
def correct_case(case_id: str, action: ReviewActionRequest):
    return ReviewService().correct(
        case_id,
        reviewer=action.reviewer,
        corrections=action.corrections,
        corrected_parameters=action.corrected_parameters,
        comments=action.comments,
    )


@app.get("/api/replay/{case_id}")
def replay(case_id: str):
    return ReviewService().replay(case_id)


@app.get("/api/templates")
def templates():
    return TemplateRegistry().list_templates()


@app.get("/api/resources")
def resources():
    return ResourceRegistry().list_resources()
