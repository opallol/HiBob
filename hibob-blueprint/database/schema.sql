-- Hibob initial canonical schema draft
-- Baseline: 2026-06-23
-- Target DB: PostgreSQL. Can be adapted to SQLite for prototype.

CREATE TABLE users (
    id UUID PRIMARY KEY,
    display_name TEXT NOT NULL,
    timezone TEXT DEFAULT 'Asia/Jakarta',
    default_privacy_tier TEXT DEFAULT 'internal',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE personas (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT,
    active BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE persona_rules (
    id UUID PRIMARY KEY,
    persona_id UUID REFERENCES personas(id),
    rule_type TEXT NOT NULL,
    content TEXT NOT NULL,
    priority INTEGER DEFAULT 100,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE conversations (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    title TEXT,
    conversation_type TEXT DEFAULT 'chat',
    status TEXT DEFAULT 'active',
    privacy_tier TEXT DEFAULT 'internal',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE model_runs (
    id UUID PRIMARY KEY,
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

CREATE TABLE messages (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    content_type TEXT DEFAULT 'text',
    model_run_id UUID REFERENCES model_runs(id),
    trace_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE session_summaries (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    summary TEXT NOT NULL,
    decisions_json JSONB DEFAULT '[]',
    assumptions_json JSONB DEFAULT '[]',
    risks_json JSONB DEFAULT '[]',
    open_questions_json JSONB DEFAULT '[]',
    memory_candidates_json JSONB DEFAULT '[]',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE memories (
    id UUID PRIMARY KEY,
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

CREATE INDEX idx_memories_user_status ON memories(user_id, status);
CREATE INDEX idx_memories_type_scope ON memories(memory_type, scope);
CREATE INDEX idx_memories_sensitivity ON memories(sensitivity);

CREATE TABLE memory_sources (
    id UUID PRIMARY KEY,
    memory_id UUID REFERENCES memories(id),
    source_type TEXT NOT NULL,
    source_id UUID,
    quote_or_excerpt TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE memory_conflicts (
    id UUID PRIMARY KEY,
    memory_id_a UUID REFERENCES memories(id),
    memory_id_b UUID REFERENCES memories(id),
    conflict_type TEXT NOT NULL,
    severity TEXT DEFAULT 'medium',
    status TEXT DEFAULT 'open',
    resolution_note TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    resolved_at TIMESTAMPTZ
);

CREATE TABLE memory_reviews (
    id UUID PRIMARY KEY,
    memory_id UUID REFERENCES memories(id),
    reviewer_user_id UUID REFERENCES users(id),
    decision TEXT NOT NULL,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE memory_embeddings (
    id UUID PRIMARY KEY,
    memory_id UUID REFERENCES memories(id),
    vector_collection TEXT NOT NULL,
    vector_id TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dim INTEGER NOT NULL,
    embedding_version TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE web_sources (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    url TEXT NOT NULL,
    canonical_url TEXT,
    crawl_status TEXT DEFAULT 'pending',
    content_hash TEXT,
    last_crawled_at TIMESTAMPTZ,
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE documents (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    title TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_uri TEXT,
    web_source_id UUID REFERENCES web_sources(id),
    file_hash TEXT,
    privacy_tier TEXT DEFAULT 'internal',
    status TEXT DEFAULT 'pending',
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE document_chunks (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_id, chunk_index)
);

CREATE TABLE document_embeddings (
    id UUID PRIMARY KEY,
    chunk_id UUID REFERENCES document_chunks(id),
    vector_collection TEXT NOT NULL,
    vector_id TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dim INTEGER NOT NULL,
    embedding_version TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE ingestion_jobs (
    id UUID PRIMARY KEY,
    document_id UUID REFERENCES documents(id),
    job_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE agent_runs (
    id UUID PRIMARY KEY,
    conversation_id UUID REFERENCES conversations(id),
    agent_name TEXT NOT NULL,
    status TEXT DEFAULT 'running',
    trace_id TEXT,
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ,
    metadata_json JSONB DEFAULT '{}'
);

CREATE TABLE agent_steps (
    id UUID PRIMARY KEY,
    agent_run_id UUID REFERENCES agent_runs(id),
    step_index INTEGER NOT NULL,
    step_type TEXT NOT NULL,
    input_json JSONB DEFAULT '{}',
    output_json JSONB DEFAULT '{}',
    status TEXT DEFAULT 'succeeded',
    trace_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tools (
    id UUID PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT NOT NULL,
    tool_type TEXT NOT NULL,
    input_schema_json JSONB NOT NULL,
    output_schema_json JSONB NOT NULL,
    risk_level TEXT NOT NULL,
    default_permission TEXT NOT NULL,
    enabled BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE policy_versions (
    id UUID PRIMARY KEY,
    policy_name TEXT NOT NULL,
    version TEXT NOT NULL,
    content TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(policy_name, version)
);

CREATE TABLE tool_permissions (
    id UUID PRIMARY KEY,
    tool_id UUID REFERENCES tools(id),
    policy_version_id UUID REFERENCES policy_versions(id),
    permission_mode TEXT NOT NULL,
    allowed_scopes JSONB DEFAULT '[]',
    constraints_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE approval_requests (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    request_type TEXT NOT NULL,
    summary TEXT NOT NULL,
    payload_json JSONB NOT NULL,
    status TEXT DEFAULT 'pending',
    expires_at TIMESTAMPTZ,
    decided_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tool_runs (
    id UUID PRIMARY KEY,
    tool_id UUID REFERENCES tools(id),
    agent_run_id UUID REFERENCES agent_runs(id),
    requested_by TEXT NOT NULL,
    input_json JSONB NOT NULL,
    output_json JSONB DEFAULT '{}',
    status TEXT DEFAULT 'requested',
    risk_level_at_run TEXT NOT NULL,
    approval_request_id UUID REFERENCES approval_requests(id),
    trace_id TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE audit_logs (
    id UUID PRIMARY KEY,
    actor_type TEXT NOT NULL,
    actor_id TEXT,
    event_type TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE eval_suites (
    id UUID PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE eval_cases (
    id UUID PRIMARY KEY,
    suite_id UUID REFERENCES eval_suites(id),
    name TEXT NOT NULL,
    input_json JSONB NOT NULL,
    expected_behavior TEXT NOT NULL,
    prohibited_behavior TEXT,
    metric_config_json JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE eval_runs (
    id UUID PRIMARY KEY,
    suite_id UUID REFERENCES eval_suites(id),
    target_version TEXT,
    status TEXT DEFAULT 'running',
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE eval_results (
    id UUID PRIMARY KEY,
    eval_run_id UUID REFERENCES eval_runs(id),
    eval_case_id UUID REFERENCES eval_cases(id),
    score NUMERIC(5,4),
    passed BOOLEAN,
    explanation TEXT,
    trace_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE trace_links (
    id UUID PRIMARY KEY,
    trace_id TEXT NOT NULL,
    entity_type TEXT NOT NULL,
    entity_id UUID NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ============================================================
-- v0.2 additions - accepted overpower recommendations
-- See adr/0005 .. adr/0013 and docs/03_ERD_DATA_MODEL.md section 10
-- ============================================================

-- ADR 0006 - Temporal Knowledge Graph Memory
CREATE TABLE memory_edges (
    id UUID PRIMARY KEY,
    memory_id_from UUID REFERENCES memories(id),
    memory_id_to UUID REFERENCES memories(id),
    relation_type TEXT NOT NULL, -- supersedes, contradicts, depends_on, supports, derived_from
    discovered_at TIMESTAMPTZ DEFAULT now(),
    confidence NUMERIC(4,3) DEFAULT 0.500,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_memory_edges_from ON memory_edges(memory_id_from);
CREATE INDEX idx_memory_edges_to ON memory_edges(memory_id_to);
CREATE INDEX idx_memory_edges_relation ON memory_edges(relation_type);

-- ADR 0007 - Self-Calibrating Memory Confidence
CREATE TABLE memory_usage_feedback (
    id UUID PRIMARY KEY,
    memory_id UUID REFERENCES memories(id),
    conversation_id UUID REFERENCES conversations(id),
    event_type TEXT NOT NULL, -- used, corrected, accepted, ignored
    signal_strength NUMERIC(4,3) DEFAULT 1.000,
    note TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_memory_usage_feedback_memory ON memory_usage_feedback(memory_id);

-- ADR 0005 - Policy-as-Code Tool Gateway with Trust Tiers and Injection Defense
CREATE TABLE policy_rules (
    id UUID PRIMARY KEY,
    policy_version_id UUID REFERENCES policy_versions(id),
    rule_key TEXT NOT NULL, -- e.g. tool_type+risk_level+sensitivity combination
    condition_json JSONB NOT NULL,
    decision TEXT NOT NULL, -- allow, ask, deny
    priority INTEGER DEFAULT 100,
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE tool_trust_scores (
    id UUID PRIMARY KEY,
    tool_id UUID REFERENCES tools(id),
    context TEXT NOT NULL, -- e.g. chat, blueprint, coding, eval
    trust_score NUMERIC(5,4) DEFAULT 0.0000,
    successful_runs INTEGER DEFAULT 0,
    flagged_runs INTEGER DEFAULT 0,
    last_reset_at TIMESTAMPTZ,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(tool_id, context)
);

CREATE TABLE content_provenance_flags (
    id UUID PRIMARY KEY,
    source_type TEXT NOT NULL, -- message, document_chunk, tool_output, web
    source_id UUID NOT NULL,
    provenance TEXT NOT NULL, -- system, user, policy, retrieved_data, tool_output
    injection_suspected BOOLEAN DEFAULT false,
    classifier_score NUMERIC(5,4),
    trace_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ADR 0008 - Deterministic Replay Harness
CREATE TABLE replay_runs (
    id UUID PRIMARY KEY,
    source_model_run_id UUID REFERENCES model_runs(id),
    candidate_provider TEXT NOT NULL,
    candidate_model TEXT NOT NULL,
    assembled_input_ref TEXT NOT NULL, -- pointer to redacted stored prompt context
    status TEXT DEFAULT 'pending', -- pending, running, succeeded, failed
    diff_summary_json JSONB DEFAULT '{}',
    eval_comparison_json JSONB DEFAULT '{}',
    decision TEXT, -- adopt, reject, inconclusive
    created_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ
);

-- ADR 0009 - Adversarial Self-Red-Team Loop and Eval Judge Integrity
CREATE TABLE redteam_attempts (
    id UUID PRIMARY KEY,
    attack_type TEXT NOT NULL, -- injected_document, permission_persuasion, persona_social_engineering
    target_tool_id UUID REFERENCES tools(id),
    payload_summary TEXT NOT NULL,
    outcome TEXT NOT NULL, -- blocked, succeeded, partial
    converted_to_eval_case_id UUID REFERENCES eval_cases(id),
    trace_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE eval_judge_versions (
    id UUID PRIMARY KEY,
    judge_provider TEXT NOT NULL,
    judge_model TEXT NOT NULL,
    judge_version TEXT NOT NULL,
    golden_set_agreement_score NUMERIC(5,4),
    validated_at TIMESTAMPTZ,
    status TEXT DEFAULT 'active', -- active, deprecated
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ADR 0010 - Reflective Sibling Proactive Loop
CREATE TABLE reflections (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    reflection_type TEXT NOT NULL, -- conflict_scan, untested_assumption, stale_source
    summary TEXT NOT NULL,
    related_memory_ids JSONB DEFAULT '[]',
    related_edge_ids JSONB DEFAULT '[]',
    proposed_candidate_ids JSONB DEFAULT '[]',
    status TEXT DEFAULT 'unread', -- unread, read, acted_on, dismissed
    created_at TIMESTAMPTZ DEFAULT now()
);

-- ADR 0011 - Ephemeral OS-Level Sandbox for Tool Execution
CREATE TABLE sandbox_runs (
    id UUID PRIMARY KEY,
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

-- ADR 0012 - Learned Model Router and Cost Circuit Breaker
CREATE TABLE budget_ceilings (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    scope TEXT NOT NULL, -- daily, session
    ceiling_amount NUMERIC(12,6) NOT NULL,
    currency TEXT DEFAULT 'USD',
    period_start TIMESTAMPTZ NOT NULL,
    period_end TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE cost_ledger (
    id UUID PRIMARY KEY,
    model_run_id UUID REFERENCES model_runs(id),
    budget_ceiling_id UUID REFERENCES budget_ceilings(id),
    amount NUMERIC(12,6) NOT NULL,
    running_total NUMERIC(12,6) NOT NULL,
    ceiling_breached BOOLEAN DEFAULT false,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE router_policy_feedback (
    id UUID PRIMARY KEY,
    task_type TEXT NOT NULL,
    provider TEXT NOT NULL,
    model TEXT NOT NULL,
    avg_eval_score NUMERIC(5,4),
    avg_latency_ms INTEGER,
    avg_cost NUMERIC(12,6),
    sample_size INTEGER DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(task_type, provider, model)
);
