from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from . import config
from .db import get_chunks
from .providers import ProviderError, pick_provider
from .rag import retrieve, build_context
from .sources import fetch_book_content

log = logging.getLogger(__name__)


@dataclass
class SkillResult:
    context: str
    skill_name: str
    use_grounding: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# ─── Base Skill ───

class BaseSkill:
    name: str = ""
    priority: int = 100

    def is_available(self, agent: dict[str, Any]) -> bool:
        return True

    def execute(self, agent: dict[str, Any], query: str, **kwargs: Any) -> SkillResult | None:
        raise NotImplementedError


# ─── RAG Skill: retrieve from indexed chunks ───

class RAGSkill(BaseSkill):
    name = "rag"
    priority = 10

    def is_available(self, agent: dict[str, Any]) -> bool:
        return agent.get("status") == "ready"

    def execute(self, agent: dict[str, Any], query: str, **kwargs: Any) -> SkillResult | None:
        agent_id = agent["id"]
        top_k = kwargs.get("top_k")
        embed_provider = (agent.get("meta") or {}).get("embed_provider")
        try:
            chunks = retrieve(agent_id, query, top_k, provider_name=embed_provider)
        except ProviderError:
            return None
        if not chunks:
            return None
        context = build_context(chunks)
        return SkillResult(
            context=context,
            skill_name=self.name,
            metadata={"chunks": chunks},
        )


# ─── Content Fetch Skill: Open Library / Google Books / Wikipedia ───

class ContentFetchSkill(BaseSkill):
    name = "content_fetch"
    priority = 20

    def execute(self, agent: dict[str, Any], query: str, **kwargs: Any) -> SkillResult | None:
        meta = agent.get("meta") or {}
        title = meta.get("title") or agent.get("name", "")
        author = meta.get("author") or agent.get("source", "")
        if not title:
            return None
        content = fetch_book_content(title, author)
        if not content:
            return None
        return SkillResult(
            context=f"Book information for \"{title}\":\n{content}",
            skill_name=self.name,
            metadata={"source": "web_apis"},
        )


# ─── Web Search Skill: Gemini Search Grounding ───

class WebSearchSkill(BaseSkill):
    name = "web_search"
    priority = 30

    def is_available(self, agent: dict[str, Any]) -> bool:
        return bool(config.GEMINI_API_KEY)

    def execute(self, agent: dict[str, Any], query: str, **kwargs: Any) -> SkillResult | None:
        # Don't call LLM here — just set the grounding flag
        # The caller will enable grounding on the final chat call
        return SkillResult(
            context="",
            skill_name=self.name,
            use_grounding=True,
            metadata={"note": "grounding enabled for final chat call"},
        )


# ─── LLM Knowledge Skill: fallback to LLM's training knowledge ───

class LLMKnowledgeSkill(BaseSkill):
    name = "llm_knowledge"
    priority = 40

    def execute(self, agent: dict[str, Any], query: str, **kwargs: Any) -> SkillResult | None:
        meta = agent.get("meta") or {}
        title = meta.get("title") or agent.get("name", "")
        author = meta.get("author") or ""
        hint = f"Use your knowledge about the book \"{title}\""
        if author:
            hint += f" by {author}"
        hint += " to answer."
        return SkillResult(
            context=hint,
            skill_name=self.name,
            metadata={"hint": hint},
        )


# ─── Skill chain ───

ALL_SKILLS: list[BaseSkill] = sorted(
    [RAGSkill(), ContentFetchSkill(), WebSearchSkill(), LLMKnowledgeSkill()],
    key=lambda s: s.priority,
)


def resolve_skills(agent: dict[str, Any], query: str, **kwargs: Any) -> SkillResult:
    """Try skills by priority, return the first successful result."""
    for skill in ALL_SKILLS:
        if not skill.is_available(agent):
            continue
        try:
            result = skill.execute(agent, query, **kwargs)
            if result is not None:
                log.info("Agent %s: skill '%s' resolved", agent.get("id"), skill.name)
                return result
        except Exception as exc:
            log.warning("Skill %s failed for agent %s: %s", skill.name, agent.get("id"), exc)
    # Should never reach here because LLMKnowledgeSkill always succeeds
    return SkillResult(context="", skill_name="none")


def resolve_multi_agent(agents: list[dict[str, Any]], query: str, **kwargs: Any) -> list[SkillResult]:
    """Resolve skills for multiple agents (for global chat)."""
    results = []
    for agent in agents:
        result = resolve_skills(agent, query, **kwargs)
        results.append(result)
    return results
