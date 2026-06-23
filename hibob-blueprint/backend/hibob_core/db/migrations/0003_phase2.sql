-- Hibob Phase 2 (Memory Core) schema subset.
-- Tables copied from ../../../database/schema.sql - DO NOT diverge.
-- Active in Phase 2: memories, memory_sources, memory_conflicts, memory_reviews, memory_embeddings.
-- Created but NOT activated (seam for Phase 2.5, ADR 0006/0007): memory_edges, memory_usage_feedback.
--
-- NOTE: the volume persists from Phase 1, so docker-entrypoint-initdb.d will NOT auto-run this.
-- Apply manually: docker exec -i hibob-core-postgres psql -U hibob -d hibob < 0003_phase2.sql

CREATE TABLE IF NOT EXISTS memories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    memory_type TEXT NOT NULL,
    scope TEXT NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'candidate',
    confidence NUMERIC(4,3) DEFAULT 0.500,
    sensitivity TEXT DEFAULT 'internal',
    stability TEXT DEFAULT 'medium',
    valid_from TIMESTAMPTZ DEFAULT now(),
    valid_until TIMESTAMPTZ,
    superseded_by_memory_id UUID REFERENCES memories(id),
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memories_user_status ON memories(user_id, status);
CREATE INDEX IF NOT EXISTS idx_memories_type_scope ON memories(memory_type, scope);
CREATE INDEX IF NOT EXISTS idx_memories_sensitivity ON memories(sensitivity);

CREATE TABLE IF NOT EXISTS memory_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID REFERENCES memories(id),
    source_type TEXT NOT NULL,
    source_id UUID,
    quote_or_excerpt TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_conflicts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id_a UUID REFERENCES memories(id),
    memory_id_b UUID REFERENCES memories(id),
    conflict_type TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'open',
    resolution_note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS memory_reviews (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID REFERENCES memories(id),
    reviewer_user_id UUID REFERENCES users(id),
    decision TEXT NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS memory_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID REFERENCES memories(id),
    vector_collection TEXT NOT NULL,
    vector_id TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dim INTEGER NOT NULL,
    embedding_version TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---- Seam for Phase 2.5 (created, not used in Phase 2) ----

-- ADR 0006 - Temporal Knowledge Graph Memory
CREATE TABLE IF NOT EXISTS memory_edges (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id_from UUID REFERENCES memories(id),
    memory_id_to UUID REFERENCES memories(id),
    relation_type TEXT NOT NULL,  -- supersedes, contradicts, depends_on, supports, derived_from
    discovered_at TIMESTAMPTZ DEFAULT now(),
    confidence NUMERIC(4,3) DEFAULT 0.500,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_edges_from ON memory_edges(memory_id_from);
CREATE INDEX IF NOT EXISTS idx_memory_edges_to ON memory_edges(memory_id_to);
CREATE INDEX IF NOT EXISTS idx_memory_edges_relation ON memory_edges(relation_type);

-- ADR 0007 - Self-Calibrating Memory Confidence
CREATE TABLE IF NOT EXISTS memory_usage_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    memory_id UUID REFERENCES memories(id),
    conversation_id UUID REFERENCES conversations(id),
    event_type TEXT NOT NULL,  -- used, corrected, accepted, ignored
    signal_strength NUMERIC(4,3) DEFAULT 1.000,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_memory_usage_feedback_memory ON memory_usage_feedback(memory_id);

-- ---- Seed: core approved memories so recall is testable immediately ----
INSERT INTO memories (id, user_id, memory_type, scope, title, content, status, confidence, sensitivity, stability)
VALUES
('00000000-0000-0000-0000-0000000000d1', '00000000-0000-0000-0000-000000000001',
 'system_identity', 'hibob', 'Hibob adalah saudara digital',
 'Hibob berinteraksi sebagai saudara digital Bob: natural, kritis, konstruktif - bukan asisten formal.',
 'approved', 0.980, 'internal', 'durable'),
('00000000-0000-0000-0000-0000000000d2', '00000000-0000-0000-0000-000000000001',
 'decision', 'project', 'Hibob Core tidak terikat Open WebUI',
 'Open WebUI boleh dipakai sebagai cockpit/UI, tapi Hibob Core yang memegang memory, tool policy, dan identitas. Core tidak boleh larut jadi satu tool.',
 'approved', 0.900, 'internal', 'durable'),
('00000000-0000-0000-0000-0000000000d3', '00000000-0000-0000-0000-000000000001',
 'preference', 'bob', 'Bob suka diskusi sebelum implementasi',
 'Bob lebih suka mendiskusikan ide secara mendalam sebelum coding/scaffolding, dan tidak suka implementasi yang terburu-buru.',
 'approved', 0.950, 'internal', 'durable')
ON CONFLICT (id) DO NOTHING;
