# Great Minds — Agent Universe Spec

> Don't just chat with books. Chat and learn with the greatest minds in history.

## Overview

Feynman today lets you chat with books and build knowledge systems from topics. **Great Minds** introduces a new dimension: AI agents that faithfully represent historical and contemporary thinkers — Aristotle, Bertrand Russell, Laozi, Steve Jobs, Richard Feynman, Charlie Munger, and others. These "mind agents" become first-class entities in the product alongside books, unlocking two new experiences:

1. **Book Discussion with Great Minds** — When you're reading a book, relevant thinkers join the conversation. Instead of one AI giving you answers, you hear perspectives from minds who would actually have something to say about the topic.

2. **Topic Exploration with Great Minds** — When you're exploring a domain (e.g., "What is consciousness?"), Feynman assembles a panel of relevant thinkers who discuss the question with you — drawing on their works, philosophies, and known viewpoints.

---

## 1. Mind Agent Design

### 1.1 What is a Mind Agent?

A mind agent represents a real person who has authored books, developed theories, or contributed significant ideas. Each mind agent has:

| Field | Description |
|-------|-------------|
| `name` | Full name (e.g., "Aristotle", "Charlie Munger") |
| `era` | Time period (e.g., "384–322 BC", "1924–2023") |
| `domain` | Primary fields — comma-separated (e.g., "philosophy, logic, ethics") |
| `persona` | A detailed system prompt that captures their thinking style, vocabulary, known positions, and intellectual temperament |
| `works` | Key works/books associated with them (linked to book agents when available) |
| `bio_summary` | 2-3 sentence biography for display |
| `avatar_seed` | Deterministic seed for generating a consistent visual avatar |

### 1.2 How Mind Agents Are Selected

Mind agents surface in two contexts. The selection logic differs:

**Context A: Book Discussion**

When a user is chatting about a book (or multiple books), the system selects relevant minds by:

1. **Author match** — If the book's author is a known mind agent, they are always included.
2. **Domain overlap** — Minds whose `domain` overlaps with the book's `category` are candidates.
3. **Intellectual relationship** — The LLM is asked: *"Given this book, which 2-4 thinkers would have the most interesting and contrasting perspectives on its ideas?"* This ensures we get complementary viewpoints, not just same-domain thinkers.

Selection prompt (sent once per book/session):
```
Given the book "{title}" by {author} about {category}:
Suggest 2-4 historical or contemporary thinkers who would have substantive, 
diverse perspectives on this book's ideas. Include at least one thinker who 
would likely disagree or offer a contrasting viewpoint.
Return JSON: [{name, reason}]
```

**Context B: Topic Exploration**

When a user asks about a topic without specific books:

1. The LLM is asked to identify 3-5 thinkers most relevant to the topic.
2. Selection prioritizes diversity: different eras, different schools of thought, at least one contrarian voice.

Selection prompt:
```
The user wants to explore: "{topic}"
Suggest 3-5 thinkers (historical or contemporary) who represent diverse, 
substantive perspectives on this topic. Include different eras and at least 
one contrarian or unconventional viewpoint.
Return JSON: [{name, era, domain, reason}]
```

### 1.3 How Mind Agents Are Generated

Mind agents are generated on-demand and cached in the database. The generation flow:

1. **Check cache** — Look up the mind by name (case-insensitive) in the `minds` table.
2. **Generate if missing** — Call the LLM to produce the mind's persona profile:

```
Create a detailed persona profile for {name} ({era}).

You must capture:
1. Their intellectual style — how they reason, argue, and explain
2. Their vocabulary and rhetorical patterns (e.g., Socratic questioning for Socrates, 
   aphoristic style for Nietzsche, mental models for Munger)
3. Their known philosophical/intellectual positions
4. How they would likely respond to modern ideas they never encountered
5. Their characteristic agreements and disagreements with other thinkers

Return JSON:
{
  "name": "...",
  "era": "...",
  "domain": "...",
  "bio_summary": "...",
  "persona": "... (detailed system prompt, 300-500 words) ...",
  "works": ["...", "..."],
  "thinking_style": "...",
  "typical_phrases": ["...", "..."]
}
```

3. **Index their works** — For each work listed, check if it exists as a book agent. If not, create a catalog agent and queue it for learning (reuses existing `_learn_agent` flow).

