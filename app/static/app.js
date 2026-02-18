/* ─── Feynman — Learn by asking questions ─── */

// ─── State ───
let agents = [];
let votes = [];
let allBooks = [];
let currentBookId = null;
let libraryFilter = 'all';
let librarySearch = '';
let pollTimer = null;

// Chat state
let selectedBooks = new Map();
let chatSessions = [];
let currentSessionId = null;
let sessionCounter = 0;

// Topic state
let topicTags = [];
let activeTopics = new Set();   // currently selected as filters
let loadingTopics = new Set();

const MOCK_QUESTIONS = [
  'What is the central thesis of this book?',
  'How does the author support their main argument?',
  'What are the key concepts introduced?',
  'How does this relate to what you already know?',
  'What are the practical implications?',
];

// ─── Greeting ───
function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return 'Good morning';
  if (h < 18) return 'Good afternoon';
  return 'Good evening';
}

// ─── Router ───
function getRoute() {
  const hash = window.location.hash || '#/';
  if (hash === '#/' || hash === '#') return { page: 'home' };
  if (hash === '#/chat') return { page: 'chat' };
  if (hash === '#/chats') return { page: 'chats' };
  if (hash === '#/library') return { page: 'library' };
  const m = hash.match(/^#\/book\/(.+)$/);
  if (m) return { page: 'book', id: m[1] };
  return { page: 'home' };
}

function navigate() {
  const route = getRoute();
  document.querySelectorAll('.page-view').forEach(el => el.classList.add('hidden'));
  const el = document.getElementById('page-' + route.page);
  if (el) el.classList.remove('hidden');

  switch (route.page) {
    case 'home':
      renderHome();
      renderSelectedChips();
      break;
    case 'chat': onChatPageShow(); break;
    case 'chats': renderChatsPage(); break;
    case 'library': renderLibrary(); break;
    case 'book':
      currentBookId = route.id;
      renderBookDetail(route.id);
      break;
  }
}
window.addEventListener('hashchange', navigate);

// ─── Sidebar toggle ───
function toggleSidebar() {
  document.getElementById('app-layout').classList.toggle('sidebar-collapsed');
}

// ─── API ───
async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const d = await r.json();
  if (!r.ok) throw new Error(d.detail || 'Request failed');
  return d;
}

async function loadAgents() {
  try { agents = await api('/api/agents'); } catch { agents = []; }
  buildBookList();
}

async function loadVotes() {
  try { votes = await api('/api/votes'); } catch { votes = []; }
}

async function loadTopics() {
  try {
    const data = await api('/api/topics');
    topicTags = data.topics || [];
  } catch { topicTags = []; }
}

function renderTopicTags() {
  const grid = document.getElementById('topic-tags-grid');
  if (!grid || !topicTags.length) return;
  grid.innerHTML = topicTags.map(topic => {
    const isLoading = loadingTopics.has(topic);
    const isActive = activeTopics.has(topic);
    let cls = 'topic-tag';
    if (isLoading) cls += ' loading';
    else if (isActive) cls += ' active';
    const spinner = isLoading ? '<span class="loading-dot" style="margin-right:5px;font-size:11px">...</span>' : '';
    return `<button class="${cls}" data-topic="${esc(topic)}">${spinner}${esc(topic)}</button>`;
  }).join('');
  grid.querySelectorAll('.topic-tag').forEach(btn => {
    btn.addEventListener('click', () => handleTopicClick(btn.dataset.topic));
  });
}

async function handleTopicClick(topic) {
  if (loadingTopics.has(topic)) return;

  // Toggle filter
  if (activeTopics.has(topic)) {
    activeTopics.delete(topic);
    renderTopicTags();
    renderLibraryGrid();
    return;
  }

  activeTopics.add(topic);
  renderTopicTags();

  // Check if any books exist for this topic
  const hasBooks = allBooks.some(b => (b.category || '').toLowerCase() === topic.toLowerCase());
  if (hasBooks) {
    renderLibraryGrid();
    return;
  }

  // No books yet — discover them
  loadingTopics.add(topic);
  renderTopicTags();
  try {
    const data = await api('/api/discover', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ topic }),
    });
    _searchUsage = data.usage?.total_tokens > 0 ? data.usage : null;
    await loadAgents();
  } catch (err) {
    activeTopics.delete(topic);
    alert('Discovery failed: ' + err.message);
  } finally {
    loadingTopics.delete(topic);
    renderTopicTags();
    renderLibraryGrid();
  }
}

// ─── Build book list from agents (DB is the single source of truth) ───
function buildBookList() {
  allBooks = agents.map(a => {
    const meta = a.meta || {};
    return {
      id: a.id,                // agent ID is the book ID
      title: a.name,
      author: meta.author || a.source || '',
      isbn: meta.isbn || null,
      category: meta.category || a.type,
      description: meta.description || '',
      agentId: a.id,           // all books have agentId
      status: a.status,
      available: a.status === 'ready',
      skills: meta.skills || {},
      isUploaded: a.type === 'upload',
      isCatalog: a.type === 'catalog',
      upvotes: 0,
    };
  });

  // Merge vote counts
  votes.forEach(v => {
    const b = allBooks.find(x => x.title.toLowerCase() === v.title.toLowerCase());
    if (b) b.upvotes = v.count;
  });
}

// ─── Polling (only when indexing) ───
function startPolling() {
  if (pollTimer) return;
  pollTimer = setInterval(async () => {
    const hasIndexing = agents.some(a => a.status === 'indexing');
    if (!hasIndexing) { clearInterval(pollTimer); pollTimer = null; return; }
    await loadAgents();
    const r = getRoute();
    if (r.page === 'library') renderLibraryGrid();
  }, 5000);
}
function ensurePolling() {
  if (agents.some(a => a.status === 'indexing')) startPolling();
}

