from __future__ import annotations

from pathlib import Path
import re

from pypdf import PdfReader

from .config import CHUNK_OVERLAP, MAX_CHUNK_CHARS


WHITESPACE_RE = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    text = text.replace("\u00a0", " ")
    return WHITESPACE_RE.sub(" ", text).strip()


def extract_text_from_file(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".txt":
        return normalize_text(path.read_text(encoding="utf-8", errors="ignore"))
    if suffix == ".pdf":
        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        return normalize_text("\n".join(pages))
    raise ValueError(f"Unsupported file type: {suffix}. Please upload .txt or .pdf")


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

