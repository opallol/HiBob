-- Hibob Phase 2.5 (Memory Graph & Calibration) activation.
-- Tables memory_edges + memory_usage_feedback already exist from 0003_phase2.sql
-- ("created, not activated"); Phase 2.5 turns them on in code. The only schema
-- change is an idempotency guard so auto-edges (from supersede/conflict) and the
-- POST /v1/memory/edges endpoint never create duplicate relations.
-- Mirrors ../../../database/schema.sql - DO NOT diverge.
--
-- Apply manually (volume persists, initdb will NOT auto-run):
--   docker exec -i hibob-core-postgres psql -U hibob -d hibob < 0004_phase2_5.sql

CREATE UNIQUE INDEX IF NOT EXISTS idx_memory_edges_unique
    ON memory_edges(memory_id_from, memory_id_to, relation_type);
