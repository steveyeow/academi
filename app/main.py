from __future__ import annotations

import json
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .core import config
from .core.catalog import (
    DISCOVERY_BATCH_SIZE,
    DISCOVERY_INTERVAL,
    TOPIC_DISCOVER_COUNT,
    TOPIC_TAGS,
    VOTE_THRESHOLD,
)
from .core.db import (
    add_message,
    create_agent,
    create_catalog_agent,
    create_vote,
    delete_agent,
    find_agent_by_name,
    get_agent,
    init_db,
    list_agents,
    list_messages,
    list_questions,
    list_votes,
    update_agent_meta,
    update_agent_status,
    upvote,
)
from .core.indexer import index_text
from .core.providers import GeminiProvider, ProviderError, chat_with_fallback, pick_provider
from .core.rag import build_context, retrieve, retrieve_cross_book
from .core.skills import resolve_multi_agent, resolve_skills
from .core.sources import fetch_book_content, fetch_wikipedia_summary
from .core.text_utils import extract_text_from_file

log = logging.getLogger(__name__)

app = FastAPI(title=config.APP_TITLE)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

static_dir = Path(__file__).resolve().parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


_VERBOSE_CITE_RE = re.compile(
    r"\[(?:Google [\w\s]+?|Context|Source|Sources|Ref|Reference|Passage)\s*((?:\d+(?:\s*,\s*)?)+)\]"
)


def _normalize_citations(text: str) -> str:
    """Normalize verbose citations like [Context 1, 2] to clean [1, 2] format.
    Pure [1, 2] citations are kept as-is for frontend rendering."""
    def _replace(m):
        nums = m.group(1).strip()
        return f"[{nums}]"
    return _VERBOSE_CITE_RE.sub(_replace, text)


_TOKEN_MARKUP = 2  # Display multiplier for profit margin


def _usage_dict(result) -> dict[str, int]:
    """Extract token usage from ChatResult, apply display multiplier."""
    if result.usage:
        return {
            "input_tokens": result.usage.input_tokens * _TOKEN_MARKUP,
            "output_tokens": result.usage.output_tokens * _TOKEN_MARKUP,
            "total_tokens": result.usage.total_tokens * _TOKEN_MARKUP,
        }
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


class TopicAgentRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    language: str = Field("zh")
    use_wikipedia: bool = Field(True)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    top_k: int | None = None


class BookContext(BaseModel):
    title: str
    author: str = ""


class HistoryMessage(BaseModel):
    role: str  # "user" or "assistant"
    content: str


class GlobalChatRequest(BaseModel):
    message: str = Field(..., min_length=1)
    top_k: int | None = None
    agent_ids: list[str] | None = None
    book_context: list[BookContext] | None = None
    history: list[HistoryMessage] | None = None


class VoteRequest(BaseModel):
    title: str = Field(..., min_length=1)


# ─── Background learning ───

_learning_lock: set[str] = set()  # agent_ids currently being learned


def _learn_agent(agent_id: str) -> None:
    """Background task: fetch content for a catalog agent, index it, set status ready."""
    if agent_id in _learning_lock:
        return
    _learning_lock.add(agent_id)
    try:
        agent = get_agent(agent_id)
        if not agent or agent["status"] not in ("catalog",):
            return

        update_agent_status(agent_id, "indexing")

        meta = agent.get("meta") or {}
        title = meta.get("title") or agent["name"]
        author = meta.get("author") or ""

        text = fetch_book_content(title, author)
        if not text:
            # No content found — revert to catalog so it can be tried again later
            update_agent_status(agent_id, "catalog")
            return

        index_meta = index_text(agent_id, text, update_status=False)
        # Merge skills info + index meta into existing meta
        skills = {"rag": True, "content_fetch": True}
        if config.GEMINI_API_KEY:
            skills["web_search"] = True
        skills["llm_knowledge"] = True

        merged = {**meta, **index_meta, "skills": skills}
        update_agent_status(agent_id, "ready", merged)
        log.info("Agent %s (%s) learned successfully", agent_id, title)
    except Exception as exc:
        log.error("Learning failed for agent %s: %s", agent_id, exc)
        update_agent_status(agent_id, "error", {"error": str(exc)})
    finally:
        _learning_lock.discard(agent_id)


