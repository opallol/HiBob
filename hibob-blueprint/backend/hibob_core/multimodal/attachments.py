"""Attachment model + validation/decoding (Phase 3.7, doc 12 §2). Pure - easy to test.

An attachment carries one image or audio blob, either inline base64 (`data`) or a local path
(`uri`). Validation enforces allowed media types and a size ceiling before anything reaches a model.
Raw media is never persisted; it is decoded in-flight only (privacy + size, see orchestrator).
"""

from __future__ import annotations

import base64
import binascii

from pydantic import BaseModel

from hibob_core.config import settings


class AttachmentError(Exception):
    pass


class Attachment(BaseModel):
    type: str                 # "image" | "audio"
    media_type: str           # e.g. "image/png", "audio/wav"
    data: str | None = None   # base64 payload
    uri: str | None = None    # OR a local file path


def _allowed_media(att: Attachment) -> bool:
    if att.type == "image":
        return att.media_type in settings.multimodal_allowed_image_types
    if att.type == "audio":
        return att.media_type in settings.multimodal_allowed_audio_types
    return False


def decode_base64(data: str) -> bytes:
    try:
        return base64.b64decode(data, validate=True)
    except (binascii.Error, ValueError) as e:
        raise AttachmentError("invalid base64 attachment data") from e


def get_bytes(att: Attachment) -> bytes:
    """Resolve an attachment to raw bytes (in-flight only)."""
    if att.data is not None:
        return decode_base64(att.data)
    if att.uri:
        with open(att.uri, "rb") as f:
            return f.read()
    raise AttachmentError("attachment needs either 'data' (base64) or 'uri'")


def get_base64(att: Attachment) -> str:
    """Base64 payload for a model call (images). Reads+encodes from uri if needed."""
    if att.data is not None:
        return att.data
    return base64.b64encode(get_bytes(att)).decode("ascii")


def validate(att: Attachment) -> None:
    if att.type not in ("image", "audio"):
        raise AttachmentError(f"unsupported attachment type: {att.type}")
    if not _allowed_media(att):
        raise AttachmentError(f"media_type not allowed for {att.type}: {att.media_type}")
    if att.data is None and not att.uri:
        raise AttachmentError("attachment needs either 'data' (base64) or 'uri'")
    if att.data is not None:
        raw = decode_base64(att.data)
        if len(raw) > settings.multimodal_max_mb * 1024 * 1024:
            raise AttachmentError(f"attachment exceeds {settings.multimodal_max_mb} MB limit")


def split(attachments: list[Attachment]) -> tuple[list[Attachment], list[Attachment]]:
    """Validate all, return (images, audios)."""
    images: list[Attachment] = []
    audios: list[Attachment] = []
    for att in attachments:
        validate(att)
        (images if att.type == "image" else audios).append(att)
    return images, audios
