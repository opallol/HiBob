"""Extraction parsing/sanitizing is pure - no DB/model needed."""

from hibob_core.memory import extraction


def test_parse_plain_json_array():
    out = extraction._parse_json_array('[{"a":1},{"b":2}]')
    assert len(out) == 2


def test_parse_fenced_json():
    text = "Berikut hasilnya:\n```json\n[{\"memory_type\":\"decision\"}]\n```\n"
    out = extraction._parse_json_array(text)
    assert out == [{"memory_type": "decision"}]


def test_parse_garbage_returns_empty():
    assert extraction._parse_json_array("tidak ada json di sini") == []


def test_sanitize_valid_item():
    item = extraction._sanitize({
        "memory_type": "decision", "scope": "project",
        "title": "Pilih Python", "content": "Bob memutuskan pakai Python.",
        "sensitivity": "internal", "stability": "durable", "confidence": 0.8,
    })
    assert item is not None
    assert item["memory_type"] == "decision"
    assert item["confidence"] == 0.8


def test_sanitize_rejects_bad_type():
    assert extraction._sanitize({"memory_type": "nonsense", "scope": "bob",
                                 "title": "x", "content": "y"}) is None


def test_sanitize_defaults_and_clamps():
    item = extraction._sanitize({
        "memory_type": "preference", "scope": "bob", "title": "t", "content": "c",
        "sensitivity": "weird", "stability": "weird", "confidence": 5,
    })
    assert item["sensitivity"] == "internal"   # invalid -> default
    assert item["stability"] == "medium"       # invalid -> default
    assert item["confidence"] == 1.0           # clamped to [0,1]
