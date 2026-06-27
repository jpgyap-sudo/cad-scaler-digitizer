-- =============================================================================
-- CAD Scaler Digitizer — Database Initialization Script
-- Runs automatically when Postgres container starts (if volume is empty)
-- Manages tables NOT covered by Prisma schema (which handles ProductReference
-- and related models via migrations).
-- =============================================================================

-- Digitizer sessions table (from existing backend)
CREATE TABLE IF NOT EXISTS digitizer_sessions (
    id SERIAL PRIMARY KEY,
    session_id TEXT UNIQUE NOT NULL,
    file_name TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Digitizer results table
CREATE TABLE IF NOT EXISTS digitizer_results (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES digitizer_sessions(session_id) ON DELETE CASCADE,
    loop_number INT DEFAULT 0,
    calibration JSONB,
    polylines JSONB,
    ocr_text JSONB,
    verification_score INT,
    verification_approved BOOLEAN,
    verification_feedback JSONB,
    raw_dxf TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Feedback learning table
CREATE TABLE IF NOT EXISTS feedback_learnings (
    id SERIAL PRIMARY KEY,
    session_id TEXT,
    field_name TEXT NOT NULL,
    original_value TEXT,
    corrected_value TEXT,
    context JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Proportion ledger (for cross-photo ratio blending)
CREATE TABLE IF NOT EXISTS proportion_ledger (
    id SERIAL PRIMARY KEY,
    furniture_type TEXT NOT NULL,
    anchor_dimension TEXT NOT NULL,
    anchor_value_cm FLOAT NOT NULL,
    component TEXT NOT NULL,
    component_value_cm FLOAT NOT NULL,
    sample_count INT DEFAULT 1,
    last_updated TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (furniture_type, anchor_dimension, component)
);

-- Drawing history log
CREATE TABLE IF NOT EXISTS drawing_history (
    id SERIAL PRIMARY KEY,
    job_id TEXT,
    furniture_type TEXT,
    dxf_name TEXT,
    dimensions_used JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Chat sessions (persistent storage)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    session_key TEXT UNIQUE NOT NULL,
    state JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_digitizer_sessions_session_id ON digitizer_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_digitizer_results_session_id ON digitizer_results(session_id);
CREATE INDEX IF NOT EXISTS idx_proportion_ledger_furniture ON proportion_ledger(furniture_type);
CREATE INDEX IF NOT EXISTS idx_chat_sessions_key ON chat_sessions(session_key);
