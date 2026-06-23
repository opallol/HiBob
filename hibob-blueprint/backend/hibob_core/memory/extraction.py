"""Candidate memory extraction from a conversation (doc 04 §4-5).

LLM proposes candidates; everything created here is status='candidate' and needs Bob's
approval (doc 04 §6). Extraction is local-first (uses the local model via the router) so a
private conversation never leaves the box just to mine memories.
"""

from __future__ import annotations

import json
import re
import uuid

import asyncpg

from hibob_core.db import repositories as core_repo
from hibob_core.memory import repository as repo
from hibob_core.models.router import ModelRouter

_VALID_TYPES = {
    "profile", "preference", "project", "decision", "principle",
    "correction", "warning", "relationship", "task", "system_identity",
}
_VALID_SCOPES = {"bob", "hibob", "project", "global"}
_VALID_SENSITIVITY = {"public", "internal", "private", "secret"}
_VALID_STABILITY = {"temporary", "session", "medium", "durable"}

_EXTRACTION_SYSTEM = """Kamu adalah ekstraktor memory untuk Hibob. Dari transkrip percakapan,
usulkan kandidat memory yang LAYAK diingat jangka panjang.

BOLEH jadi memory: keputusan desain, preferensi eksplisit, koreksi terhadap Hibob,
prinsip jangka panjang, data personal stabil, batas/larangan, info proyek penting, perubahan arah.

JANGAN jadikan memory: emosi sesaat, candaan ambigu, asumsi belum dikonfirmasi,
instruksi sekali pakai, fakta tidak relevan jangka panjang.

Balas HANYA JSON array. Tiap item:
{"memory_type": one of [profile,preference,project,decision,principle,correction,warning,relationship,task,system_identity],
 "scope": one of [bob,hibob,project,global],
 "title": "ringkas <80 char",
 "content": "1-2 kalimat",
 "sensitivity": one of [public,internal,private,secret],
 "stability": one of [temporary,session,medium,durable],
 "confidence": 0.0-1.0}
Kalau tidak ada yang layak, balas []."""


def _parse_json_array(text: str) -> list[dict]:
    text = text.strip()
    # strip ```json ... ``` fences if present
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start = text.find("[")
    end = text.rfind("]")
    if start == -1 or end == -1:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _sanitize(item: dict) -> dict | None:
    try:
        mt = str(item["memory_type"]).strip()
        scope = str(item["scope"]).strip()
        title = str(item["title"]).strip()
        content = str(item["content"]).strip()
    except (KeyError, TypeError):
        return None
    if mt not in _VALID_TYPES or scope not in _VALID_SCOPES or not title or not content:
        return None
    sens = str(item.get("sensitivity", "internal"))
    sens = sens if sens in _VALID_SENSITIVITY else "internal"
    stab = str(item.get("stability", "medium"))
    stab = stab if stab in _VALID_STABILITY else "medium"
    try:
        conf = float(item.get("confidence", 0.5))
    except (TypeError, ValueError):
        conf = 0.5
    conf = min(max(conf, 0.0), 1.0)
    return {
        "memory_type": mt, "scope": scope, "title": title[:200],
        "content": content, "sensitivity": sens, "stability": stab, "confidence": conf,
    }


def _render_transcript(history: list[dict]) -> str:
    return "\n".join(f"{m['role'].upper()}: {m['content']}" for m in history)


async def extract_candidates(
    conn: asyncpg.Connection,
    router: ModelRouter,
    *,
    user_id: uuid.UUID,
    conversation_id: uuid.UUID,
) -> list[uuid.UUID]:
    """Run extraction over a conversation; persist candidate rows. Returns new memory ids."""
    history = await core_repo.get_history(conn, conversation_id)
    if not history:
        return []
    transcript = _render_transcript(history)

    adapter = router.embed_adapter()  # local model owner; reuse for extraction (local-first)
    result = await adapter.generate_text(
        system=_EXTRACTION_SYSTEM,
        messages=[{"role": "user", "content": transcript}],
    )

    created: list[uuid.UUID] = []
    for raw in _parse_json_array(result.text):
        item = _sanitize(raw)
        if item is None:
            continue
        mem_id = await repo.create_candidate(conn, user_id=user_id, **item)
        await repo.add_source(
            conn, memory_id=mem_id, source_type="conversation",
            source_id=conversation_id, quote=None,
        )
        created.append(mem_id)
    return created
