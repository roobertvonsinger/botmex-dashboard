// Botmexico v2 — vanilla, sin frameworks.

const FRASES = [
  "¿Ya desayunaste o puro café y ansiedad?",
  "Échale ganas, mi rey — la chamba no se hace sola.",
  "Hoy es buen día pa' tirar pa'rriba 🇲🇽",
  "Si no puedes con el enemigo, hackéalo.",
  "El que madruga, encuentra cuentas LIVE.",
  "Calladito te ves más bonito… y vendes más.",
  "No es magia, es disciplina. Bueno, y un poquito de magia.",
  "Trabaja en silencio, deja que tu saldo haga el ruido.",
  "Hoy se chambea con todo, mañana descansamos (mentira).",
  "El éxito sabe a tacos al pastor.",
];

const esc = s => s == null ? '' : String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');

const state = {
  section: 'accounts',
  status: 'LIVE',
  grade: '',
  view: 'simple',
  rows: [],
  user: null,
  page: 1,
  pageSize: 50,
  lockHours: 2,
  filterInUse: false,
};


const selectedIds = new Set();
let searchQuery = '';
let activityRows = [];
let activityFilter = { kind: '', who: null };
let notifications = [];
let _evtSrc = null;
let _sortCol = null, _sortDir = -1;

function sortRows(col) {
  if (_sortCol === col) _sortDir = -_sortDir;
  else { _sortCol = col; _sortDir = -1; }
  const numeric = ['balance_total', 'balance_real', 'last_deposit_amount', 'check_count'];
  state.rows.sort((a, b) => {
    const av = numeric.includes(col) ? (a[col] || 0) : (parseTs(a[col] || '').getTime() || 0);
    const bv = numeric.includes(col) ? (b[col] || 0) : (parseTs(b[col] || '').getTime() || 0);
    return (av - bv) * _sortDir;
  });
  state.page = 1;
  renderTable();
}

const $ = sel => document.querySelector(sel);
const $$ = sel => document.querySelectorAll(sel);