// ─── Home ───
function renderHome() {
  document.getElementById('greeting').textContent = getGreeting();
}

// ─── Chat messages ───
function appendMsg(container, role, text, sources, opts) {
  const el = document.createElement('div');
  el.className = 'chat-message ' + role;
  el.dataset.raw = text;
  if (sources?.length) el.dataset.sources = JSON.stringify(sources);
  if (opts && Object.keys(opts).length) el.dataset.opts = JSON.stringify(opts);
  const webSrcs = opts?.webSources || [];
  const refs = opts?.references || [];
  if (role === 'assistant') {
    const content = document.createElement('div');
    content.className = 'msg-content';
    let html = renderMarkdown(text);
    // Convert [1], [2], [1, 2] etc. to clickable citation superscripts
    if (refs.length || webSrcs.length) {
      html = html.replace(/\[(\d+(?:\s*,\s*\d+)*)\]/g, (match, nums) => {
        const indices = nums.split(/\s*,\s*/).map(n => parseInt(n, 10));
        const links = indices.map(num => {
          const idx = num - 1;
          if (refs.length && idx >= 0 && idx < refs.length) {
            return `<a class="cite-link" href="#ref-${num}" title="${esc(refs[idx].book + ': ' + refs[idx].snippet.slice(0, 60))}"><sup>${num}</sup></a>`;
          } else if (webSrcs.length && idx >= 0 && idx < webSrcs.length) {
            return `<a class="cite-link" href="${esc(webSrcs[idx].url)}" target="_blank" rel="noopener" title="${esc(webSrcs[idx].title || '')}"><sup>${num}</sup></a>`;
          }
          return `<sup>${num}</sup>`;
        });
        return `<span class="cite-group">[${links.join(', ')}]</span>`;
      });
    }
    content.innerHTML = html;
    el.appendChild(content);
  } else {
    el.textContent = text;
  }
  if (sources?.length) {
    const t = document.createElement('div');
    t.className = 'source-tags';
    sources.forEach(s => {
      const a = document.createElement('a');
      a.className = 'source-tag';
      a.textContent = s.name;
      a.href = '#/book/' + s.id;
      t.appendChild(a);
    });
    el.appendChild(t);
  }
  // References (RAG chunk sources)
  if (refs.length) {
    const refsEl = document.createElement('div');
    refsEl.className = 'msg-references';
    refsEl.innerHTML = '<div class="refs-header">References</div>' +
      refs.map(r =>
        `<div class="ref-item" id="ref-${r.index}"><span class="ref-num">${r.index}</span><div class="ref-body"><span class="ref-book">${esc(r.book)}</span><span class="ref-snippet">${esc(r.snippet)}</span></div></div>`
      ).join('');
    el.appendChild(refsEl);
  }
  // Web sources (grounding citations)
  if (webSrcs.length) {
    const ws = document.createElement('div');
    ws.className = 'web-sources';
    webSrcs.forEach((src, i) => {
      const a = document.createElement('a');
      a.className = 'web-source-link';
      a.href = src.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.innerHTML = `<span class="web-source-num">${i + 1}</span> ${esc(src.title || src.url)}`;
      ws.appendChild(a);
    });
    el.appendChild(ws);
  }
  // Skill badge
  if (opts?.skillUsed && opts.skillUsed !== 'none') {
    const sb = document.createElement('span');
    sb.className = 'skill-badge skill-' + opts.skillUsed;
    const labels = { rag: 'RAG', content_fetch: 'Web APIs', web_search: 'Web Search', llm_knowledge: 'LLM Knowledge' };
    sb.textContent = labels[opts.skillUsed] || opts.skillUsed;
    el.appendChild(sb);
  }
  // Token usage
  if (opts?.usage && opts.usage.total_tokens > 0) {
    const u = opts.usage;
    const tu = document.createElement('div');
    tu.className = 'token-usage';
    tu.textContent = `${u.total_tokens} tokens`;
    tu.title = `Input: ${u.input_tokens} · Output: ${u.output_tokens}`;
    el.appendChild(tu);
  }
  container.appendChild(el);
  container.scrollTop = container.scrollHeight;
}

function showLoading(c) {
  const el = document.createElement('div');
  el.className = 'chat-message assistant';
  el.id = 'loading-msg';
  el.innerHTML = '<span class="loading-dot">Thinking...</span>';
  c.appendChild(el);
  c.scrollTop = c.scrollHeight;
}
function removeLoading() { document.getElementById('loading-msg')?.remove(); }

// ─── Chat sessions ───
function persistSessions() {
  saveCurrentSession();
  try {
    const data = chatSessions.map(s => ({
      id: s.id, title: s.title, messages: s.messages,
      books: s.books instanceof Map ? [...s.books.entries()] : [],
    }));
    localStorage.setItem('chatSessions', JSON.stringify(data));
    localStorage.setItem('sessionCounter', String(sessionCounter));
    localStorage.setItem('currentSessionId', currentSessionId || '');
  } catch {}
}

function restoreSessions() {
  try {
    const raw = localStorage.getItem('chatSessions');
    if (!raw) return;
    const data = JSON.parse(raw);
    chatSessions = data.map(s => ({
      ...s,
      books: new Map(s.books || []),
    }));
    sessionCounter = parseInt(localStorage.getItem('sessionCounter') || '0', 10);
    currentSessionId = localStorage.getItem('currentSessionId') || null;
  } catch {}
}

function createSession() {
  saveCurrentSession();
  const id = 's-' + (++sessionCounter);
  const session = { id, title: 'New chat', messages: [], books: new Map() };
  chatSessions.unshift(session);
  currentSessionId = id;
  document.getElementById('chat-messages').innerHTML = '';
  hideChatRightSidebar();
  renderChatHistory();
  persistSessions();
  return session;
}

