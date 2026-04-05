from __future__ import annotations

from html.parser import HTMLParser
from io import StringIO
from pathlib import Path
import re

from pypdf import PdfReader

from .config import CHUNK_OVERLAP, MAX_CHUNK_CHARS

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".epub", ".md"}

WHITESPACE_RE = re.compile(r"\s+")
_SUPPORTED_LIST = ", ".join(sorted(SUPPORTED_EXTENSIONS))


class _HTMLTextExtractor(HTMLParser):
    """Minimal HTML→plain-text converter for EPUB chapter content."""

    def __init__(self) -> None:
        super().__init__()
        self._buf = StringIO()

    def handle_data(self, data: str) -> None:
        self._buf.write(data)

    def get_text(self) -> str:
        return self._buf.getvalue()


def _html_to_text(html: str) -> str:
    extractor = _HTMLTextExtractor()
    extractor.feed(html)
    return extractor.get_text()


def html_to_plain_text(html: str) -> str:
    """Strip HTML tags to plain text (for web page imports)."""
    return normalize_text(_html_to_text(html))


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    return WHITESPACE_RE.sub(" ", text).strip()


def _extract_epub(path: Path) -> str:
    import ebooklib  # type: ignore[import-untyped]
    from ebooklib import epub  # type: ignore[import-untyped]

    book = epub.read_epub(str(path), options={"ignore_ncx": True})
    parts: list[str] = []
    for item in book.get_items_of_type(ebooklib.ITEM_DOCUMENT):
        raw = item.get_content()
        text = _html_to_text(raw.decode("utf-8", errors="ignore"))
        stripped = text.strip()
        if stripped:
            parts.append(stripped)
    return "\n".join(parts)


def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt" or suffix == ".md":
        return normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return normalize_text("\n".join(pages))
    if suffix == ".epub":
        return normalize_text(_extract_epub(path))
    raise ValueError(
        f"Unsupported file type: {suffix}. Supported formats: {_SUPPORTED_LIST}"
    )


def chunk_text(text: str, max_chars: int | None = None, overlap: int | None = None) -> list[str]:
    if not text:
        return []
    max_chars = max_chars or MAX_CHUNK_CHARS
    overlap = overlap if overlap is not None else CHUNK_OVERLAP
    chunks: list[str] = []
    start = 0
    length = len(text)
    while start < length:
        end = min(start + max_chars, length)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == length:
            break
        start = max(0, end - overlap)
    return chunks