const fmtMoney = v => `$${(v || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;

// Cuenta regresiva hacia un timestamp ISO. Devuelve {text, expired, urgent}.
const fmtUntil = ts => {
  if (!ts || ts === 'N/A') return null;
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return null;
  const diff = (d.getTime() - Date.now()) / 1000;
  if (diff <= 0) return { text: 'venció', expired: true, urgent: true };
  if (diff < 60) return { text: `${Math.floor(diff)}s`, expired: false, urgent: true };
  if (diff < 3600) return { text: `${Math.floor(diff/60)}m`, expired: false, urgent: diff < 600 };
  if (diff < 86400) {
    const h = Math.floor(diff/3600), m = Math.floor((diff%3600)/60);
    return { text: m ? `${h}h ${m}m` : `${h}h`, expired: false, urgent: false };
  }
  return { text: `${Math.floor(diff/86400)}d`, expired: false, urgent: false };
};

const parseTs = ts => {
  if (!ts || ts === 'N/A') return new Date(NaN);
  const mx = ts.match(/^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (mx) { const [, dd, mm, yyyy, h, mi, ss] = mx; return new Date(+yyyy, +mm - 1, +dd, +h, +mi, +(ss || 0)); }
  const iso = ts.match(/^(\d{4})-(\d{2})-(\d{2})[\sT](\d{2}):(\d{2}):(\d{2})/);
  if (iso) { const [, yyyy, mm, dd, h, mi, ss] = iso; return new Date(+yyyy, +mm - 1, +dd, +h, +mi, +ss); }
  return new Date(ts);
};
const fmtAgo = ts => {
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return '—';
  const diff = (Date.now() - d.getTime()) / 1000;
  if (diff < 0) return '—';
  if (diff < 60) return `${Math.floor(diff)}s`;
  if (diff < 3600) return `${Math.floor(diff/60)}m`;
  if (diff < 86400) return `${Math.floor(diff/3600)}h`;
  return `${Math.floor(diff/86400)}d`;
};
// Fecha + hora absoluta (para bitácora persistente — saber qué hiciste antier)
const fmtAbs = ts => {
  const d = parseTs(ts);
  if (isNaN(d.getTime())) return '';
  const sameDay = d.toDateString() === new Date().toDateString();
  const opts = sameDay
    ? { hour: '2-digit', minute: '2-digit', hour12: false }
    : { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit', hour12: false };
  return d.toLocaleString('es-MX', opts).replace('.', '');
};
const gradeClass = g => ({ A: 'A', B: 'B', C: 'C' })[g] || 'U';
// Glow tiers para el saldo:
//   ≥ $10  → glow (verde brillante)
//   $5-$10 → tenue/grisecito
//   ≤ $5   → default (verde normal)
//   $0     → zero (gris)
const balanceCls = v => {
  if (!v || v <= 0) return 'zero';
  if (v >= 10) return 'glow';
  if (v > 5) return 'dim-amount';
  return '';
};
const getVisible = () => state.filterInUse
  ? state.rows.filter(r => r.locked_by)
  : state.rows;

function getPaged() {
  const v = getVisible();
  const totalPages = Math.max(1, Math.ceil(v.length / state.pageSize));
  if (state.page > totalPages) state.page = totalPages;
  const start = (state.page - 1) * state.pageSize;
  return { rows: v.slice(start, start + state.pageSize), total: v.length, totalPages };
}

// ─── toast ───
let _toastTimer = null;
function toast(msg, kind = '') {
  const el = $('#toast');
  el.className = `toast ${kind}`;
  el.textContent = msg;
  if (_toastTimer) clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.add('hidden'), 2500);
}

// ─── greeting + frase ───
function tickGreeting() {
  const now = new Date();
  $('#sbDate').textContent = now.toLocaleDateString('es-MX', { weekday: 'short', day: '2-digit', month: 'short' }).replace('.', '');
  $('#sbTime').textContent = now.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false });
}
let fraseIdx = Math.floor(Math.random() * FRASES.length);
function tickFrase() {
  $('#fraseTxt').textContent = `"${FRASES[fraseIdx]}"`;
  $('#fraseTxt').style.animation = 'none';
  void $('#fraseTxt').offsetWidth;
  $('#fraseTxt').style.animation = 'fraseFade 600ms ease-out';
  fraseIdx = (fraseIdx + 1) % FRASES.length;
}

// ─── auth/me bootstrap ───
async function loadMe() {
  const r = await fetch('/api/auth/me').catch(() => null);
  if (!r || r.status === 401) { window.location.href = '/login'; return; }
  const me = await r.json();
  state.user = me;
  $('#sbGreetName').textContent = me.username || '—';
  $('#sbUserName').textContent = me.username || '—';
  $('#sbUserRole').textContent = me.role || '—';
  $('#sbUserAv').textContent = (me.username || '··').slice(0, 2).toUpperCase();
  // Roles
  const isSuper = me.role === 'superadmin';
  const isAdmin = me.role === 'admin' || isSuper;
  const isUser  = !isAdmin;

  // L invertida (control multiusuario) SOLO superadmin — admin no debe ver indicios de SA
  if (!isSuper) {
    $('#adminPanel').style.display = 'none';
    document.body.classList.add('no-kpis');
  }
  // Vista Detallada solo superadmin (admin/user usan Simple)
  if (!isSuper) {
    const viewSeg = document.querySelector('.seg[data-seg="view"]');
    if (viewSeg) viewSeg.style.display = 'none';
    state.view = 'simple';
  }
  // Logs y Health solo superadmin
  if (!isSuper) {
    $('#navLogs').style.display = 'none';
    $('#navHealth').style.display = 'none';
  }
  // Liberar (asignar a otros) solo superadmin — el "admin" NO debe verlo (vista secreta)
  if (!isSuper) {
    $('#cmdRelease').closest('.cmd-release-wrap').style.display = 'none';
  }
  // Trastienda solo SA (es feature de dosificación tuya)
  if (!isSuper) {
    $('#cmdTrastienda').style.display = 'none';
  }
  // Page sizes según rol
  const sizes = isSuper ? [100, 200, 500] : [20, 30, 50];
  const sel = $('#pageSize');
  sel.innerHTML = sizes.map(n => `<option value="${n}">${n}</option>`).join('');
  state.pageSize = sizes[0];
  sel.value = String(state.pageSize);
}

// ─── data fetchers ───
async function fetchAccounts() {
  const url = new URL('/api/accounts', location.origin);
  url.searchParams.set('status', state.status);
  if (state.grade) url.searchParams.set('grade', state.grade);
  if (searchQuery) url.searchParams.set('q', searchQuery);
  url.searchParams.set('limit', '500');
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
async function fetchStats() {
  const r = await fetch('/api/stats');
  if (!r.ok) return null;
  return r.json();
}
async function fetchCombos(ids) {
  const r = await fetch('/api/accounts/combos', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ ids }),
  });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

// ─── tabla ───
function renderTable() {
  const paged = getPaged();
  const visible = paged.rows;
  const t = $('#accTable');
  const _th = (col, label, cls = '') => {
    const on = _sortCol === col;
    const ic = on ? (_sortDir === 1 ? ' ↑' : ' ↓') : '';
    return `<th class="th-sort${on ? ' sort-on' : ''} ${cls}" data-sort="${col}">${label}${ic}</th>`;
  };
  const cols = state.view === 'simple'
    ? `<tr>
        <th class="grade-bar-th"></th>${_th('balance_total','Saldo','num')}<th>Cuenta</th>
        ${_th('last_deposit_date','Últ. depósito')}
        <th class="sel-cell"><input type="checkbox" id="selAll"></th>
      </tr>`
    : `<tr>
        <th class="grade-bar-th"></th>${_th('balance_total','Saldo','num')}<th>Cuenta</th>
        ${_th('last_deposit_date','Últ. depósito')}<th>Estado</th>
        ${_th('last_checked_at','Últ. check')}${_th('check_count','Checks','num')}
        <th class="sel-cell"><input type="checkbox" id="selAll"></th>
      </tr>`;
  t.querySelector('thead').innerHTML = cols;

  const colspan = state.view === 'simple' ? 5 : 8;
  const rowsHtml = visible.map(r => {
    const g = gradeClass(r.grade);
    const until = r.locked_by ? fmtUntil(r.locked_until) : null;
    const lockedCls = r.locked_by ? (until?.expired ? 'row-locked row-lock-expired' : 'row-locked') : '';
    const selCls = selectedIds.has(r.id) ? 'row-sel' : '';
    const checked = selectedIds.has(r.id) ? 'checked' : '';
    const dep = r.last_deposit_amount
      ? `<b>${fmtMoney(r.last_deposit_amount)}</b><span class="ago">${fmtAgo(r.last_deposit_date)}</span>`
      : '<span class="dim">sin dep.</span>';
    const combo = `${r.email}:${r.password || ''}`;
    const opCol = r.locked_color || 'accent';
    const opClass = r.locked_by ? `op-row-${opCol}` : '';
    const trasClass = r.published_to_pool === 0 ? 'row-trastienda' : '';
    const trClasses = `r-grade-${g} ${lockedCls} ${selCls} ${opClass} ${trasClass}`.trim();
    const lockChip = r.locked_by
      ? `<span class="lock-chip op-${esc(opCol)} ${until?.expired ? 'expired' : ''}" title="Lockeada por ${esc(r.locked_by)}${until ? ` · ${until.expired ? 'vencido' : `vence en ${until.text}`}` : ''}">🔒 ${esc(r.locked_by)}${until && !until.expired ? ` <span class="lock-chip-time dim">${until.text}</span>` : ''}</span>`
      : '';
    const isSA = state.user?.role === 'superadmin';
    const trTitle = isSA ? `Grade ${esc(r.grade) || '?'}` : '';
    if (state.view === 'simple') {
      return `<tr class="${trClasses}" data-id="${r.id}" title="${trTitle}">
        <td class="grade-bar-cell"></td>
        <td class="num"><span class="balance ${balanceCls(r.balance_total)}">${fmtMoney(r.balance_total)}</span></td>
        <td class="combo">${r.cards_count > 0 ? `<span class="card-ind" title="${r.cards_count} tarjeta${r.cards_count > 1 ? 's' : ''} guardada${r.cards_count > 1 ? 's' : ''}">💳<sup>${r.cards_count}</sup></span>` : ''}<b data-id="${r.id}" data-combo="${esc(combo)}">${esc(combo)}</b>${lockChip}</td>
        <td class="dep">${dep}</td>
        <td class="sel-cell"><input type="checkbox" class="rowsel" data-id="${r.id}" ${checked}></td>
      </tr>`;
    }
    return `<tr class="${trClasses}" data-id="${r.id}" title="${trTitle}">
      <td class="grade-bar-cell"></td>
      <td class="num"><span class="balance ${balanceCls(r.balance_total)}">${fmtMoney(r.balance_total)}</span></td>
      <td class="combo">${r.cards_count > 0 ? `<span class="card-ind" title="${r.cards_count} tarjeta${r.cards_count > 1 ? 's' : ''} guardada${r.cards_count > 1 ? 's' : ''}">💳<sup>${r.cards_count}</sup></span>` : ''}<b data-id="${r.id}" data-combo="${esc(combo)}">${esc(combo)}</b></td>
      <td class="dep">${dep}</td>
      <td>${r.status === 'LIVE' ? '<span style="color:var(--accent)">LIVE</span>' : '<span class="dim">DEAD</span>'}</td>
      <td class="dep dim">${fmtAgo(r.last_checked_at)}</td>
      <td class="num">${r.check_count || 0}</td>
      <td class="sel-cell"><input type="checkbox" class="rowsel" data-id="${r.id}" ${checked}></td>
    </tr>`;
  }).join('');

  t.querySelector('tbody').innerHTML = rowsHtml || `<tr><td colspan="${colspan}" class="loading">Sin cuentas</td></tr>`;

  // selectAll en sync con visible
  const allChecked = visible.length > 0 && visible.every(r => selectedIds.has(r.id));
  const selAll = $('#selAll');
  if (selAll) selAll.checked = allChecked;

  renderPagination(paged);
  updateCmdBar();
}

function renderPagination(paged) {
  $('#pbVisibleCount').textContent = `${paged.rows.length} de ${paged.total}`;
  const c = $('#pbPages');
  if (paged.totalPages <= 1) { c.innerHTML = ''; return; }
  const cur = state.page, last = paged.totalPages;
  const range = [];
  range.push(1);
  for (let i = cur - 1; i <= cur + 1; i++) if (i > 1 && i < last) range.push(i);
  if (last > 1) range.push(last);
  const uniq = [...new Set(range)].sort((a, b) => a - b);
  let html = `<button class="pg-btn" data-pg="prev" ${cur === 1 ? 'disabled' : ''}>‹</button>`;
  let prev = 0;
  for (const p of uniq) {
    if (p - prev > 1) html += `<span class="pg-gap">…</span>`;
    html += `<button class="pg-btn ${p === cur ? 'on' : ''}" data-pg="${p}">${p}</button>`;
    prev = p;
  }
  html += `<button class="pg-btn" data-pg="next" ${cur === last ? 'disabled' : ''}>›</button>`;
  c.innerHTML = html;
}

function renderStats(s) {
  if (!s) return;
  const visible = getVisible();
  $('#navCount').textContent = s.live;
  $('#countLabel').textContent = `${visible.length} / ${s.live.toLocaleString()}`;
  $('#stInUse').textContent = s.inUse;
}

// ─── command bar ───
function updateCmdBar() {
  const n = selectedIds.size;
  const bar = $('#cmdBar');
  $('#cmdSelCount').textContent = n;
  if (n === 0) { bar.classList.add('hidden'); return; }
  bar.classList.remove('hidden');

  // sumas
  const selRows = state.rows.filter(r => selectedIds.has(r.id));
  const totalBal = selRows.reduce((s, r) => s + (r.balance_total || 0), 0);
  $('#cmdStats').textContent = `Σ ${fmtMoney(totalBal)}`;

  // Depositar solo con 1 seleccionada
  $('#cmdDeposit').style.display = n === 1 ? '' : 'none';

  // Label dinámico de Trastienda según estado de la selección
  const tBtn = $('#cmdTrastienda');
  if (tBtn && tBtn.style.display !== 'none') {
    const selRowsArr = state.rows.filter(r => selectedIds.has(r.id));
    const allPub = selRowsArr.every(r => r.published_to_pool !== 0);
    tBtn.innerHTML = allPub ? '📤 Trastienda' : '📥 A pool';
    tBtn.title = allPub
      ? 'Ocultar de la pool (solo tú las verás)'
      : 'Publicar a la pool (todos las verán)';
  }
}

async function copySelectedCombos() {
  if (selectedIds.size === 0) { toast('Nada seleccionado', 'error'); return; }
  try {
    const data = await fetchCombos(Array.from(selectedIds));
    const txt = data.combos.map(c => `${c.email}:${c.password}`).join('\n');
    await navigator.clipboard.writeText(txt);
    toast(`✓ ${data.combos.length} combo${data.combos.length > 1 ? 's' : ''} copiado${data.combos.length > 1 ? 's' : ''}`, 'success');
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function bulkLock() {
  if (selectedIds.size === 0) return;
  const op = state.user?.username || 'op';
  let ok = 0, fail = 0;
  for (const id of selectedIds) {
    const r = await fetch(`/api/accounts/${id}/lock`, {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ operator: op, hours: state.lockHours }),
    });
    if (r.ok) ok++; else fail++;
  }
  toast(`🔒 Lock ${state.lockHours}h: ${ok} ok${fail ? `, ${fail} fallidos` : ''}`, fail ? 'error' : 'success');
  await reload();
}
async function bulkUnlock() {
  if (selectedIds.size === 0) return;
  let ok = 0, fail = 0;
  for (const id of selectedIds) {
    const r = await fetch(`/api/accounts/${id}/unlock`, { method: 'POST' });
    if (r.ok) ok++; else fail++;
  }
  toast(`🔓 Unlock: ${ok} ok${fail ? `, ${fail} fallidos` : ''}`, fail ? 'error' : 'success');
  await reload();
}

async function bulkTrastienda() {
  if (selectedIds.size === 0) return;
  const sel = state.rows.filter(r => selectedIds.has(r.id));
  // Decidir dirección: si todas están publicadas → a trastienda; si no → a pool.
  const allPublished = sel.every(r => r.published_to_pool !== 0);
  const publish = !allPublished;  // si todas públicas, las ocultamos; si no, las publicamos
  try {
    const r = await fetch('/api/accounts/publish', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ ids: Array.from(selectedIds), publish }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    toast(publish
      ? `📥 ${data.changed} a la pool (visibles)`
      : `📤 ${data.changed} a trastienda (ocultas)`,
      'success');
    await reload();
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

async function bulkPrewarm() {
  if (selectedIds.size === 0) return;
  const sel = state.rows.filter(r => selectedIds.has(r.id));
  const emails = sel.map(r => r.email);
  toast(`🔥 Prewarming ${emails.length}…`);
  try {
    const r = await fetch('/api/prewarm/select', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ account_emails: emails }),
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    if (data.status === 'capmonster_low') {
      toast(`⚠️ CapMonster bajo ($${data.capmonster_balance ?? '?'}) — prewarm cancelado`, 'error');
      pushNotif({ icon: '⚠️', msg: `Prewarm bloqueado: CapMonster bajo` });
      return;
    }
    const parts = [];
    if (data.started) parts.push(`${data.started} iniciados`);
    if (data.cached) parts.push(`${data.cached} cacheados`);
    if (data.skipped) parts.push(`${data.skipped} skip`);
    toast(`🔥 Prewarm: ${parts.join(' · ') || 'sin cambios'}`, 'success');
    pushNotif({ icon: '🔥', msg: `Prewarm: ${parts.join(' · ')} (cap ${data.cap_used}/${data.cap_max})` });
  } catch (e) {
    toast(`Prewarm error: ${e.message}`, 'error');
  }
}

function deselectAll() {
  selectedIds.clear();
  renderTable();
}

// ─── Actividad (event log en vivo) ───
async function fetchActivity() {
  const url = new URL('/api/activity', location.origin);
  url.searchParams.set('limit', '200');
  if (activityFilter.who != null) url.searchParams.set('operator_id', activityFilter.who);
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

function actionLabel(kind) {
  if (kind === 'deposit') return '💳 Depósito';
  if (kind === 'lock') return '🔒 Lock';
  if (kind === 'unlock') return '🔓 Unlock';
  if (kind === 'note') return '📝 Nota';
  if (kind?.startsWith('prewarm_complete')) return '🔥 Prewarm OK';
  if (kind?.startsWith('prewarm_error')) return '🔥 Prewarm err';
  if (kind?.startsWith('prewarm_timeout')) return '🔥 Prewarm timeout';
  if (kind?.startsWith('prewarm_')) return '🔥 ' + kind.replace('prewarm_', '');
  return kind;
}
function statusPill(e) {
  if (e.kind === 'deposit') {
    const c = e.status === 'approved' ? 'var(--accent)'
            : e.status === 'rejected' ? 'var(--danger)'
            : 'var(--text-muted)';
    return `<span style="color:${c}">${esc(e.status || '—')}</span>${e.reason ? `<span class="dim mono"> · ${esc(e.reason).slice(0, 40)}</span>` : ''}`;
  }
  if (e.kind === 'lock') return `<span class="dim">activo</span>`;
  if (e.kind === 'unlock') return `<span class="dim">liberado</span>`;
  if (e.kind === 'note') return `<span class="dim mono" title="${esc(e.text || '')}">${esc((e.text || '').slice(0, 60))}</span>`;
  return '';
}
function getFilteredActivity() {
  return activityRows.filter(e => {
    if (activityFilter.kind) {
      if (activityFilter.kind === 'prewarm') return (e.kind || '').startsWith('prewarm_');
      if (e.kind !== activityFilter.kind) return false;
    }
    if (activityFilter.who != null && e.who != activityFilter.who) return false;
    return true;
  });
}
function renderActivity() {
  const t = $('#actTable');
  t.querySelector('thead').innerHTML = `
    <tr>
      <th>Cuándo</th><th>Quién</th><th>Acción</th><th>Cuenta</th>
      <th class="num">Monto</th><th>Estado</th>
    </tr>`;
  const filtered = getFilteredActivity();
  $('#actCountLabel').textContent = `${filtered.length} eventos`;
  t.querySelector('tbody').innerHTML = filtered.map(e => `
    <tr class="act-${esc(e.kind)}">
      <td class="dim mono act-when" title="${esc(e.ts || '')}">
        <span class="act-abs">${fmtAbs(e.ts)}</span>
        <span class="act-rel dim">${fmtAgo(e.ts)}</span>
      </td>
      <td><span class="act-who" data-who="${esc(e.who ?? '')}">${esc(e.who ?? '—')}</span></td>
      <td>${actionLabel(e.kind)}</td>
      <td class="combo"><b class="act-target" data-email="${esc(e.target || '')}">${esc(e.target || '—')}</b></td>
      <td class="num">${e.amount != null ? fmtMoney(e.amount) : ''}</td>
      <td>${statusPill(e)}</td>
    </tr>`).join('') || '<tr><td colspan="6" class="loading">Sin actividad reciente</td></tr>';

  // Filtro info
  const parts = [];
  if (activityFilter.kind) parts.push(activityFilter.kind);
  if (activityFilter.who != null) parts.push(`op:${activityFilter.who}`);
  $('#actFilterInfo').textContent = parts.length ? `(filtrado: ${parts.join(' · ')})` : '';
  $('#actClearFilter').style.display = parts.length ? '' : 'none';
}
async function reloadActivity() {
  try {
    activityRows = await fetchActivity();
    renderActivity();
  } catch (e) {
    $('#actTable').querySelector('tbody').innerHTML =
      `<tr><td colspan="6" class="loading" style="color:var(--danger)">Error: ${esc(e.message)}</td></tr>`;
  }
}
function pushActivityEvent(ev) {
  // Insert at top, dedupe-ish, cap 500
  activityRows.unshift({
    kind: ev.kind, ts: ev.ts, who: ev.who, target: ev.target,
    amount: ev.amount, status: ev.status, reason: ev.reason,
    duration_ms: ev.duration_ms, id: ev.id, text: ev.text,
  });
  if (activityRows.length > 500) activityRows.length = 500;
  if (state.section === 'activity') renderActivity();
}

// ─── notifications ───
function pushNotif(n) {
  notifications.unshift({ ...n, ts: Date.now(), id: Date.now() + Math.random(), unread: true });
  if (notifications.length > 50) notifications.length = 50;
  renderNotifBadge();
  if (state.section === 'notifications') renderNotifs();
}
function renderNotifBadge() {
  const unread = notifications.filter(n => n.unread).length;
  const badge = $('#bellBadge');
  const navBadge = $('#navNotifBadge');
  if (unread > 0) {
    badge.textContent = unread;
    badge.classList.remove('hidden');
    navBadge.classList.remove('hidden');
  } else {
    badge.classList.add('hidden');
    navBadge.classList.add('hidden');
  }
}
function renderNotifs() {
  const list = $('#notifList');
  $('#notifCountLabel').textContent = `${notifications.length} eventos`;
  if (notifications.length === 0) {
    list.innerHTML = '<div class="loading">Sin notificaciones.</div>';
    return;
  }
  list.innerHTML = notifications.map(n => `
    <div class="notif-item ${n.unread ? 'new' : ''}">
      <span class="ni-icon">${n.icon || '🔔'}</span>
      <span class="ni-msg">${esc(n.msg)}</span>
      <span class="ni-time">${fmtAgo(new Date(n.ts).toISOString())}</span>
    </div>`).join('');
  // marcar como leídas
  notifications.forEach(n => n.unread = false);
  renderNotifBadge();
}

// ─── navigation ───
let _lastNonNotifSection = 'accounts';
function showSection(name) {
  if (state.section !== 'notifications' && name !== state.section) {
    _lastNonNotifSection = state.section;
  }
  state.section = name;
  $('#accountsMain').style.display = name === 'accounts' ? 'flex' : 'none';
  $('#activityMain').style.display = name === 'activity' ? 'flex' : 'none';
  $('#notificationsMain').style.display = name === 'notifications' ? 'flex' : 'none';
  const logsM = $('#logsMain'); if (logsM) logsM.style.display = name === 'logs' ? 'flex' : 'none';
  const healthM = $('#healthMain'); if (healthM) healthM.style.display = name === 'health' ? 'flex' : 'none';
  $$('.nav[data-section]').forEach(btn => btn.classList.toggle('on', btn.dataset.section === name));
  if (name === 'activity') reloadActivity();
  if (name === 'notifications') renderNotifs();
  if (name === 'logs') startLogsPolling(); else stopLogsPolling();
  if (name === 'health') loadHealth(false);
}

// ─── reload ───
async function reload() {
  try {
    const [rows, stats] = await Promise.all([fetchAccounts(), fetchStats()]);
    state.rows = rows;
    // limpia selección de cuentas que ya no están visibles
    const valid = new Set(rows.map(r => r.id));
    for (const id of selectedIds) if (!valid.has(id)) selectedIds.delete(id);
    renderTable();
    renderStats(stats);
  } catch (e) {
    $('#accTable').querySelector('tbody').innerHTML =
      `<tr><td colspan="9" class="loading" style="color:var(--danger)">Error: ${esc(e.message)}</td></tr>`;
  }
}

// ─── SSE ───
function connectSSE() {
  _evtSrc = new EventSource('/api/events');
  _evtSrc.onmessage = e => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.type === 'activity') {
        // Feed de Actividad
        pushActivityEvent(ev);
        // Notificaciones para acciones que importan
        if (ev.kind === 'lock') {
          pushNotif({ icon: '🔒', msg: `${ev.who} bloqueó ${ev.target}` });
          reload();
        } else if (ev.kind === 'unlock') {
          pushNotif({ icon: '🔓', msg: `${ev.who} liberó ${ev.target}` });
          reload();
        } else if (ev.kind === 'deposit') {
          const ok = ev.status === 'approved';
          pushNotif({
            icon: ok ? '✅' : '❌',
            msg: `${ev.who} depositó ${fmtMoney(ev.amount)} en ${ev.target} → ${ev.status}`,
          });
          if (ok) reload();
        } else if (ev.kind === 'note') {
          const myTg = state.user?.telegram_id;
          const isMine = ev.who_id && myTg && ev.who_id === myTg;
          const isSA = state.user?.role === 'superadmin';
          if (isMine || isSA) {
            pushNotif({ icon: '📝', msg: `${ev.who} anotó en ${ev.target}: ${(ev.text || '').slice(0, 60)}` });
          }
        } else if (ev.kind === 'prewarm_error' || ev.kind === 'prewarm_timeout') {
          pushNotif({ icon: '🔥', msg: `Prewarm ${ev.kind.replace('prewarm_','')} en ${ev.target}` });
        }
      } else if (ev.type === 'health_warning') {
        pushNotif({ icon: '⚠️', msg: `Salud: ${(ev.issues || []).join(' · ')}` });
      }
    } catch {}
  };
  _evtSrc.onerror = () => {
    _evtSrc.close();
    setTimeout(connectSSE, 5000);
  };
}

// ─── L invertida del SuperAdmin (spec chat2) ───
let kpiRefreshing = false;
async function refreshKpis() {
  // Pulse del topbar lo refresca todo el mundo (no es exclusivo SA)
  const isSA = state.user?.role === 'superadmin';
  if (kpiRefreshing) return;
  kpiRefreshing = true;
  try {
    const k = isSA
      ? await fetch('/api/superadmin/kpis').then(r => r.ok ? r.json() : null).catch(() => null)
      : null;

    // Sidebar status (xCAPTCHA, Proxies, En uso) para todos
    const stCap = $('#stCap');
    if (k?.capmonster_balance != null) {
      stCap.textContent = `$${Number(k.capmonster_balance).toFixed(2)}`;
      stCap.classList.toggle('warn', Number(k.capmonster_balance) < 5);
      stCap.classList.toggle('ok', Number(k.capmonster_balance) >= 5);
      stCap.title = 'Saldo CapMonster';
    } else {
      stCap.textContent = 'n/d';
      stCap.classList.remove('ok'); stCap.classList.add('dim');
      stCap.title = k?.capmonster_error || 'CAPMONSTER_KEY no configurado';
    }

    const stProxy = $('#stProxy');
    if (stProxy) {
      const p = k?.proxy;
      stProxy.classList.remove('ok', 'warn', 'danger', 'dim');
      if (p && p.ok) {
        const lat = p.latency_ms != null ? `${p.latency_ms}ms` : 'OK';
        stProxy.textContent = `${p.country || 'OK'} · ${lat}`;
        stProxy.classList.add(p.latency_ms > 1500 ? 'warn' : 'ok');
        stProxy.title = `LitPort ${p.host}\nIP: ${p.ip || '?'}\nLatencia: ${lat}`;
      } else if (p) {
        stProxy.textContent = 'caído';
        stProxy.classList.add('danger');
        stProxy.title = `LitPort ${p.host || ''}\n${p.error || 'sin respuesta'}`;
      } else {
        stProxy.textContent = '—';
        stProxy.classList.add('dim');
      }
    }

    if (!k) return;

    // ── Bloque 1: Online ──
    const ops = k.online?.operators || [];
    $('#lpOnlineActive').textContent = k.online?.active ?? 0;
    $('#lpOnlineTotal').textContent = k.online?.total ?? 0;
    $('#lpOps').innerHTML = ops.map(o => {
      const initials = (o.display || '··').slice(0, 2).toUpperCase();
      return `<div class="lp-op lp-op-${esc(o.status)}" data-uid="${o.telegram_id}" data-color="${esc(o.color || 'accent')}" title="${esc(o.display)} · ${esc(o.status)}${o.in_use ? ` · ${o.in_use} en uso` : ''}">
        <span class="lp-av lp-av-${esc(o.color || 'accent')}">${initials}</span>
        <span class="lp-op-name">${esc(o.display)}</span>
        ${o.in_use ? `<span class="lp-op-n mono">${o.in_use}</span>` : ''}
      </div>`;
    }).join('');

    // ── Bloque 2: Feed live ──
    const feed = k.feed || [];
    $('#lpFeedCount').textContent = feed.length ? `${feed.length} eventos` : '—';
    $('#lpFeed').innerHTML = feed.length === 0
      ? '<div class="lp-empty dim mono">esperando actividad…</div>'
      : feed.map(e => {
          const isDepOk   = e.kind === 'deposit' && e.status === 'approved';
          const isDepFail = e.kind === 'deposit' && e.status !== 'approved';
          const ic = e.kind === 'deposit' ? (isDepOk ? '💰' : '✗')
                   : e.kind === 'lock' ? '🔒' : '·';
          const col = e.who_color || 'accent';
          const rowCls = isDepOk ? 'lp-feed-ok' : isDepFail ? 'lp-feed-fail' : 'lp-feed-neutral';
          return `<div class="lp-feed-row ${rowCls}">
            <span class="lp-feed-ic">${ic}</span>
            <span class="lp-feed-who lp-color-${esc(col)}">${esc(e.who || '—')}</span>
            <span class="lp-feed-target dim mono">${esc(e.target || '')}</span>
            ${e.amount != null ? `<span class="lp-feed-amt mono">${fmtMoney(e.amount)}</span>` : ''}
            <span class="lp-feed-time mono dim">${fmtAgo(e.ts)}</span>
          </div>`;
        }).join('');

    // ── Bloque 3: Alertas ──
    const alerts = k.alerts || [];
    $('#lpAlertCount').textContent = alerts.length;
    $('#lpAlertCount').classList.toggle('warn', alerts.length > 0);
    $('#lpAlerts').innerHTML = alerts.length === 0
      ? '<div class="lp-empty dim mono">sin alertas</div>'
      : alerts.map(a => `<div class="lp-alert-row sev-${esc(a.severity)}">
          <span class="lp-alert-msg">${esc(a.msg)}</span>
          <span class="lp-alert-time mono dim">${fmtAgo(a.ts)}</span>
        </div>`).join('');

    // ── Bloque 4: Pool ──
    const p = k.pool || {};
    $('#lpPool').textContent = (p.pool ?? 0).toLocaleString();
    $('#lpInUse').textContent = (p.in_use ?? 0).toLocaleString();
    $('#lpTras').textContent = p.trastienda ?? 0;
    $('#lpReb').textContent = (p.rebotadas ?? 0).toLocaleString();
    $('#lpPoolSub').textContent = `${(p.pool ?? 0) + (p.in_use ?? 0)} LIVE`;
  } catch (e) {
    console.error('KPI error:', e);
  } finally {
    kpiRefreshing = false;
  }
}

// ─── Refresh visible ───
async function refreshVisible() {
  const ids = getPaged().rows.map(r => r.id);
  if (!ids.length) return;
  toast(`↻ Actualizando ${ids.length}…`);
  try {
    const r = await fetch('/api/accounts/refresh', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ ids }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    // Patch state.rows
    const map = new Map(data.rows.map(r => [r.id, r]));
    state.rows = state.rows.map(r => map.get(r.id) || r);
    renderTable();
    toast(`✓ ${data.rows.length} actualizadas`, 'success');
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ─── Logs view ───
let _logsTimer = null;
let _logsPaused = false;
async function reloadLogs() {
  const v = $('#logsView');
  if (!v) return;
  try {
    const r = await fetch('/api/logs?limit=300');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    $('#logsCount').textContent = `${data.lines.length} líneas`;
    v.textContent = data.lines.join('\n');
    v.scrollTop = v.scrollHeight;
  } catch (e) {
    v.textContent = `Error: ${e.message}`;
  }
}
function startLogsPolling() {
  stopLogsPolling();
  if (state.section === 'logs' && !_logsPaused) {
    reloadLogs();
    _logsTimer = setInterval(reloadLogs, 4000);
  }
}
function stopLogsPolling() {
  if (_logsTimer) { clearInterval(_logsTimer); _logsTimer = null; }
}

// ─── Health view ───
async function loadHealth(forceRun = false) {
  const v = $('#healthView');
  if (!v) return;
  try {
    const r = await fetch(forceRun ? '/api/health/full' : '/api/health/last');
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const h = await r.json();
    const badge = $('#navHealthBadge');
    if (h.last_run) $('#healthLast').textContent = `últ. ${fmtAgo(h.last_run)}`;
    else $('#healthLast').textContent = 'sin runs aún';
    if (h.ok) {
      v.innerHTML = `<div class="health-ok"><span class="hh">✓</span> Sistema OK</div>`;
      badge.classList.remove('hidden');
      badge.classList.remove('danger');
      badge.textContent = '✓';
    } else {
      v.innerHTML = `<div class="health-bad"><span class="hh">✗</span> Issues:<ul>${(h.issues || []).map(i => `<li>${esc(i)}</li>`).join('')}</ul></div>`;
      badge.classList.remove('hidden');
      badge.classList.add('danger');
      badge.textContent = (h.issues || []).length;
    }
  } catch (e) {
    v.innerHTML = `<div class="health-bad">Error: ${esc(e.message)}</div>`;
  }
}

// ─── Liberar popup ───
let _users = [];
async function openReleasePopup() {
  if (selectedIds.size === 0) { toast('Selecciona cuentas primero', 'error'); return; }
  if (_users.length === 0) {
    try { _users = await fetch('/api/users').then(r => r.json()); }
    catch (e) { toast(`Error: ${e.message}`, 'error'); return; }
  }
  // Solo usuarios role 'user' (a quienes liberar)
  const targets = _users.filter(u => u.role === 'user');
  const popup = $('#releasePopup');
  popup.innerHTML = `
    <div class="rp-title">Liberar ${selectedIds.size} a:</div>
    ${targets.map(u => `
      <button class="rp-user" data-uid="${u.telegram_id}">
        <span class="rp-name">${esc(u.display)}</span>
        <span class="rp-role mono dim">${esc(u.role)}</span>
      </button>`).join('')}
  `;
  popup.classList.remove('hidden');
}
function closeReleasePopup() { $('#releasePopup').classList.add('hidden'); }
async function assignSelected(userId) {
  const sel = state.rows.filter(r => selectedIds.has(r.id));
  const emails = sel.map(r => r.email);
  if (!emails.length) return;
  closeReleasePopup();
  try {
    const r = await fetch('/api/assignments/assign', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ emails, user_id: userId }),
    });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    toast(`🎁 ${data.assigned} liberadas`, 'success');
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
}

// ─── handlers ───
$$('.nav[data-section]').forEach(btn => {
  btn.addEventListener('click', () => showSection(btn.dataset.section));
});

let _searchTimer = null;
$('#searchInput').addEventListener('input', e => {
  searchQuery = e.target.value.trim();
  state.page = 1;
  if (_searchTimer) clearTimeout(_searchTimer);
  _searchTimer = setTimeout(() => reload(), 300);
});

// Pagination handlers
$('#pageSize').addEventListener('change', e => {
  state.pageSize = parseInt(e.target.value);
  state.page = 1;
  renderTable();
});
$('#pbPages').addEventListener('click', e => {
  const btn = e.target.closest('.pg-btn');
  if (!btn || btn.disabled) return;
  const v = btn.dataset.pg;
  const paged = getPaged();
  if (v === 'prev') state.page = Math.max(1, state.page - 1);
  else if (v === 'next') state.page = Math.min(paged.totalPages, state.page + 1);
  else state.page = parseInt(v);
  renderTable();
});
$('#btnRefreshVisible').addEventListener('click', refreshVisible);

// Logs handlers
$('#btnLogsPause')?.addEventListener('click', () => {
  _logsPaused = !_logsPaused;
  $('#btnLogsPause').textContent = _logsPaused ? '▶ Reanudar' : '⏸ Pausar';
  if (_logsPaused) stopLogsPolling(); else startLogsPolling();
});
$('#btnLogsClear')?.addEventListener('click', () => { $('#logsView').textContent = ''; });

// Health
$('#btnHealthRun')?.addEventListener('click', () => loadHealth(true));
$('#btnHealthDismiss')?.addEventListener('click', async () => {
  try {
    const r = await fetch('/api/health/dismiss', { method: 'POST' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const h = await r.json();
    if (h.ok) toast('✓ Salud OK — alertas limpias', 'success');
    else toast(`Issues persisten: ${h.issues.length}`, 'error');
    await loadHealth(false);
  } catch (e) {
    toast(`Error: ${e.message}`, 'error');
  }
});

// Liberar
$('#cmdRelease')?.addEventListener('click', openReleasePopup);
$('#releasePopup')?.addEventListener('click', e => {
  const u = e.target.closest('.rp-user');
  if (u && u.dataset.uid) assignSelected(parseInt(u.dataset.uid));
});
document.addEventListener('click', e => {
  if (!e.target.closest('.cmd-release-wrap') && !$('#releasePopup').classList.contains('hidden')) {
    closeReleasePopup();
  }
});

// Ctrl+K → focus search
document.addEventListener('keydown', e => {
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    $('#searchInput').focus();
    $('#searchInput').select();
  }
  if (e.key === 'Escape' && selectedIds.size > 0) deselectAll();
});

$$('.seg').forEach(seg => {
  const key = seg.dataset.seg;
  seg.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', async () => {
      seg.querySelectorAll('button').forEach(b => b.classList.remove('on'));
      btn.classList.add('on');
      if (key === 'actkind') {
        activityFilter.kind = btn.dataset.v;
        return renderActivity();
      }
      state[key] = btn.dataset.v;
      state.page = 1;
      if (key === 'view') return renderTable();
      await reload();
    });
  });
});

// Activity table — clicks interactivos
$('#actTable').addEventListener('click', e => {
  const tgt = e.target.closest('.act-target');
  if (tgt && tgt.dataset.email) {
    // Lleva a Cuentas con esa cuenta filtrada en search
    searchQuery = tgt.dataset.email.toLowerCase();
    $('#searchInput').value = tgt.dataset.email;
    showSection('accounts');
    renderTable();
    return;
  }
  const who = e.target.closest('.act-who');
  if (who && who.dataset.who) {
    activityFilter.who = isNaN(+who.dataset.who) ? who.dataset.who : +who.dataset.who;
    reloadActivity();
    return;
  }
});
$('#actClearFilter')?.addEventListener('click', () => {
  activityFilter = { kind: '', who: null };
  document.querySelectorAll('.seg[data-seg="actkind"] button').forEach((b, i) => b.classList.toggle('on', i === 0));
  reloadActivity();
});

// ─── Tabla: click en checkbox, click en combo (copia), click en fila (detalle) ───
$('#accTable').addEventListener('click', e => {
  const th = e.target.closest('th.th-sort');
  if (th?.dataset.sort) { sortRows(th.dataset.sort); return; }
  const cb = e.target.closest('.rowsel');
  if (cb) {
    const id = parseInt(cb.dataset.id);
    if (cb.checked) selectedIds.add(id); else selectedIds.delete(id);
    const tr = cb.closest('tr');
    if (tr) tr.classList.toggle('row-sel', cb.checked);
    updateCmdBar();
    return;
  }
  if (e.target.id === 'selAll') {
    const visible = getVisible();
    if (e.target.checked) visible.forEach(r => selectedIds.add(r.id));
    else visible.forEach(r => selectedIds.delete(r.id));
    renderTable();
    return;
  }
  const comboB = e.target.closest('td.combo b');
  if (comboB && comboB.dataset.combo) {
    e.stopPropagation();
    navigator.clipboard.writeText(comboB.dataset.combo)
      .then(() => toast(`✓ ${comboB.dataset.combo}`, 'success'))
      .catch(err => toast(`Error: ${err.message}`, 'error'));
    return;
  }
  // Click en cualquier otra parte de la fila → abre modal de detalle
  const tr = e.target.closest('tr');
  if (tr && tr.dataset.id) {
    openDetailModal(parseInt(tr.dataset.id));
  }
});

// Modal de detalle: form de notas (submit + delete)
$('#detModalBody').addEventListener('submit', async e => {
  const form = e.target.closest('.d-note-form');
  if (!form) return;
  e.preventDefault();
  const accId = parseInt(form.dataset.accId);
  const inp = form.querySelector('.d-note-input');
  const text = inp.value.trim();
  if (!text) { inp.focus(); return; }
  const btn = form.querySelector('.d-note-submit');
  btn.disabled = true;
  try {
    await submitNote(accId, text);
    inp.value = '';
    toast('✓ Nota guardada', 'success');
    // Re-render modal
    openDetailModal(accId);
  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
  }
});
$('#detModalBody').addEventListener('click', async e => {
  const del = e.target.closest('.d-note-del');
  if (!del) return;
  e.preventDefault();
  e.stopPropagation();
  const noteId = parseInt(del.dataset.noteId);
  const li = del.closest('li[data-note-id]');
  const form = $('#detModalBody').querySelector('.d-note-form');
  const accId = form ? parseInt(form.dataset.accId) : null;
  if (!accId || !noteId) return;
  if (!confirm('¿Borrar esta nota?')) return;
  try {
    await deleteNote(accId, noteId);
    if (li) li.remove();
    toast('✓ Nota borrada', 'success');
  } catch (err) {
    toast(`Error: ${err.message}`, 'error');
  }
});

// Cerrar modal detalle: X, click fuera, Escape
$('#detModalClose').addEventListener('click', closeDetailModal);
$('#detModalOverlay').addEventListener('click', e => {
  if (e.target.id === 'detModalOverlay') closeDetailModal();
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !$('#detModalOverlay').classList.contains('hidden')) {
    closeDetailModal();
  }
});

// ─── Drag-select sobre la columna del checkbox (.sel-cell) ───
// Pointer Events: cubre mouse + touch + pen sin long-press.
let _dragMode = null;  // null | 'select' | 'deselect'
let _dragPointerId = null;

function _toggleCellSelection(cell, wantChecked) {
  const cb = cell.querySelector('.rowsel');
  if (!cb) return;
  const id = parseInt(cb.dataset.id);
  if (cb.checked === wantChecked) return;
  cb.checked = wantChecked;
  if (wantChecked) selectedIds.add(id); else selectedIds.delete(id);
  cb.closest('tr').classList.toggle('row-sel', wantChecked);
  updateCmdBar();
}

function _cellAtPoint(x, y) {
  const el = document.elementFromPoint(x, y);
  return el ? el.closest('td.sel-cell') : null;
}

const _accTable = $('#accTable');
_accTable.addEventListener('pointerdown', e => {
  const cell = e.target.closest('td.sel-cell');
  if (!cell) return;
  const cb = cell.querySelector('.rowsel');
  if (!cb) return;
  // El primer click se procesa por el handler normal; el drag continúa con
  // el estado opuesto (si arrancas en una marcada, deseleccionas mientras arrastras).
  _dragMode = cb.checked ? 'deselect' : 'select';
  _dragPointerId = e.pointerId;
  try { _accTable.setPointerCapture(e.pointerId); } catch {}
});
_accTable.addEventListener('pointermove', e => {
  if (!_dragMode) return;
  const cell = _cellAtPoint(e.clientX, e.clientY);
  if (!cell) return;
  e.preventDefault();
  _toggleCellSelection(cell, _dragMode === 'select');
});
function _endDrag(e) {
  if (_dragPointerId != null) {
    try { _accTable.releasePointerCapture(_dragPointerId); } catch {}
    _dragPointerId = null;
  }
  _dragMode = null;
}
_accTable.addEventListener('pointerup', _endDrag);
_accTable.addEventListener('pointercancel', _endDrag);
document.addEventListener('pointerup', _endDrag);

// touch-action: none en sel-cell para no scrollear mientras arrastras (CSS lo aplica).

// ─── Modal de detalle (fijo con scroll interno solo en secciones largas) ───
async function openDetailModal(id) {
  const overlay = $('#detModalOverlay');
  const body = $('#detModalBody');
  const title = $('#detModalTitle');
  body.innerHTML = '<div class="detail-loading"><span class="dep-spinner"></span> Cargando…</div>';
  title.textContent = 'Detalle de cuenta';
  overlay.classList.remove('hidden');
  try {
    const r = await fetch(`/api/accounts/${id}/details`);
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    const data = await r.json();
    title.textContent = `${data.email}:${data.password || ''}`;
    body.innerHTML = renderDetail(data);
  } catch (e) {
    body.innerHTML = `<div class="detail-error">Error: ${esc(e.message)}</div>`;
  }
}
function closeDetailModal() {
  $('#detModalOverlay').classList.add('hidden');
}

function renderDetail(d) {
  const personal = `
    <div class="d-section">
      <h4>📋 Datos personales</h4>
      <ul class="d-list">
        <li><span>Combo</span><b class="d-copy" data-copy="${esc(d.email + ':' + (d.password || ''))}">${esc(d.email)}:${esc(d.password || '')}</b></li>
        <li><span>Saldo total</span><b>${fmtMoney(d.balance_total)}</b></li>
        <li><span>Saldo real</span><b>${fmtMoney(d.balance_real)}</b></li>
        <li><span>Grade</span><b>${esc(d.grade) || '?'}</b></li>
        <li><span>Status</span><b>${esc(d.status)}</b></li>
        <li><span>Lock</span><b>${d.locked_by ? `por ${esc(d.locked_by)}${(() => { const u = fmtUntil(d.locked_until); return u ? ` <span class="${u.expired ? 'lock-expired' : (u.urgent ? 'lock-urgent' : 'dim')}">· ${u.text}</span>` : ''; })()}` : '<span class="dim">libre</span>'}</b></li>
        <li><span>Últ. dep.</span><b>${d.last_deposit_amount ? fmtMoney(d.last_deposit_amount) + ' · ' + fmtAgo(d.last_deposit_date) : '<span class="dim">—</span>'}</b></li>
        <li><span>Últ. check</span><b>${fmtAgo(d.last_checked_at)}</b></li>
        <li><span>Total checks</span><b>${d.check_count || 0}</b></li>
      </ul>
    </div>`;

  const cards = (d.cards && d.cards.length > 0)
    ? `<div class="d-section">
        <h4>💳 Tarjetas guardadas <span class="d-count">${d.cards.length}</span></h4>
        <div class="d-cards">
          ${d.cards.map(c => {
            const num = c.card_number || '';
            const exp = (c.card_expiry || '').replace('/', '');
            const cvv = c.card_cvv || '';
            const pipe = `${num}|${exp}|${cvv}`;
            const stats = `${c.total_approved || 0}/${c.total_deposits || 0} ok`;
            return `<div class="d-card" data-copy="${esc(pipe)}" title="Click para copiar pipe">
              <div class="d-card-pipe">${esc(pipe)}</div>
              <div class="d-card-meta">
                <span class="d-card-stats">${stats}</span>
                <span class="d-card-status ${esc((c.status || '').toLowerCase())}">${esc(c.status || '')}</span>
              </div>
            </div>`;
          }).join('')}
        </div>
      </div>`
    : `<div class="d-section"><h4>💳 Tarjetas</h4><div class="d-empty">Sin tarjetas guardadas.</div></div>`;

  // BetMexico API: txn_type 1=depósito, 2=retiro. Gateway 1=tarjeta, 2=SPEI, 3=OXXO.
  const _txnType = t => ({1: '⬇️ Depósito', 2: '⬆️ Retiro'})[t] ?? '🔄 Otro';
  const _txnGateway = g => ({1: '💳 Tarjeta', 2: '🏦 SPEI', 3: '🏪 OXXO'})[g] || (g ? `gw${g}` : '—');
  const _txnStatus = s => {
    const m = {6: 'Exitoso', 0: 'Pendiente', '-4': 'Fallido', 5: 'Error'};
    return m[s] ?? m[String(s)] ?? `cod ${s}`;
  };
  const _txnStatusCls = s => ({6: 'ok', 0: 'pending', '-4': 'fail', 5: 'fail'})[s]
    ?? ({6: 'ok', 0: 'pending', '-4': 'fail', 5: 'fail'})[String(s)] ?? '';
  const txns = (d.transactions && d.transactions.length > 0)
    ? `<div class="d-section">
        <h4>📊 Transacciones <span class="d-count">${d.transactions.length}</span></h4>
        <div class="d-txn-scroll">
          <table class="d-txn-table">
            <thead><tr><th>Cuándo</th><th>Tipo</th><th>Método</th><th class="num">Monto</th><th>Estado</th></tr></thead>
            <tbody>
              ${d.transactions.map(t => {
                const isCard = t.txn_type === 1 && t.gateway === 1;
                const rowCls = isCard ? '' : 'txn-row-other';
                return `<tr class="${rowCls}">
                  <td class="dim mono" title="${esc(t.txn_date || '')}">${fmtAbs(t.txn_date)}</td>
                  <td>${_txnType(t.txn_type)}</td>
                  <td class="txn-gw${isCard ? ' txn-gw-card' : ' dim'}">${esc(_txnGateway(t.gateway))}</td>
                  <td class="num">${fmtMoney(t.amount)}</td>
                  <td><span class="txn-st txn-st-${_txnStatusCls(t.status)}">${esc(_txnStatus(t.status))}</span></td>
                </tr>`;
              }).join('')}
            </tbody>
          </table>
        </div>
      </div>`
    : `<div class="d-section"><h4>📊 Transacciones</h4><div class="d-empty">Sin transacciones registradas.</div></div>`;

  const notes = `<div class="d-section">
      <h4>📝 Notas ${d.notes && d.notes.length > 0 ? `<span class="d-count">${d.notes.length}</span>` : ''}</h4>
      <form class="d-note-form" data-acc-id="${d.id}">
        <textarea class="d-note-input" placeholder="Nueva nota (visible solo para ti${state.user?.role === 'superadmin' ? '' : ' y SA'})…" maxlength="2000" rows="2"></textarea>
        <button type="submit" class="d-note-submit">Guardar</button>
      </form>
      ${(d.notes && d.notes.length > 0)
        ? `<ul class="d-notes">
            ${d.notes.map(n => `<li data-note-id="${n.id}">
              <div class="d-note-head">
                <span class="d-note-by">${esc(n.created_by_name || '—')}</span>
                <span class="d-note-when dim mono" title="${esc(n.created_at || '')}">${fmtAbs(n.created_at)} · ${fmtAgo(n.created_at)}</span>
                ${n.mine || state.user?.role === 'superadmin' ? `<button class="d-note-del" data-note-id="${n.id}" title="Borrar">✕</button>` : ''}
              </div>
              <div class="d-note-body">${esc(n.note_text)}</div>
            </li>`).join('')}
          </ul>`
        : '<div class="d-empty">Sin notas todavía.</div>'}
    </div>`;

  return `<div class="d-grid">${personal}${cards}${txns}${notes}</div>`;
}

async function submitNote(accId, text) {
  const r = await fetch(`/api/accounts/${accId}/notes`, {
    method: 'POST', headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({ text }),
  });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

async function deleteNote(accId, noteId) {
  const r = await fetch(`/api/accounts/${accId}/notes/${noteId}`, { method: 'DELETE' });
  if (!r.ok) {
    const err = await r.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${r.status}`);
  }
  return r.json();
}