4. **Save to database** — Store the mind agent for future reuse.

### 1.4 How Many Minds Per Conversation

- **Book discussion**: 2-3 minds (the author + 1-2 others with contrasting views)
- **Topic exploration**: 3-5 minds
- The user can manually add/remove minds from the panel at any time
- Minds can be "muted" (hidden from auto-responses but still available if directly addressed)

### 1.5 How Mind Agents Stay Faithful

Persona fidelity is the hardest problem. The approach:

**System prompt layering:**
Each mind agent's LLM call uses a three-layer system prompt:

```
Layer 1 (Identity): You are {name}, the {era} {domain} thinker. {persona}
Layer 2 (Grounding): Your known works include: {works}. Your key positions: {positions}.
Layer 3 (Constraints): 
  - Stay in character. Never break the fourth wall.
  - When discussing topics beyond your historical knowledge, reason from your 
    established principles rather than inventing positions.
  - Use your characteristic communication style: {thinking_style}.
  - Occasionally use phrases characteristic of you: {typical_phrases}.
  - When you disagree with another thinker in the conversation, be specific 
    about why, grounding it in your actual philosophical positions.
  - Acknowledge the limits of your knowledge honestly.
```

**RAG grounding:**
When a mind's works are indexed as book agents, their responses are grounded in actual text passages from their books — the same RAG pipeline used for regular book chat. This prevents hallucination of positions they never held.

**Cross-validation:**
For critical claims about a thinker's position, the system can optionally verify via web search grounding (existing Gemini Search Grounding skill).

### 1.6 Pre-generated Seed Minds

To ensure a great first experience, Feynman ships with a set of pre-generated seed minds that are created on first startup. These cover major domains so users always have minds to explore:

| Domain | Seed Minds |
|--------|------------|
| Philosophy | Aristotle, Socrates, Nietzsche, Laozi |
| Science | Richard Feynman, Albert Einstein, Charles Darwin |
| Economics & Business | Adam Smith, Charlie Munger, Peter Drucker |
| Literature & Thought | Bertrand Russell, Fyodor Dostoevsky |
| Technology & Practice | Steve Jobs, Elon Musk |
| Psychology | Carl Jung, Daniel Kahneman |
| Politics & History | Niccolò Machiavelli, Winston Churchill |

Approximately 15-20 minds, generated once and cached permanently. Additional minds are generated on-demand as users explore new books and topics.

### 1.7 Memory and Iteration

Mind agents are not static — they accumulate memory over time, making them richer with each conversation.

**Two layers of memory:**

| Layer | Scope | What it captures | When it's used |
|-------|-------|-----------------|----------------|
| **Global memory** | Across all users | Key discussion points, frequently debated positions, refined takes on common questions | Appended to the mind's context in every conversation |
| **User memory** | Per user | What this user has discussed with this mind before, their interests, where the conversation left off | Appended when the same user chats with the same mind again |

**How memory works:**

1. After each conversation, the system extracts a brief summary (2-3 sentences) of the key points discussed.
2. Global memory entries are stored in a `mind_memories` table and capped (e.g., most recent 50 entries per mind) to keep context windows manageable.
3. User memory entries are stored with a `user_id` tag (or anonymous session ID for the self-hosted version).
4. When building the system prompt for a mind, relevant memories are injected as an additional context layer:

```
Layer 4 (Memory):
  Global: You have previously discussed {topic_summaries} with various people.
  User: You last spoke with this person about {previous_discussion}. They were 
  particularly interested in {interests}.
```

This means a mind like Charlie Munger gets sharper over time — his responses to questions about mental models become more nuanced as he "accumulates" discussion experience, while still staying grounded in his actual persona and works.

### 1.8 Updating Mind Agents

- Mind agents' **persona is immutable once generated** — their core identity doesn't change.
- **Memory grows** — their accumulated discussion context evolves with every conversation.
- If a user reports inaccuracy, the persona can be regenerated with a `version` increment.
- New works can be linked to existing minds without regenerating the persona.

---

## 2. User Interaction Design

### 2.1 Experience A: Book Discussion with Great Minds

**Trigger:** User is chatting about a book (single-book or cross-book chat).

**Flow:**

1. User sends a message about a book.
2. Feynman answers normally (existing behavior — RAG + skills).
3. Below the main answer, a **"Perspectives" panel** shows:
   - 2-3 mind agents with short commentary on the topic.
   - Each mind's response is clearly attributed with their name and avatar.
   - Responses are concise (2-4 sentences) — these are perspectives, not essays.

