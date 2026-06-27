CREATE TABLE IF NOT EXISTS comparison_results (
    id SERIAL PRIMARY KEY,
    job_id TEXT UNIQUE NOT NULL,
    product_id TEXT,
    overall_score FLOAT NOT NULL DEFAULT 0.0,
    edge_overlap_score FLOAT DEFAULT 0.0,
    entity_match_score FLOAT DEFAULT 0.0,
    dimension_deviation_pct FLOAT DEFAULT 0.0,
    errors_json JSONB DEFAULT '[]',
    dimension_comparisons_json JSONB DEFAULT '[]',
    image_width INT DEFAULT 0,
    image_height INT DEFAULT 0,
    dxf_width_mm FLOAT DEFAULT 0.0,
    dxf_height_mm FLOAT DEFAULT 0.0,
    image_url TEXT,
    dxf_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_comparison_results_score ON comparison_results(overall_score);
CREATE INDEX IF NOT EXISTS idx_comparison_results_job_id ON comparison_results(job_id);