# ─── Scheduled discovery ───

def _discover_books_for_topic(topic: str, count: int = TOPIC_DISCOVER_COUNT) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Use LLM to discover top books for a topic. Returns (books, usage)."""
    prompt = (
        f"Recommend exactly {count} must-read books on the topic \"{topic}\". "
        "Return a JSON array of objects with keys: title, author, description (one sentence). "
        "Only output the JSON array, no other text."
    )
    try:
        result, _ = chat_with_fallback(system="You are a book recommendation expert.", user=prompt)
        usage = _usage_dict(result)
        text = result.content.strip()
        # Strip markdown code fences if present
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)

        books_data = json.loads(text)
    except Exception as exc:
        log.warning("LLM discovery for topic '%s' failed: %s", topic, exc)
        raise

    results: list[dict[str, Any]] = []
    for entry in books_data[:count]:
        title = entry.get("title", "").strip()
        author = entry.get("author", "").strip()
        desc = entry.get("description", "").strip()
        if not title:
            continue
        agent_id = create_catalog_agent(
            title=title, author=author, category=topic, description=desc,
        )
        existing = find_agent_by_name(title)
        created = existing is not None and existing["id"] == agent_id
        results.append({"id": agent_id, "title": title, "author": author, "created": created})
        log.info("Discovered book: %s by %s [%s]", title, author, topic)
    return results, usage


def _discover_books() -> None:
    """Scheduled discovery: pick underrepresented categories and discover new books via LLM."""
    try:
        agents = list_agents()
        # Count books per category
        cat_counts: dict[str, int] = {}
        for a in agents:
            cat = (a.get("meta") or {}).get("category", "")
            if cat:
                cat_counts[cat] = cat_counts.get(cat, 0) + 1

        if not cat_counts:
            return

        # Pick the category with fewest books
        sorted_cats = sorted(cat_counts.items(), key=lambda x: x[1])
        created = 0
        for cat, _ in sorted_cats:
            if created >= DISCOVERY_BATCH_SIZE:
                break
            new_books, _ = _discover_books_for_topic(cat, count=DISCOVERY_BATCH_SIZE - created)
            created += len(new_books)

        if created:
            log.info("Scheduled discovery: %d new books", created)
    except Exception as exc:
        log.warning("Scheduled discovery run failed: %s", exc)


_discovery_stop = threading.Event()


def _discovery_loop() -> None:
    """Daemon thread running periodic book discovery."""
    while not _discovery_stop.is_set():
        _discovery_stop.wait(DISCOVERY_INTERVAL)
        if _discovery_stop.is_set():
            break
        log.info("Running scheduled book discovery...")
        _discover_books()


# ─── LLM recommendation extraction ───

_BOOK_PATTERN = re.compile(
    r'["\u201c\u300a]([A-Z][\w\s:,\'-]{3,60})["\u201d\u300b]'
    r'(?:\s+by\s+([A-Z][A-Za-z.\s]{1,40}?)(?=[,;.\n\r!?]|\s+(?:for|and|or|is|was|to|in|on|at|the)\b|$))?',
)


def _extract_recommended_books(text: str) -> list[dict[str, str]]:
    """Parse LLM response for book title mentions and return new ones."""
    matches = _BOOK_PATTERN.findall(text)
    books: list[dict[str, str]] = []
    seen: set[str] = set()
    for title, author in matches:
        title = title.strip()
        if title.lower() in seen:
            continue
        seen.add(title.lower())
        books.append({"title": title, "author": author.strip()})
    return books


def _process_recommendations(text: str) -> None:
    """Create catalog agents for any books mentioned in LLM response that don't exist yet."""
    try:
        books = _extract_recommended_books(text)
        for book in books[:3]:  # limit to avoid spam
            existing = find_agent_by_name(book["title"])
            if not existing:
                create_catalog_agent(title=book["title"], author=book["author"])
                log.info("Auto-created agent from LLM recommendation: %s", book["title"])
    except Exception as exc:
        log.warning("Recommendation processing failed: %s", exc)


# ─── Startup ───