**UI Layout:**

```
┌─────────────────────────────────────────────┐
│ User: What is the main argument in "Wealth  │
│       of Nations"?                          │
├─────────────────────────────────────────────┤
│ Feynman: [Main RAG-grounded answer with     │
│          citations as today]                │
├─────────────────────────────────────────────┤
│ 💭 Great Minds                              │
│                                             │
│ ┌─ Karl Marx ──────────────────────────┐    │
│ │ "Smith's analysis of the division of │    │
│ │  labor is insightful, but he fails   │    │
│ │  to see how..."                      │    │
│ │                         [Chat →]     │    │
│ └──────────────────────────────────────┘    │
│                                             │
│ ┌─ John Maynard Keynes ───────────────┐    │
│ │ "Smith was right about markets, but  │    │
│ │  what he couldn't foresee was..."    │    │
│ │                         [Chat →]     │    │
│ └──────────────────────────────────────┘    │
│                                             │
│ [+ Invite a mind]  [🔄 Different perspectives] │
└─────────────────────────────────────────────┘
```

**Clicking [Chat →]** on a mind opens a threaded sub-conversation with that specific mind, grounded in the current book context. The user can ask follow-up questions directly to Marx, Keynes, etc.

### 2.2 Experience B: Topic Exploration with Great Minds

**Trigger:** User asks about a topic (no specific book selected, or explicitly requests minds).

**Flow:**

1. User sends a topic question (e.g., "What is the nature of consciousness?").
2. Feynman provides an initial overview (existing behavior).
3. A **"Round Table" panel** appears below, showing a curated panel of minds.
4. Each mind gives their perspective on the topic.
5. The user can then engage in a **multi-mind discussion** — asking questions that all minds respond to, or directing questions to specific minds.

**UI Layout:**

```
┌──────────────────────────────────────────────────┐
│ User: What is the nature of consciousness?       │
├──────────────────────────────────────────────────┤
│ Feynman: [Overview answer with book suggestions] │
├──────────────────────────────────────────────────┤
│ 🏛️ Round Table                                   │
│                                                  │
│ Panelists:                                       │
│ [🧠 Descartes] [🧠 Daniel Dennett]              │
│ [🧠 Alan Turing] [🧠 Buddhist: Thich Nhat Hanh] │
│                                                  │
│ ┌─ Descartes ─────────────────────────────┐      │
│ │ "Consciousness is the one thing we      │      │
│ │  cannot doubt. Cogito ergo sum..."      │      │
│ └─────────────────────────────────────────┘      │
│                                                  │
│ ┌─ Daniel Dennett ────────────────────────┐      │
│ │ "Descartes got it backwards. There is   │      │
│ │  no 'theater of the mind'..."           │      │
│ └─────────────────────────────────────────┘      │
│                                                  │
│ ┌─ Alan Turing ───────────────────────────┐      │
│ │ "The question isn't whether machines    │      │
│ │  think, but whether we can tell..."     │      │
│ └─────────────────────────────────────────┘      │
│                                                  │
│ ┌─ Thich Nhat Hanh ──────────────────────┐      │
│ │ "Consciousness is not a thing to be     │      │
│ │  studied, but an experience to be..."   │      │
│ └─────────────────────────────────────────┘      │
│                                                  │
│ [+ Invite a mind]  [Ask the panel a question ↓]     │
│                                                  │
│ ┌────────────────────────────────────────┐       │
│ │ @Dennett, how do you respond to        │       │
│ │ Descartes' certainty argument?    [→]  │       │
│ └────────────────────────────────────────┘       │
└──────────────────────────────────────────────────┘
```

### 2.3 Interaction Patterns

**Addressing specific minds:**
- `@Aristotle, what do you think?` → Only Aristotle responds.
- `@Marx @Keynes, do you agree on this?` → Marx and Keynes respond.
- No @ mention → All panelists respond (brief mode).

**Adding/removing minds:**
- [+ Invite a mind] opens a search/suggest popover where the user can type a name or pick from suggestions.
- Each mind chip has an × to remove from the panel.
- Adding a mind triggers on-demand generation if not cached.

