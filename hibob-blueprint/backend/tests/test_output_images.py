"""Image generation safety (ADR 0015). Pure (provider is a stub seam)."""

import pytest

from hibob_core.multimodal import image_gen as images


def test_default_local_returns_draft():
    art = images.generate("a cat", privacy_tier="internal")
    assert art["type"] == "image"
    assert art["published"] is False  # never auto-published


def test_private_cannot_use_cloud():
    with pytest.raises(images.OutputError):
        images.generate("x", privacy_tier="private", model_preference="cloud")
    with pytest.raises(images.OutputError):
        images.generate("x", privacy_tier="secret", model_preference="cloud")


def test_cloud_disabled_by_default():
    with pytest.raises(images.OutputError):
        images.generate("x", privacy_tier="public", model_preference="cloud")