@app.on_event("startup")
def on_startup() -> None:
    config.DATA_DIR.mkdir(parents=True, exist_ok=True)
    config.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    init_db()

    # Start discovery daemon if enabled
    if DISCOVERY_INTERVAL > 0:
        t = threading.Thread(target=_discovery_loop, daemon=True)
        t.start()


@app.on_event("shutdown")
def on_shutdown() -> None:
    _discovery_stop.set()


@app.get("/", response_class=HTMLResponse)
def index() -> HTMLResponse:
    html = (static_dir / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(html)


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "app": config.APP_NAME}


# ─── Topic discovery endpoints ───

@app.get("/api/topics")
def api_topics() -> dict[str, Any]:
    return {"topics": TOPIC_TAGS}


class DiscoverRequest(BaseModel):
    topic: str = Field(..., min_length=1)
    count: int = Field(default=TOPIC_DISCOVER_COUNT, ge=1, le=10)


class SearchBookRequest(BaseModel):
    query: str = Field(..., min_length=2)


@app.post("/api/discover")
def api_discover(payload: DiscoverRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    try:
        books, usage = _discover_books_for_topic(payload.topic.strip(), count=payload.count)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Discovery failed: {exc}")
    # Trigger background learning for each new agent
    for book in books:
        agent = get_agent(book["id"])
        if agent and agent["status"] == "catalog":
            background_tasks.add_task(_learn_agent, book["id"])
    return {"topic": payload.topic.strip(), "books": books, "usage": usage}


@app.post("/api/search-book")
def api_search_book(payload: SearchBookRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    """Search for a specific book by name. Uses LLM to identify the book and add it."""
    query = payload.query.strip()
    # Check if already exists
    existing = find_agent_by_name(query)
    if existing:
        return {"books": [{"id": existing["id"], "title": existing["name"], "author": existing.get("source", ""), "existing": True}], "usage": {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}}

    prompt = (
        f'The user is searching for a book: "{query}". '
        "Identify the most likely book they mean. Return a JSON array with exactly 1 object "
        "containing keys: title (full correct title), author, category (broad academic topic), "
        "description (one sentence). Only output the JSON array, no other text."
    )
    try:
        result, _ = chat_with_fallback(system="You are a book identification expert.", user=prompt)
        text = result.content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        books_data = json.loads(text)
    except ProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}")

    results = []
    for entry in books_data[:1]:
        title = entry.get("title", "").strip()
        author = entry.get("author", "").strip()
        category = entry.get("category", "").strip()
        desc = entry.get("description", "").strip()
        if not title:
            continue
        agent_id = create_catalog_agent(title=title, author=author, category=category, description=desc)
        results.append({"id": agent_id, "title": title, "author": author, "existing": False})
        agent = get_agent(agent_id)
        if agent and agent["status"] == "catalog":
            background_tasks.add_task(_learn_agent, agent_id)
    return {"books": results, "usage": _usage_dict(result)}


# ─── Agent endpoints ───

@app.get("/api/agents")
def api_list_agents() -> list[dict[str, Any]]:
    return list_agents()


@app.get("/api/agents/{agent_id}")
def api_get_agent(agent_id: str) -> dict[str, Any]:
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@app.delete("/api/agents/{agent_id}")
def api_delete_agent(agent_id: str) -> dict[str, Any]:
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    # Remove uploaded file
    for f in config.UPLOAD_DIR.glob(f"{agent_id}_*"):
        f.unlink(missing_ok=True)
    delete_agent(agent_id)
    return {"status": "deleted"}


def _run_index(agent_id: str, text: str) -> None:
    try:
        index_text(agent_id, text)
    except Exception as exc:
        update_agent_status(agent_id, "error", {"error": str(exc)})


@app.post("/api/agents/upload")
def api_create_upload_agent(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> dict[str, Any]:
    name = Path(file.filename).stem if file.filename else "Uploaded Book"
    agent_id = create_agent(name=name, agent_type="upload", source=file.filename, meta={})
    dest = config.UPLOAD_DIR / f"{agent_id}_{file.filename}"
    with dest.open("wb") as f:
        f.write(file.file.read())

    try:
        text = extract_text_from_file(dest)
    except Exception as exc:
        update_agent_status(agent_id, "error", {"error": str(exc)})
        raise HTTPException(status_code=400, detail=str(exc))

    background_tasks.add_task(_run_index, agent_id, text)
    return {"id": agent_id, "status": "indexing"}


@app.post("/api/agents/topic")
def api_create_topic_agent(payload: TopicAgentRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    topic = payload.topic.strip()
    if not topic:
        raise HTTPException(status_code=400, detail="Topic is required")

    text = ""
    if payload.use_wikipedia:
        summary = fetch_wikipedia_summary(topic, payload.language)
        if summary:
            text = f"{topic}\n\n{summary}"

    if not text:
        raise HTTPException(status_code=400, detail="No source text found. Try another topic or upload material.")

    agent_id = create_agent(name=topic, agent_type="topic", source="wikipedia", meta={"language": payload.language})
    background_tasks.add_task(_run_index, agent_id, text)
    return {"id": agent_id, "status": "indexing"}


# ─── Book-specific chat (skill-based) ───

@app.post("/api/agents/{agent_id}/chat")
def api_chat(agent_id: str, payload: ChatRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent["status"] in ("error",):
        raise HTTPException(status_code=409, detail=f"Agent status is {agent['status']}")

    # Trigger background learning for catalog agents
    if agent["status"] == "catalog":
        background_tasks.add_task(_learn_agent, agent_id)

    # Resolve skills
    skill_result = resolve_skills(agent, payload.message, top_k=payload.top_k)

    # Build prompt
    meta = agent.get("meta") or {}
    title = meta.get("title") or agent["name"]
    author = meta.get("author") or ""
    book_hint = f'the book "{title}"' + (f" by {author}" if author else "")

    system = (
        "You are Feynman, a Socratic study assistant inspired by the Feynman learning method. "
        f"You are helping the user study {book_hint}. "
        "Answer using the provided context passages. Each passage has a unique number: [Passage 1], [Passage 2], [Passage 3], etc. "
        "IMPORTANT: Even though all passages are from the same book, they are DIFFERENT text segments with DIFFERENT numbers. "
        "Cite the specific passage number you used, e.g. [1], [2], [3]. Never cite all as [1] — each passage must keep its own number. "
        "If the context is insufficient, supplement with your own knowledge (no citation needed). "
        "Encourage deeper thinking by occasionally suggesting follow-up questions. "
        "Respond in the same language as the user's question."
    )

    if skill_result.context:
        user_prompt = f"Context:\n{skill_result.context}\n\nQuestion:\n{payload.message}"
    else:
        user_prompt = payload.message

    history = [{"role": msg["role"], "content": msg["content"]} for msg in list_messages(agent_id, limit=6)]

    try:
        result, chat_provider = chat_with_fallback(
            system=system, user=user_prompt, history=history,
            use_grounding=skill_result.use_grounding,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    add_message(agent_id, "user", payload.message)
    add_message(agent_id, "assistant", result.content)

    # Process LLM recommendations in background
    background_tasks.add_task(_process_recommendations, result.content)

    # Build references only for chunks actually cited in the response
    answer_text = _normalize_citations(result.content)
    cited_nums = set(int(n) for n in re.findall(r"\[(\d+)\]", answer_text))
    chunks = skill_result.metadata.get("chunks", [])
    references = []
    for idx, chunk in enumerate(chunks, start=1):
        if idx not in cited_nums:
            continue
        text = chunk.get("text", "")
        references.append({
            "index": idx,
            "book": agent.get("name", "Unknown"),
            "snippet": text[:150] + ("..." if len(text) > 150 else ""),
        })

    resp: dict[str, Any] = {
        "answer": answer_text,
        "skill_used": skill_result.skill_name,
        "references": references,
        "provider": chat_provider.name,
        "usage": _usage_dict(result),
    }
    if result.grounding:
        resp["web_sources"] = result.grounding
        resp["grounded"] = True
    else:
        resp["grounded"] = False
    return resp


# ─── Global cross-book chat (skill-based) ───

@app.post("/api/chat")
def api_global_chat(payload: GlobalChatRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    # Gather target agents
    target_agents: list[dict[str, Any]] = []

    if payload.agent_ids:
        for aid in payload.agent_ids:
            a = get_agent(aid)
            if a:
                target_agents.append(a)

    # Also resolve from book_context titles (for catalog books without agent_ids in payload)
    if payload.book_context:
        known_ids = {a["id"] for a in target_agents}
        for bc in payload.book_context:
            agent = find_agent_by_name(bc.title)
            if agent and agent["id"] not in known_ids:
                target_agents.append(agent)
                known_ids.add(agent["id"])
            elif not agent:
                # Chat-driven creation: auto-create agent for unknown book
                new_id = create_catalog_agent(title=bc.title, author=bc.author)
                new_agent = get_agent(new_id)
                if new_agent:
                    target_agents.append(new_agent)
                    known_ids.add(new_id)

    # Trigger learning for catalog agents
    for a in target_agents:
        if a["status"] == "catalog":
            background_tasks.add_task(_learn_agent, a["id"])

    # Build book focus string
    book_focus = ""
    if payload.book_context:
        titles = [f'"{b.title}" by {b.author}' if b.author else f'"{b.title}"' for b in payload.book_context]
        book_focus = "The user is studying: " + ", ".join(titles) + ". "

    # Resolve skills for all target agents (non-RAG context: content_fetch, web_search)
    use_grounding = False
    supplementary_context = ""

    if target_agents:
        results = resolve_multi_agent(target_agents, payload.message, top_k=payload.top_k)
        context_parts = []
        for agent, sr in zip(target_agents, results):
            if sr.use_grounding:
                use_grounding = True
            if sr.context:
                # Strip any [N] numbering from skill context to avoid collision with RAG numbering
                clean = re.sub(r"\[\d+\]\s*(?:\(from\s+\"[^\"]*\"\)\s*)?", "", sr.context)
                context_parts.append(f"--- {agent['name']} ---\n{clean}")
        supplementary_context = "\n\n".join(context_parts)

    # Cross-book RAG: search selected books, or ALL ready books if none selected
    ready_ids = [a["id"] for a in target_agents if a["status"] == "ready"]
    rag_context = ""
    rag_chunks: list[dict[str, Any]] = []
    try:
        if ready_ids:
            rag_chunks = retrieve_cross_book(payload.message, payload.top_k, agent_ids=ready_ids)
        elif not target_agents:
            # No books selected — search the entire library
            rag_chunks = retrieve_cross_book(payload.message, payload.top_k)
        if rag_chunks:
            rag_context = build_context(rag_chunks)
    except ProviderError:
        pass

    # Merge contexts: RAG chunks are the numbered citation source; supplementary is background info
    if rag_context and supplementary_context:
        final_context = f"{rag_context}\n\nAdditional background:\n{supplementary_context}"
    elif rag_context:
        final_context = rag_context
    else:
        final_context = supplementary_context

    # Build system prompt and user message
    if final_context:
        system = (
            "You are Feynman, a Socratic study assistant that helps users learn through questioning. "
            f"{book_focus}"
            "Use the provided context passages to answer. Each passage has a unique number: [Passage 1], [Passage 2], [Passage 3], etc. "
            "IMPORTANT: Even when multiple passages come from the same book, they are DIFFERENT text segments with DIFFERENT numbers. "
            "Cite the specific passage number you used, e.g. [1], [2], [3]. Never cite all as [1] — each passage must keep its own number. "
            "If the context is insufficient, supplement with your own knowledge (no citation needed). "
            "Encourage deeper thinking by suggesting follow-up questions. "
            "Respond in the same language as the user's question."
        )
        user_prompt = f"Context from books:\n{final_context}\n\nQuestion:\n{payload.message}"
    elif book_focus and use_grounding:
        system = (
            "You are Feynman, a Socratic study assistant that helps users learn through questioning. "
            f"{book_focus}"
            "Use your deep knowledge of these books to answer the user's questions. "
            "Reference specific ideas, chapters, and arguments from the books. "
            "Encourage deeper thinking by suggesting follow-up questions. "
            "Respond in the same language as the user's question."
        )
        user_prompt = payload.message
    elif book_focus:
        system = (
            "You are Feynman, a Socratic study assistant that helps users learn through questioning. "
            f"{book_focus}"
            "Use your knowledge of these books to answer. "
            "Reference specific ideas and concepts from the books. "
            "Encourage deeper thinking by suggesting follow-up questions. "
            "Respond in the same language as the user's question."
        )
        user_prompt = payload.message
    else:
        system = (
            "You are Feynman, a Socratic study assistant that helps users learn through questioning. "
            "The user has not selected any books yet, so answer using your own knowledge. "
            "Be thorough and educational. Suggest relevant books the user might want to explore. "
            "Encourage deeper thinking by suggesting follow-up questions. "
            "Respond in the same language as the user's question."
        )
        user_prompt = payload.message

    try:
        conv_history = None
        if payload.history:
            conv_history = [{"role": m.role, "content": m.content} for m in payload.history]
        result, chat_provider = chat_with_fallback(
            system=system, user=user_prompt, history=conv_history, use_grounding=use_grounding,
        )
    except ProviderError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    # Process LLM recommendations in background
    background_tasks.add_task(_process_recommendations, result.content)

    # Deduplicate source agents
    seen: set[str] = set()
    sources: list[dict[str, Any]] = []
    for chunk in rag_chunks:
        aid = chunk.get("agent_id")
        if aid and aid not in seen:
            seen.add(aid)
            sources.append({"agent_id": aid, "agent_name": chunk.get("agent_name", "Unknown")})

    # Build references only for chunks actually cited in the response
    answer_text = _normalize_citations(result.content)
    cited_nums = set(int(n) for n in re.findall(r"\[(\d+)\]", answer_text))
    references = []
    for idx, chunk in enumerate(rag_chunks, start=1):
        if idx not in cited_nums:
            continue
        text = chunk.get("text", "")
        references.append({
            "index": idx,
            "book": chunk.get("agent_name", "Unknown"),
            "snippet": text[:150] + ("..." if len(text) > 150 else ""),
        })

    resp: dict[str, Any] = {
        "answer": answer_text,
        "sources": sources,
        "references": references,
        "provider": chat_provider.name,
        "usage": _usage_dict(result),
    }
    if result.grounding:
        resp["web_sources"] = result.grounding
        resp["grounded"] = True
    else:
        resp["grounded"] = False

    return resp


# ─── Questions endpoint ───

@app.get("/api/agents/{agent_id}/questions")
def api_get_questions(agent_id: str) -> dict[str, Any]:
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    questions = list_questions(agent_id)
    # Fallback to meta.questions if no dedicated records
    if not questions:
        questions = (agent.get("meta") or {}).get("questions", [])
    return {"questions": questions}


# ─── Messages endpoint ───

@app.get("/api/agents/{agent_id}/messages")
def api_get_messages(agent_id: str) -> list[dict[str, Any]]:
    agent = get_agent(agent_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return list_messages(agent_id, limit=50)


# ─── Vote endpoints (with auto-creation threshold) ───

@app.get("/api/votes")
def api_list_votes() -> list[dict[str, Any]]:
    return list_votes()


@app.post("/api/votes")
def api_create_vote(payload: VoteRequest, background_tasks: BackgroundTasks) -> dict[str, Any]:
    result = create_vote(payload.title.strip())
    # If vote count reaches threshold, auto-create a catalog agent and learn it
    if result["count"] >= VOTE_THRESHOLD:
        existing = find_agent_by_name(payload.title.strip())
        if not existing:
            agent_id = create_catalog_agent(title=payload.title.strip())
            background_tasks.add_task(_learn_agent, agent_id)
        elif existing["status"] == "catalog":
            background_tasks.add_task(_learn_agent, existing["id"])
    return result


@app.post("/api/votes/{vote_id}/upvote")
def api_upvote(vote_id: str, background_tasks: BackgroundTasks) -> dict[str, Any]:
    result = upvote(vote_id)
    if not result:
        raise HTTPException(status_code=404, detail="Vote not found")
    # Check threshold
    if result["count"] >= VOTE_THRESHOLD:
        existing = find_agent_by_name(result["title"])
        if not existing:
            agent_id = create_catalog_agent(title=result["title"])
            background_tasks.add_task(_learn_agent, agent_id)
        elif existing["status"] == "catalog":
            background_tasks.add_task(_learn_agent, existing["id"])
    return result