**Mind-to-mind interaction:**
- When one mind's response references another panelist, the UI shows a subtle "reply" indicator.
- The system prompt includes awareness of other panelists: *"Other thinkers in this discussion: {names}. You may reference or respond to their positions."*

### 2.4 The Minds Page

Minds get a **top-level navigation entry** — equal in prominence to Library, not buried as a tab within it.

The Minds page shows all live mind agents as cards in a grid, similar to the Library's book grid:

- **Avatar** — deterministic visual identity based on `avatar_seed`
- **Name and era** — e.g., "Aristotle (384–322 BC)"
- **Domain tags** — e.g., "Philosophy · Logic · Ethics"
- **Bio summary** — 2-3 sentence description
- **Works** — linked to book agents in the Library
- **[Chat →]** — start a direct conversation with this mind
- **Status indicator** — shows if the mind has accumulated memories (e.g., "42 discussions")

Users can also search/filter minds by domain, and an [+ Invite a mind] button allows generating any mind on demand by typing a name.

### 2.5 Where Minds Appear in the UI

| Location | Behavior |
|----------|----------|
| **Home page** | Starter prompts featuring minds: "Discuss philosophy with Aristotle and Nietzsche" |
| **Global chat** | Perspectives/Round Table panel below Feynman's answer |
| **Book chat** | Perspectives panel below Feynman's answer (author always included) |
| **Minds page** | Top-level nav — browse, search, and chat with all live minds |
| **Right sidebar** | When minds are active in chat, show panelist list with avatars |

---

## 3. Technical Architecture

### 3.1 Database Schema

New table: `minds`

```sql
CREATE TABLE IF NOT EXISTS minds (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    era TEXT,
    domain TEXT,
    bio_summary TEXT,
    persona TEXT NOT NULL,        -- detailed system prompt
    thinking_style TEXT,
    typical_phrases TEXT,         -- JSON array
    works TEXT,                   -- JSON array of work titles
    avatar_seed TEXT,
    version INTEGER DEFAULT 1,
    chat_count INTEGER DEFAULT 0, -- total conversations across all users
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_minds_name ON minds(LOWER(name));
```

Junction table to link minds to their book agents:

```sql
CREATE TABLE IF NOT EXISTS mind_works (
    mind_id TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    PRIMARY KEY (mind_id, agent_id),
    FOREIGN KEY (mind_id) REFERENCES minds(id),
    FOREIGN KEY (agent_id) REFERENCES agents(id)
);
```

Memory table for accumulated discussion context:

```sql
CREATE TABLE IF NOT EXISTS mind_memories (
    id TEXT PRIMARY KEY,
    mind_id TEXT NOT NULL,
    user_id TEXT,                 -- NULL for global memories
    summary TEXT NOT NULL,        -- 2-3 sentence discussion summary
    topic TEXT,                   -- topic tag for retrieval
    created_at TEXT NOT NULL,
    FOREIGN KEY (mind_id) REFERENCES minds(id)
);

CREATE INDEX IF NOT EXISTS idx_mind_memories_mind ON mind_memories(mind_id);
CREATE INDEX IF NOT EXISTS idx_mind_memories_user ON mind_memories(mind_id, user_id);
```

### 3.2 New API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/minds` | GET | List all cached mind agents |
| `/api/minds/{id}` | GET | Get a specific mind agent |
| `/api/minds/suggest` | POST | Suggest minds for a book or topic |
| `/api/minds/generate` | POST | Generate (or retrieve cached) a mind by name |
| `/api/minds/{id}/chat` | POST | Chat with a specific mind agent |
| `/api/minds/panel-chat` | POST | Send a message to all panelists |

**POST `/api/minds/suggest`**
```json
// Request
{
  "book_title": "Wealth of Nations",     // optional
  "book_author": "Adam Smith",           // optional
  "topic": "free market economics",      // optional
  "exclude": ["Adam Smith"],             // already in panel
  "count": 3
}

// Response
{
  "minds": [
    {"name": "Karl Marx", "era": "1818-1883", "reason": "Directly critiqued Smith's capitalism"},
    {"name": "John Maynard Keynes", "era": "1883-1946", "reason": "Challenged laissez-faire economics"},
    {"name": "Friedrich Hayek", "era": "1899-1992", "reason": "Defended and extended Smith's free market ideas"}
  ],
  "usage": {...}
}
```

