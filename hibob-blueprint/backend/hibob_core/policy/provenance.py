"""Injection-defense layer (Phase 4, ADR 0005 #3).

Content from documents/web/tool output/user is tagged with a provenance and scanned for
imperative/instruction-like patterns before any resulting tool call runs. v0.1 is deterministic
(regex) - it flags for audit and forces `ask` (it does not silently block the response). The
structural "this is data, not instructions" framing already lives in the memory/doc prompt renders.
"""

from __future__ import annotations

import re
import uuid

import asyncpg

# Imperative / known-injection patterns (English + Indonesian). Deterministic on purpose:
# a classifier alone is not a security boundary (ADR 0005, alternatives considered).
_PATTERNS = [
    r"ignore (all )?(previous|prior) (instructions|context)",
    r"abaikan (semua )?(instruksi|perintah) (sebelumnya|di atas)",
    r"disregard (the )?(above|system)",
    r"\byou are now\b|\bsekarang kamu\b",
    r"\b(run|execute|jalankan)\b.*\b(command|shell|script|perintah)\b",
    r"\b(delete|drop|rm -rf|hapus)\b",
    r"\b(send|kirim|transfer|exfiltrate|leak|bocorkan)\b.*\b(secret|password|token|kredensial|api key)\b",
    r"reveal (your |the )?(system )?prompt",
]
_COMPILED = [re.compile(p, re.IGNORECASE) for p in _PATTERNS]


def classify(text: str) -> tuple[bool, float]:
    """Return (injection_suspected, score in [0,1]) from imperative-pattern hits."""
    if not text:
        return False, 0.0
    hits = sum(1 for rx in _COMPILED if rx.search(text))
    if hits == 0:
        return False, 0.0
    score = min(1.0, 0.5 + 0.25 * hits)
    return True, round(score, 4)


async def tag(
    conn: asyncpg.Connection,
    *,
    source_type: str,
    source_id: uuid.UUID,
    provenance: str,
    suspected: bool,
    score: float,
    trace_id: str | None = None,
) -> None:
    await conn.execute(
        """
        INSERT INTO content_provenance_flags
            (source_type, source_id, provenance, injection_suspected, classifier_score, trace_id)
        VALUES ($1,$2,$3,$4,$5,$6)
        """,
        source_type, source_id, provenance, suspected, score, trace_id,
    )
