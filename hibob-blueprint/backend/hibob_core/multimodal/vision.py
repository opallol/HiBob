"""Build provider-agnostic multimodal message blocks (Phase 3.7). Pure.

A multimodal user message is a list of blocks the model adapters translate to their own shape
(see models/ollama_adapter.to_ollama_messages, models/anthropic_adapter.to_anthropic_messages):
  {"type": "text", "text": ...}
  {"type": "image", "media_type": "image/png", "data": "<base64>"}
"""

from __future__ import annotations

from hibob_core.multimodal import attachments as att_mod
from hibob_core.multimodal.attachments import Attachment


def build_user_blocks(text: str, image_attachments: list[Attachment]) -> list[dict]:
    blocks: list[dict] = []
    if text:
        blocks.append({"type": "text", "text": text})
    for att in image_attachments:
        blocks.append({
            "type": "image",
            "media_type": att.media_type,
            "data": att_mod.get_base64(att),
        })
    return blocks
