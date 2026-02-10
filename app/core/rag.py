from __future__ import annotations

from typing import Any

import numpy as np

from .config import TOP_K
from .db import get_chunks, list_agents
from .providers import get_provider, pick_provider, ProviderError


def _bytes_to_vector(blob: bytes, dim: int) -> np.ndarray:
    return np.frombuffer(blob, dtype=np.float32, count=dim)


def retrieve(agent_id: str, query: str, top_k: int | None = None, provider_name: str | None = None) -> list[dict[str, Any]]:
    top_k = top_k or TOP_K
    if provider_name:
        embedder = get_provider(provider_name)
        if not embedder.supports_embeddings():
            raise ProviderError(f"Provider {provider_name} does not support embeddings")
    else:
        embedder = pick_provider("embed")

    query_vec_list = embedder.embed_texts([query], task_type="RETRIEVAL_QUERY")
    query_vec = np.array(query_vec_list[0], dtype=np.float32)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0.0:
        query_norm = 1.0

    rows = get_chunks(agent_id)
    scored = []
    for row in rows:
        vec = _bytes_to_vector(row["vector"], row["dim"])
        denom = float(query_norm * row["norm"]) or 1.0
        score = float(np.dot(query_vec, vec) / denom)
        scored.append(
            {
                "id": row["id"],
                "chunk_index": row["chunk_index"],
                "text": row["text"],
                "score": score,
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def retrieve_cross_book(query: str, top_k: int | None = None, agent_ids: list[str] | None = None) -> list[dict[str, Any]]:
    """Retrieve chunks across ready agents for global chat. Optionally filter by agent_ids."""
    top_k = top_k or TOP_K
    embedder = pick_provider("embed")

    query_vec_list = embedder.embed_texts([query], task_type="RETRIEVAL_QUERY")
    query_vec = np.array(query_vec_list[0], dtype=np.float32)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0.0:
        query_norm = 1.0

    all_agents = list_agents()
    ready_agents = {a["id"]: a for a in all_agents if a["status"] == "ready"}
    if agent_ids:
        ready_agents = {k: v for k, v in ready_agents.items() if k in agent_ids}

    scored = []
    for agent_id, agent in ready_agents.items():
        rows = get_chunks(agent_id)
        for row in rows:
            vec = _bytes_to_vector(row["vector"], row["dim"])
            denom = float(query_norm * row["norm"]) or 1.0
            score = float(np.dot(query_vec, vec) / denom)
            scored.append(
                {
                    "id": row["id"],
                    "agent_id": agent_id,
                    "agent_name": agent["name"],
                    "chunk_index": row["chunk_index"],
                    "text": row["text"],
                    "score": score,
                }
            )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def build_context(chunks: list[dict[str, Any]]) -> str:
    lines = []
    for idx, chunk in enumerate(chunks, start=1):
        lines.append(f"[{idx}] {chunk['text']}")
    return "\n\n".join(lines)
