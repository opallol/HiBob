"""Unified multi-source recall (Phase 8). Retrieval deps faked."""

from hibob_core import recall as recall_mod
from hibob_core.knowledge import retrieval as doc_retrieval
from hibob_core.memory import retrieval as mem_retrieval


def _mem(mid, title, content, score, scope="project"):
    return {"id": mid, "title": title, "content": content, "scope": scope,
            "memory_type": "decision", "final_score": score}


def _doc(cid, text, score):
    return {"chunk_id": cid, "document_id": "d1", "score": score, "text": text, "source": "docs/a.md#H"}


async def test_merges_and_normalizes_sources(monkeypatch):
    async def mem_retrieve(conn, router, *, query, privacy_tier, scope=None, memory_type=None):
        return [_mem("m1", "Pindah ke Python", "isi memory", 2.0)]  # memory scores can exceed 1

    async def doc_retrieve(conn, router, *, query, privacy_tier):
        return [_doc("c1", "isi dokumen", 0.8)]

    monkeypatch.setattr(mem_retrieval, "retrieve", mem_retrieve)
    monkeypatch.setattr(doc_retrieval, "retrieve", doc_retrieve)

    out = await recall_mod.recall(None, object(), query="python", privacy_tier="internal")
    assert {r["source_type"] for r in out} == {"memory", "document"}
    # each source normalized to its own max (1.0), so both top items score 1.0
    assert all(r["score"] <= 1.0 for r in out)
    mem = next(r for r in out if r["source_type"] == "memory")
    assert mem["score"] == 1.0 and "Pindah ke Python" in mem["label"]


async def test_project_scope_passed_to_memory(monkeypatch):
    seen = {}

    async def mem_retrieve(conn, router, *, query, privacy_tier, scope=None, memory_type=None):
        seen["scope"] = scope
        return []

    async def doc_retrieve(conn, router, *, query, privacy_tier):
        return []

    monkeypatch.setattr(mem_retrieval, "retrieve", mem_retrieve)
    monkeypatch.setattr(doc_retrieval, "retrieve", doc_retrieve)

    out = await recall_mod.recall(None, object(), query="x", privacy_tier="internal", project="alpha")
    assert out == []
    assert seen["scope"] == "alpha"


async def test_limit_caps_results(monkeypatch):
    async def mem_retrieve(conn, router, *, query, privacy_tier, scope=None, memory_type=None):
        return [_mem(f"m{i}", f"t{i}", "c", 1.0 - i * 0.1) for i in range(5)]

    async def doc_retrieve(conn, router, *, query, privacy_tier):
        return [_doc(f"c{i}", "c", 0.9 - i * 0.1) for i in range(5)]

    monkeypatch.setattr(mem_retrieval, "retrieve", mem_retrieve)
    monkeypatch.setattr(doc_retrieval, "retrieve", doc_retrieve)
    out = await recall_mod.recall(None, object(), query="x", privacy_tier="internal", limit=3)
    assert len(out) == 3
