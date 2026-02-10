# AcademiAI

A Socratic study assistant that turns any book into an intelligent agent. Ask questions, get answers grounded in real book content, and let the system learn and grow its library automatically.

## How It Works

Every book is an **Agent** with pluggable **Skills**:

| Skill | Priority | Description |
|-------|----------|-------------|
| RAG | 1st | Retrieves from indexed chunks (requires content) |
| Content Fetch | 2nd | Pulls info from Open Library / Google Books / Wikipedia |
| Web Search | 3rd | Gemini Search Grounding for real-time answers |
| LLM Knowledge | 4th | Falls back to the model's training knowledge |

When you chat with a book, skills are tried in order — the first one that succeeds provides the context for the answer.

## Catalog Growth

The library starts with 24 seed books and grows through 4 mechanisms:

- **Upload** — Upload PDF/TXT files to create agents
- **Chat-driven** — Mention an unknown book in chat → agent auto-created
- **Vote threshold** — Books that receive enough upvotes get auto-indexed
- **Scheduled discovery** — Periodically discovers new books from Open Library based on existing categories

Catalog books start in `catalog` status. On first chat, the system fetches content in the background and indexes it — subsequent chats use full RAG.

## Quick Start

```bash
git clone https://github.com/steveyeow/academi.git
cd academi
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # add at least one API key
uvicorn app.main:app --reload
```

Open http://localhost:8000

## Configuration

Edit `.env` to set your LLM provider keys. At least one is required:

| Variable | Provider | Notes |
|----------|----------|-------|
| `GEMINI_API_KEY` | Google Gemini | Recommended — supports embeddings + web search grounding |
| `OPENAI_API_KEY` | OpenAI | GPT-4o-mini for chat, text-embedding-3-small for embeddings |
| `KIMI_API_KEY` | Moonshot Kimi | Chat only, no embeddings |

The system auto-selects the best available provider (order: Gemini → OpenAI → Kimi).

### Auto-update settings

| Variable | Default | Description |
|----------|---------|-------------|
| `VOTE_THRESHOLD` | 3 | Upvotes needed to auto-index a book |
| `DISCOVERY_INTERVAL` | 21600 | Seconds between discovery runs (0 to disable) |
| `DISCOVERY_BATCH_SIZE` | 5 | Max books discovered per run |

## Tech Stack

- **Backend**: FastAPI + SQLite (vector embeddings as BLOBs)
- **Frontend**: Vanilla JS SPA with hash-based routing
- **LLM**: Multi-provider with auto-fallback (Gemini, OpenAI, Kimi)
- **Search**: Cosine similarity over embeddings, Gemini Search Grounding

## License

MIT
