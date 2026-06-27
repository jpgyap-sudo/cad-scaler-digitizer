from datetime import datetime
from app.productionization.config import settings
from app.productionization.storage import LocalStore

store = LocalStore(settings.data_dir)


class ReviewService:
    def create_from_generation(self, case_id, request, engineering, artifacts, quality, resource_ids):
        case = {
            "id": case_id,
            "product_id": request.product_id,
            "product_name": request.product_name,
            "product_type": engineering["product_type"],
            "template_id": engineering["template_id"],
            "status": "generated",
            "generated_parameters": engineering["canonical_parameters"],
            "corrected_parameters": {},
            "artifacts": [a.model_dump() for a in artifacts],
            "quality": quality,
            "resource_ids": resource_ids,
            "corrections": [],
            "comments": [],
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat(),
        }
        store.save_index(f"cases/{case_id}", case)
        return case

    def get(self, case_id):
        return store.load_index(f"cases/{case_id}", {})

    def accept(self, case_id, reviewer="engineer", comments=None):
        case = self.get(case_id)
        case["status"] = "accepted"
        case["reviewer"] = reviewer
        case["comments"] = case.get("comments", []) + (comments or [])
        case["corrected_parameters"] = case.get("generated_parameters", {})
        case["updated_at"] = datetime.utcnow().isoformat()
        store.save_index(f"cases/{case_id}", case)
        return case

    def reject(self, case_id, reviewer="engineer", comments=None):
        case = self.get(case_id)
        case["status"] = "rejected"
        case["reviewer"] = reviewer
        case["comments"] = case.get("comments", []) + (comments or [])
        case["updated_at"] = datetime.utcnow().isoformat()
        store.save_index(f"cases/{case_id}", case)
        return case

    def correct(self, case_id, reviewer, corrections, corrected_parameters, comments=None):
        case = self.get(case_id)
        case["status"] = "edited"
        case["reviewer"] = reviewer
        case["corrections"] = [c.model_dump() if hasattr(c, "model_dump") else c for c in corrections]
        case["corrected_parameters"] = corrected_parameters
        case["comments"] = case.get("comments", []) + (comments or [])
        case["updated_at"] = datetime.utcnow().isoformat()
        store.save_index(f"cases/{case_id}", case)
        return case

    def replay(self, case_id):
        case = self.get(case_id)
        return {
            "case_id": case_id,
            "pipeline_replay": {
                "request": case.get("request"),
                "generated_parameters": case.get("generated_parameters"),
                "corrected_parameters": case.get("corrected_parameters"),
                "artifacts": case.get("artifacts"),
                "quality": case.get("quality"),
                "corrections": case.get("corrections"),
            },
        }
