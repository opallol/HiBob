-- Hibob Phase 8 (Personal AI OS Beta) - projects registry.
-- New feature table; mirrored into ../../../database/schema.sql.
-- Lightweight project organization; unified recall + memory can be scoped to a project.
--
-- Apply manually: docker exec -i hibob-core-postgres psql -U hibob -d hibob < 0010_phase8.sql

CREATE TABLE IF NOT EXISTS projects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'active',   -- active | archived
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, name)
);

CREATE INDEX IF NOT EXISTS idx_projects_user_status ON projects(user_id, status);
