from __future__ import annotations

import uuid
from typing import Any

import numpy as np

from .db import add_chunks, update_agent_status
from .providers import pick_provider, ProviderError
from .questions import generate_questions
from .text_utils import chunk_text


def _vector_bytes(values: list[float]) -> tuple[bytes, int, float]:
    array = np.array(values, dtype=np.float32)
    norm = float(np.linalg.norm(array))
    if norm == 0.0:
        norm = 1.0
    return array.tobytes(), array.shape[0], norm


def index_text(agent_id: str, text: str, update_status: bool = True) -> dict[str, Any]:
    """Index text into chunks + embeddings.

    Args:
        update_status: If True (default), sets agent status to "ready" with meta.
            If False, only indexes and returns meta without changing status.
            Use False when the caller needs to merge additional data into meta first.
    """
    chunks = chunk_text(text)
    if not chunks:
        raise ValueError("No text to index")

    embedder = pick_provider("embed")
    embeddings = embedder.embed_texts(chunks, task_type="RETRIEVAL_DOCUMENT")
    if len(embeddings) != len(chunks):
        raise ProviderError("Embedding count mismatch")

    records = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        vector_bytes, dim, norm = _vector_bytes(emb)
        records.append(
            {
                "id": str(uuid.uuid4()),
                "chunk_index": idx,
                "text": chunk,
                "vector": vector_bytes,
                "dim": dim,
                "norm": norm,
            }
        )

    add_chunks(agent_id, records)

    # Generate study questions from a sample of the text
    questions = generate_questions(agent_id, text)

    meta = {
        "chunk_count": len(chunks),
        "embed_provider": embedder.name,
        "embed_model": getattr(embedder, "embed_model", None),
        "questions": questions,
    }
    if update_status:
        update_agent_status(agent_id, "ready", meta)
    return meta