function saveCurrentSession() {
  if (!currentSessionId) return;
  const session = chatSessions.find(s => s.id === currentSessionId);
  if (!session) return;
  const msgs = [];
  document.querySelectorAll('#chat-messages .chat-message').forEach(el => {
    const role = el.classList.contains('user') ? 'user' : 'assistant';
    const msg = { role, content: el.dataset.raw || el.textContent };
    if (el.dataset.sources) try { msg.sources = JSON.parse(el.dataset.sources); } catch {}
    if (el.dataset.opts) try { msg.opts = JSON.parse(el.dataset.opts); } catch {}
    msgs.push(msg);
  });
  session.messages = msgs;
  session.books = new Map(selectedBooks);
}

function switchToSession(id) {
  if (id === currentSessionId) return;
  saveCurrentSession();
  const session = chatSessions.find(s => s.id === id);
  if (!session) return;
  currentSessionId = id;
  selectedBooks = new Map(session.books);
  const chatBox = document.getElementById('chat-messages');
  chatBox.innerHTML = '';
  session.messages.forEach(m => appendMsg(chatBox, m.role, m.content, m.sources, m.opts));
  persistSessions();
  renderSelectedChips();
  restoreChatSidebar(session.messages);
  renderChatHistory();
  if (getRoute().page !== 'chat') {
    window.location.hash = '#/chat';
  }
}

function updateSessionTitle(message) {
  const session = chatSessions.find(s => s.id === currentSessionId);
  if (session && session.title === 'New chat') {
    session.title = message.length > 40 ? message.slice(0, 40) + '...' : message;
    renderChatHistory();
  }
}

function renderChatHistory() {
  const list = document.getElementById('chat-history-list');
  if (!list) return;
  list.innerHTML = chatSessions.map(s =>
    `<button class="history-item ${s.id === currentSessionId ? 'active' : ''}" data-sid="${s.id}">${esc(s.title)}</button>`
  ).join('');
  list.querySelectorAll('.history-item').forEach(btn => {
    btn.addEventListener('click', () => switchToSession(btn.dataset.sid));
  });
}

// ─── Chats page ───
function renderChatsPage() {
  const listEl = document.getElementById('chats-list');
  const emptyEl = document.getElementById('chats-empty');
  const searchEl = document.getElementById('chats-search');
  searchEl.value = '';
  _renderChatsList('');
}

function _renderChatsList(query) {
  const listEl = document.getElementById('chats-list');
  const emptyEl = document.getElementById('chats-empty');
  let sessions = chatSessions;
  if (query) {
    sessions = sessions.filter(s => s.title.toLowerCase().includes(query));
  }
  if (!sessions.length) {
    listEl.innerHTML = '';
    emptyEl.classList.remove('hidden');
    return;
  }
  emptyEl.classList.add('hidden');
  listEl.innerHTML = sessions.map(s =>
    `<div class="chats-list-item" data-sid="${s.id}">
      <svg class="chat-item-icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
      <span class="chat-item-title">${esc(s.title)}</span>
    </div>`
  ).join('');
  listEl.querySelectorAll('.chats-list-item').forEach(el => {
    el.addEventListener('click', () => {
      switchToSession(el.dataset.sid);
    });
  });
}

// ─── Right sidebar visibility ───
function showChatRightSidebar() {
  const el = document.getElementById('chat-right-sidebar');
  if (el) el.classList.add('visible');
}
function hideChatRightSidebar() {
  const el = document.getElementById('chat-right-sidebar');
  if (el) el.classList.remove('visible');
}

// ─── Global chat ───
let pendingHomeMessage = null;

async function sendGlobalChat(message) {
  const chatBox = document.getElementById('chat-messages');

  if (getRoute().page !== 'chat') {
    pendingHomeMessage = message;
    window.location.hash = '#/chat';
    return;
  }

  if (!currentSessionId) createSession();
  updateSessionTitle(message);

  appendMsg(chatBox, 'user', message);
  showLoading(chatBox);

  try {
    const body = { message };
    const agentIds = [];
    const bookContext = [];
    for (const [, book] of selectedBooks) {
      agentIds.push(book.agentId);
      bookContext.push({ title: book.title, author: book.author || '' });
    }
    if (bookContext.length) {
      body.agent_ids = agentIds;
      body.book_context = bookContext;
    }

    const data = await api('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    });
    removeLoading();
    const sources = (data.sources || []).map(s => ({ id: s.agent_id, name: s.agent_name }));
    const msgOpts = {};
    if (data.web_sources?.length) msgOpts.webSources = data.web_sources;
    if (data.grounded) msgOpts.grounded = true;
    if (data.references?.length) msgOpts.references = data.references;
    if (data.usage) msgOpts.usage = data.usage;
    appendMsg(chatBox, 'assistant', data.answer, sources, msgOpts);
    renderChatSidebar(sources, message);
    showChatRightSidebar();
    persistSessions();
    // Trigger polling if any catalog books are being learned
    ensurePolling();
  } catch (err) {
    removeLoading();
    const msg = err.message.includes('No available provider')
      ? 'No LLM API key configured. Please add GEMINI_API_KEY, OPENAI_API_KEY, or KIMI_API_KEY to your .env file and restart the server.'
      : 'Error: ' + err.message;
    appendMsg(chatBox, 'assistant', msg);
    persistSessions();
  }
}

function handleHomeSend() {
  const input = document.getElementById('home-input');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  input.style.height = 'auto';
  sendGlobalChat(msg);
}

function handleChatSend() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';
  input.style.height = 'auto';
  sendGlobalChat(msg);
}

