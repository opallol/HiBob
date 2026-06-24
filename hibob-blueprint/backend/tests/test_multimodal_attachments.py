"""Attachment validation/decoding (Phase 3.7). Pure."""

import base64

import pytest

from hibob_core.multimodal import attachments as mm
from hibob_core.multimodal.attachments import Attachment

_PNG = base64.b64encode(b"fake-png-bytes").decode()
_WAV = base64.b64encode(b"fake-wav-bytes").decode()


def test_split_validates_and_partitions():
    images, audios = mm.split([
        Attachment(type="image", media_type="image/png", data=_PNG),
        Attachment(type="audio", media_type="audio/wav", data=_WAV),
    ])
    assert len(images) == 1 and len(audios) == 1


def test_rejects_unknown_type_and_media():
    with pytest.raises(mm.AttachmentError):
        mm.validate(Attachment(type="video", media_type="video/mp4", data=_PNG))
    with pytest.raises(mm.AttachmentError):
        mm.validate(Attachment(type="image", media_type="image/gif", data=_PNG))


def test_requires_data_or_uri():
    with pytest.raises(mm.AttachmentError):
        mm.validate(Attachment(type="image", media_type="image/png"))


def test_rejects_oversize(monkeypatch):
    from hibob_core.config import settings
    monkeypatch.setattr(settings, "multimodal_max_mb", 0)  # everything is "too big"
    with pytest.raises(mm.AttachmentError):
        mm.validate(Attachment(type="image", media_type="image/png", data=_PNG))


def test_decode_base64_roundtrip_and_error():
    assert mm.decode_base64(_PNG) == b"fake-png-bytes"
    with pytest.raises(mm.AttachmentError):
        mm.decode_base64("not!!base64")
