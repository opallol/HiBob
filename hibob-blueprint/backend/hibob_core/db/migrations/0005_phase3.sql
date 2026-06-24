-- Hibob Phase 3 (Knowledge Base / RAG) schema subset.
-- Tables copied from ../../../database/schema.sql - DO NOT diverge.
-- Active in Phase 3: web_sources, documents, document_chunks, document_embeddings, ingestion_jobs.
-- Scope v0.1 = text extraction only (doc 06). Vision/audio sources land in Phase 3.7.
--
-- NOTE: the volume persists from earlier phases, so docker-entrypoint-initdb.d will NOT auto-run this.
-- Apply manually: docker exec -i hibob-core-postgres psql -U hibob -d hibob < 0005_phase3.sql

CREATE TABLE IF NOT EXISTS web_sources (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    url TEXT NOT NULL,
    canonical_url TEXT,
    crawl_status TEXT DEFAULT 'pending',
    content_hash TEXT,
    last_crawled_at TIMESTAMPTZ,
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

CREATE INDEX IF NOT EXISTS idx_documents_user_status ON documents(user_id, status);
CREATE INDEX IF NOT EXISTS idx_documents_privacy ON documents(privacy_tier);

CREATE TABLE IF NOT EXISTS document_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_document_chunks_document ON document_chunks(document_id);

CREATE TABLE IF NOT EXISTS document_embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID REFERENCES document_chunks(id),
    vector_collection TEXT NOT NULL,
    vector_id TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding_dim INTEGER NOT NULL,
    embedding_version TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_document_embeddings_chunk ON document_embeddings(chunk_id);

CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID REFERENCES documents(id),
    job_type TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    metadata_json JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_document ON ingestion_jobs(document_id);
