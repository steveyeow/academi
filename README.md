# AcademiAI

**Turn any book into a conversation.** AcademiAI is a Socratic study assistant that lets you chat with books, discover new ones through your interests, and get answers grounded in real content — with traceable citations back to the source.

## Core Features

### Interest-Driven Book Discovery
Pick topics you care about — Psychology, Philosophy, Economics, Physics, and more. The system uses LLM to curate the best books for each topic and adds them to your personal library instantly. No predefined catalog; your library grows from your curiosity.

### Chat With Any Book
Ask questions about a book and get answers powered by a multi-layered skill system:

| Skill | What it does |
|-------|-------------|
| **RAG** | Retrieves relevant passages from the book's indexed content |
| **Content Fetch** | Pulls information from Open Library, Google Books, and Wikipedia |
| **Web Search** | Uses Gemini Search Grounding for real-time web answers |
| **LLM Knowledge** | Falls back to the model's training knowledge |

Skills are tried in priority order — you always get the best available answer.

### Cross-Book Search
Select multiple books and ask questions across all of them. AcademiAI searches across your entire library to find the most relevant passages, regardless of which book they come from.

### Traceable Citations
Every answer cites its sources with clickable `[1]`, `[2]` markers. Click a citation to jump to the reference — see exactly which book and passage the answer came from. No more black-box AI responses.

### Self-Growing Library
Your library expands naturally through multiple channels:
- **Topic discovery** — Pick an interest, get curated book recommendations via LLM
- **Search & add** — Search for any book in the library; if it's not there, the system finds and adds it automatically
- **Chat-driven** — Mention an unknown book in conversation and it gets added to your library
- **Upload** — Bring your own PDF or TXT files
- **Community voting** — Books with enough upvotes get auto-indexed

### Token Usage Transparency
Every LLM call shows its token consumption — chat responses, book discovery, and search operations all display cost in real time. No hidden usage.

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
| `DEEPSEEK_API_KEY` | DeepSeek | Cost-effective chat, no embeddings |
| `OPENAI_API_KEY` | OpenAI | GPT-4o-mini for chat, text-embedding-3-small for embeddings |
| `KIMI_API_KEY` | Moonshot Kimi | Chat only, no embeddings |
| `ANTHROPIC_API_KEY` | Anthropic Claude | Chat only, no embeddings |

The system auto-selects the best available provider and falls back through the chain: Gemini → DeepSeek → OpenAI → Kimi → Anthropic.

### Library settings

| Variable | Default | Description |
|----------|---------|-------------|
| `VOTE_THRESHOLD` | 3 | Upvotes needed to auto-index a book |
| `DISCOVERY_INTERVAL` | 21600 | Seconds between scheduled discovery runs (0 to disable) |
| `DISCOVERY_BATCH_SIZE` | 5 | Max books discovered per scheduled run |
| `TOPIC_DISCOVER_COUNT` | 5 | Books discovered per topic click |

## Tech Stack

- **Backend**: Python / FastAPI, SQLite with vector embeddings stored as BLOBs
- **Frontend**: Vanilla JS SPA, hash-based routing, no framework dependencies
- **LLM**: 5-provider auto-fallback (Gemini, DeepSeek, OpenAI, Kimi, Anthropic)
- **RAG**: Cosine similarity over embeddings + Gemini Search Grounding
- **Persistence**: Chat sessions in localStorage, book data in SQLite

## License

MIT
