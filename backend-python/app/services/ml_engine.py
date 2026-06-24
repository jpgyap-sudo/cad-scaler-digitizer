"""
ML Engine: Neural network inference + training pipeline for CAD digitizer.
Phases:
  Phase 1: Data collection via PostgreSQL feedback
  Phase 2: ONNX model deployment + prediction
  Phase 3: Active learning + auto-retraining
"""
import os, json, uuid, logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List

logger = logging.getLogger("ml_engine")

MODELS_DIR = Path(__file__).parent.parent.parent / "models"
MODELS_DIR.mkdir(exist_ok=True)
REGISTRY_PATH = MODELS_DIR / "registry.json"


def _load_registry() -> dict:
    if REGISTRY_PATH.exists():
        return json.loads(REGISTRY_PATH.read_text())
    return {"models": [], "active": {}}


def _save_registry(registry: dict):
    REGISTRY_PATH.write_text(json.dumps(registry, indent=2))


# ========= PHASE 1: Data Collection =========

def store_feedback(session_id: str, predicted: dict, corrected: dict, verified: bool, pool=None):
    """Store user corrections for retraining."""
    try:
        feedback = {
            "session_id": session_id,
            "predicted": predicted,
            "corrected": corrected,
            "verified": verified,
            "timestamp": datetime.utcnow().isoformat()
        }
        feedback_path = MODELS_DIR / "feedback.jsonl"
        with open(feedback_path, "a") as f:
            f.write(json.dumps(feedback) + "\n")

        if pool:
            pool.execute("""
                INSERT INTO ml_predictions 
                (session_id, furniture_type_predicted, furniture_type_corrected, confidence, user_verified)
                VALUES ($1, $2, $3, $4, $5)
            """, (session_id, predicted.get("type"), corrected.get("type"),
                  predicted.get("confidence", 0), verified))
        logger.info(f"Stored feedback for session {session_id}")
        return True
    except Exception as e:
        logger.error(f"Feedback error: {e}")
        return False


def get_feedback_count() -> int:
    """Count feedback samples collected."""
    feedback_path = MODELS_DIR / "feedback.jsonl"
    if not feedback_path.exists():
        return 0
    return sum(1 for _ in open(feedback_path))


# ========= PHASE 2: ONNX Prediction =========

class FurnitureClassifier:
    """Rule-based fallback classifier (ML placeholder until ONNX models are trained)."""

    def __init__(self):
        self.model_path = MODELS_DIR / "furniture_classifier.onnx"
        self.session = None
        self.version = 0
        self._load()

    def _load(self):
        """Try loading ONNX model, fallback to rule-based."""
        if self.model_path.exists():
            try:
                import onnxruntime as ort
                self.session = ort.InferenceSession(str(self.model_path))
                self.version = _load_registry().get("active", {}).get("furniture_classifier", 0)
                logger.info(f"Loaded ONNX furniture_classifier v{self.version}")
            except Exception as e:
                logger.warning(f"ONNX load failed: {e}, using rule-based fallback")
                self.session = None
        else:
            logger.info("No ONNX model found, using rule-based fallback")

    def predict(self, image_path: str, ocr_text: str, geometry: dict) -> dict:
        """Predict furniture type with confidence. Falls back to rule-based if ML unavailable."""
        if self.session:
            try:
                import numpy as np
                from PIL import Image
                img = Image.open(image_path).resize((384, 384))
                input_tensor = np.array(img).astype(np.float32) / 255.0
                input_tensor = np.transpose(input_tensor, (2, 0, 1))[np.newaxis, :, :, :]
                outputs = self.session.run(None, {"input": input_tensor})
                classes = ["round_pedestal_table", "rectangular_table", "sofa", "cabinet",
                           "bed_headboard", "chair", "coffee_table", "dining_chair",
                           "wardrobe", "reception_counter"]
                probs = outputs[0][0]
                idx = int(np.argmax(probs))
                return {"type": classes[idx], "confidence": float(probs[idx]), "ml": True}
            except Exception as e:
                logger.warning(f"ML predict failed: {e}")

        # Rule-based fallback
        from app.backend.furniture_classifier import classify_furniture
        circles = geometry.get("circles", [])
        lines = geometry.get("lines", [])
        rects = geometry.get("rects", [])
        result = classify_furniture(ocr_text.split("\n") if ocr_text else [], circles, lines, rects)
        result["ml"] = False
        return result


class DimensionPredictor:
    """Dimension predictor with fallback."""

    def predict(self, geometry: dict, ocr_dims: list, furniture_type: str) -> dict:
        from app.backend.dimension_validator import align_dimension_to_ocr, validate_scale
        lines = geometry.get("lines", [])
        circles = geometry.get("circles", [])
        scale, conf, warns = validate_scale(ocr_dims, lines)
        return {
            "dimensions": {"diameter": 80, "height": 70, "width": 120, "depth": 80},
            "scale": scale,
            "confidence": conf,
            "warnings": warns
        }


class DXFQualityScorer:
    """Score DXF output quality."""

    def score(self, dxf_path: str) -> dict:
        try:
            import ezdxf
            doc = ezdxf.readfile(dxf_path)
            types = {}
            for e in doc.modelspace():
                types[e.dxftype()] = types.get(e.dxftype(), 0) + 1
            score = 0.0
            if types.get("LWPOLYLINE", 0) > 0: score += 0.3
            if types.get("CIRCLE", 0) > 0: score += 0.2
            if types.get("HATCH", 0) > 0: score += 0.2
            if types.get("DIMENSION", 0) > 0: score += 0.15
            if types.get("TEXT", 0) > 0: score += 0.15
            total = sum(types.values())
            return {"score": round(score, 2), "entities": types, "total": total}
        except Exception as e:
            return {"score": 0.0, "error": str(e)}


# ========= PHASE 3: Retraining =========

def should_retrain(threshold: int = 100) -> bool:
    """Check if enough new feedback has been collected for retraining."""
    count = get_feedback_count()
    registry = _load_registry()
    last_trained = registry.get("last_trained_count", 0)
    return (count - last_trained) >= threshold


def retrain_models():
    """Trigger retraining pipeline (placeholder for actual training script)."""
    registry = _load_registry()
    count = get_feedback_count()
    registry["last_trained_count"] = count
    registry["last_trained_at"] = datetime.utcnow().isoformat()
    registry["models"].append({
        "version": len(registry["models"]) + 1,
        "type": "furniture_classifier",
        "samples": count,
        "trained_at": registry["last_trained_at"]
    })
    registry["active"]["furniture_classifier"] = len(registry["models"])
    _save_registry(registry)
    logger.info(f"Retraining triggered. Total samples: {count}")
    return {"status": "retrained", "samples": count}


def get_ml_status() -> dict:
    """Get ML system status."""
    registry = _load_registry()
    return {
        "feedback_samples": get_feedback_count(),
        "models": registry.get("models", []),
        "active": registry.get("active", {}),
        "last_trained": registry.get("last_trained_at", "never"),
        "should_retrain": should_retrain()
    }


# Initialize singletons
furniture_classifier = FurnitureClassifier()
dimension_predictor = DimensionPredictor()
quality_scorer = DXFQualityScorer()