**POST `/api/minds/panel-chat`**
```json
// Request
{
  "message": "What do you think about Smith's invisible hand?",
  "mind_ids": ["id1", "id2", "id3"],
  "target_minds": ["Karl Marx"],         // optional: @mention targeting
  "book_context": [...],                 // optional: books being discussed
  "agent_ids": [...],                    // optional: book agents for RAG
  "history": [...]                       // conversation history
}

// Response
{
  "responses": [
    {
      "mind_id": "id1",
      "mind_name": "Karl Marx",
      "response": "Smith's invisible hand is a convenient fiction...",
      "references": [...],
      "usage": {...}
    },
    {
      "mind_id": "id2",
      "mind_name": "Friedrich Hayek",
      "response": "Smith's insight about spontaneous order...",
      "references": [...],
      "usage": {...}
    }
  ],
  "total_usage": {...}
}
```

### 3.3 New Backend Module: `app/core/minds.py`

```python
# Key functions:

def get_or_create_mind(name: str) -> dict:
    """Look up a mind by name; generate via LLM if not cached."""

def suggest_minds_for_book(title: str, author: str, category: str, count: int = 3) -> list[dict]:
    """Use LLM to suggest relevant minds for a book."""

def suggest_minds_for_topic(topic: str, count: int = 4) -> list[dict]:
    """Use LLM to suggest relevant minds for a topic."""

def build_mind_system_prompt(mind: dict, book_context: str = "", other_minds: list[str] = None) -> str:
    """Construct the layered system prompt for a mind agent."""

def mind_chat(mind: dict, message: str, book_context: str = "", 
              rag_chunks: list = None, history: list = None,
              other_minds: list[str] = None) -> ChatResult:
    """Chat as a specific mind, grounded in their persona + optional book context."""
```

### 3.4 Integration with Existing Systems

**RAG integration:**
When a mind has linked book agents (`mind_works`), their responses are grounded in RAG passages from those books — exactly like current book chat. The mind's persona is the system prompt; the RAG context is injected into the user prompt.

**Skill chain reuse:**
Mind chat uses the same skill chain (RAG → Content Fetch → Web Search → LLM Knowledge) but with the mind's persona as the system prompt instead of the generic Feynman prompt.

**Global chat integration:**
The existing `api_global_chat` endpoint is extended: after Feynman's main response, if minds are active, a follow-up call to `panel-chat` generates mind perspectives. These are returned in the response payload as a new `perspectives` field.

### 3.5 Performance Considerations

- **Parallel mind responses:** When generating panel responses, all mind LLM calls are made concurrently (using `asyncio.gather` or `ThreadPoolExecutor`).
- **Brief mode:** Panel responses are capped at ~100 tokens each to keep the UI snappy and costs down.
- **Lazy generation:** Minds are only generated when first needed, then cached permanently.
- **Token budget:** Display per-mind token usage separately so users see the cost breakdown.

---

## 4. Implementation Phases

### Phase 1: Core Infrastructure & Minds Page
- `minds`, `mind_works`, `mind_memories` tables and CRUD in `db.py`
- `minds.py` module: `get_or_create_mind`, `build_mind_system_prompt`, `mind_chat`
- API endpoints: `/api/minds`, `/api/minds/generate`, `/api/minds/{id}/chat`
- Pre-generate seed minds on first startup
- Frontend: top-level Minds page with grid, search, and direct chat

### Phase 2: Perspectives Panel (Book + Topic Chat)
- `/api/minds/suggest` endpoint
- `/api/minds/panel-chat` endpoint with concurrent LLM calls
- Integrate perspectives into `api_chat` and `api_global_chat` responses
- Frontend: Perspectives / Round Table panel below assistant messages
- Frontend: @mention targeting for specific minds

### Phase 3: Memory System
- Post-conversation memory extraction (global + user-level summaries)
- Memory injection into mind system prompts
- `chat_count` tracking per mind
- Frontend: memory indicator on mind cards ("42 discussions")

### Phase 4: Polish
- Threaded sub-conversations with individual minds
- Mind-to-mind awareness in prompts
- Starter prompts featuring minds on home page
- Mind avatar generation
- Mind popularity and domain filtering

---

## 5. Network Graph Visualization

The Minds page renders all mind agents as an interactive force-directed graph. This section documents the design decisions and implementation constraints. **Read this before touching the graph code.**

