from __future__ import annotations

from .db import add_questions, list_questions
from .providers import pick_provider, ProviderError


def generate_questions(agent_id: str, text_sample: str, count: int = 5) -> list[str]:
    """Generate study questions for a book using LLM, then store them."""
    existing = list_questions(agent_id)
    if existing:
        return existing

    # Use first ~3000 chars as a representative sample
    sample = text_sample[:3000]

    prompt = (
        f"Based on the following text excerpt, generate exactly {count} thought-provoking study questions "
        f"that would help a student deeply understand the material using the Feynman technique. "
        f"Questions should encourage critical thinking and connecting ideas. "
        f"Return ONLY the questions, one per line, numbered 1-{count}. No extra text.\n\n"
        f"Text:\n{sample}"
    )

    try:
        provider = pick_provider("chat")
        result = provider.chat(
            system="You are a Socratic tutor. Generate insightful study questions.",
            user=prompt,
        )
        lines = [line.strip() for line in result.content.strip().split("\n") if line.strip()]
        # Strip numbering prefixes like "1. " or "1) "
        questions = []
        for line in lines:
            cleaned = line.lstrip("0123456789.)- ").strip()
            if cleaned:
                questions.append(cleaned)
        questions = questions[:count]
    except ProviderError:
        # Fallback questions if LLM is unavailable
        questions = [
            "What is the central thesis of this text?",
            "What evidence does the author provide?",
            "How would you explain the key concepts in your own words?",
            "What are the practical implications?",
            "What questions remain unanswered?",
        ]

    add_questions(agent_id, questions)
    return questions
