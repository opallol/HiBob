"""TTS synthesis (ADR 0015). Returns a draft audio artifact (stub seam)."""

from hibob_core.multimodal import tts


def test_synthesize_returns_audio_artifact():
    art = tts.synthesize("halo Bob")
    assert art["type"] == "audio"
    assert art["media_type"] == "audio/wav"
    assert art["ref"].startswith("aud-")


def test_synthesize_is_deterministic():
    assert tts.synthesize("x")["ref"] == tts.synthesize("x")["ref"]
    assert tts.synthesize("x")["ref"] != tts.synthesize("y")["ref"]
