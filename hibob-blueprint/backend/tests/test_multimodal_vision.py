"""Vision block building + per-provider translation (Phase 3.7). Pure - no HTTP/model."""

import base64

from hibob_core.models.anthropic_adapter import to_anthropic_messages
from hibob_core.models.ollama_adapter import to_ollama_messages
from hibob_core.multimodal import vision
from hibob_core.multimodal.attachments import Attachment

_PNG = base64.b64encode(b"img").decode()


def test_build_user_blocks_has_text_then_image():
    blocks = vision.build_user_blocks(
        "apa ini?", [Attachment(type="image", media_type="image/png", data=_PNG)]
    )
    assert blocks[0] == {"type": "text", "text": "apa ini?"}
    assert blocks[1]["type"] == "image" and blocks[1]["data"] == _PNG


def test_to_ollama_messages_moves_images_to_sibling_list():
    blocks = vision.build_user_blocks("x", [Attachment(type="image", media_type="image/png", data=_PNG)])
    out = to_ollama_messages([{"role": "user", "content": blocks}])
    assert out[0]["content"] == "x"
    assert out[0]["images"] == [_PNG]


def test_to_ollama_messages_passes_plain_text_through():
    out = to_ollama_messages([{"role": "user", "content": "hai"}])
    assert out == [{"role": "user", "content": "hai"}]
    assert "images" not in out[0]


def test_to_anthropic_messages_builds_image_source_block():
    blocks = vision.build_user_blocks("x", [Attachment(type="image", media_type="image/png", data=_PNG)])
    out = to_anthropic_messages([{"role": "user", "content": blocks}])
    content = out[0]["content"]
    assert content[0] == {"type": "text", "text": "x"}
    assert content[1] == {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/png", "data": _PNG},
    }
