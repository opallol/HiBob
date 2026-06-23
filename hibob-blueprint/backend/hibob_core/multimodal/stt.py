"""Speech-to-text (Phase 3.7). Always local (privacy + cost), like embeddings.

faster-whisper is an optional `multimodal` extra, lazy-imported. Absent -> STTUnavailable, and the
orchestrator degrades gracefully (answers without the transcript) rather than failing the chat.
"""

from __future__ import annotations

import tempfile

from hibob_core.config import settings

_model = None  # cached WhisperModel


class STTUnavailable(Exception):
    """faster-whisper isn't installed (pip install '.[multimodal]')."""


def _get_model():
    global _model
    if _model is None:
        try:
            from faster_whisper import WhisperModel  # lazy (optional extra)
        except ImportError as e:
            raise STTUnavailable(
                "audio understanding needs the 'multimodal' extra (faster-whisper): "
                "pip install '.[multimodal]'"
            ) from e
        _model = WhisperModel(settings.stt_model)
    return _model


def transcribe(audio_bytes: bytes, *, media_type: str | None = None) -> str:
    """Transcribe an audio blob to text. Synchronous; call via asyncio.to_thread from async code."""
    model = _get_model()
    with tempfile.NamedTemporaryFile(suffix=".audio") as tmp:
        tmp.write(audio_bytes)
        tmp.flush()
        segments, _info = model.transcribe(tmp.name)
        return " ".join(seg.text for seg in segments).strip()