function onChatPageShow() {
  renderSelectedChips();
  renderChatHistory();
  // Restore messages if chat box is empty and we have a current session
  const chatBox = document.getElementById('chat-messages');
  if (currentSessionId && !chatBox.children.length) {
    const session = chatSessions.find(s => s.id === currentSessionId);
    if (session?.messages?.length) {
      session.messages.forEach(m => appendMsg(chatBox, m.role, m.content, m.sources, m.opts));
      restoreChatSidebar(session.messages);
    }
  }
  if (pendingHomeMessage) {
    const msg = pendingHomeMessage;
    pendingHomeMessage = null;
    setTimeout(() => sendGlobalChat(msg), 50);
  }
}

// ─── Chat sidebar (right) ───
function renderChatSidebar(sources, query) {
  const srcEl = document.getElementById('sidebar-sources');
  if (!sources.length) {
    if (selectedBooks.size) {
      srcEl.innerHTML = [...selectedBooks.values()].map(b =>
        sidebarBookItem(b.agentId || b.id, b.title, b.author, b.isbn)
      ).join('');
    } else {
      srcEl.innerHTML = '<p style="font-size:12px;color:var(--text-muted)">No specific sources used</p>';
    }
  } else {
    srcEl.innerHTML = sources.map(s => sidebarBookItem(s.id, s.name, '')).join('');
  }

  const relEl = document.getElementById('sidebar-related');
  // Collect IDs to exclude (sources + selected)
  const excludeIds = new Set(sources.map(s => s.id));
  for (const [, b] of selectedBooks) excludeIds.add(b.agentId || b.id);
  // Collect categories from sources + selected books
  const relCategories = new Set();
  sources.forEach(s => {
    const book = allBooks.find(b => b.id === s.id);
    if (book?.category) relCategories.add(book.category.toLowerCase());
  });
  for (const [, b] of selectedBooks) {
    const book = allBooks.find(x => (x.agentId || x.id) === (b.agentId || b.id));
    if (book?.category) relCategories.add(book.category.toLowerCase());
  }
  // Related = same category, excluding already shown books
  const related = relCategories.size
    ? allBooks
        .filter(b => !excludeIds.has(b.id) && relCategories.has((b.category || '').toLowerCase()))
        .slice(0, 4)
    : [];
  relEl.innerHTML = related.length ? related.map(b => sidebarBookItem(b.agentId || b.id, b.title, b.author, b.isbn)).join('') : '';
}

function restoreChatSidebar(messages) {
  // Find the last assistant message that has sources
  let lastSources = null;
  for (let i = messages.length - 1; i >= 0; i--) {
    if (messages[i].role === 'assistant' && messages[i].sources?.length) {
      lastSources = messages[i].sources;
      break;
    }
  }
  if (lastSources) {
    renderChatSidebar(lastSources, '');
    showChatRightSidebar();
  } else {
    hideChatRightSidebar();
  }
}

function sidebarBookItem(id, title, author, isbn) {
  const coverUrl = isbn ? `https://covers.openlibrary.org/b/isbn/${isbn}-S.jpg` : '';
  const coverHtml = coverUrl
    ? `<img class="sidebar-book-cover" src="${coverUrl}" alt="" onerror="this.style.display='none'" />`
    : '';
  return `<div class="sidebar-book-item" onclick="selectBookFromSidebar('${esc(id)}')">
    ${coverHtml}
    <div class="sidebar-book-info">
      <div class="sidebar-book-title">${esc(title)}</div>
      <div class="sidebar-book-author">${esc(author)}</div>
    </div>
  </div>`;
}

function selectBookFromSidebar(bookKey) {
  const book = allBooks.find(b => (b.agentId || b.id) === bookKey);
  if (book && !selectedBooks.has(book.id)) {
    selectedBooks.set(book.id, book);
    renderSelectedChips();
  }
}
window.selectBookFromSidebar = selectBookFromSidebar;

// ─── Library ───
function renderLibrary() { renderTopicTags(); renderLibraryGrid(); }

function renderLibraryGrid() {
  const c = document.getElementById('library-grid');
  let filtered = [...allBooks];
  if (libraryFilter === 'available') filtered = filtered.filter(b => b.available);
  else if (libraryFilter === 'popular') filtered.sort((a,b) => (b.upvotes||0) - (a.upvotes||0));
  if (activeTopics.size) {
    const topics = new Set([...activeTopics].map(t => t.toLowerCase()));
    filtered = filtered.filter(b => topics.has((b.category || '').toLowerCase()));
  }
  if (librarySearch) {
    const q = librarySearch.toLowerCase();
    filtered = filtered.filter(b =>
      b.title.toLowerCase().includes(q) || b.author.toLowerCase().includes(q) ||
      (b.category||'').toLowerCase().includes(q) || _searchDiscoveredIds.has(b.id)
    );
  }
  renderBookGrid(c, filtered);
  // If searching and no results, show searching indicator (only while actively searching)
  if (librarySearch && librarySearch.length >= 2 && !filtered.length) {
    if (_searchingQuery) {
      c.innerHTML = `<div class="search-discover-prompt" id="search-discover-prompt">
        <span class="loading-dot">Searching for "${esc(librarySearch)}"...</span>
      </div>`;
    } else {
      c.innerHTML = `<div class="search-discover-prompt"><p style="color:var(--text-muted)">No results for "${esc(librarySearch)}"</p></div>`;
    }
  }
  // Show token usage for search/discover inline
  if (_searchUsage && _searchUsage.total_tokens > 0) {
    c.insertAdjacentHTML('beforeend',
      `<div class="token-usage" style="grid-column:1/-1;text-align:center;margin-top:8px" title="Input: ${_searchUsage.input_tokens} · Output: ${_searchUsage.output_tokens}">${_searchUsage.total_tokens} tokens</div>`);
  }
  // Show "Discover more" card when topic filters are active
  if (activeTopics.size && !librarySearch) {
    const topics = [...activeTopics];
    const label = topics.length === 1 ? topics[0] : 'these topics';
    c.insertAdjacentHTML('beforeend',
      `<div class="book-card discover-more-card" id="discover-more-card">
        <div class="card-cover-gen" style="background:var(--bg-sidebar)">
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="var(--text-muted)" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
        </div>
        <div class="card-body"><h3 class="card-title" style="color:var(--text-muted)">Discover more</h3><p class="card-author">${esc(label)}</p></div>
      </div>`);
    document.getElementById('discover-more-card').addEventListener('click', () => discoverMore(topics));
  }
}