### 5.1 Connection Topology: Vector Similarity (not tags)

Links between nodes are derived from **cosine similarity of embedding vectors**, not keyword/domain matching. Each mind has an embedding generated from their name, domain, bio, thinking style, works, and persona text (see `embed_mind()` in `minds.py`).

**Why vector similarity:**
Tag matching only connects minds within the same domain. Vector similarity can surface cross-domain relationships — e.g., Nietzsche ↔ Dostoevsky (both deal in existential suffering), or Taleb ↔ Darwin (both think about survival under uncertainty). The graph becomes a semantic network, not a taxonomy.

**Link computation** (`compute_mind_similarities()` in `minds.py`):
- Builds a pairwise cosine similarity matrix across all minds with embeddings.
- For each mind, keeps only its **top-K strongest neighbors** (currently K=4), regardless of absolute similarity score.
- This bounds total link count to ~`n * K / 2` regardless of how dense the embedding space is.

> **Warning:** Do NOT switch back to a global absolute threshold (e.g., `s > 0.65`). All intellectual personas embed near each other in vector space (they all discuss ideas, reason, write). A threshold approach produces 200+ links for 47 minds, which overwhelms the repulsion forces and collapses the graph into a single cluster.

### 5.2 Spatial Layout: PCA Projection

Node positions are derived from **PCA of the embedding matrix** (`compute_mind_layout()` in `minds.py`):

1. Stack all normalized embedding vectors into a matrix.
2. Center the matrix (subtract column mean).
3. Run SVD, project onto first 2 principal components.
4. Normalize each axis to `[0.08, 0.92]` of canvas size.

This means **position encodes semantic meaning**: nodes that are close in embedding space appear close on the canvas. Thinkers who span multiple domains (Russell, da Vinci, Taleb) naturally land between clusters. No domain labels or manual placement are needed.

**API:** `GET /api/minds/similarities` returns both `links` and `layout` in a single response to avoid a second round-trip.

> **Warning:** Do NOT replace PCA layout with hand-coded domain coordinates (e.g., `{philosophy: {rx: 0.2, ry: 0.3}, science: {rx: 0.7, ry: 0.2}}`). Hard-coded clusters are arbitrary and inconsistent with the vector-based connection logic. The two systems must share the same semantic foundation.

### 5.3 Force Simulation Parameters

The graph uses D3 `forceSimulation` with these forces (in `_renderMindsGraph`, `app.js`):

| Force | Parameters | Purpose |
|-------|-----------|---------|
| `link` | distance `max(80, 280 - strength*70)`, strength `0.08 + strength*0.15` | Pull connected nodes together |
| `charge` | strength `-600`, distanceMax `800` | Repel all nodes from each other |
| `embedding` | strength `0.04` | Gently guide each node toward its PCA position |
| `collision` | radius `BASE_R + 20` | Prevent node overlap |

**Critical constraint — `embedding` force strength must stay near `0.04`:**

The embedding force nudges each node toward its PCA target position. If this value is too high (e.g., `0.20`), nodes are pulled hard toward their targets while link forces pull in other directions — this creates continuous oscillation/jitter and the graph never settles. The value `0.04` matches the original `forceCenter` strength (`0.03`) and produces smooth, organic settling.

> **Warning:** Do NOT use `forceCenter`, `forceX`, or `forceY` alongside `embedding`. These three forces all pull toward the global canvas center, which — combined with hundreds of link forces — collapses all nodes into the center of the canvas.

### 5.4 Entry Animation

The entry animation (nodes flying in from the top-left on page load) is **not explicitly coded** — it is a natural consequence of D3's default node initialization behavior:

- When a node has no explicit `x`/`y` set, D3 places it at the origin `(0, 0)`, which is the **top-left corner** of the canvas.
- The simulation starts at high alpha (`1.0`) and decays (`alphaDecay: 0.015`), causing nodes to fly outward from `(0,0)` to their force-equilibrium positions.
- This produces the "shooting in from the top-left" effect automatically.

> **Warning:** Do NOT pre-seed node `x`/`y` positions before calling `d3.forceSimulation()`. Setting initial positions (even to PCA coordinates or a scatter point) eliminates the fly-in animation because nodes start near their final positions and the simulation has no distance to travel. The PCA positions are used only as the **target** of the `embedding` force — not as initial positions.
