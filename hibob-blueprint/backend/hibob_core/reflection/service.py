"""Reflective sibling job (Phase 3.5, ADR 0010, doc 04 §11a).

A scheduled-capable, strictly READ-ONLY scan that turns Hibob from purely reactive into a digital
sibling that proactively flags things for Bob. It looks at the memory graph and RAG sources for:
  - conflict_scan        - unresolved memory_conflicts / `contradicts` edges,
  - untested_assumption  - fragile, low-confidence beliefs other decisions `depends_on`,
  - stale_source         - RAG sources not recrawled within the window (doc 06 §13).

Findings are written to `reflections` (Bob reads async). HARD CONTRACT (doc 13 §11, ADR 0010): this
job NEVER writes durable memory and NEVER calls a tool. It only writes `reflections` + audit rows.
Summaries are deterministic templates phrased like doc 15 §5 ("...keputusan final atau masih
hipotesis?"); local-model phrasing is a future option, not a v0.1 dependency.
"""

from __future__ import annotations

import uuid

import asyncpg

from hibob_core.config import settings
from hibob_core.db import repositories as core_repo
from hibob_core.reflection import repository as repo

VALID_STATUSES = {"unread", "read", "acted_on", "dismissed"}


class ReflectionError(Exception):
    pass


def _short(text: str | None, n: int = 60) -> str:
    text = (text or "memory").strip()
    return text if len(text) <= n else text[: n - 1] + "…"


async def _emit(
    conn: asyncpg.Connection,
    *,
    user_id: uuid.UUID,
    reflection_type: str,
    key_id: str,
    summary: str,
    related_memory_ids: list[str],
    related_edge_ids: list[str],
) -> str | None:
    """Create one finding unless an open duplicate already exists. Returns id or None (skipped)."""
    if await repo.reflection_exists(conn, reflection_type=reflection_type, key_id=key_id):
        return None
    rid = await repo.create_reflection(
        conn, user_id=user_id, reflection_type=reflection_type, summary=summary,
        related_memory_ids=related_memory_ids, related_edge_ids=related_edge_ids,
    )
    await core_repo.write_audit(
        conn, actor_type="system", actor_id=None,
        event_type="reflection.created", target_type="reflection", target_id=str(rid),
        metadata={"reflection_type": reflection_type},
    )
    return str(rid)


async def run(conn: asyncpg.Connection, *, user_id: uuid.UUID) -> dict:
    """Run all scans and persist new findings. Read-only re: memory/tools (ADR 0010)."""
    cap = settings.reflection_max_findings
    created: list[str] = []

    # 1) conflict_scan
    for c in await repo.open_conflicts(conn, cap):
        cid = str(c["id"])
        summary = (
            f"Bob, ada konflik yang belum diselesaikan antara '{_short(c.get('title_a'))}' dan "
            f"'{_short(c.get('title_b'))}'. Ini keputusan final atau masih perlu kamu pilih?"
        )
        rid = await _emit(
            conn, user_id=user_id, reflection_type="conflict_scan", key_id=cid, summary=summary,
            related_memory_ids=[str(c["memory_id_a"]), str(c["memory_id_b"])],
            related_edge_ids=[cid],
        )
        if rid:
            created.append(rid)

    # 2) untested_assumption
    for a in await repo.untested_assumptions(conn, max_conf=settings.reflection_low_confidence, limit=cap):
        edge_id = str(a["edge_id"])
        summary = (
            f"Bob, keputusan lain bergantung pada '{_short(a.get('title'))}', tapi confidence-nya "
            f"masih {float(a['confidence']):.2f}. Ini sudah teruji atau masih hipotesis?"
        )
        rid = await _emit(
            conn, user_id=user_id, reflection_type="untested_assumption", key_id=edge_id,
            summary=summary, related_memory_ids=[str(a["memory_id_to"])], related_edge_ids=[edge_id],
        )
        if rid:
            created.append(rid)

    # 3) stale_source
    for s in await repo.stale_sources(conn, older_than_days=settings.reflection_stale_days, limit=cap):
        doc_id = str(s["document_id"])
        crawled = s.get("last_crawled_at")
        when = crawled.date().isoformat() if crawled else "lama"
        summary = (
            f"Bob, sumber '{_short(s.get('title'))}' ({s.get('url')}) terakhir di-crawl {when} dan "
            f"mungkin sudah basi. Perlu di-recrawl sebelum dipakai jawab?"
        )
        rid = await _emit(
            conn, user_id=user_id, reflection_type="stale_source", key_id=doc_id, summary=summary,
            related_memory_ids=[doc_id], related_edge_ids=[],
        )
        if rid:
            created.append(rid)

    await core_repo.write_audit(
        conn, actor_type="system", actor_id=str(user_id),
        event_type="reflection.run", target_type="user", target_id=str(user_id),
        metadata={"created": len(created)},
    )
    return {"created": len(created), "reflection_ids": created}


async def set_status(
    conn: asyncpg.Connection, *, reflection_id: uuid.UUID, status: str
) -> dict:
    if status not in VALID_STATUSES:
        raise ReflectionError(f"invalid status '{status}' (allowed: {sorted(VALID_STATUSES)})")
    if await repo.get(conn, reflection_id) is None:
        raise ReflectionError("reflection not found")
    await repo.set_status(conn, reflection_id, status)
    return {"id": str(reflection_id), "status": status}
