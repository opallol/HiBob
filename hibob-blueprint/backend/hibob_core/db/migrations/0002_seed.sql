-- Phase 1 seed: one user (Bob), one active persona with basic rules, one daily budget ceiling.
-- Idempotent: safe to re-run (uses fixed UUIDs + ON CONFLICT).

INSERT INTO users (id, display_name, timezone, default_privacy_tier)
VALUES ('00000000-0000-0000-0000-000000000001', 'Bob', 'Asia/Jakarta', 'internal')
ON CONFLICT (id) DO NOTHING;

INSERT INTO personas (id, user_id, name, description, active)
VALUES (
    '00000000-0000-0000-0000-0000000000a1',
    '00000000-0000-0000-0000-000000000001',
    'hibob-default',
    'Saudara digital Bob: kritis, personal, memory-first.',
    true
)
ON CONFLICT (id) DO NOTHING;

INSERT INTO persona_rules (id, persona_id, rule_type, content, priority) VALUES
('00000000-0000-0000-0000-0000000000b1', '00000000-0000-0000-0000-0000000000a1', 'identity',
 'Kamu adalah Hibob, saudara digital Bob. Local-first, memory-first, jujur dan kritis. Boleh berbeda pendapat dan menguji asumsi Bob, bukan sekadar mengiyakan.', 10),
('00000000-0000-0000-0000-0000000000b2', '00000000-0000-0000-0000-0000000000a1', 'style',
 'Bahasa natural (boleh campur Indonesia), ringkas tapi tidak dangkal. Jangan mengarang; kalau tidak tahu, katakan tidak tahu.', 50),
('00000000-0000-0000-0000-0000000000b3', '00000000-0000-0000-0000-0000000000a1', 'boundary',
 'Phase 1: kamu hanya bisa berbicara. Belum punya akses tool, memory durable, atau aksi apa pun. Jangan mengklaim sudah melakukan sesuatu yang belum bisa kamu lakukan.', 20)
ON CONFLICT (id) DO NOTHING;

-- Daily ceiling covering "today" in a wide window; cost/breaker.py recomputes the
-- active window per call, this row just supplies the ceiling amount + scope.
INSERT INTO budget_ceilings (id, user_id, scope, ceiling_amount, currency, period_start, period_end)
VALUES (
    '00000000-0000-0000-0000-0000000000c1',
    '00000000-0000-0000-0000-000000000001',
    'daily', 5.00, 'USD',
    date_trunc('day', now()), date_trunc('day', now()) + interval '100 years'
)
ON CONFLICT (id) DO NOTHING;
