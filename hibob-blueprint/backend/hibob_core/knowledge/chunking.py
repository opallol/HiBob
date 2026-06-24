"""Chunking (Phase 3, doc 06 §7). Pure functions - no I/O, easy to test.

Strategy: split by semantic boundary FIRST (parsers already split markdown by heading), then
window long blocks into ~`target_tokens` chunks with overlap. Each chunk inherits its block's
`heading_path`/`page_number`, so unrelated sections never get mixed (doc 06 §7, §15).

Token counting is approximated from whitespace words (no tokenizer dependency): close enough to
keep chunks inside the 500-900 range without pulling a heavy model in.
"""

from __future__ import annotations

import hashlib

_TOKENS_PER_WORD = 1.3  # rough English/Indonesian approximation


def estimate_tokens(text: str) -> int:
    return max(1, round(len(text.split()) * _TOKENS_PER_WORD))


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _window_words(words: list[str], size: int, overlap: int) -> list[list[str]]:
    if size <= 0:
        return [words]
    step = max(1, size - overlap)
    out: list[list[str]] = []
    i = 0
    while i < len(words):
        out.append(words[i : i + size])
        if i + size >= len(words):
            break
        i += step
    return out


def chunk_blocks(
    blocks: list[dict],
    *,
    target_tokens: int,
    overlap_tokens: int,
    min_chars: int,
) -> list[dict]:
    """Turn normalized parser blocks into ordered chunk dicts.

    Each input block: {text, heading_path, page_number, type}.
    Each output chunk: {chunk_index, content, token_count, heading_path, page_number, content_hash}.
    """
    words_per_chunk = max(1, round(target_tokens / _TOKENS_PER_WORD))
    overlap_words = max(0, round(overlap_tokens / _TOKENS_PER_WORD))

    chunks: list[dict] = []
    idx = 0
    for block in blocks:
        text = (block.get("text") or "").strip()
        if not text:
            continue
        words = text.split()
        for window in _window_words(words, words_per_chunk, overlap_words):
            content = " ".join(window).strip()
            if len(content) < min_chars:
                continue
            chunks.append(
                {
                    "chunk_index": idx,
                    "content": content,
                    "token_count": estimate_tokens(content),
                    "heading_path": block.get("heading_path") or [],
                    "page_number": block.get("page_number"),
                    "content_hash": content_hash(content),
                }
            )
            idx += 1
    return chunks
