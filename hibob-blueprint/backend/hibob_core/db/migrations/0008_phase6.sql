-- Hibob Phase 6 (Observability & Regression Quality) activation.
-- Tables copied from ../../../database/schema.sql - DO NOT diverge.
-- Active: eval_suites, eval_cases, eval_runs, eval_results (rule-based harness).
-- Seam (created + recordable, live wiring later): replay_runs (ADR 0008),
-- eval_judge_versions (ADR 0009), router_policy_feedback (ADR 0012).
--
-- Apply manually: docker exec -i hibob-core-postgres psql -U hibob -d hibob < 0008_phase6.sql

CREATE TABLE IF NOT EXISTS eval_suites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suite_id UUID REFERENCES eval_suites(id),
    name TEXT NOT NULL,
    input_json JSONB NOT NULL,
    expected_behavior TEXT NOT NULL,
    prohibited_behavior TEXT,
    metric_config_json JSONB DEFAULT '{}',
    enabled BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS eval_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    suite_id UUID REFERENCES eval_suites(id),
    target_version TEXT,
    status TEXT DEFAULT 'running',
    started_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS eval_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    eval_run_id UUID REFERENCES eval_runs(id),
    eval_case_id UUID REFERENCES eval_cases(id),
    score NUMERIC(5,4),
    passed BOOLEAN,
    explanation TEXT,
    trace_id TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_eval_results_run ON eval_results(eval_run_id);

CREATE TABLE IF NOT EXISTS replay_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source_model_run_id UUID REFERENCES model_runs(id),
    candidate_provider TEXT NOT NULL,
    candidate_model TEXT NOT NULL,
    assembled_input_ref TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    diff_summary_json JSONB DEFAULT '{}',
    eval_comparison_json JSONB DEFAULT '{}',
    decision TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS eval_judge_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    judge_provider TEXT NOT NULL,
    judge_model TEXT NOT NULL,
    judge_version TEXT NOT NULL,
    golden_set_agreement_score NUMERIC(5,4),
    validated_at TIMESTAMPTZ,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS router_policy_feedback (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

-- ---- Seed: a deterministic tool_policy_eval suite (validates the Policy Engine, ADR 0005) ----
INSERT INTO eval_suites (id, name, description) VALUES
('00000000-0000-0000-0000-0000000000e1', 'tool_policy_eval',
 'Deterministic allow/ask/deny checks against the Policy Engine (doc 09 §5).')
ON CONFLICT (name) DO NOTHING;

INSERT INTO eval_cases (id, suite_id, name, input_json, expected_behavior, metric_config_json) VALUES
('00000000-0000-0000-0000-0000000000c1', '00000000-0000-0000-0000-0000000000e1',
 'low risk auto-allow', '{"risk_level":"low","tool_type":"internal"}', 'allow', '{"metric":"policy"}'),
('00000000-0000-0000-0000-0000000000c2', '00000000-0000-0000-0000-0000000000e1',
 'medium below trust asks', '{"risk_level":"medium","tool_type":"internal","trust_score":0.0}', 'ask', '{"metric":"policy"}'),
('00000000-0000-0000-0000-0000000000c3', '00000000-0000-0000-0000-0000000000e1',
 'medium above trust allows', '{"risk_level":"medium","tool_type":"internal","trust_score":0.95}', 'allow', '{"metric":"policy"}'),
('00000000-0000-0000-0000-0000000000c4', '00000000-0000-0000-0000-0000000000e1',
 'high always asks', '{"risk_level":"high","tool_type":"internal","trust_score":1.0}', 'ask', '{"metric":"policy"}'),
('00000000-0000-0000-0000-0000000000c5', '00000000-0000-0000-0000-0000000000e1',
 'critical denied', '{"risk_level":"critical","tool_type":"internal"}', 'deny', '{"metric":"policy"}'),
('00000000-0000-0000-0000-0000000000c6', '00000000-0000-0000-0000-0000000000e1',
 'shell without sandbox denied', '{"risk_level":"low","tool_type":"shell","sandbox_available":false}', 'deny', '{"metric":"policy"}')
ON CONFLICT (id) DO NOTHING;

-- ---- Seed: pinned eval judge version (ADR 0009) ----
INSERT INTO eval_judge_versions (judge_provider, judge_model, judge_version, golden_set_agreement_score, validated_at, status)
VALUES ('ollama', 'qwen3.5:9b', 'judge-v1', NULL, now(), 'active')
ON CONFLICT DO NOTHING;