async function discoverMore(topics) {
  const card = document.getElementById('discover-more-card');
  if (card) card.innerHTML = '<div class="card-cover-gen" style="background:var(--bg-sidebar)"><span class="loading-dot">...</span></div><div class="card-body"><h3 class="card-title" style="color:var(--text-muted)">Discovering...</h3></div>';
  for (const topic of topics) {
    loadingTopics.add(topic);
  }
  renderTopicTags();
  try {
    let totalTokens = 0;
    for (const topic of topics) {
      const data = await api('/api/discover', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ topic }),
      });
      if (data.usage?.total_tokens) totalTokens += data.usage.total_tokens;
    }
    await loadAgents();
    if (totalTokens > 0) _searchUsage = { total_tokens: totalTokens, input_tokens: 0, output_tokens: 0 };
  } catch (err) {
    alert('Discovery failed: ' + err.message);
  }
  for (const topic of topics) loadingTopics.delete(topic);
  renderTopicTags();
  renderLibraryGrid();
}

let _searchingQuery = null;
let _searchDiscoveredIds = new Set();
let _searchUsage = null;
async function autoSearchBook(query) {
  if (_searchingQuery === query) return;
  _searchingQuery = query;
  try {
    const data = await api('/api/search-book', {
      method: 'POST', headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ query }),
    });
    if (_searchingQuery !== query) return; // user typed something else
    // Track discovered book IDs so they show even if title doesn't match search text
    (data.books || []).forEach(b => { if (b.id) _searchDiscoveredIds.add(b.id); });
    _searchUsage = data.usage?.total_tokens > 0 ? data.usage : null;
    await loadAgents();
    buildBookList();
    renderLibraryGrid();
  } catch (err) {
    if (_searchingQuery !== query) return;
    const c = document.getElementById('search-discover-prompt');
    if (c) c.innerHTML = `<p style="color:var(--text-muted)">Could not find "${esc(query)}"</p>`;
  } finally {
    if (_searchingQuery === query) _searchingQuery = null;
  }
}

const COVER_COLORS = ['#264653','#2a9d8f','#e76f51','#457b9d','#6d597a','#355070','#b56576','#0077b6','#588157','#9b2226'];
function coverColor(title) { let h = 0; for (let i = 0; i < title.length; i++) h = ((h << 5) - h + title.charCodeAt(i)) | 0; return COVER_COLORS[Math.abs(h) % COVER_COLORS.length]; }
function coverInitials(title) { return title.split(/[\s:—]+/).filter(w => w.length > 2).slice(0, 2).map(w => w[0].toUpperCase()).join(''); }

function renderBookGrid(container, books) {
  if (!books.length) { container.innerHTML = '<div class="empty-state"><p>No books found.</p></div>'; return; }
  container.innerHTML = books.map(b => {
    const cover = `<div class="card-cover-gen" style="background:${coverColor(b.title)}"><span>${coverInitials(b.title)}</span></div>`;
    let statusBadge = '';
    if (b.status === 'indexing') statusBadge = '<span class="card-badge indexing">Indexing...</span>';
    else if (b.status === 'catalog') statusBadge = '<span class="card-badge catalog">Catalog</span>';
    else if (b.status === 'ready') statusBadge = '<span class="card-badge ready">Ready</span>';
    const deleteBtn = (b.isUploaded || b.isCatalog) && b.agentId ? `<button class="card-delete-btn" onclick="event.stopPropagation();deleteBook('${esc(b.agentId)}')" title="Delete">&times;</button>` : '';
    return `<div class="book-card" onclick="selectBookForChat('${esc(b.id)}')">
      ${deleteBtn}
      ${cover}
      <div class="card-body"><h3 class="card-title">${esc(b.title)}</h3><p class="card-author">${esc(b.author)}</p></div>
      <div class="card-footer">
        ${statusBadge}
        <button class="card-chat-btn" onclick="event.stopPropagation();selectBookForChat('${esc(b.id)}')">Chat &rarr;</button>
        <button class="upvote-btn" onclick="event.stopPropagation();handleUpvote('${esc(b.title)}')">&#9650; ${b.upvotes||''}</button>
      </div>
    </div>`;
  }).join('');
}

// ─── Delete book ───
async function deleteBook(agentId) {
  if (!confirm('Delete this book? This cannot be undone.')) return;
  try {
    await api('/api/agents/' + agentId, { method: 'DELETE' });
    // Remove from selectedBooks if present
    for (const [key, book] of selectedBooks) {
      if (book.agentId === agentId) { selectedBooks.delete(key); break; }
    }
    await loadAgents();
    renderSelectedChips();
    if (getRoute().page === 'library') renderLibraryGrid();
  } catch (err) {
    alert('Error deleting: ' + err.message);
  }
}
window.deleteBook = deleteBook;

