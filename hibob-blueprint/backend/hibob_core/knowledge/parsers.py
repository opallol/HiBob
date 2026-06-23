"""Source parsers (Phase 3, doc 06 §5/§6). Output is normalized blocks for chunking.py.

Lean core: `text`/`markdown` are parsed natively (no heavy deps), so ingestion runs and tests
green out of the box. `pdf`/`docx` (Unstructured) and `web` (Crawl4AI) are optional adapters with
LAZY imports - if the `ingest` extra isn't installed they raise ParserUnavailable rather than
crashing import, mirroring how the cloud SDK stays optional elsewhere.

A normalized block: {text, heading_path, page_number, type} (doc 06 §5.2).
"""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import urlparse


class ParserError(Exception):
    pass


class ParserUnavailable(ParserError):
    """The optional dependency for this source_type is not installed."""


def normalize_type(source_type: str) -> str:
    t = source_type.lower().strip()
    return {"md": "markdown", "txt": "text", "note": "text", "github": "markdown"}.get(t, t)


def parse_text(content: str) -> list[dict]:
    content = (content or "").strip()
    if not content:
        return []
    return [{"text": content, "heading_path": [], "page_number": None, "type": "NarrativeText"}]


_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")


def parse_markdown(content: str) -> list[dict]:
    """Split by heading boundaries, carrying a heading_path stack (semantic-first, doc 06 §7)."""
    blocks: list[dict] = []
    stack: list[tuple[int, str]] = []  # (level, title)
    buf: list[str] = []

    def flush() -> None:
        text = "\n".join(buf).strip()
        if text:
            blocks.append({
                "text": text,
                "heading_path": [title for _, title in stack],
                "page_number": None,
                "type": "NarrativeText",
            })
        buf.clear()

    for line in (content or "").splitlines():
        m = _HEADING.match(line)
        if m:
            flush()
            level = len(m.group(1))
            title = m.group(2).strip()
            while stack and stack[-1][0] >= level:
                stack.pop()
            stack.append((level, title))
        else:
            buf.append(line)
    flush()
    return blocks or parse_text(content)


def _parse_unstructured(path: str, source_type: str) -> list[dict]:
    try:
        from unstructured.partition.auto import partition  # lazy (optional `ingest` extra)
    except ImportError as e:
        raise ParserUnavailable(
            f"parsing {source_type} needs the 'ingest' extra (unstructured): pip install '.[ingest]'"
        ) from e
    elements = partition(filename=path)
    blocks: list[dict] = []
    for el in elements:
        text = (getattr(el, "text", "") or "").strip()
        if not text:
            continue
        meta = getattr(el, "metadata", None)
        blocks.append({
            "text": text,
            "heading_path": [],
            "page_number": getattr(meta, "page_number", None) if meta else None,
            "type": getattr(el, "category", "NarrativeText"),
        })
    return blocks


def parse(source_type: str, *, content: str | None = None, path: str | None = None) -> list[dict]:
    """Parse a non-web source into blocks. `web` is handled by fetch_web (it's async + networked)."""
    t = normalize_type(source_type)
    if content is None and path is not None and t in ("text", "markdown"):
        with open(path, encoding="utf-8") as f:
            content = f.read()
    if t == "text":
        return parse_text(content or "")
    if t == "markdown":
        return parse_markdown(content or "")
    if t in ("pdf", "docx"):
        if not path:
            raise ParserError(f"{t} ingestion needs a file path (source_uri)")
        return _parse_unstructured(path, t)
    raise ParserError(f"unsupported source_type for parse(): {source_type}")


def _host_allowed(url: str, allowlist: list[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return any(host == d.lower() or host.endswith("." + d.lower()) for d in allowlist)


async def fetch_web(url: str, *, allowlist: list[str]) -> tuple[str, dict]:
    """Crawl one URL to clean markdown (doc 06 §6). Allowlist-only (doc 06 §6.2)."""
    if not allowlist or not _host_allowed(url, allowlist):
        raise ParserError(f"url host not in crawl allowlist: {url}")
    try:
        from crawl4ai import AsyncWebCrawler  # lazy (optional `ingest` extra)
    except ImportError as e:
        raise ParserUnavailable(
            "web ingestion needs the 'ingest' extra (crawl4ai): pip install '.[ingest]'"
        ) from e
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
    markdown = getattr(result, "markdown", "") or ""
    meta = {
        "canonical_url": getattr(result, "url", url),
        "content_hash": hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
        "crawled_at": datetime.now(timezone.utc).isoformat(),
    }
    return markdown, meta
