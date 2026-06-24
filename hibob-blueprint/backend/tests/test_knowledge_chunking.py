"""Chunking (doc 06 §7): heading-aware splitting, sizing/overlap, stable hashes. Pure functions."""

from hibob_core.knowledge import chunking, parsers


def test_markdown_splits_by_heading_with_path():
    md = "# Arch\nintro text\n## Memory Core\nmemory details here\n## RAG\nrag details here"
    blocks = parsers.parse_markdown(md)
    paths = [b["heading_path"] for b in blocks]
    assert ["Arch"] in paths
    assert ["Arch", "Memory Core"] in paths
    assert ["Arch", "RAG"] in paths
    # sections are not mixed: the memory block text doesn't contain rag text
    mem = next(b for b in blocks if b["heading_path"] == ["Arch", "Memory Core"])
    assert "rag details" not in mem["text"]


def test_chunk_blocks_windows_long_block_with_overlap():
    words = " ".join(f"w{i}" for i in range(300))
    blocks = [{"text": words, "heading_path": ["H"], "page_number": None, "type": "NarrativeText"}]
    chunks = chunking.chunk_blocks(blocks, target_tokens=130, overlap_tokens=26, min_chars=5)
    assert len(chunks) > 1                          # long block produced multiple chunks
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))
    assert all(c["heading_path"] == ["H"] for c in chunks)
    # consecutive chunks overlap (last words of chunk 0 reappear at the start of chunk 1)
    first_tail = chunks[0]["content"].split()[-1]
    assert first_tail in chunks[1]["content"].split()


def test_chunk_blocks_skips_tiny_and_empty():
    blocks = [
        {"text": "ok this is long enough to keep", "heading_path": [], "page_number": None, "type": "x"},
        {"text": "  ", "heading_path": [], "page_number": None, "type": "x"},
    ]
    chunks = chunking.chunk_blocks(blocks, target_tokens=700, overlap_tokens=120, min_chars=20)
    assert len(chunks) == 1


def test_content_hash_is_stable_and_token_estimate_positive():
    assert chunking.content_hash("hello") == chunking.content_hash("hello")
    assert chunking.content_hash("a") != chunking.content_hash("b")
    assert chunking.estimate_tokens("one two three") >= 3