// ─── Book detail ───
async function renderBookDetail(bookId) {
  const headerEl = document.getElementById('book-header');
  const questionsEl = document.getElementById('book-questions');
  const chatBox = document.getElementById('book-chat-messages');
  const metaSidebar = document.getElementById('book-meta-sidebar');
  chatBox.innerHTML = '';

  let book = allBooks.find(b => b.agentId === bookId);
  let agent = agents.find(a => a.id === bookId);
  if (!agent) { try { agent = await api('/api/agents/' + bookId); } catch {} }

  const title = book?.title || agent?.name || 'Unknown';
  const author = book?.author || agent?.source || '';
  const isbn = book?.isbn;
  const desc = book?.description || '';
  const meta = agent?.meta || {};
  const coverUrl = isbn ? `https://covers.openlibrary.org/b/isbn/${isbn}-M.jpg` : '';

  headerEl.innerHTML = `
    ${coverUrl ? `<img class="book-inline-cover" src="${coverUrl}" alt="" onerror="this.style.display='none'" />` : ''}
    <div class="book-inline-info"><h2>${esc(title)}</h2><p>${esc(author)}</p></div>`;

  metaSidebar.innerHTML = `
    <h3 class="sidebar-title">BOOK INFO</h3>
    ${coverUrl ? `<img style="width:100%;border-radius:8px;margin-bottom:12px" src="${coverUrl}" alt="" onerror="this.style.display='none'" />` : ''}
    <p style="font-size:14px;font-weight:600;margin-bottom:4px">${esc(title)}</p>
    <p style="font-size:12px;color:var(--text-muted);margin-bottom:8px">${esc(author)}</p>
    ${desc ? `<p style="font-size:12px;color:var(--text-secondary);line-height:1.5;margin-bottom:12px">${esc(desc)}</p>` : ''}
    <p style="font-size:11px;color:var(--text-muted)">${meta.chunk_count || '—'} chunks</p>
    <p style="font-size:11px;color:var(--text-muted);margin-top:4px">Status: ${agent?.status || '—'}</p>`;

  let questions = [];
  if (agent) {
    try { const q = await api('/api/agents/' + bookId + '/questions'); questions = q.questions || []; } catch {}
  }
  if (!questions.length) questions = meta.questions || MOCK_QUESTIONS;

  questionsEl.innerHTML = `<h4>TRY ASKING</h4>` +
    questions.map(q => `<button class="sidebar-question" data-q="${esc(q)}">${esc(q)}</button>`).join('');
  questionsEl.querySelectorAll('.sidebar-question').forEach(btn => {
    btn.addEventListener('click', () => sendBookChat(bookId, btn.dataset.q));
  });

  if (agent) {
    try { const msgs = await api('/api/agents/' + bookId + '/messages'); msgs.forEach(m => appendMsg(chatBox, m.role, m.content)); } catch {}
  }
}

async function sendBookChat(bookId, message) {
  const chatBox = document.getElementById('book-chat-messages');
  const input = document.getElementById('book-chat-input');
  appendMsg(chatBox, 'user', message);
  if (input) input.value = '';
  showLoading(chatBox);
  try {
    const data = await api('/api/agents/' + bookId + '/chat', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message }),
    });
    removeLoading();
    const msgOpts = {};
    if (data.skill_used) msgOpts.skillUsed = data.skill_used;
    if (data.web_sources?.length) msgOpts.webSources = data.web_sources;
    if (data.grounded) msgOpts.grounded = true;
    if (data.references?.length) msgOpts.references = data.references;
    if (data.usage) msgOpts.usage = data.usage;
    appendMsg(chatBox, 'assistant', data.answer, null, msgOpts);
    // Start polling if the agent started learning
    ensurePolling();
  } catch (err) {
    removeLoading();
    appendMsg(chatBox, 'assistant', 'Error: ' + err.message);
  }
}

// ─── Upload (multi-file) — auto-selects uploaded books as chips ───
async function handleFileUpload(files, statusElId) {
  const statusEl = statusElId ? document.getElementById(statusElId) : null;
  const fileList = Array.from(files);
  let uploaded = 0;
  const uploadedAgentIds = [];

  for (const file of fileList) {
    if (statusEl) statusEl.textContent = `Uploading "${file.name}"${fileList.length > 1 ? ` (${uploaded+1}/${fileList.length})` : ''}...`;
    const fd = new FormData();
    fd.append('file', file);
    try {
      const result = await api('/api/agents/upload', { method: 'POST', body: fd });
      uploadedAgentIds.push(result.id);
      uploaded++;
    } catch (err) {
      if (statusEl) statusEl.textContent = `Error uploading "${file.name}": ${err.message}`;
      return;
    }
  }

  if (statusEl) statusEl.textContent = uploaded > 1 ? `${uploaded} books uploaded — indexing...` : `"${fileList[0].name}" uploaded — indexing...`;

  await loadAgents();
  ensurePolling();

  // Auto-select uploaded books as chips
  for (const agentId of uploadedAgentIds) {
    const book = allBooks.find(b => b.agentId === agentId);
    if (book) selectedBooks.set(book.id, book);
  }
  renderSelectedChips();

  setTimeout(() => { if (statusEl) statusEl.textContent = ''; }, 5000);
}

// ─── Upvote ───
async function handleUpvote(title) {
  try {
    await api('/api/votes', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({title}) });
    await loadVotes(); buildBookList();
  } catch {
    const b = allBooks.find(x => x.title === title);
    if (b) b.upvotes = (b.upvotes||0) + 1;
  }
  if (getRoute().page === 'library') renderLibraryGrid();
}
window.handleUpvote = handleUpvote;

// ─── Popover & book selection ───
function togglePopover(popId, listId, emptyId) {
  popId = popId || 'chat-popover';
  listId = listId || 'popover-book-list';
  emptyId = emptyId || 'popover-no-books';
  const pop = document.getElementById(popId);
  const show = pop.classList.contains('hidden');
  // Close all popovers first
  document.querySelectorAll('.composer-popover').forEach(p => p.classList.add('hidden'));
  if (show) {
    pop.classList.remove('hidden');
    renderPopoverBookList(listId, emptyId);
  }
}

