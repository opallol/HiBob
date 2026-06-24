-- Hibob Phase 4 (Tool Gateway + Policy Engine) activation.
-- Tables copied from ../../../database/schema.sql - DO NOT diverge.
-- Active in Phase 4: tools, policy_versions, policy_rules, approval_requests, tool_runs,
-- tool_trust_scores, content_provenance_flags. Seam (created, unused): sandbox_runs (ADR 0011).
-- Credential Vault (ADR 0014) is deferred to the first credential-using tool (Phase 7).
--
-- Apply manually (volume persists, initdb will NOT auto-run):
--   docker exec -i hibob-core-postgres psql -U hibob -d hibob < 0007_phase4.sql

CREATE TABLE IF NOT EXISTS agent_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id),
    agent_name TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    trace_id TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ,
    metadata_json JSONB DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS tools (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    tool_type TEXT NOT NULL,            -- internal | shell | browser | mcp | agent
    input_schema_json JSONB NOT NULL,
    output_schema_json JSONB NOT NULL,
    risk_level TEXT NOT NULL,           -- low | medium | high | critical
    default_permission TEXT NOT NULL,   -- allow | ask | deny
    enabled BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS policy_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_name TEXT NOT NULL,
    version TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(policy_name, version)
);

CREATE TABLE IF NOT EXISTS policy_rules (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    policy_version_id UUID REFERENCES policy_versions(id),
    rule_key TEXT NOT NULL,
    condition_json JSONB NOT NULL,
    decision TEXT NOT NULL,             -- allow | ask | deny
    priority INTEGER DEFAULT 100,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS approval_requests (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    request_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    status TEXT DEFAULT 'pending',      -- pending | approved | denied
    expires_at TIMESTAMPTZ,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS tool_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id UUID REFERENCES tools(id),
    agent_run_id UUID REFERENCES agent_runs(id),
    requested_by TEXT NOT NULL,
    input_json JSONB NOT NULL,
    output_json JSONB DEFAULT '{}',
    status TEXT DEFAULT 'requested',    -- requested | pending_approval | running | succeeded | failed | denied
    risk_level_at_run TEXT NOT NULL,
    approval_request_id UUID REFERENCES approval_requests(id),
    trace_id TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tool_runs_tool ON tool_runs(tool_id);
CREATE INDEX IF NOT EXISTS idx_tool_runs_status ON tool_runs(status);

CREATE TABLE IF NOT EXISTS tool_trust_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_id UUID REFERENCES tools(id),
    context TEXT NOT NULL,              -- chat | blueprint | coding | eval
    trust_score NUMERIC(5,4) DEFAULT 0.0000,
    successful_runs INTEGER DEFAULT 0,
    flagged_runs INTEGER DEFAULT 0,
    last_reset_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tool_id, context)
);

CREATE TABLE IF NOT EXISTS content_provenance_flags (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_type TEXT NOT NULL,         -- message | document_chunk | tool_output | web
    source_id UUID NOT NULL,
    provenance TEXT NOT NULL,          -- system | user | policy | retrieved_data | tool_output
    injection_suspected BOOLEAN DEFAULT false,
    classifier_score NUMERIC(5,4),
    trace_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Seam for ADR 0011 (created, unused in Phase 4): shell/browser/mcp tools are default-deny
-- until a real ephemeral sandbox runtime is wired here.
CREATE TABLE IF NOT EXISTS sandbox_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tool_run_id UUID REFERENCES tool_runs(id),
    container_image TEXT NOT NULL,
    network_mode TEXT DEFAULT 'none',
    filesystem_mode TEXT DEFAULT 'read_only',
    workdir_scope TEXT,
    started_at TIMESTAMPTZ,
    destroyed_at TIMESTAMPTZ,
    exit_status TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Version pointer for the active tool policy (the effective rules live in the engine).
INSERT INTO policy_versions (policy_name, version, content, status)
VALUES ('tool_policy', 'v1', 'risk-tiered allow/ask/deny with trust escalation (ADR 0005)', 'active')
ON CONFLICT (policy_name, version) DO NOTHING;
