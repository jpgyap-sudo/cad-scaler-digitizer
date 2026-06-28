CREATE TABLE IF NOT EXISTS engineering_analyses (
    id SERIAL PRIMARY KEY,
    product_id TEXT UNIQUE NOT NULL,
    furniture_type TEXT,
    furniture_subtype TEXT,
    family TEXT,
    overall_dims_json JSONB DEFAULT '{}',
    materials_json JSONB DEFAULT '[]',
    components_json JSONB DEFAULT '[]',
    joinery_json JSONB DEFAULT '[]',
    bom_json JSONB DEFAULT '[]',
    hardware_json JSONB DEFAULT '[]',
    confidence_scores_json JSONB DEFAULT '{}',
    analysis_json JSONB DEFAULT '{}',
    image_url TEXT,
    source_url TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_engineering_furniture_type ON engineering_analyses(furniture_type);
CREATE INDEX IF NOT EXISTS idx_engineering_family ON engineering_analyses(family);
CREATE INDEX IF NOT EXISTS idx_engineering_created ON engineering_analyses(created_at DESC);