function closeAllPopovers() {
  document.querySelectorAll('.composer-popover').forEach(p => p.classList.add('hidden'));
}
// Expose globally so onclick attributes work
window.togglePopover = togglePopover;
window.closeAllPopovers = closeAllPopovers;

function renderPopoverBookList(listId, emptyId) {
  listId = listId || 'popover-book-list';
  emptyId = emptyId || 'popover-no-books';
  const list = document.getElementById(listId);
  const empty = document.getElementById(emptyId);
  if (!allBooks.length) { list.innerHTML = ''; empty.classList.remove('hidden'); return; }
  empty.classList.add('hidden');
  list.innerHTML = allBooks.map(b => {
    const sel = selectedBooks.has(b.id);
    const tag = b.available ? ' (indexed)' : b.status === 'catalog' ? ' (catalog)' : '';
    return `<div class="popover-book-item ${sel?'selected':''}" data-bid="${b.id}">
      <div class="popover-book-check">${sel?'&#10003;':''}</div>
      <span>${esc(b.title)}${tag}</span>
    </div>`;
  }).join('');
  list.querySelectorAll('.popover-book-item').forEach(el => {
    el.addEventListener('click', () => {
      const id = el.dataset.bid;
      if (selectedBooks.has(id)) {
        selectedBooks.delete(id);
      } else {
        const book = allBooks.find(x => x.id === id);
        if (book) selectedBooks.set(id, book);
      }
      renderPopoverBookList(listId, emptyId);
      renderSelectedChips();
    });
  });
}

// Renders chips in BOTH home and chat composers + updates placeholder
function renderSelectedChips() {
  ['home-selected-chips', 'chat-selected-chips'].forEach(cId => {
    const c = document.getElementById(cId);
    if (!c) return;
    if (!selectedBooks.size) { c.innerHTML = ''; return; }
    c.innerHTML = [...selectedBooks.entries()].map(([id, b]) =>
      `<div class="book-chip"><span>${esc(b.title)}</span><button class="chip-remove" data-bid="${id}">&times;</button></div>`
    ).join('');
    c.querySelectorAll('.chip-remove').forEach(btn => {
      btn.addEventListener('click', () => {
        selectedBooks.delete(btn.dataset.bid);
        renderSelectedChips();
        document.querySelectorAll('.composer-popover').forEach(pop => {
          if (!pop.classList.contains('hidden')) {
            const list = pop.querySelector('.popover-book-list');
            const empty = pop.querySelector('.popover-empty');
            if (list && empty) renderPopoverBookList(list.id, empty.id);
          }
        });
      });
    });
  });
  // Update placeholder based on selected books
  const homeInput = document.getElementById('home-input');
  if (homeInput) {
    homeInput.placeholder = selectedBooks.size > 0 ? 'Ask your question...' : 'Ask and learn across one or more books...';
  }
}

// Select a book and navigate to chat
function selectBookForChat(bookId) {
  const book = allBooks.find(b => b.id === bookId);
  if (!book) return;
  saveCurrentSession();
  currentSessionId = null;
  selectedBooks.clear();
  selectedBooks.set(bookId, book);
  window.location.hash = '#/';
}
window.selectBookForChat = selectBookForChat;

// ─── Textarea auto-resize ───
function autoResize(textarea) {
  textarea.addEventListener('input', () => {
    textarea.style.height = 'auto';
    textarea.style.height = Math.min(textarea.scrollHeight, 200) + 'px';
  });
}

function bindEnterSend(textarea, handler) {
  textarea.addEventListener('keydown', e => {
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handler(); }
  });
}

// ─── Utility ───
function esc(s) { if (!s) return ''; const d = document.createElement('div'); d.textContent = s; return d.innerHTML; }

function showToast(msg) {
  const t = document.createElement('div');
  t.className = 'token-toast';
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(() => { t.classList.add('fade-out'); setTimeout(() => t.remove(), 400); }, 2000);
}

