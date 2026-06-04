/* ── Enterprise RAG – SPA ─────────────────────────────────── */

const App = {
  token:    localStorage.getItem('rag_token'),
  username: localStorage.getItem('rag_username'),
  role:     localStorage.getItem('rag_role'),
  view:     'chat',
  messages: [],
  backendUrl: '',
  settings: {
    alpha:        parseFloat(localStorage.getItem('rag_alpha') ?? '0.5'),
    topK:         parseInt(localStorage.getItem('rag_topk')  ?? '5', 10),
    useExpansion: localStorage.getItem('rag_expansion') !== 'false',
  },

  /* ── Boot ──────────────────────────────────────────────── */
  async init() {
    try {
      const cfg = await fetch('/api/config').then(r => r.json());
      this.backendUrl = cfg.backend_url;
    } catch {
      this.backendUrl = 'http://localhost:8000/api/v1';
    }
    this.token ? this.renderApp() : this.renderLogin();
    if (this.token) this.loadHistory();
  },

  /* ── Auth ──────────────────────────────────────────────── */
  decodeToken(token) {
    try {
      const b64 = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/');
      return JSON.parse(atob(b64));
    } catch { return {}; }
  },
  async login(username, password) {
    const res = await fetch(`${this.backendUrl}/token`, {
      method: 'POST',
      body: new URLSearchParams({ username, password }),
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Login failed');
    this.setAuth((await res.json()).access_token, username);
  },
  async register(username, password) {
    const res = await fetch(`${this.backendUrl}/register`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
    });
    if (!res.ok) throw new Error((await res.json()).detail || 'Registration failed');
    this.setAuth((await res.json()).access_token, username);
  },
  setAuth(token, username) {
    this.token    = token;
    this.username = username;
    this.role     = this.decodeToken(token).role || 'viewer';
    this.messages = [];
    localStorage.setItem('rag_token',    token);
    localStorage.setItem('rag_username', username);
    localStorage.setItem('rag_role',     this.role);
    this.renderApp();
    this.loadHistory();
  },
  logout() {
    ['rag_token','rag_username','rag_role'].forEach(k => localStorage.removeItem(k));
    this.token = this.username = this.role = null;
    this.messages = [];
    this.renderLogin();
  },

  /* ── HTTP helper ───────────────────────────────────────── */
  async api(path, method = 'GET', body = null) {
    const headers = { Authorization: `Bearer ${this.token}` };
    if (body && !(body instanceof FormData))
      headers['Content-Type'] = 'application/json';
    return fetch(`${this.backendUrl}${path}`, {
      method,
      headers,
      body: body instanceof FormData ? body : (body ? JSON.stringify(body) : null),
    });
  },

  /* ── History ───────────────────────────────────────────── */
  async loadHistory() {
    try {
      const res = await this.api(`/history/${this.username}`);
      if (!res.ok) return;
      this.messages = (await res.json()).map(m => ({ role: m.role, content: m.content }));
      this.renderChatMessages();
    } catch { /* history is optional */ }
  },

  /* ── Login view ────────────────────────────────────────── */
  renderLogin() {
    document.getElementById('app').innerHTML = `
      <div class="login-page">
        <div class="login-card">
          <div class="login-header">
            <div class="logo">⚡</div>
            <h1>Enterprise RAG</h1>
            <p>AI-powered document intelligence</p>
          </div>
          <div class="tabs">
            <button class="tab active" onclick="App.switchTab('login')">Sign In</button>
            <button class="tab"        onclick="App.switchTab('register')">Register</button>
          </div>
          <form id="login-form" class="auth-form" onsubmit="App.handleLogin(event)">
            <div class="form-group">
              <label>Username</label>
              <input type="text" id="login-u" placeholder="Enter username" required autocomplete="username">
            </div>
            <div class="form-group">
              <label>Password</label>
              <input type="password" id="login-p" placeholder="Enter password" required autocomplete="current-password">
            </div>
            <div id="login-err" class="error-msg hidden"></div>
            <button type="submit" class="btn btn-primary btn-full">Sign In</button>
          </form>
          <form id="register-form" class="auth-form hidden" onsubmit="App.handleRegister(event)">
            <div class="form-group">
              <label>Username</label>
              <input type="text" id="reg-u" placeholder="Choose a username" required autocomplete="username">
            </div>
            <div class="form-group">
              <label>Password</label>
              <input type="password" id="reg-p" placeholder="Choose a password" required autocomplete="new-password">
            </div>
            <div id="reg-err" class="error-msg hidden"></div>
            <button type="submit" class="btn btn-primary btn-full">Create Account</button>
          </form>
        </div>
      </div>`;
  },
  switchTab(tab) {
    document.querySelectorAll('.tab').forEach((t, i) =>
      t.classList.toggle('active', (tab === 'login') === (i === 0)));
    document.getElementById('login-form').classList.toggle('hidden', tab !== 'login');
    document.getElementById('register-form').classList.toggle('hidden', tab !== 'register');
  },
  async handleLogin(e) {
    e.preventDefault();
    const err = document.getElementById('login-err');
    err.classList.add('hidden');
    try { await this.login(document.getElementById('login-u').value, document.getElementById('login-p').value); }
    catch (ex) { err.textContent = ex.message; err.classList.remove('hidden'); }
  },
  async handleRegister(e) {
    e.preventDefault();
    const err = document.getElementById('reg-err');
    err.classList.add('hidden');
    try { await this.register(document.getElementById('reg-u').value, document.getElementById('reg-p').value); }
    catch (ex) { err.textContent = ex.message; err.classList.remove('hidden'); }
  },

  /* ── App shell ─────────────────────────────────────────── */
  renderApp() {
    const isAdmin = this.role === 'admin';
    document.getElementById('app').innerHTML = `
      <div class="app-layout">
        <nav class="sidebar">
          <div class="sidebar-header">
            <span class="logo-icon">⚡</span>
            <span class="logo-text">Enterprise RAG</span>
          </div>
          <div class="user-info">
            <div class="user-avatar">${(this.username?.[0] || 'U').toUpperCase()}</div>
            <div>
              <div class="user-name">${this.esc(this.username)}</div>
              <span class="badge badge-${isAdmin ? 'blue' : 'gray'} user-role">${this.role}</span>
            </div>
          </div>
          <div class="nav-items">
            <button class="nav-item ${this.view==='chat'?'active':''}" onclick="App.setView('chat')">
              ${icon('chat')} Chat
            </button>
            ${isAdmin ? `
            <button class="nav-item ${this.view==='kb'?'active':''}" onclick="App.setView('kb')">
              ${icon('kb')} Knowledge Base
            </button>
            <button class="nav-item ${this.view==='analytics'?'active':''}" onclick="App.setView('analytics')">
              ${icon('analytics')} Analytics
            </button>` : ''}
          </div>
          <div class="sidebar-settings">
            <div class="settings-label">Search Settings</div>
            <div class="setting-item">
              <label>Alpha <span id="alpha-val">${this.settings.alpha.toFixed(1)}</span></label>
              <input type="range" min="0" max="1" step="0.1" value="${this.settings.alpha}"
                oninput="App.setSetting('alpha', parseFloat(this.value)); document.getElementById('alpha-val').textContent=parseFloat(this.value).toFixed(1)">
              <span class="setting-hint">0 = keyword  ·  1 = semantic</span>
            </div>
            <div class="setting-item">
              <label>Top K <span id="topk-val">${this.settings.topK}</span></label>
              <input type="range" min="1" max="10" step="1" value="${this.settings.topK}"
                oninput="App.setSetting('topK', parseInt(this.value)); document.getElementById('topk-val').textContent=this.value">
            </div>
            <div class="setting-item toggle-item">
              <label>Query Expansion</label>
              <label class="toggle">
                <input type="checkbox" ${this.settings.useExpansion?'checked':''}
                  onchange="App.setSetting('useExpansion', this.checked)">
                <span class="toggle-track"></span>
              </label>
            </div>
          </div>
          <button class="btn btn-ghost logout-btn" onclick="App.logout()">
            ${icon('logout')} Sign Out
          </button>
        </nav>
        <main class="main-content" id="main"></main>
      </div>`;
    this.renderView();
  },
  setView(v) { this.view = v; this.renderApp(); },
  renderView() {
    const el = document.getElementById('main');
    if (!el) return;
    if (this.view === 'chat')      this.renderChat(el);
    else if (this.view === 'kb')   this.renderKB(el);
    else if (this.view === 'analytics') this.renderAnalytics(el);
  },

  /* ── Chat view ─────────────────────────────────────────── */
  renderChat(el) {
    el.innerHTML = `
      <div class="chat-container">
        <div class="chat-header">
          <h2>Knowledge Assistant</h2>
          <p>Ask questions about your uploaded documents</p>
        </div>
        <div class="messages" id="msgs"></div>
        <div class="chat-input-area">
          <form class="chat-form" onsubmit="App.handleQuery(event)">
            <input type="text" id="q-input" placeholder="Ask a question about your documents…" autocomplete="off">
            <button type="submit" class="btn btn-primary" id="send-btn">${icon('send')}</button>
          </form>
        </div>
      </div>`;
    this.renderChatMessages();
    document.getElementById('q-input')?.focus();
  },
  renderChatMessages() {
    const el = document.getElementById('msgs');
    if (!el) return;
    if (!this.messages.length) {
      el.innerHTML = `<div class="empty-state"><div class="empty-icon">💬</div><p>No messages yet. Ask a question to get started.</p></div>`;
      return;
    }
    el.innerHTML = this.messages.map(m => this.msgHTML(m)).join('');
    el.scrollTop = el.scrollHeight;
  },
  msgHTML(m) {
    const isUser = m.role === 'user';
    const body = isUser
      ? `<p>${this.esc(m.content)}</p>`
      : (typeof marked !== 'undefined' ? marked.parse(m.content || '') : this.esc(m.content));
    return `
      <div class="message message-${m.role}">
        <div class="message-avatar">${isUser ? (this.username?.[0]||'U').toUpperCase() : '⚡'}</div>
        <div class="message-body">
          <div class="message-content">${body}</div>
          ${m.confidence !== undefined ? this.confidenceBadge(m.confidence) : ''}
          ${m.warning ? `<div class="warning-msg">⚠️ ${this.esc(m.warning)}</div>` : ''}
          ${m.sources  ? this.sourcesHTML(m.sources) : ''}
        </div>
      </div>`;
  },

  /* ── Confidence badge ──────────────────────────────────── */
  confidenceBadge(score) {
    const tier   = score >= 75 ? 'success' : score >= 45 ? 'warning' : 'danger';
    const label  = score >= 75 ? 'High'    : score >= 45 ? 'Medium'  : 'Low';
    const filled = Math.round(score / 20);
    const bars   = Array.from({length:5}, (_,i) =>
      `<span class="conf-bar ${i<filled?'filled '+tier:''}"></span>`).join('');
    return `<div class="confidence-row">
      <div class="confidence-bars">${bars}</div>
      <span class="badge badge-${tier}">Confidence: ${score}% · ${label}</span>
    </div>`;
  },

  /* ── Source citations ──────────────────────────────────── */
  sourcesHTML(sources) {
    if (!sources?.length) return '';
    const sigmoid = x => Math.round(100 / (1 + Math.exp(-x)));
    const cards = sources.map((s, i) => {
      const name = s.metadata?.filename || s.metadata?.source || s.id || `Document ${i+1}`;
      const page = s.metadata?.page  ? ` · Page ${s.metadata.page}` : '';
      const chunk= s.metadata?.chunk_index != null ? ` · Chunk ${s.metadata.chunk_index}` : '';
      const rel  = sigmoid(s.rerank_score ?? 0);
      const snip = (s.content || '').slice(0, 240);
      return `
        <div class="source-card">
          <div class="source-header">
            ${icon('file')}
            <span class="source-name">${this.esc(name)}${page}${chunk}</span>
            <span class="source-relevance">${rel}% match</span>
          </div>
          <p class="source-snippet">${this.esc(snip)}${snip.length>=240?'…':''}</p>
        </div>`;
    }).join('');
    return `
      <div class="sources-section">
        <button class="sources-toggle" onclick="this.classList.toggle('open');this.nextElementSibling.classList.toggle('hidden')">
          ${icon('chevron')} ${sources.length} source${sources.length>1?'s':''} cited
        </button>
        <div class="sources-list hidden">${cards}</div>
      </div>`;
  },

  /* ── Send a query ──────────────────────────────────────── */
  async handleQuery(e) {
    e.preventDefault();
    const input = document.getElementById('q-input');
    const query = input.value.trim();
    if (!query) return;
    input.value = '';
    const btn = document.getElementById('send-btn');
    btn.disabled = true;

    const msgsEl = document.getElementById('msgs');
    const emptyEl = msgsEl?.querySelector('.empty-state');
    if (emptyEl) emptyEl.remove();

    const userMsg = { role: 'user', content: query };
    this.messages.push(userMsg);
    msgsEl?.insertAdjacentHTML('beforeend', this.msgHTML(userMsg));

    const tid = `t${Date.now()}`;
    msgsEl?.insertAdjacentHTML('beforeend', `
      <div class="message message-assistant" id="${tid}">
        <div class="message-avatar">⚡</div>
        <div class="message-body">
          <div class="message-content">
            <div class="typing-indicator"><span></span><span></span><span></span></div>
          </div>
        </div>
      </div>`);
    if (msgsEl) msgsEl.scrollTop = msgsEl.scrollHeight;

    try {
      const res  = await this.api('/rag/query', 'POST', {
        query, top_k: this.settings.topK,
        alpha: this.settings.alpha, use_query_expansion: this.settings.useExpansion,
      });
      const data = await res.json();
      document.getElementById(tid)?.remove();

      const aMsg = res.ok
        ? { role:'assistant', content: data.answer, confidence: data.confidence, sources: data.sources, warning: data.warning }
        : { role:'assistant', content: `Error ${res.status}: ${data.detail || res.statusText}` };
      this.messages.push(aMsg);
      msgsEl?.insertAdjacentHTML('beforeend', this.msgHTML(aMsg));
    } catch (err) {
      document.getElementById(tid)?.remove();
      const aMsg = { role:'assistant', content: `Connection error: ${err.message}` };
      this.messages.push(aMsg);
      msgsEl?.insertAdjacentHTML('beforeend', this.msgHTML(aMsg));
    }
    btn.disabled = false;
    if (msgsEl) msgsEl.scrollTop = msgsEl.scrollHeight;
    input.focus();
  },

  /* ── Knowledge Base ────────────────────────────────────── */
  renderKB(el) {
    el.innerHTML = `
      <div class="kb-container">
        <div class="page-header"><h2>Knowledge Base</h2><p>Upload and manage documents in your vector store</p></div>
        <div class="card upload-card">
          <h3>Upload Document</h3>
          <div class="upload-area" onclick="document.getElementById('file-inp').click()"
               ondragover="event.preventDefault();this.classList.add('drag-over')"
               ondragleave="this.classList.remove('drag-over')"
               ondrop="App.handleDrop(event)">
            ${icon('upload', 36)}
            <p>Drop file here or click to browse</p>
            <span class="upload-hint">PDF · TXT · DOCX · up to 50 MB</span>
          </div>
          <input type="file" id="file-inp" accept=".pdf,.txt,.docx" class="hidden" onchange="App.handleFileSelect(event)">
          <div id="upload-status" style="margin-top:.75rem"></div>
        </div>
        <div class="card">
          <div class="card-header">
            <h3>Stored Documents</h3>
            <button class="btn btn-ghost btn-sm" onclick="App.loadFiles()">${icon('refresh')} Refresh</button>
          </div>
          <div id="files-list"><div class="loading">Loading…</div></div>
          <div id="kb-actions" class="kb-actions hidden">
            <select id="file-sel" class="select" style="flex:1"></select>
            <button class="btn btn-danger btn-sm" onclick="App.deleteFile()">Delete</button>
            <button class="btn btn-ghost btn-sm" onclick="App.rebuildIndex(this)">Rebuild Index</button>
          </div>
        </div>
      </div>`;
    this.loadFiles();
  },
  async handleFileSelect(e) { if (e.target.files[0]) await this.uploadFile(e.target.files[0]); },
  async handleDrop(e) {
    e.preventDefault();
    document.querySelector('.upload-area')?.classList.remove('drag-over');
    if (e.dataTransfer.files[0]) await this.uploadFile(e.dataTransfer.files[0]);
  },
  async uploadFile(file) {
    const status = document.getElementById('upload-status');
    status.innerHTML = '<div class="loading">Uploading and ingesting…</div>';
    const form = new FormData(); form.append('file', file);
    try {
      const res  = await this.api('/ingest/upload', 'POST', form);
      const data = await res.json();
      status.innerHTML = res.ok
        ? `<div class="success-msg">✓ ${data.message}</div>`
        : `<div class="error-msg">✗ ${data.detail || 'Upload failed'}</div>`;
      if (res.ok) this.loadFiles();
    } catch (err) { status.innerHTML = `<div class="error-msg">✗ ${err.message}</div>`; }
  },
  async loadFiles() {
    const list    = document.getElementById('files-list');
    const actions = document.getElementById('kb-actions');
    if (!list) return;
    try {
      const files = await this.api('/ingest/files').then(r => r.json());
      if (!files.length) {
        list.innerHTML = '<p class="muted">No documents uploaded yet.</p>';
        actions?.classList.add('hidden'); return;
      }
      list.innerHTML = `
        <table class="data-table">
          <thead><tr><th>Filename</th><th>Size</th><th>Chunks</th><th>Uploaded</th></tr></thead>
          <tbody>${files.map(f=>`
            <tr>
              <td><span class="file-icon">📄</span>${this.esc(f.filename)}</td>
              <td>${f.size_kb ? f.size_kb+' KB' : '—'}</td>
              <td>${f.chunk_count ?? '—'}</td>
              <td>${f.uploaded_at ? new Date(f.uploaded_at).toLocaleDateString() : '—'}</td>
            </tr>`).join('')}
          </tbody>
        </table>`;
      const sel = document.getElementById('file-sel');
      if (sel) sel.innerHTML = files.map(f=>`<option value="${this.esc(f.filename)}">${this.esc(f.filename)}</option>`).join('');
      actions?.classList.remove('hidden');
    } catch { list.innerHTML = '<div class="error-msg">Failed to load documents.</div>'; }
  },
  async deleteFile() {
    const sel = document.getElementById('file-sel');
    if (!sel?.value) return;
    const res = await this.api(`/ingest/files/${encodeURIComponent(sel.value)}`, 'DELETE');
    if (res.ok) this.loadFiles();
  },
  async rebuildIndex(btn) {
    btn.disabled = true; btn.textContent = 'Rebuilding…';
    await this.api('/ingest/rebuild', 'POST');
    btn.textContent = 'Rebuild Index'; btn.disabled = false;
  },

  /* ── Analytics ─────────────────────────────────────────── */
  async renderAnalytics(el) {
    el.innerHTML = `
      <div class="analytics-container">
        <div class="page-header"><h2>Analytics Dashboard</h2><p>Query metrics and usage statistics</p></div>
        <div id="analytics-body"><div class="loading">Loading analytics…</div></div>
      </div>`;
    try {
      const res = await this.api('/admin/analytics');
      if (!res.ok) { document.getElementById('analytics-body').innerHTML = '<div class="error-msg">Failed to load analytics.</div>'; return; }
      this.renderAnalyticsContent(await res.json());
    } catch (err) { document.getElementById('analytics-body').innerHTML = `<div class="error-msg">${err.message}</div>`; }
  },
  renderAnalyticsContent(d) {
    document.getElementById('analytics-body').innerHTML = `
      <div class="stats-grid">
        <div class="stat-card"><div class="stat-value">${d.queries_today}</div><div class="stat-label">Queries Today</div></div>
        <div class="stat-card"><div class="stat-value">${d.total_queries.toLocaleString()}</div><div class="stat-label">Total Queries</div></div>
        <div class="stat-card"><div class="stat-value">${(d.avg_response_ms/1000).toFixed(1)}s</div><div class="stat-label">Avg Response Time</div></div>
        <div class="stat-card"><div class="stat-value text-danger">${d.failed_queries}</div><div class="stat-label">Failed Queries</div></div>
      </div>
      <div class="card">
        <h3>Top Questions</h3>
        ${d.top_questions.length ? '<canvas id="chart" height="180"></canvas>' : '<p class="muted">No queries recorded yet.</p>'}
      </div>
      <div class="card">
        <h3>Recent Queries</h3>
        ${d.recent_logs.length ? `
          <table class="data-table">
            <thead><tr><th>User</th><th>Query</th><th>Time (ms)</th><th>Status</th></tr></thead>
            <tbody>${d.recent_logs.map(r=>`
              <tr>
                <td>${this.esc(r.user)}</td>
                <td class="query-cell">${this.esc(r.query)}</td>
                <td>${r.response_time_ms}</td>
                <td><span class="status-badge ${r.success?'status-ok':'status-fail'}">${r.success?'✓':'✗'}</span></td>
              </tr>`).join('')}
            </tbody>
          </table>` : '<p class="muted">No queries recorded yet.</p>'}
      </div>`;
    if (d.top_questions.length && typeof Chart !== 'undefined') {
      new Chart(document.getElementById('chart').getContext('2d'), {
        type: 'bar',
        data: {
          labels: d.top_questions.map(q => q.query.slice(0,45)+(q.query.length>45?'…':'')),
          datasets: [{ label:'Times Asked', data: d.top_questions.map(q=>q.count),
            backgroundColor:'rgba(59,130,246,.7)', borderColor:'rgb(59,130,246)',
            borderWidth:1, borderRadius:4 }],
        },
        options: {
          indexAxis:'y', responsive:true,
          plugins:{ legend:{ display:false } },
          scales:{
            x:{ ticks:{color:'#71717a'}, grid:{color:'#27272a'} },
            y:{ ticks:{color:'#71717a'}, grid:{color:'#27272a'} },
          },
        },
      });
    }
  },

  /* ── Settings ──────────────────────────────────────────── */
  setSetting(k, v) {
    this.settings[k] = v;
    localStorage.setItem('rag_' + k.toLowerCase(), String(v));
  },

  /* ── Utils ─────────────────────────────────────────────── */
  esc(s) {
    return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
  },
};

/* ── SVG icon helper ──────────────────────────────────────── */
function icon(name, size = 16) {
  const s = size, paths = {
    chat:     '<path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>',
    kb:       '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/>',
    analytics:'<line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>',
    logout:   '<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><polyline points="16,17 21,12 16,7"/><line x1="21" y1="12" x2="9" y2="12"/>',
    send:     '<line x1="22" y1="2" x2="11" y2="13"/><polygon points="22,2 15,22 11,13 2,9"/>',
    file:     '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14,2 14,8 20,8"/>',
    chevron:  '<polyline points="9,18 15,12 9,6"/>',
    upload:   '<path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="17,8 12,3 7,8"/><line x1="12" y1="3" x2="12" y2="15"/>',
    refresh:  '<polyline points="1,4 1,10 7,10"/><path d="M3.51 15a9 9 0 1 0 .49-3.51"/>',
  };
  return `<svg width="${s}" height="${s}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${paths[name]||''}</svg>`;
}

App.init();
