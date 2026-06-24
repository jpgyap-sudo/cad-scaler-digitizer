-- ML tables for CAD Digitizer learning ecosystem
CREATE TABLE IF NOT EXISTS ml_predictions (
    id SERIAL PRIMARY KEY,
    session_id TEXT,
    model_version TEXT,
    furniture_type_predicted TEXT,
    furniture_type_corrected TEXT,
    confidence FLOAT,
    dimensions_predicted JSONB,
    dimensions_corrected JSONB,
    user_verified BOOLEAN DEFAULT FALSE,
    latency_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS ml_models (
    id SERIAL PRIMARY KEY,
    model_type TEXT,
    version INTEGER,
    path TEXT,
    accuracy FLOAT,
    f1_score FLOAT,
    training_samples INTEGER,
    is_active BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