function renderMarkdown(text) {
  if (!text) return '';
  // Protect code blocks first
  const codeBlocks = [];
  let s = text.replace(/```(\w*)\n([\s\S]*?)```/g, (_, lang, code) => {
    codeBlocks.push('<pre><code>' + esc(code) + '</code></pre>');
    return '\x00CB' + (codeBlocks.length - 1) + '\x00';
  });
  // Protect inline code
  const inlineCodes = [];
  s = s.replace(/`([^`]+)`/g, (_, code) => {
    inlineCodes.push('<code>' + esc(code) + '</code>');
    return '\x00IC' + (inlineCodes.length - 1) + '\x00';
  });
  // Process line by line
  const lines = s.split('\n');
  const out = [];
  let inList = false;
  for (let line of lines) {
    let trimmed = line.trim();
    // Headers
    if (trimmed.startsWith('### ')) { if (inList) { out.push('</ul>'); inList = false; } out.push('<h4>' + inline(trimmed.slice(4)) + '</h4>'); continue; }
    if (trimmed.startsWith('## ')) { if (inList) { out.push('</ul>'); inList = false; } out.push('<h3>' + inline(trimmed.slice(3)) + '</h3>'); continue; }
    if (trimmed.startsWith('# ')) { if (inList) { out.push('</ul>'); inList = false; } out.push('<h2>' + inline(trimmed.slice(2)) + '</h2>'); continue; }
    // Unordered list
    const ulMatch = trimmed.match(/^[-*]\s+(.+)$/);
    if (ulMatch) { if (!inList) { out.push('<ul>'); inList = true; } out.push('<li>' + inline(ulMatch[1]) + '</li>'); continue; }
    // Ordered list
    const olMatch = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (olMatch) { if (!inList) { out.push('<ul>'); inList = true; } out.push('<li>' + inline(olMatch[1]) + '</li>'); continue; }
    // Close list if needed
    if (inList) { out.push('</ul>'); inList = false; }
    // Code block placeholder
    if (trimmed.startsWith('\x00CB')) { out.push(trimmed); continue; }
    // Empty line = paragraph break
    if (!trimmed) { out.push('<br>'); continue; }
    // Normal text
    out.push('<p>' + inline(trimmed) + '</p>');
  }
  if (inList) out.push('</ul>');
  let html = out.join('\n');
  // Restore code blocks and inline code
  html = html.replace(/\x00CB(\d+)\x00/g, (_, i) => codeBlocks[+i]);
  html = html.replace(/\x00IC(\d+)\x00/g, (_, i) => inlineCodes[+i]);
  return html;

  function inline(t) {
    t = esc(t);
    t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    t = t.replace(/\*(.+?)\*/g, '<em>$1</em>');
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    t = t.replace(/\x00IC(\d+)\x00/g, (_, i) => inlineCodes[+i]);
    return t;
  }
}

// ─── Init ───
async function init() {
  await Promise.all([loadAgents(), loadVotes(), loadTopics()]);
  buildBookList();
  restoreSessions();

  document.getElementById('app-layout').classList.add('sidebar-collapsed');

  // Sidebar toggle
  document.getElementById('sidebar-toggle-btn').addEventListener('click', toggleSidebar);
  document.getElementById('sidebar-float-btn').addEventListener('click', toggleSidebar);

  // Chats page
  document.getElementById('chats-search').addEventListener('input', e => {
    _renderChatsList(e.target.value.trim().toLowerCase());
  });
  document.getElementById('chats-new-btn').addEventListener('click', () => {
    saveCurrentSession();
    currentSessionId = null;
    selectedBooks.clear();
    window.location.hash = '#/';
  });

  // New Chat → go to homepage
  document.getElementById('new-chat-btn').addEventListener('click', () => {
    saveCurrentSession();
    currentSessionId = null;
    selectedBooks.clear();
    window.location.hash = '#/';
  });

  // Home composer
  const homeInput = document.getElementById('home-input');
  autoResize(homeInput);
  bindEnterSend(homeInput, handleHomeSend);
  document.getElementById('home-send-btn').addEventListener('click', handleHomeSend);

  // Home + button → popover (upload or select from library)
  const uploadBtn = document.getElementById('upload-btn');
  const uploadInput = document.getElementById('upload-file-input');
  uploadBtn.addEventListener('click', e => { e.stopPropagation(); togglePopover('home-popover', 'home-popover-book-list', 'home-popover-no-books'); });
  document.getElementById('home-popover-upload').addEventListener('click', () => { closeAllPopovers(); uploadInput.click(); });
  uploadInput.addEventListener('change', () => { if (uploadInput.files.length) { handleFileUpload(uploadInput.files, 'home-upload-status'); uploadInput.value = ''; } });
  document.getElementById('home-upload-link').addEventListener('click', e => { e.preventDefault(); togglePopover('home-popover', 'home-popover-book-list', 'home-popover-no-books'); });

  // Chat page composer
  const chatInput = document.getElementById('chat-input');
  autoResize(chatInput);
  bindEnterSend(chatInput, handleChatSend);
  document.getElementById('chat-send-btn').addEventListener('click', handleChatSend);

  // Chat + button → popover
  const chatPlusBtn = document.getElementById('chat-plus-btn');
  const chatUploadInput = document.getElementById('chat-upload-file-input');
  chatPlusBtn.addEventListener('click', e => { e.stopPropagation(); togglePopover('chat-popover', 'popover-book-list', 'popover-no-books'); });
  document.getElementById('popover-upload-action').addEventListener('click', () => { closeAllPopovers(); chatUploadInput.click(); });
  chatUploadInput.addEventListener('change', () => { if (chatUploadInput.files.length) { handleFileUpload(chatUploadInput.files, null); chatUploadInput.value = ''; } });
  document.addEventListener('click', e => {
    document.querySelectorAll('.composer-popover').forEach(pop => {
      if (!pop.classList.contains('hidden') && !pop.contains(e.target) && !e.target.closest('.composer-icon-btn')) {
        pop.classList.add('hidden');
      }
    });
  });

  // Book chat
  const bookInput = document.getElementById('book-chat-input');
  autoResize(bookInput);
  bindEnterSend(bookInput, () => {
    const msg = bookInput.value.trim();
    if (msg && currentBookId) { bookInput.value = ''; sendBookChat(currentBookId, msg); }
  });
  document.getElementById('book-send-btn').addEventListener('click', () => {
    const msg = bookInput.value.trim();
    if (msg && currentBookId) { bookInput.value = ''; sendBookChat(currentBookId, msg); }
  });

  // Library controls
  let searchTimer = null;
  document.getElementById('library-search').addEventListener('input', e => {
    librarySearch = e.target.value.trim();
    _searchDiscoveredIds.clear();
    _searchUsage = null;
    renderLibraryGrid();
    clearTimeout(searchTimer);
    if (librarySearch.length >= 2) {
      // Check if local results are empty
      const q = librarySearch.toLowerCase();
      const hasLocal = allBooks.some(b => b.title.toLowerCase().includes(q) || b.author.toLowerCase().includes(q));
      if (!hasLocal) {
        searchTimer = setTimeout(() => autoSearchBook(librarySearch), 600);
      }
    }
  });
  document.querySelectorAll('.filter-tag').forEach(btn => {
    btn.addEventListener('click', () => {
      document.querySelectorAll('.filter-tag').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      libraryFilter = btn.dataset.filter;
      renderLibraryGrid();
    });
  });

  navigate();
  ensurePolling();
}

init();
