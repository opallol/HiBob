"""Document retrieval: privacy containment + source-referenced results (doc 06 §4/§9). Deps faked."""

import uuid

from hibob_core.knowledge import retrieval
from hibob_core.knowledge import vector_store


class _EmbedAdapter:
    async def embed_text(self, texts, model=None):
        return [[0.1, 0.2, 0.3] for _ in texts]


class _Router:
    def embed_adapter(self):
        return _EmbedAdapter()


def _chunk_row(doc_id, tier, content="c", title="t", uri="docs/x.md", heading=("Sec",)):
    return {
        "document_id": uuid.UUID(doc_id), "content": content, "title": title,
        "source_uri": uri, "privacy_tier": tier, "doc_status": "active",
        "metadata_json": {"heading_path": list(heading)},
    }


async def test_privacy_containment_excludes_more_sensitive(monkeypatch):
    secret = str(uuid.uuid4())
    internal = str(uuid.uuid4())
    doc = str(uuid.uuid4())

    async def fake_search(vector, *, allowed_tiers, limit):
        # the store would filter, but assert retrieval also defends itself
        return [(secret, 0.95, {}), (internal, 0.90, {})]

    async def fake_fetch(conn, ids):
        return {secret: _chunk_row(doc, "secret"), internal: _chunk_row(doc, "internal")}

    monkeypatch.setattr(vector_store, "search", fake_search)
    monkeypatch.setattr(retrieval.repo, "fetch_chunks_by_ids", fake_fetch)

    out = await retrieval.retrieve(None, _Router(), query="x", privacy_tier="internal")
    ids = [c["chunk_id"] for c in out]
    assert internal in ids and secret not in ids
    assert out[0]["source"].endswith("#Sec")  # source reference carries heading path


async def test_empty_hits_returns_empty(monkeypatch):
    async def fake_search(vector, *, allowed_tiers, limit):
        return []
    monkeypatch.setattr(vector_store, "search", fake_search)
    out = await retrieval.retrieve(None, _Router(), query="x", privacy_tier="internal")
    assert out == []


def test_allowed_tiers_monotonic():
    assert set(retrieval._allowed_tiers("public")) == {"public"}
    assert set(retrieval._allowed_tiers("internal")) == {"public", "internal"}
    assert set(retrieval._allowed_tiers("secret")) == {"public", "internal", "private", "secret"}


def test_render_for_prompt_labels_sources():
    rendered = retrieval.render_for_prompt(
        [{"chunk_id": "1", "document_id": "d", "score": 0.8, "text": "fakta", "source": "docs/a.md#H"}]
    )
    assert "docs/a.md#H" in rendered and "fakta" in rendered