// Click en .d-card / .d-copy / .d-card-copy → copia el pipe
$('#accTable').addEventListener('click', e => {
  const copyTarget = e.target.closest('[data-copy]');
  if (copyTarget && copyTarget.dataset.copy) {
    e.stopPropagation();
    navigator.clipboard.writeText(copyTarget.dataset.copy)
      .then(() => toast(`✓ ${copyTarget.dataset.copy.slice(0, 60)}`, 'success'))
      .catch(err => toast(`Error: ${err.message}`, 'error'));
  }
}, true);  // capture para que ejecute antes del click handler de fila

// ─── Deposit modal ───
let _depAccountId = null;
let _depAmount = 50;
let _depBusy = false;

async function openDepositModal(accountId) {
  const acc = state.rows.find(r => r.id === accountId);
  if (!acc) { toast('Cuenta no encontrada', 'error'); return; }
  _depAccountId = accountId;
  _depAmount = 50;
  $('#depTargetEmail').textContent = acc.email;
  $('#depTargetBalance').textContent = fmtMoney(acc.balance_total);
  $('#depCardPipe').value = '';
  $('#depCardErr').classList.add('hidden');
  $('#depResult').classList.add('hidden');
  $('#depCustomAmount').value = '';
  $('#depCustomAmount').classList.add('hidden');
  $$('#depAmounts .dep-amt').forEach(b => b.classList.toggle('on', b.dataset.v === '50'));
  $('#depExec').disabled = false;
  $('#depExec').textContent = '🚀 Ejecutar depósito';
  $('#depModalOverlay').classList.remove('hidden');

  // Auto-rellenar última tarjeta usada de esta cuenta (proceso completo en un paso)
  if (acc.cards_count > 0) {
    try {
      const data = await fetch(`/api/accounts/${accountId}/details`).then(r => r.ok ? r.json() : null);
      const lastCard = (data?.cards || [])[0];  // ya viene ordenada DESC last_used_at
      if (lastCard?.card_number && lastCard?.card_expiry && lastCard?.card_cvv) {
        const exp = String(lastCard.card_expiry).replace('/', '');
        const pipe = `${lastCard.card_number}|${exp}|${lastCard.card_cvv}`;
        $('#depCardPipe').value = pipe;
        $('#depCardPipe').classList.add('dep-prefilled');
        $('#depCardHint')?.classList.remove('hidden');
      }
    } catch {}
  }
  setTimeout(() => {
    const inp = $('#depCardPipe');
    inp.focus();
    if (inp.value) inp.select();  // ya rellenada → seleccionada para reemplazar fácil
  }, 50);
}

