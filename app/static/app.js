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
  if (hash === '#/library') return { page: 'library' };
  const m = hash.match(/^#\/book\/(.+)$/);
  if (m) return { page: 'book', id: m[1] };
  return { page: 'home' };
}

function navigate() {
  const route = getRoute();
  const chatsOverlay = document.getElementById('chats-overlay');
  if (chatsOverlay) chatsOverlay.classList.add('hidden');
  document.querySelectorAll('.page-view').forEach(el => el.classList.add('hidden'));
  const el = document.getElementById('page-' + route.page);
  if (el) el.classList.remove('hidden');

  switch (route.page) {
    case 'home':
      renderHome();
      renderSelectedChips(); // show chips on home too
      break;
    case 'chat': onChatPageShow(); break;
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
  el.textContent = text;
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
  // Web sources (grounding citations)
  if (opts?.webSources?.length) {
    const ws = document.createElement('div');
    ws.className = 'web-sources';
    if (opts.grounded) {
      const badge = document.createElement('span');
      badge.className = 'web-search-badge';
      badge.innerHTML = '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/></svg> Searched the web';
      ws.appendChild(badge);
    }
    opts.webSources.forEach(src => {
      const a = document.createElement('a');
      a.className = 'web-source-link';
      a.href = src.url;
      a.target = '_blank';
      a.rel = 'noopener noreferrer';
      a.textContent = src.title || src.url;
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
function createSession() {
  saveCurrentSession();
  const id = 's-' + (++sessionCounter);
  const session = { id, title: 'New chat', messages: [], books: new Map() };
  chatSessions.unshift(session);
  currentSessionId = id;
  document.getElementById('chat-messages').innerHTML = '';
  hideChatRightSidebar();
  renderChatHistory();
  return session;
}

function saveCurrentSession() {
  if (!currentSessionId) return;
  const session = chatSessions.find(s => s.id === currentSessionId);
  if (!session) return;
  const msgs = [];
  document.querySelectorAll('#chat-messages .chat-message').forEach(el => {
    const role = el.classList.contains('user') ? 'user' : 'assistant';
    msgs.push({ role, content: el.textContent });
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
  session.messages.forEach(m => appendMsg(chatBox, m.role, m.content));
  renderSelectedChips();
  hideChatRightSidebar();
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

// ─── Chats overlay panel ───
function toggleChatsPanel() {
  const overlay = document.getElementById('chats-overlay');
  if (overlay.classList.contains('hidden')) {
    overlay.classList.remove('hidden');
    document.getElementById('chats-search').value = '';
    renderChatsPanel('');
    document.getElementById('chats-search').focus();
  } else {
    closeChatsPanel();
  }
}

function closeChatsPanel() {
  document.getElementById('chats-overlay').classList.add('hidden');
}

function renderChatsPanel(query) {
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
      closeChatsPanel();
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
    appendMsg(chatBox, 'assistant', data.answer, sources, msgOpts);
    renderChatSidebar(sources, message);
    showChatRightSidebar();
    // Trigger polling if any catalog books are being learned
    ensurePolling();
  } catch (err) {
    removeLoading();
    const msg = err.message.includes('No available provider')
      ? 'No LLM API key configured. Please add GEMINI_API_KEY, OPENAI_API_KEY, or KIMI_API_KEY to your .env file and restart the server.'
      : 'Error: ' + err.message;
    appendMsg(chatBox, 'assistant', msg);
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
  const q = (query || '').toLowerCase();
  const related = allBooks
    .filter(b => !selectedBooks.has(b.id) && (b.title.toLowerCase().includes(q) || (b.category || '').toLowerCase().includes(q) || (b.description || '').toLowerCase().includes(q)))
    .slice(0, 4);
  relEl.innerHTML = related.length ? related.map(b => sidebarBookItem(b.agentId || b.id, b.title, b.author, b.isbn)).join('') : '';
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
function renderLibrary() { renderLibraryGrid(); }

function renderLibraryGrid() {
  const c = document.getElementById('library-grid');
  let filtered = [...allBooks];
  if (libraryFilter === 'available') filtered = filtered.filter(b => b.available);
  else if (libraryFilter === 'popular') filtered.sort((a,b) => (b.upvotes||0) - (a.upvotes||0));
  if (librarySearch) {
    const q = librarySearch.toLowerCase();
    filtered = filtered.filter(b => b.title.toLowerCase().includes(q) || b.author.toLowerCase().includes(q) || (b.category||'').toLowerCase().includes(q));
  }
  renderBookGrid(c, filtered);
}

function renderBookGrid(container, books) {
  if (!books.length) { container.innerHTML = '<div class="empty-state"><p>No books found.</p></div>'; return; }
  container.innerHTML = books.map(b => {
    const cover = b.isbn ? `<img class="card-cover" src="https://covers.openlibrary.org/b/isbn/${b.isbn}-M.jpg" alt="${esc(b.title)}" loading="lazy" onerror="this.outerHTML='<div class=\\'card-cover-placeholder\\'>&#128218;</div>'" />` : '<div class="card-cover-placeholder">&#128218;</div>';
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

// ─── Init ───
async function init() {
  await Promise.all([loadAgents(), loadVotes()]);
  buildBookList();

  document.getElementById('app-layout').classList.add('sidebar-collapsed');

  // Sidebar toggle
  document.getElementById('sidebar-toggle-btn').addEventListener('click', toggleSidebar);
  document.getElementById('sidebar-float-btn').addEventListener('click', toggleSidebar);

  // Chats → show chats overlay panel
  document.getElementById('sidebar-chats-btn').addEventListener('click', () => {
    toggleChatsPanel();
  });
  document.getElementById('chats-overlay').addEventListener('click', e => {
    if (e.target === document.getElementById('chats-overlay')) closeChatsPanel();
  });
  document.getElementById('chats-search').addEventListener('input', e => {
    renderChatsPanel(e.target.value.trim().toLowerCase());
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
  document.getElementById('library-search').addEventListener('input', e => { librarySearch = e.target.value; renderLibraryGrid(); });
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
