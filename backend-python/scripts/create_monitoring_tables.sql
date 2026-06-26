-- =============================================================
-- CAD Drawing Assistant — Performance Monitoring Tables
-- =============================================================
-- Tracks every chat, task, decision, and tool usage so the
-- monitoring worker can generate improvement recommendations.
-- =============================================================

-- 1. Chat Log — every user↔assistant exchange
CREATE TABLE IF NOT EXISTS assistant_chat_log (
    id              SERIAL PRIMARY KEY,
    session_id      VARCHAR(100) NOT NULL,
    user_message    TEXT,
    assistant_response TEXT,
    extracted_action VARCHAR(50),          -- render, continue, etc.
    furniture_type  VARCHAR(100),
    dimension_changes JSONB,               -- {top_diameter_cm: 80.0, ...}
    material_changes JSONB,                -- {tabletop: "solid wood", ...}
    backend_used    VARCHAR(20),            -- OpenAI or Ollama
    response_time_ms INTEGER,              -- LLM round-trip time
    token_count     INTEGER,               -- tokens used (if available)
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_log_session ON assistant_chat_log(session_id);
CREATE INDEX IF NOT EXISTS idx_chat_log_created  ON assistant_chat_log(created_at);
CREATE INDEX IF NOT EXISTS idx_chat_log_backend  ON assistant_chat_log(backend_used);


-- 2. Task Log — every operation the assistant performed
CREATE TABLE IF NOT EXISTS assistant_task_log (
    id              SERIAL PRIMARY KEY,
    session_id      VARCHAR(100),
    task_type       VARCHAR(50) NOT NULL,   -- digitize, hybrid_digitize, adjust, material_edit, batch_convert, chat, correction, benchmark, etc.
    furniture_type  VARCHAR(100),
    input_params    JSONB,                  -- what was passed in
    output_summary  JSONB,                  -- key results (confidence, dims, etc.)
    success         BOOLEAN DEFAULT TRUE,
    error_message   TEXT,
    duration_ms     INTEGER,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_task_log_session   ON assistant_task_log(session_id);
CREATE INDEX IF NOT EXISTS idx_task_log_type      ON assistant_task_log(task_type);
CREATE INDEX IF NOT EXISTS idx_task_log_created   ON assistant_task_log(created_at);
CREATE INDEX IF NOT EXISTS idx_task_log_success   ON assistant_task_log(success);


-- 3. Decision Log — every AI decision with confidence & rationale
CREATE TABLE IF NOT EXISTS assistant_decision_log (
    id              SERIAL PRIMARY KEY,
    session_id      VARCHAR(100),
    decision_type   VARCHAR(50) NOT NULL,   -- furniture_type_classification, dimension_association, scale_estimate, material_recommendation, component_visibility, exporter_selection, proportion_estimate, etc.
    confidence      FLOAT,                  -- 0.0 - 1.0
    rationale       TEXT,                   -- why this decision was made
    alternatives    JSONB,                  -- other options considered
    context         JSONB,                  -- what influenced the decision (image quality, OCR results, etc.)
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_decision_log_session ON assistant_decision_log(session_id);
CREATE INDEX IF NOT EXISTS idx_decision_log_type    ON assistant_decision_log(decision_type);
CREATE INDEX IF NOT EXISTS idx_decision_log_created ON assistant_decision_log(created_at);


-- 4. Tool Log — every internal function/tool call
CREATE TABLE IF NOT EXISTS assistant_tool_log (
    id              SERIAL PRIMARY KEY,
    session_id      VARCHAR(100),
    tool_name       VARCHAR(100) NOT NULL,  -- classify_furniture, reconstruct_geometry, compute_scale, export_dxf, brain_sync_record, ocr_extract, etc.
    input_summary   TEXT,
    output_summary  TEXT,
    duration_ms     INTEGER,
    success         BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_tool_log_session  ON assistant_tool_log(session_id);
CREATE INDEX IF NOT EXISTS idx_tool_log_tool     ON assistant_tool_log(tool_name);
CREATE INDEX IF NOT EXISTS idx_tool_log_created  ON assistant_tool_log(created_at);


-- 5. Performance Metrics — daily aggregated stats
CREATE TABLE IF NOT EXISTS assistant_performance_metrics (
    id                      SERIAL PRIMARY KEY,
    metric_date             DATE DEFAULT CURRENT_DATE,
    total_chats             INTEGER DEFAULT 0,
    total_tasks             INTEGER DEFAULT 0,
    total_errors            INTEGER DEFAULT 0,
    avg_response_time_ms    FLOAT,
    p50_response_time_ms    FLOAT,
    p95_response_time_ms    FLOAT,
    avg_confidence          FLOAT,
    openai_usage_count      INTEGER DEFAULT 0,
    ollama_usage_count      INTEGER DEFAULT 0,
    unique_sessions         INTEGER DEFAULT 0,
    furniture_type_breakdown JSONB,         -- {"round_pedestal_table": 15, "cabinet": 3}
    error_type_breakdown    JSONB,          -- {"OCR_failed": 2, "DXF_export_failed": 1}
    updated_at              TIMESTAMP DEFAULT NOW(),
    UNIQUE(metric_date)
);

CREATE INDEX IF NOT EXISTS idx_perf_metrics_date ON assistant_performance_metrics(metric_date);


-- 6. Improvement Recommendations — auto-generated by the monitoring worker
CREATE TABLE IF NOT EXISTS assistant_improvement_recommendations (
    id                  SERIAL PRIMARY KEY,
    recommendation_type VARCHAR(50) NOT NULL,  -- accuracy, performance, ui, error, pattern
    title               VARCHAR(200) NOT NULL,
    description         TEXT,
    evidence            JSONB,                 -- data supporting the recommendation
    impact              VARCHAR(50) DEFAULT 'medium',  -- high, medium, low
    effort              VARCHAR(50) DEFAULT 'medium',  -- high, medium, low
    status              VARCHAR(20) DEFAULT 'open',    -- open, in_progress, implemented, dismissed
    source             VARCHAR(100),           -- the monitoring analysis that generated this
    created_at          TIMESTAMP DEFAULT NOW(),
    implemented_at      TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_recommendation_status ON assistant_improvement_recommendations(status);
CREATE INDEX IF NOT EXISTS idx_recommendation_type   ON assistant_improvement_recommendations(recommendation_type);
CREATE INDEX IF NOT EXISTS idx_recommendation_created ON assistant_improvement_recommendations(created_at);
