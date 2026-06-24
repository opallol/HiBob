"""Text-to-speech (Phase 9, ADR 0015). Always local (privacy + cost, like STT).

Closes the two-way voice loop: STT input (Phase 3.7) -> text -> answer -> TTS output. The real local
voice model is a lazy seam; absent, a draft audio artifact stub is returned so the chat flow works.
"""

from __future__ import annotations

import hashlib


class OutputUnavailable(Exception):
    """The local TTS provider isn't installed (lazy seam)."""


def _local_provider():
    raise OutputUnavailable("local TTS provider not installed (seam)")


def synthesize(text: str) -> dict:
    """Return a draft audio artifact for the given text. Local only."""
    ref = "aud-" + hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]
    try:
        _local_provider()
    except OutputUnavailable:
        return {"type": "audio", "media_type": "audio/wav", "ref": ref, "provider": "stub"}
    return {"type": "audio", "media_type": "audio/wav", "ref": ref, "provider": "local"}
