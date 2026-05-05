// Botmexico v2 — vanilla, sin frameworks. ~150 lineas.

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
  status: 'LIVE',
  grade: '',
  view: 'simple',
  rows: [],
};

const $ = sel => document.querySelector(sel);
const fmtMoney = v => `$${(v || 0).toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
// Parsea formatos de la BD: ISO "YYYY-MM-DD HH:MM:SS" y MX "DD/MM/YYYY HH:MM".
// Devuelve Date inválido (NaN-time) si no matchea.
const parseTs = ts => {
  if (!ts || ts === 'N/A') return new Date(NaN);
  const mx = ts.match(/^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?$/);
  if (mx) {
    const [, dd, mm, yyyy, h, mi, ss] = mx;
    return new Date(+yyyy, +mm - 1, +dd, +h, +mi, +(ss || 0));
  }
  const iso = ts.match(/^(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2}):(\d{2})$/);
  if (iso) {
    const [, yyyy, mm, dd, h, mi, ss] = iso;
    return new Date(+yyyy, +mm - 1, +dd, +h, +mi, +ss);
  }
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
const gradeClass = g => ({ A: 'A', B: 'B', C: 'C' })[g] || 'U';

// ─── greeting + frase rotativa ───
function tickGreeting() {
  const now = new Date();
  $('#sbDate').textContent = now.toLocaleDateString('es-MX', { weekday: 'short', day: '2-digit', month: 'short' }).replace('.', '');
  $('#sbTime').textContent = now.toLocaleTimeString('es-MX', { hour: '2-digit', minute: '2-digit', hour12: false });
}
let fraseIdx = Math.floor(Math.random() * FRASES.length);
function tickFrase() {
  $('#fraseTxt').textContent = `“${FRASES[fraseIdx]}”`;
  $('#fraseTxt').style.animation = 'none';
  void $('#fraseTxt').offsetWidth;
  $('#fraseTxt').style.animation = 'fraseFade 600ms ease-out';
  fraseIdx = (fraseIdx + 1) % FRASES.length;
}

// ─── data ───
async function fetchAccounts() {
  const url = new URL('/api/accounts', location.origin);
  url.searchParams.set('status', state.status);
  if (state.grade) url.searchParams.set('grade', state.grade);
  url.searchParams.set('limit', '200');
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function fetchStats() {
  const r = await fetch('/api/stats');
  if (!r.ok) return null;
  return r.json();
}

// ─── render ───
function renderTable() {
  const t = $('#accTable');
  if (state.view === 'simple') {
    t.querySelector('thead').innerHTML = `
      <tr>
        <th></th><th>Grade</th><th class="num">Saldo</th><th>Cuenta</th>
        <th>Últ. depósito</th>
      </tr>`;
    t.querySelector('tbody').innerHTML = state.rows.map(r => {
      const g = gradeClass(r.grade);
      const locked = r.locked_by ? 'row-locked' : '';
      return `<tr class="${locked}">
        <td><span class="locked-bar"></span></td>
        <td><span class="grade ${g}">${esc(r.grade) || '?'}</span></td>
        <td class="num"><span class="balance ${r.balance_total > 0 ? '' : 'zero'}">${fmtMoney(r.balance_total)}</span></td>
        <td class="combo"><b>${esc(r.email)}</b>:••••••••</td>
        <td class="dep">${r.last_deposit_amount ? `<b>${fmtMoney(r.last_deposit_amount)}</b><span class="ago">${fmtAgo(r.last_deposit_date)}</span>` : '<span class="dim">sin dep.</span>'}</td>
      </tr>`;
    }).join('') || `<tr><td colspan="5" class="loading">Sin cuentas</td></tr>`;
  } else {
    t.querySelector('thead').innerHTML = `
      <tr>
        <th></th><th>Grade</th><th class="num">Saldo</th><th>Cuenta</th>
        <th>Últ. depósito</th><th>Estado</th><th>Últ. check</th><th class="num">Checks</th>
      </tr>`;
    t.querySelector('tbody').innerHTML = state.rows.map(r => {
      const g = gradeClass(r.grade);
      const locked = r.locked_by ? 'row-locked' : '';
      return `<tr class="${locked}">
        <td><span class="locked-bar"></span></td>
        <td><span class="grade ${g}">${esc(r.grade) || '?'}</span></td>
        <td class="num"><span class="balance ${r.balance_total > 0 ? '' : 'zero'}">${fmtMoney(r.balance_total)}</span></td>
        <td class="combo"><b>${esc(r.email)}</b></td>
        <td class="dep">${r.last_deposit_amount ? `<b>${fmtMoney(r.last_deposit_amount)}</b><span class="ago">${fmtAgo(r.last_deposit_date)}</span>` : '<span class="dim">—</span>'}</td>
        <td>${r.status === 'LIVE' ? '<span style="color:var(--accent)">LIVE</span>' : '<span class="dim">DEAD</span>'}</td>
        <td class="dep dim">${fmtAgo(r.last_checked_at)}</td>
        <td class="num">${r.check_count || 0}</td>
      </tr>`;
    }).join('') || `<tr><td colspan="8" class="loading">Sin cuentas</td></tr>`;
  }
}

function renderStats(s) {
  if (!s) return;
  $('#navCount').textContent = s.live;
  $('#countLabel').textContent = `${state.rows.length} / ${s.live.toLocaleString()}`;
  $('#stInUse').textContent = s.inUse;
}

// ─── filter handlers ───
document.querySelectorAll('.seg').forEach(seg => {
  const key = seg.dataset.seg;
  seg.querySelectorAll('button').forEach(btn => {
    btn.addEventListener('click', async () => {
      seg.querySelectorAll('button').forEach(b => b.classList.remove('on'));
      btn.classList.add('on');
      state[key] = btn.dataset.v;
      if (key === 'view') return renderTable();
      await reload();
    });
  });
});

async function reload() {
  try {
    const [rows, stats] = await Promise.all([fetchAccounts(), fetchStats()]);
    state.rows = rows;
    renderTable();
    renderStats(stats);
  } catch (e) {
    $('#accTable').querySelector('tbody').innerHTML = `<tr><td colspan="8" class="loading" style="color:var(--danger)">Error: ${e.message}</td></tr>`;
  }
}

// ─── init ───
tickGreeting();
const greetingTimer = setInterval(tickGreeting, 30000);
tickFrase();
const fraseTimer = setInterval(tickFrase, 9000);
reload();

// ─── admin panel ───
let adminRefreshing = false;
async function refreshAdminPanel() {
  if (adminRefreshing) return;
  adminRefreshing = true;
  try {
    const [con, act, alt, pool] = await Promise.all([
      fetch('/api/superadmin/conectados').then(r => r.json()).catch(() => null),
      fetch('/api/superadmin/actividad').then(r => r.json()).catch(() => null),
      fetch('/api/superadmin/alertas').then(r => r.json()).catch(() => null),
      fetch('/api/superadmin/pool').then(r => r.json()).catch(() => null),
    ]);

    if (con) {
      const conCount = con.reduce((s, o) => s + o.count, 0);
      document.getElementById('apConVal').textContent = conCount;
      document.getElementById('apConSub').textContent =
        con.map(o => `${o.operator}(${o.count})`).join(', ') || 'nadie activo';
    }
    if (act) {
      document.getElementById('apActVal').textContent = act.recentChecks.length;
      const peak = act.byHour.reduce((p, h) => h.count > (p?.count ?? 0) ? h : p, null);
      document.getElementById('apActSub').textContent =
        peak ? `pico ${peak.hour}:00 (${peak.count} checks)` : 'sin actividad 24h';
    }
    if (alt) {
      const altTotal = alt.recentDead.length + (alt.noRecentCheck > 0 ? 1 : 0);
      document.getElementById('apAltVal').textContent = altTotal || '✓';
      document.getElementById('apAltSub').textContent =
        `${alt.recentDead.length} DEAD · ${alt.noRecentCheck} sin check 48h`;
    }
    if (pool && pool.capmonster) {
      const cm = pool.capmonster;
      document.getElementById('apPoolVal').textContent =
        cm.balance != null ? `$${Number(cm.balance).toFixed(2)}` : '—';
      document.getElementById('apPoolSub').textContent =
        cm.error ? cm.error.slice(0, 30) : 'disponibles';
    }
  } catch (e) {
    console.error('Admin panel error:', e);
  } finally {
    adminRefreshing = false;
  }
}

refreshAdminPanel();
const adminTimer = setInterval(refreshAdminPanel, 30_000);

window.addEventListener('beforeunload', () => {
  clearInterval(greetingTimer);
  clearInterval(fraseTimer);
  clearInterval(adminTimer);
});