function closeDepositModal() {
  if (_depBusy) { toast('Espera a que termine el depósito', 'error'); return; }
  $('#depModalOverlay').classList.add('hidden');
  _depAccountId = null;
}

function validatePipe(s) {
  if (!s) return null;
  const parts = s.replace(/\s/g, '').split('|').filter(Boolean);
  if (parts.length === 3) {
    const [num, exp, cvv] = parts;
    if (!/^\d{13,19}$/.test(num)) return 'Número de tarjeta inválido';
    // Acepta MMYY (4 dígitos), MM/YY o MMYYYY
    if (!/^(0[1-9]|1[0-2])\/?(\d{2}|\d{4})$/.test(exp)) return 'Vencimiento inválido (MMYY)';
    if (!/^\d{3,4}$/.test(cvv)) return 'CVV inválido';
    return null;
  }
  if (parts.length === 4) {
    const [num, mm, yy, cvv] = parts;
    if (!/^\d{13,19}$/.test(num)) return 'Número de tarjeta inválido';
    if (!/^(0?[1-9]|1[0-2])$/.test(mm)) return 'Mes inválido';
    if (!/^\d{2,4}$/.test(yy)) return 'Año inválido';
    if (!/^\d{3,4}$/.test(cvv)) return 'CVV inválido';
    return null;
  }
  return 'Formato: numero|MMYY|CVV o numero|MM|YY|CVV';
}

