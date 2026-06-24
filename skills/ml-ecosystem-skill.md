# ML Learning Ecosystem Skill

## Purpose
Guide agents to build, train, and deploy neural networks that improve CAD digitization accuracy over time through continuous learning.

## Core Architecture

```
User Upload → OpenCV + OCR → Rule-based Prediction (fallback)
                                   ↓
                         Neural Network (when confidence < 0.7)
                                   ↓
                         DXF Output + Confidence Score
                                   ↓
                         User Corrections → PostgreSQL
                                   ↓
                         Weekly Retraining → Better Models
```

## Three Neural Networks

### 1. Furniture Classifier (Vision Transformer)
- **Input**: Image (384x384) + OCR text tokens
- **Output**: Furniture type (10 classes)
- **Training**: Supervised from PostgreSQL session data
- **When to use**: When user uploads a new drawing
- **Fallback**: Rule-based `classify_furniture()` when ML confidence < 0.6

### 2. Dimension Predictor (MLP Regressor)
- **Input**: Geometry primitives + OCR dimensions + furniture type
- **Output**: 6 dimension values + confidence
- **Training**: Semi-supervised from OCR + user corrections
- **When to use**: After furniture classification

### 3. DXF Quality Scorer (Binary Classifier)
- **Input**: DXF entity features (count, types, patterns)
- **Output**: Quality score 0.0-1.0
- **Training**: From user verification (approved/rejected)
- **When to use**: Before serving DXF to user

## Data Collection

Every user interaction generates training data:

```sql
-- Store corrections automatically
INSERT INTO ml_predictions 
(session_id, furniture_type_predicted, furniture_type_corrected, confidence, user_verified)
VALUES ($1, $2, $3, $4, $5);
```

## Feedback Endpoint

```python
@app.post("/api/ml/feedback")
async def ml_feedback(session_id: str, corrections: dict):
    """Store user corrections for retraining."""
    pool.execute("UPDATE ml_predictions SET ... WHERE session_id = $1", ...)
```

## Model Deployment

1. Train → Export ONNX → Deploy to `/backend-python/models/`
2. Load at startup, predict via `/api/ml/predict`
3. Log all predictions for continuous improvement
4. Auto-retrain when 1000+ new samples collected

## Key Resources
- `memory/ml_learning_schema.json` — Full ML pipeline specification
- `resources/training/lwpolyline_samples.json` — Training samples
- PostgreSQL `ml_predictions` and `ml_models` tables
