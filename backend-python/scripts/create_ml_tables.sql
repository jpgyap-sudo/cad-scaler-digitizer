-- Central Brain: Furniture Intelligence Graph
-- Extends existing ml_predictions + ml_models tables

-- 1. Every correction tracked for cross-user learning
CREATE TABLE IF NOT EXISTS furniture_corrections (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    furniture_type TEXT,
    field TEXT NOT NULL,            -- e.g. "pedestal_diameter_cm"
    old_value TEXT,                  -- system default or previous
    new_value TEXT,                  -- user-specified
    correction_ratio FLOAT,          -- new/old (for dimension multipliers)
    correction_type TEXT,            -- "dimension", "material", "visibility", "type"
    user_id TEXT DEFAULT 'default',
    context JSONB,                   -- full drawing context at time of correction
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_corrections_type ON furniture_corrections(furniture_type);
CREATE INDEX IF NOT EXISTS idx_corrections_field ON furniture_corrections(field);
CREATE INDEX IF NOT EXISTS idx_corrections_user ON furniture_corrections(user_id);

-- 2. Global material library with usage frequency
CREATE TABLE IF NOT EXISTS material_library (
    id SERIAL PRIMARY KEY,
    component TEXT NOT NULL,          -- e.g. "tabletop", "pedestal_base"
    material TEXT NOT NULL,           -- e.g. "Solid European Oak"
    finish TEXT,                      -- e.g. "natural oil"
    texture TEXT,                     -- e.g. "hammered", "brushed"
    color TEXT,
    usage_count INTEGER DEFAULT 1,
    furniture_type TEXT,
    hatch_pattern TEXT,               -- recommended DXF hatch
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(component, material, furniture_type)
);

CREATE INDEX IF NOT EXISTS idx_materials_component ON material_library(component);
CREATE INDEX IF NOT EXISTS idx_materials_type ON material_library(furniture_type);

-- 3. Persisted style presets (replaces JSON files)
CREATE TABLE IF NOT EXISTS style_presets (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    user_id TEXT DEFAULT 'default',
    furniture_type TEXT DEFAULT 'round_pedestal_table',
    materials JSONB DEFAULT '{}',     -- {component: material}
    dimensions JSONB DEFAULT '{}',    -- {key: value_cm}
    visibility JSONB DEFAULT '{}',    -- {component: bool}
    notes JSONB DEFAULT '[]',
    finish_notes JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_presets_user ON style_presets(user_id);

-- 4. Persistent chat sessions (replaces in-memory dict)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL UNIQUE,
    user_id TEXT DEFAULT 'default',
    image_id TEXT,
    state JSONB DEFAULT '{}',         -- full DrawingState
    message_count INTEGER DEFAULT 0,
    last_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_chat_sessions_id ON chat_sessions(session_id);

-- 5. Drawing history with quality tracking
CREATE TABLE IF NOT EXISTS drawing_history (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    furniture_type TEXT,
    dxf_file TEXT,
    quality_score FLOAT,              -- from dxf_auditor
    entity_counts JSONB,              -- {CIRCLE:1, LINE:21, ...}
    dimensions_used JSONB,            -- actual dims used for generation
    preview_urls JSONB,               -- {svg, png, pdf}
    correction_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_drawings_session ON drawing_history(session_id);
CREATE INDEX IF NOT EXISTS idx_drawings_type ON drawing_history(furniture_type);

-- 6. Global component proportion statistics
CREATE TABLE IF NOT EXISTS component_proportions (
    id SERIAL PRIMARY KEY,
    furniture_type TEXT NOT NULL,
    anchor_dimension TEXT NOT NULL,    -- e.g. "top_diameter_cm"
    anchor_value FLOAT NOT NULL,       -- e.g. 80.0
    component TEXT NOT NULL,           -- e.g. "pedestal_diameter_cm"
    component_value FLOAT NOT NULL,    -- e.g. 44.0
    ratio FLOAT NOT NULL,              -- component/anchor ratio
    sample_count INTEGER DEFAULT 1,
    confidence FLOAT DEFAULT 0.5,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(furniture_type, anchor_dimension, anchor_value, component)
);

CREATE INDEX IF NOT EXISTS idx_proportions_type ON component_proportions(furniture_type);