async function executeDeposit() {
  if (_depBusy) return;
  if (!_depAccountId) { toast('Sin cuenta seleccionada', 'error'); return; }

  const pipe = $('#depCardPipe').value.trim();
  const err = validatePipe(pipe);
  if (err) {
    $('#depCardErr').textContent = err;
    $('#depCardErr').classList.remove('hidden');
    $('#depCardPipe').focus();
    return;
  }
  $('#depCardErr').classList.add('hidden');

  let amount = _depAmount;
  if (amount === 'custom') {
    amount = parseFloat($('#depCustomAmount').value) || 0;
    if (amount < 1 || amount > 5000) { toast('Monto fuera de rango (1-5000)', 'error'); return; }
  }

  _depBusy = true;
  $('#depExec').disabled = true;
  $('#depExec').textContent = 'Procesando…';
  const res = $('#depResult');
  res.className = 'dep-result loading';
  res.innerHTML = `<span class="dep-spinner"></span> Login → BeginDeposit → makePayment…`;

  try {
    const r = await fetch('/api/deposits/execute', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ account_id: _depAccountId, card_pipe: pipe, amount }),
    });
    const data = await r.json();

    if (!r.ok) {
      res.className = 'dep-result error';
      res.innerHTML = `<b>✗ ${esc(data.detail || 'Error')}</b>`;
      $('#depExec').disabled = false;
      $('#depExec').textContent = '🚀 Ejecutar depósito';
      return;
    }

    if (data.success) {
      res.className = 'dep-result success';
      res.innerHTML = `<b>✓ Depósito aprobado</b> — $${amount.toFixed(2)} <span class="dim mono"> · ${data.duration_ms}ms</span>`;
      pushNotif({ icon: '💳', msg: `Depósito $${amount.toFixed(2)} aprobado` });
      reload();
    } else {
      res.className = 'dep-result error';
      res.innerHTML = `<b>✗ Rechazado</b><br><span class="mono">${esc(data.error || data.result_code || 'Sin detalle')}</span>`;
      pushNotif({ icon: '⚠️', msg: `Depósito rechazado: ${data.error || data.result_code}` });
    }
    $('#depExec').disabled = false;
    $('#depExec').textContent = '🔁 Otro intento';
  } catch (e) {
    res.className = 'dep-result error';
    res.innerHTML = `<b>✗ Error de red</b><br><span class="mono">${esc(e.message)}</span>`;
    $('#depExec').disabled = false;
    $('#depExec').textContent = '🔁 Reintentar';
  } finally {
    _depBusy = false;
  }
}

