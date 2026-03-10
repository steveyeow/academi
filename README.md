# Feynman

> "You learn by asking questions, by thinking, and by experimenting." — Richard Feynman

**Read books the way Feynman did. Ask questions, connect ideas across much broader sources than any single book, and let AI help you build a knowledge system.**

### Why I built this

Feynman is **not** a replacement for reading. I'm a devoted paper-book lover — the tactile act of flipping through physical pages puts me in a near-meditative state, and nothing replaces that.

Richard Feynman rarely read a book cover to cover — he approached books with questions, pulled insights from multiple sources, and moved on when a book had nothing left to teach him. I read the same way. When I want to explore a new domain, I need to know *which* books are worth the deep read and how they fit together. This tool helps me:

- **Scout before committing** — quickly understand what a book covers and whether it deserves my full attention.
- **Build a knowledge scaffold** — when I'm entering an unfamiliar field, it synthesizes key ideas across multiple authoritative works so I can form an initial mental map before diving in.
- **Go beyond the text** — imagine sitting down with the author for a few hours; you'd learn far more than what's on the page. Feynman gives you that experience — because the AI draws on broader knowledge related to the book, every conversation surfaces valuable context and insights you wouldn't get from reading alone.

In short: Feynman helps you read the way Feynman did — not replace reading itself.

---

Feynman is a Socratic study companion powered by AcademiAI. It does two things:

**1. Turn any book into a conversation** — Ask questions and get answers grounded in the book's actual content, with every claim traced back to a specific passage. But it doesn't stop at the text — the AI brings in broader context and related knowledge, so you learn more than the book alone could teach you.

**2. Turn any topic into a knowledge system** — Curious about microeconomics but don't know where to start? Feynman discovers the right books, generates the questions you should be asking, and teaches you through conversation — all grounded in real sources, enriched by knowledge that goes beyond any single book.

---

## Chat With Books

Have a book but don't want to read all 300 pages? Chat with it instead. Ask anything and get answers backed by a multi-layered skill system:

| Priority | Skill | What it does |
|----------|-------|-------------|
| 1st | **RAG** | Retrieves relevant passages from the book's indexed content |
| 2nd | **Content Fetch** | Pulls information from Open Library, Google Books, and Wikipedia |
| 3rd | **Web Search** | Uses Gemini Search Grounding for real-time web answers |
| 4th | **LLM Knowledge** | Falls back to the model's training knowledge |

Every answer includes clickable `[1]`, `[2]` citations — click to see exactly which passage the answer came from. No black-box responses.

Select multiple books and ask questions across all of them — Feynman searches your entire library to find the most relevant passages regardless of source.

## Topic-Driven Knowledge Building

Don't have a book? Start with a topic.

Pick an interest — Psychology, Philosophy, Economics, Physics, or anything — and Feynman:
1. **Discovers the right books** via LLM curation (no predefined catalog)
2. **Proposes study questions** that map out what you need to understand
3. **Answers your questions** grounded in the discovered books' content
4. **Grows your library organically** as you explore deeper

Your library also expands through search, chat mentions, PDF/TXT uploads, and community voting (books with enough upvotes get auto-indexed).

## Token Usage Transparency

Every LLM call shows its token consumption in real time — chat, discovery, and search. No hidden costs.

## Quick Start

```bash
git clone https://github.com/steveyeow/feynman.git
cd feynman
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

## Roadmap

### Great Minds — Not just chat with books, but chat with great minds *(coming soon)*

Feynman already lets you chat with books. **Great Minds** takes it further — now you can also chat and learn with the great minds behind the ideas: scholars, professors, academics, and great practitioners across every field.

AI agents simulate these great minds — faithfully capturing how they think, argue, and reason, grounded in their actual works. Whether you're reading a specific book or exploring a new domain, these agents join the conversation as companions who read with you and discuss with you.

- **Reading a book together** — When you chat about a book, relevant minds join in. Reading "Wealth of Nations"? Adam Smith explains his reasoning while Marx challenges it and Keynes offers a different lens. They don't just answer your questions — they bring perspectives you wouldn't have thought to ask about.

- **Exploring a topic together** — Curious about consciousness, investing, or moral philosophy? A panel of great minds across eras and disciplines sits down with you to discuss, debate, and teach — each from their own unique vantage point.

Think of it as having a study group of the most brilliant people in history, always available to read with you and think alongside you. See the full design in [`SPEC-great-minds.md`](SPEC-great-minds.md).

## Community

Join our [Discord](https://discord.gg/BkYSkkwq) to share what you're reading, exchange reading methods, and tell us what you'd like to see in the product — or DM me directly on [Twitter/X](https://x.com/steve_yeow).

## License

MIT
