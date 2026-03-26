/* ── Perplex Frontend Application ──────────────────────────────────────────── */

const API = {
  upload: (formData) => fetch('/api/contracts/upload', { method: 'POST', body: formData }),
  list: () => fetch('/api/contracts/'),
  get: (id) => fetch(`/api/contracts/${id}`),
  status: (id) => fetch(`/api/contracts/${id}/status`),
  delete: (id) => fetch(`/api/contracts/${id}`, { method: 'DELETE' }),
  ask: (id, question, history) => fetch(`/api/query/${id}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question, chat_history: history }),
  }),
};

// ── State ────────────────────────────────────────────────────────────────────
let state = {
  contracts: {},
  activeId: null,
  chatHistory: [],
  pollingTimers: {},
};

// ── DOM refs ─────────────────────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const uploadZone     = $('#uploadZone');
const fileInput      = $('#fileInput');
const contractList   = $('#contractList');
const welcomeScreen  = $('#welcomeScreen');
const contractView   = $('#contractView');
const uploadOverlay  = $('#uploadOverlay');
const progressBar    = $('#progressBar');
const progressTitle  = $('#progressTitle');
const progressSub    = $('#progressSub');
const progressStep   = $('#progressStep');

// ── Init ─────────────────────────────────────────────────────────────────────
async function init() {
  setupUpload();
  setupTabs();
  setupQA();
  await loadContracts();
}

// ── Upload ───────────────────────────────────────────────────────────────────
function setupUpload() {
  uploadZone.addEventListener('click', () => fileInput.click());
  fileInput.addEventListener('change', (e) => {
    if (e.target.files[0]) handleFileUpload(e.target.files[0]);
  });

  uploadZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadZone.classList.add('drag-over');
  });
  uploadZone.addEventListener('dragleave', () => uploadZone.classList.remove('drag-over'));
  uploadZone.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file && file.type === 'application/pdf') handleFileUpload(file);
    else alert('Please drop a PDF file.');
  });
}

async function handleFileUpload(file) {
  showProgressOverlay('Uploading…', file.name, 10);

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await API.upload(formData);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || 'Upload failed');
    }
    const data = await res.json();
    updateProgress('Indexing embeddings…', 30);
    await loadContracts();
    startPolling(data.doc_id);
  } catch (err) {
    hideProgressOverlay();
    alert(`Upload failed: ${err.message}`);
  }
}

function showProgressOverlay(title, sub, pct) {
  progressTitle.textContent = title;
  progressSub.textContent = sub;
  progressBar.style.width = pct + '%';
  progressStep.textContent = '';
  uploadOverlay.style.display = 'flex';
}

function updateProgress(step, pct) {
  progressStep.textContent = step;
  progressBar.style.width = pct + '%';
}

function hideProgressOverlay() {
  uploadOverlay.style.display = 'none';
  progressBar.style.width = '0%';
}

// ── Polling ──────────────────────────────────────────────────────────────────
const STATUS_STEPS = {
  indexing: { label: 'Indexing embeddings…', pct: 30 },
  extracting_clauses: { label: 'Extracting clauses…', pct: 55 },
  scoring_risk: { label: 'Scoring risk…', pct: 75 },
  summarizing: { label: 'Generating summary…', pct: 90 },
  ready: { label: 'Complete!', pct: 100 },
  error: { label: 'Error', pct: 0 },
};

function startPolling(docId) {
  if (state.pollingTimers[docId]) return;
  state.pollingTimers[docId] = setInterval(async () => {
    try {
      const res = await API.status(docId);
      const data = await res.json();
      const step = STATUS_STEPS[data.status] || {};

      if (data.status !== 'ready' && data.status !== 'error') {
        updateProgress(step.label || data.status, step.pct || 50);
      }

      if (data.status === 'ready') {
        clearInterval(state.pollingTimers[docId]);
        delete state.pollingTimers[docId];
        updateProgress('Complete!', 100);
        await loadContracts();
        setTimeout(() => {
          hideProgressOverlay();
          selectContract(docId);
        }, 600);
      } else if (data.status === 'error') {
        clearInterval(state.pollingTimers[docId]);
        delete state.pollingTimers[docId];
        hideProgressOverlay();
        await loadContracts();
        alert(`Analysis failed: ${data.error || 'Unknown error'}`);
      }

      // Update sidebar item
      renderSidebar();
    } catch (e) {
      console.error('Polling error:', e);
    }
  }, 2500);
}

// ── Contracts List ────────────────────────────────────────────────────────────
async function loadContracts() {
  try {
    const res = await API.list();
    const data = await res.json();
    data.contracts.forEach((c) => { state.contracts[c.doc_id] = c; });
    renderSidebar();
  } catch (e) {
    console.error('Load contracts error:', e);
  }
}

function renderSidebar() {
  const contracts = Object.values(state.contracts);
  if (!contracts.length) {
    contractList.innerHTML = '<p class="empty-state">No contracts yet</p>';
    return;
  }

  contractList.innerHTML = contracts.map((c) => {
    const isActive = c.doc_id === state.activeId;
    const riskLevel = c.risk?.risk_level || '';
    const riskBadge = riskLevel
      ? `<span class="contract-item-risk risk-${riskLevel}">${riskLevel.toUpperCase()}</span>`
      : '';
    const statusText = c.status === 'ready'
      ? `${c.page_count || '?'} pages · ${(c.clauses || []).length} clauses`
      : c.status || 'processing…';

    return `
      <div class="contract-item ${isActive ? 'active' : ''}" data-id="${c.doc_id}">
        <span class="contract-item-icon">📄</span>
        <div class="contract-item-info">
          <div class="contract-item-name">${escHtml(c.filename)}</div>
          <div class="contract-item-status">${statusText}</div>
        </div>
        ${riskBadge}
      </div>`;
  }).join('');

  // Attach click handlers
  contractList.querySelectorAll('.contract-item').forEach((el) => {
    el.addEventListener('click', () => selectContract(el.dataset.id));
  });
}

async function selectContract(docId) {
  state.activeId = docId;
  state.chatHistory = [];
  renderSidebar();
  welcomeScreen.style.display = 'none';
  contractView.style.display = 'flex';
  contractView.style.flexDirection = 'column';
  contractView.style.height = '100%';

  // Load full record
  try {
    const res = await API.get(docId);
    const contract = await res.json();
    state.contracts[docId] = contract;
    renderContractView(contract);
  } catch (e) {
    console.error('Select contract error:', e);
  }
}

// ── Render Contract ───────────────────────────────────────────────────────────
function renderContractView(contract) {
  // Header
  $('#contractName').textContent = contract.filename || '—';
  $('#contractMeta').textContent =
    `${contract.page_count || '?'} pages · ${contract.chunk_count || '?'} chunks · ${formatDate(contract.created_at)}`;

  const badge = $('#statusBadge');
  badge.textContent = contract.status || '—';
  badge.className = 'status-badge ' + (contract.status === 'ready' ? 'ready' : contract.status === 'error' ? 'error' : '');

  // Stats
  const risk = contract.risk || {};
  $('#statPages').textContent = contract.page_count || '—';
  $('#statChunks').textContent = contract.chunk_count || '—';
  $('#statClauses').textContent = (contract.clauses || []).length || '—';
  const riskEl = $('#statRisk');
  riskEl.textContent = risk.risk_level ? risk.risk_level.charAt(0).toUpperCase() + risk.risk_level.slice(1) : '—';
  riskEl.className = 'stat-value risk-value ' + (risk.risk_level || '');

  // Summary
  const summaryEl = $('#summaryText');
  if (contract.summary) {
    summaryEl.textContent = contract.summary;
  } else if (contract.status !== 'ready') {
    summaryEl.innerHTML = '<div class="skeleton-lines"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton short"></div></div>';
  } else {
    summaryEl.textContent = 'Summary not available.';
  }

  // Clauses
  renderClauses(contract.clauses || []);

  // Risk
  renderRisk(contract.risk || null);

  // Q&A reset
  resetQA();

  // Delete button
  $('#deleteBtn').onclick = () => deleteContract(contract.doc_id);

  // Resume polling if needed
  if (contract.status !== 'ready' && contract.status !== 'error') {
    startPolling(contract.doc_id);
  }
}

// ── Clauses ───────────────────────────────────────────────────────────────────
function renderClauses(clauses) {
  const container = $('#clausesList');
  const filterBar = $('#clauseFilter');

  if (!clauses.length) {
    filterBar.innerHTML = '';
    container.innerHTML = '<p class="empty-state">No clauses extracted yet.</p>';
    return;
  }

  // Build filter chips from unique clause types
  const types = [...new Set(clauses.map((c) => c.clause_type))];
  filterBar.innerHTML = `
    <button class="filter-chip active" data-type="all">All (${clauses.length})</button>
    ${types.map((t) => {
      const clause = clauses.find((c) => c.clause_type === t);
      const count = clauses.filter((c) => c.clause_type === t).length;
      return `<button class="filter-chip" data-type="${t}">${clause?.icon || ''} ${clause?.label || t} (${count})</button>`;
    }).join('')}`;

  filterBar.querySelectorAll('.filter-chip').forEach((chip) => {
    chip.addEventListener('click', () => {
      filterBar.querySelectorAll('.filter-chip').forEach((c) => c.classList.remove('active'));
      chip.classList.add('active');
      const type = chip.dataset.type;
      const filtered = type === 'all' ? clauses : clauses.filter((c) => c.clause_type === type);
      renderClauseCards(filtered, container);
    });
  });

  renderClauseCards(clauses, container);
}

function renderClauseCards(clauses, container) {
  container.innerHTML = clauses.map((c) => `
    <div class="clause-card" style="border-left-color: ${c.color || '#6b7280'}">
      <div class="clause-header">
        <span class="clause-icon">${c.icon || '📄'}</span>
        <span class="clause-type-badge" style="background:${hexToRgba(c.color, 0.15)};color:${c.color}">${c.label || c.clause_type}</span>
        <span class="clause-title">${escHtml(c.title || '')}</span>
        ${c.page_ref ? `<span class="clause-page">p.${c.page_ref}</span>` : ''}
      </div>
      ${c.text ? `<div class="clause-text">${escHtml(c.text)}</div>` : ''}
      ${c.notes ? `<p class="clause-notes">${escHtml(c.notes)}</p>` : ''}
      ${c.risk_indicators?.length ? `
        <div class="clause-risks">
          ${c.risk_indicators.map((r) => `<span class="risk-tag">${escHtml(r)}</span>`).join('')}
        </div>` : ''}
    </div>`).join('');
}

// ── Risk ──────────────────────────────────────────────────────────────────────
function renderRisk(risk) {
  const container = $('#riskOverview');
  if (!risk) {
    container.innerHTML = '<p class="empty-state">Risk analysis not yet available.</p>';
    return;
  }

  const score = risk.overall_score || 0;
  const riskColor = getRiskColor(risk.risk_level);
  const circumference = 2 * Math.PI * 48;
  const dashOffset = circumference * (1 - score / 100);

  const categoryRows = Object.entries(risk.category_scores || {})
    .map(([key, val]) => {
      const s = val.score || val || 0;
      const color = s >= 70 ? 'var(--risk-high)' : s >= 40 ? 'var(--risk-medium)' : 'var(--risk-low)';
      return `
        <div class="risk-category-row">
          <span class="risk-cat-label">${val.label || key}</span>
          <div class="risk-bar-wrap">
            <div class="risk-bar-fill" style="width:${s}%;background:${color}"></div>
          </div>
          <span class="risk-cat-score">${s}</span>
        </div>`;
    }).join('');

  const flags = (risk.risk_flags || []).map((f) => `
    <div class="risk-flag ${f.severity}">
      <div class="flag-header">
        <span class="flag-severity ${f.severity}">${f.severity?.toUpperCase()}</span>
        <span class="flag-title">${escHtml(f.title || '')}</span>
      </div>
      <p class="flag-desc">${escHtml(f.description || '')}</p>
      ${f.clause_excerpt ? `<div class="flag-excerpt">"${escHtml(f.clause_excerpt)}"</div>` : ''}
    </div>`).join('');

  const missing = (risk.missing_provisions || [])
    .map((m) => `<div class="missing-item">${escHtml(m)}</div>`).join('');

  const recs = (risk.recommendations || [])
    .map((r, i) => `<div class="rec-item"><span class="rec-num">${i + 1}</span><span>${escHtml(r)}</span></div>`).join('');

  container.innerHTML = `
    <div class="risk-score-hero">
      <div class="risk-gauge">
        <svg viewBox="0 0 120 120" width="120" height="120">
          <circle cx="60" cy="60" r="48" fill="none" stroke="var(--bg-elevated)" stroke-width="10"/>
          <circle cx="60" cy="60" r="48" fill="none" stroke="${riskColor}" stroke-width="10"
            stroke-dasharray="${circumference}" stroke-dashoffset="${dashOffset}"
            stroke-linecap="round"/>
        </svg>
        <div class="risk-gauge-text">
          <div class="risk-gauge-score">${score}</div>
          <div class="risk-gauge-label">/ 100</div>
        </div>
      </div>
      <div class="risk-hero-info">
        <div class="risk-level-badge" style="background:${hexToRgba(riskColor, 0.15)};color:${riskColor}">
          ${(risk.risk_level || 'unknown').toUpperCase()} RISK
        </div>
        <p class="risk-summary-text">${escHtml(risk.executive_summary || '')}</p>
      </div>
    </div>

    <div class="risk-categories">
      <h3 class="card-title">Risk by Category</h3>
      ${categoryRows}
    </div>

    ${flags ? `
    <div>
      <h3 class="section-header">Risk Flags</h3>
      <div class="risk-flags">${flags}</div>
    </div>` : ''}

    ${missing ? `
    <div class="risk-categories">
      <h3 class="card-title">Missing Provisions</h3>
      <div class="missing-list">${missing}</div>
    </div>` : ''}

    ${recs ? `
    <div class="recommendations">
      <h3 class="card-title">Recommendations</h3>
      <div class="rec-list">${recs}</div>
    </div>` : ''}
  `;
}

// ── Q&A ───────────────────────────────────────────────────────────────────────
function setupQA() {
  const input = $('#qaInput');
  const sendBtn = $('#qaSend');

  sendBtn.addEventListener('click', sendQuestion);
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendQuestion();
    }
  });
  input.addEventListener('input', () => {
    input.style.height = 'auto';
    input.style.height = Math.min(input.scrollHeight, 120) + 'px';
  });

  // Suggestion buttons (delegated)
  document.addEventListener('click', (e) => {
    if (e.target.classList.contains('suggestion-btn')) {
      const q = e.target.dataset.q;
      $('#qaInput').value = q;
      sendQuestion();
    }
  });
}

function resetQA() {
  state.chatHistory = [];
  $('#qaMessages').innerHTML = `
    <div class="qa-welcome">
      <p>Ask anything about this contract in plain English.</p>
      <div class="qa-suggestions" id="qaSuggestions">
        <button class="suggestion-btn" data-q="What are the termination conditions?">What are the termination conditions?</button>
        <button class="suggestion-btn" data-q="What is the payment schedule?">What is the payment schedule?</button>
        <button class="suggestion-btn" data-q="Who owns the intellectual property?">Who owns the intellectual property?</button>
        <button class="suggestion-btn" data-q="What happens in case of a dispute?">What happens in case of a dispute?</button>
      </div>
    </div>`;
}

async function sendQuestion() {
  const input = $('#qaInput');
  const question = input.value.trim();
  if (!question || !state.activeId) return;

  const contract = state.contracts[state.activeId];
  if (contract?.status !== 'ready') {
    alert('Contract is still being analyzed. Please wait.');
    return;
  }

  // Add user bubble
  appendBubble('user', question);
  input.value = '';
  input.style.height = 'auto';

  // Typing indicator
  const typingId = 'typing-' + Date.now();
  const messagesEl = $('#qaMessages');
  const typingEl = document.createElement('div');
  typingEl.id = typingId;
  typingEl.className = 'qa-bubble assistant';
  typingEl.innerHTML = '<div class="typing-indicator"><div class="typing-dot"></div><div class="typing-dot"></div><div class="typing-dot"></div></div>';
  messagesEl.appendChild(typingEl);
  scrollMessages();

  try {
    const res = await API.ask(state.activeId, question, state.chatHistory);
    const data = await res.json();

    // Remove typing indicator
    document.getElementById(typingId)?.remove();

    if (data.error) {
      appendBubble('assistant', `Error: ${data.error}`);
      return;
    }

    // Append answer
    appendBubble('assistant', data.answer, data.sources);

    // Update chat history
    state.chatHistory.push({ role: 'user', content: question });
    state.chatHistory.push({ role: 'assistant', content: data.answer });

    // Keep history bounded
    if (state.chatHistory.length > 12) state.chatHistory = state.chatHistory.slice(-12);

  } catch (e) {
    document.getElementById(typingId)?.remove();
    appendBubble('assistant', 'Request failed. Please try again.');
  }
}

function appendBubble(role, text, sources = []) {
  const messagesEl = $('#qaMessages');
  // Remove welcome if present
  const welcome = messagesEl.querySelector('.qa-welcome');
  if (welcome) welcome.remove();

  const el = document.createElement('div');
  el.className = `qa-bubble ${role}`;

  const sourceTags = sources?.length
    ? `<div class="bubble-sources">${sources.slice(0, 4).map((s) =>
        `<span class="source-tag">p.${s.page_num || '?'} · ${Math.round(s.score * 100)}%</span>`
      ).join('')}</div>`
    : '';

  el.innerHTML = `
    <div class="bubble-label">${role === 'user' ? 'YOU' : 'PERPLEX'}</div>
    <div class="bubble-content">${escHtml(text)}</div>
    ${sourceTags}`;
  messagesEl.appendChild(el);
  scrollMessages();
}

function scrollMessages() {
  const el = $('#qaMessages');
  el.scrollTop = el.scrollHeight;
}

// ── Tabs ──────────────────────────────────────────────────────────────────────
function setupTabs() {
  document.querySelectorAll('.tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach((t) => t.classList.remove('active'));
      document.querySelectorAll('.tab-panel').forEach((p) => p.classList.remove('active'));
      tab.classList.add('active');
      const panel = document.getElementById('panel-' + tab.dataset.tab);
      if (panel) panel.classList.add('active');
    });
  });
}

// ── Delete ────────────────────────────────────────────────────────────────────
async function deleteContract(docId) {
  if (!confirm('Delete this contract and all its analysis data?')) return;
  try {
    await API.delete(docId);
    delete state.contracts[docId];
    if (state.activeId === docId) {
      state.activeId = null;
      contractView.style.display = 'none';
      welcomeScreen.style.display = 'flex';
    }
    renderSidebar();
  } catch (e) {
    alert('Delete failed.');
  }
}

// ── Utilities ─────────────────────────────────────────────────────────────────
function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function formatDate(iso) {
  if (!iso) return '';
  try {
    return new Date(iso).toLocaleDateString('en-US', {
      month: 'short', day: 'numeric', year: 'numeric'
    });
  } catch { return ''; }
}

function hexToRgba(hex, alpha) {
  if (!hex || !hex.startsWith('#')) return `rgba(100,100,100,${alpha})`;
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
}

function getRiskColor(level) {
  return {
    low: '#34d399',
    medium: '#fbbf24',
    high: '#f87171',
    critical: '#ef4444',
  }[level] || '#6b7280';
}

// ── Boot ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', init);