$('#depModalClose').addEventListener('click', closeDepositModal);
$('#depModalOverlay').addEventListener('click', e => { if (e.target.id === 'depModalOverlay') closeDepositModal(); });
$('#depAmounts').addEventListener('click', e => {
  const btn = e.target.closest('.dep-amt');
  if (!btn) return;
  $$('#depAmounts .dep-amt').forEach(b => b.classList.remove('on'));
  btn.classList.add('on');
  _depAmount = btn.dataset.v === 'custom' ? 'custom' : parseFloat(btn.dataset.v);
  const cust = $('#depCustomAmount');
  if (btn.dataset.v === 'custom') { cust.classList.remove('hidden'); setTimeout(() => cust.focus(), 30); }
  else cust.classList.add('hidden');
});
$('#depExec').addEventListener('click', executeDeposit);
$('#depCardPipe').addEventListener('input', () => {
  $('#depCardErr').classList.add('hidden');
  $('#depCardPipe').classList.remove('dep-prefilled');
  $('#depCardHint')?.classList.add('hidden');
});
document.addEventListener('keydown', e => {
  if (e.key === 'Escape' && !$('#depModalOverlay').classList.contains('hidden')) closeDepositModal();
  if (e.key === 'Enter' && !$('#depModalOverlay').classList.contains('hidden') && document.activeElement?.id === 'depCardPipe') {
    executeDeposit();
  }
});

