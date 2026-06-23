"""End-of-session summary (doc 04 §11 / doc 15 §3). Local-first.

Produces a session_summaries row and (optionally) runs candidate extraction so the
end-of-session ritual yields both a summary and memory candidates for Bob to review.
"""

from __future__ import annotations

import uuid

import asyncpg

from hibob_core.db import repositories as core_repo
from hibob_core.memory import extraction
from hibob_core.models.router import ModelRouter

_SUMMARY_SYSTEM = """Ringkas percakapan ini untuk arsip Hibob. Balas ringkas dalam Bahasa
Indonesia: 2-4 kalimat inti percakapan, lalu (kalau ada) daftar keputusan singkat. Jangan
mengarang hal yang tidak ada di transkrip."""


async def summarize_session(
    conn: asyncpg.Connection,
    router: ModelRouter,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
    extract: bool = True,
) -> dict:
    history = await core_repo.get_history(conn, conversation_id)
    if not history:
        return {"summary_id": None, "candidate_ids": []}

    transcript = "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)
    result = await router.embed_adapter().generate_text(
        system=_SUMMARY_SYSTEM, messages=[{"role": "user", "content": transcript}]
    )

    summary_id = await core_repo.create_session_summary(
        conn, conversation_id=conversation_id, summary=result.text.strip()
    )

    candidate_ids: list[uuid.UUID] = []
    if extract:
        candidate_ids = await extraction.extract_candidates(
            conn, router, user_id=user_id, conversation_id=conversation_id
        )

    return {
        "summary_id": str(summary_id),
        "candidate_ids": [str(c) for c in candidate_ids],
    }
