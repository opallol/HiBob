-- Hibob Phase 1 (Core Minimal) schema subset.
-- Tables copied verbatim from ../../../database/schema.sql - DO NOT diverge.
-- Scope: identity, conversation, model_runs, cost breaker (ADR 0012), audit.
-- Later phases add memory/knowledge/tools/policy tables from the same canonical file.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";  -- for gen_random_uuid()

-- ---- Identity ----
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    display_name TEXT NOT NULL,
    timezone TEXT DEFAULT 'Asia/Jakarta',
    default_privacy_tier TEXT DEFAULT 'internal',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS personas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    active BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS persona_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    persona_id UUID REFERENCES personas(id),
    rule_type TEXT NOT NULL,
    content TEXT NOT NULL,
    priority INTEGER DEFAULT 100,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---- Model runs (cost/latency/trace ledger) ----
CREATE TABLE IF NOT EXISTS model_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    task_type TEXT,
    prompt_version TEXT,
    input_tokens INTEGER,
    output_tokens INTEGER,
    latency_ms INTEGER,
    cost_estimate NUMERIC(12,6),
    trace_id TEXT,
    status TEXT DEFAULT 'succeeded',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---- Conversation ----
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    title TEXT,
    conversation_type TEXT DEFAULT 'chat',
    status TEXT DEFAULT 'active',
    privacy_tier TEXT DEFAULT 'internal',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'text',
    model_run_id UUID REFERENCES model_runs(id),
    trace_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS session_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    summary TEXT NOT NULL,
    decisions_json JSONB DEFAULT '[]',
    assumptions_json JSONB DEFAULT '[]',
    risks_json JSONB DEFAULT '[]',
    open_questions_json JSONB DEFAULT '[]',
    memory_candidates_json JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---- Cost circuit breaker (ADR 0012) ----
CREATE TABLE IF NOT EXISTS budget_ceilings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    scope TEXT NOT NULL,                 -- daily, session
    ceiling_amount NUMERIC(12,6) NOT NULL,
    currency TEXT DEFAULT 'USD',
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS cost_ledger (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_run_id UUID REFERENCES model_runs(id),
    budget_ceiling_id UUID REFERENCES budget_ceilings(id),
    amount NUMERIC(12,6) NOT NULL,
    running_total NUMERIC(12,6) NOT NULL,
    ceiling_breached BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ---- Audit ----
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    actor_type TEXT NOT NULL,            -- user, assistant, system, tool
    actor_id TEXT,
    event_type TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);