$('#cmdDeposit').addEventListener('click', () => {
  if (selectedIds.size !== 1) { toast('Selecciona exactamente 1 cuenta', 'error'); return; }
  openDepositModal([...selectedIds][0]);
});

$('#cmdCopy')?.addEventListener('click', copySelectedCombos);
$('#cmdPrewarm')?.addEventListener('click', bulkPrewarm);
$('#cmdTrastienda')?.addEventListener('click', bulkTrastienda);
$('#cmdLock').addEventListener('click', bulkLock);
$('#cmdUnlock')?.addEventListener('click', bulkUnlock);
$('#cmdDeselect').addEventListener('click', deselectAll);

// Click en el chip "2h" del botón Lock abre el selector
$('#cmdLockHours')?.addEventListener('click', e => {
  e.preventDefault();
  e.stopPropagation();
  $('#lockHoursPopup').classList.toggle('hidden');
});
$('#lockHoursPopup')?.addEventListener('click', e => {
  const btn = e.target.closest('.lh-btn');
  if (!btn) return;
  state.lockHours = parseInt(btn.dataset.h);
  $('#cmdLockHours').textContent = `${state.lockHours}h`;
  $$('#lockHoursPopup .lh-btn').forEach(b => b.classList.toggle('on', b === btn));
  $('#lockHoursPopup').classList.add('hidden');
});
document.addEventListener('click', e => {
  if (!e.target.closest('.cmd-lock-wrap')) $('#lockHoursPopup')?.classList.add('hidden');
});

