"""Ingestion pipeline (doc 06 §3/§11): pending->active, quality gate, job + embedding recorded."""

import uuid

import pytest

from hibob_core.db import repositories as core_repo
from hibob_core.knowledge import ingestion
from hibob_core.knowledge import repository as repo
from hibob_core.knowledge import vector_store

DOC = uuid.uuid4()
USER = core_repo.BOB_USER_ID


class _EmbedAdapter:
    async def embed_text(self, texts, model=None):
        return [[0.1, 0.2, 0.3] for _ in texts]


class _Router:
    def embed_adapter(self):
        return _EmbedAdapter()


def _doc(inline_text):
    return {
        "id": DOC, "user_id": USER, "title": "t", "source_type": "markdown",
        "source_uri": None, "privacy_tier": "internal",
        "metadata_json": {"inline_text": inline_text},
    }


def _patch_common(monkeypatch, captured):
    async def create_job(conn, **k):
        return uuid.uuid4()

    async def set_status(conn, document_id, status):
        captured["status"] = status

    async def add_chunk(conn, **k):
        captured["chunks"] += 1
        return uuid.uuid4()

    async def add_embedding(conn, **k):
        captured["embeddings"] += 1

    async def upsert(chunk_id, vector, payload):
        captured["upserts"] += 1

    async def finish_job(conn, *, job_id, status, error_message=None, metadata=None):
        captured["job_status"] = status
        captured["job_error"] = error_message

    async def audit(conn, **k):
        captured["audits"] += 1

    monkeypatch.setattr(repo, "create_job", create_job)
    monkeypatch.setattr(repo, "set_document_status", set_status)
    monkeypatch.setattr(repo, "add_chunk", add_chunk)
    monkeypatch.setattr(repo, "add_embedding", add_embedding)
    monkeypatch.setattr(vector_store, "upsert", upsert)
    monkeypatch.setattr(repo, "finish_job", finish_job)
    monkeypatch.setattr(core_repo, "write_audit", audit)


async def test_ingest_happy_path_activates_and_indexes(monkeypatch):
    captured = {"chunks": 0, "embeddings": 0, "upserts": 0, "audits": 0,
                "status": None, "job_status": None, "job_error": None}

    async def get_document(conn, document_id):
        return _doc("# Title\nisi dokumen yang cukup panjang untuk jadi satu chunk utuh")

    monkeypatch.setattr(repo, "get_document", get_document)
    _patch_common(monkeypatch, captured)

    out = await ingestion.run(None, _Router(), document_id=DOC)
    assert out["status"] == "active"
    assert out["chunks"] >= 1
    assert captured["status"] == "active"
    assert captured["embeddings"] == captured["chunks"] == captured["upserts"]
    assert captured["job_status"] == "done"
    assert captured["audits"] == 1


async def test_quality_gate_marks_failed_on_empty_text(monkeypatch):
    captured = {"chunks": 0, "embeddings": 0, "upserts": 0, "audits": 0,
                "status": None, "job_status": None, "job_error": None}

    async def get_document(conn, document_id):
        return _doc("   ")  # nothing extractable

    monkeypatch.setattr(repo, "get_document", get_document)
    _patch_common(monkeypatch, captured)

    with pytest.raises(ingestion.IngestionError):
        await ingestion.run(None, _Router(), document_id=DOC)
    assert captured["status"] == "failed"
    assert captured["job_status"] == "failed"
    assert captured["chunks"] == 0
