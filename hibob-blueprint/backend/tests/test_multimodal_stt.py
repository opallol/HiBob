"""STT degrades when the optional dep is missing (Phase 3.7)."""

import builtins

import pytest

from hibob_core.multimodal import stt


def test_transcribe_raises_when_faster_whisper_absent(monkeypatch):
    # Force the lazy import to fail regardless of the local environment.
    monkeypatch.setattr(stt, "_model", None)
    real_import = builtins.__import__

    def fake_import(name, *a, **k):
        if name.startswith("faster_whisper"):
            raise ImportError("no faster_whisper")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(stt.STTUnavailable):
        stt.transcribe(b"audio-bytes", media_type="audio/wav")