$('#bellBtn').addEventListener('click', () => {
  if (state.section === 'notifications') {
    showSection(_lastNonNotifSection || 'accounts');
  } else {
    showSection('notifications');
  }
});

// Click en "En uso" del Pool → filtra accounts por las que tienen lock activo
$('#lpInUse')?.addEventListener('click', () => {
  state.filterInUse = !state.filterInUse;
  state.page = 1;
  $('#lpInUse').classList.toggle('lp-stat-active', state.filterInUse);
  showSection('accounts');
  renderTable();
  toast(state.filterInUse ? '🎣 Filtro: solo en uso' : '↺ Filtro removido', 'success');
});
// Click en "Pool" → quita filtros, muestra todas
$('#lpPool')?.addEventListener('click', () => {
  if (state.filterInUse) {
    state.filterInUse = false;
    $('#lpInUse').classList.remove('lp-stat-active');
    state.page = 1;
    showSection('accounts');
    renderTable();
  }
});

// Click en avatar de la L invertida → filtra activity por ese operador
$('#lpOps')?.addEventListener('click', e => {
  const op = e.target.closest('.lp-op');
  if (!op) return;
  const uid = parseInt(op.dataset.uid);
  if (!uid) return;
  activityFilter.who = uid;
  showSection('activity');
});
$('#btnClearNotif').addEventListener('click', () => { notifications = []; renderNotifs(); renderNotifBadge(); });

$$('.ico-btn[title="Salir"], .power').forEach(btn => {
  btn.addEventListener('click', async () => {
    await fetch('/api/auth/logout', { method: 'POST' });
    window.location.href = '/login';
  });
});

// ─── init ───
(async () => {
  await loadMe();
  tickGreeting();
  setInterval(tickGreeting, 30_000);
  tickFrase();
  setInterval(tickFrase, 9_000);
  await reload();
  refreshKpis();
  setInterval(refreshKpis, 30_000);
  loadHealth(false);
  connectSSE();
})();

window.addEventListener('beforeunload', () => {
  if (_evtSrc) _evtSrc.close();
});
