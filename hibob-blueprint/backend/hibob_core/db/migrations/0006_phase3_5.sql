-- Hibob Phase 3.5 (Reflective Sibling) activation.
-- Table copied from ../../../database/schema.sql - DO NOT diverge.
-- The reflection job is strictly read-only re: memory/tools; it only writes `reflections`
-- (and audit_logs). Findings are candidates Bob reads async, never auto-applied (ADR 0010).
--
-- Apply manually (volume persists, initdb will NOT auto-run):
--   docker exec -i hibob-core-postgres psql -U hibob -d hibob < 0006_phase3_5.sql

CREATE TABLE IF NOT EXISTS reflections (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    reflection_type TEXT NOT NULL,  -- conflict_scan, untested_assumption, stale_source
    summary TEXT NOT NULL,
    related_memory_ids JSONB DEFAULT '[]',
    related_edge_ids JSONB DEFAULT '[]',
    proposed_candidate_ids JSONB DEFAULT '[]',
    status TEXT DEFAULT 'unread',   -- unread, read, acted_on, dismissed
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_reflections_user_status ON reflections(user_id, status);
