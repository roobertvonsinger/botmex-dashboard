(function () {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const mv = $('#missionView');
  const grid = $('#accountsGrid');
  const accountsSection = $('#accountsSection');
  const btnAccounts = $('#btnAccounts');
  const btnMissions = $('#btnMissions');
  const phRole = $('#phRole');

  let sse = null;
  let activeMissionId = null;
  let missionState = null;
  let countdownTimer = null;
  let userRole = null;

  // ── View-as scope ──────────────────────────────────────────────
  // /user/{id}: {id} identifica de quién es este portal. Si el que mira es
  // SA, el backend narrowea su sesión (rol/telegram_id) a ese {id} vía
  // ?view_as= — así SA ve exactamente lo que ese usuario vería, incl. sus
  // propias cuentas depositadas con /bet, sin la omnisciencia de SA.
  const VIEW_AS = (window.location.pathname.match(/^\/user\/(\d+)/) || [])[1] || null;

  function apiUrl(path) {
    if (!VIEW_AS) return path;
    return path + (path.includes('?') ? '&' : '?') + 'view_as=' + VIEW_AS;
  }

  // ── Utils ──────────────────────────────────────────────────────
  function showToast(msg, type) {
    const t = document.createElement('div');
    t.className = 'toast ' + (type || '');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  function fmtMoney(n) {
    return '$' + (parseFloat(n || 0)).toFixed(2);
  }

  function shortEmail(e) {
    if (!e) return '?';
    const [u, d] = e.split('@');
    if (!d) return e.slice(0, 4) + '…';
    return u.slice(0, 3) + '…@' + d;
  }

  function statusClass(st) {
    const m = {
      matching: 'st-matching', scheduling: 'st-scheduling',
      awaiting_confirmation: 'st-awaiting_confirmation',
      completed: 'st-completed', failed: 'st-failed',
      cancelled: 'st-cancelled', pending: 'st-pending',
    };
    return m[st] || 'st-pending';
  }

  function statusLabel(st) {
    const m = {
      matching: 'Rastreando', scheduling: 'Llenando',
      awaiting_confirmation: 'Confirmar',
      completed: 'Completado', failed: 'Falló',
      cancelled: 'Cancelado', pending: 'En cola',
    };
    return m[st] || st;
  }

  // ── SSE ────────────────────────────────────────────────────────
  function connectSSE() {
    if (sse) sse.close();
    sse = new EventSource(apiUrl('/api/events'));
    sse.onmessage = (ev) => {
      try {
        const d = JSON.parse(ev.data);
        onBusEvent(d);
      } catch (_) {}
    };
    sse.onerror = () => {
      setTimeout(() => { if (sse) sse.close(); connectSSE(); }, 3000);
    };
  }

  function onBusEvent(ev) {
    if (ev.type === 'activity' && ev.kind === 'auto_mission') {
      if (activeMissionId && ev.mission_id === activeMissionId) {
        onMissionEvent(ev);
      }
    }
    if (ev.type === 'activity' && (ev.kind === 'account_refreshed' || ev.kind === 'withdrawal' || ev.kind === 'withdrawal_status')) {
      if (!activeMissionId) loadAccounts();
    }
    if (ev.type === 'activity' && ev.kind === 'auto_mission' && ev.status === 'completed') {
      if (!activeMissionId || ev.mission_id !== activeMissionId) {
        loadAccounts();
      }
    }
  }

  // ── Mission View ───────────────────────────────────────────────
  async function loadMission(mid) {
    activeMissionId = mid;
    accountsSection.style.display = 'none';
    mv.style.display = 'block';
    missionState = { matches: [], deposited: 0, approved: 0, failed: 0, status: 'pending' };
    renderMission();

    try {
      const res = await fetch('/api/deposits/auto/' + mid + '/status');
      if (res.ok) {
        const d = await res.json();
        missionState.status = d.status || 'pending';
        missionState.deposited = d.total_deposited || 0;
        missionState.approved = d.total_approved || 0;
        missionState.failed = d.total_failed || 0;
        try {
          const ms = typeof d.matches === 'string' ? JSON.parse(d.matches) : (d.matches || []);
          missionState.matches = ms;
        } catch (_) {}
        renderMission();
      }
    } catch (_) {}
  }

  function onMissionEvent(ev) {
    if (!missionState) missionState = { matches: [], deposited: 0, approved: 0, failed: 0, status: 'pending' };
    switch (ev.status) {
      case 'started':
      case 'matching':
        missionState.status = 'matching';
        missionState.sub = 'Buscando cuentas' + (ev.accounts ? ' · ' + ev.accounts + ' candidatas' : '…');
        missionState.pct = 15;
        break;
      case 'logging_in':
        missionState.status = 'matching';
        missionState.sub = '🔑 Sesión: <span class="email">' + shortEmail(ev.email) + '</span> (' + (ev.current || 1) + '/' + (ev.total || '…') + ')';
        missionState.pct = Math.min(70, 15 + ((ev.current || 1) / Math.max(ev.total || 1, 1)) * 30);
        break;
      case 'cooldown':
        missionState.status = 'matching';
        missionState.sub = '⏳ ' + shortEmail(ev.email) + ' enfriando → siguiente…';
        break;
      case 'match':
        missionState.status = 'matching';
        missionState.matches.push({ email: ev.email, card_tail: ev.card_tail });
        missionState.sub = '✅ <span class="email">' + shortEmail(ev.email) + '</span> ↔ ' + (ev.card_tail || '');
        missionState.pct = Math.min(85, 25 + missionState.matches.length * 15);
        break;
      case 'awaiting_confirmation':
        missionState.status = 'awaiting_confirmation';
        missionState.sub = '⚠️ Listo para confirmar llenado';
        break;
      case 'scheduling':
        missionState.status = 'scheduling';
        if (ev.completed != null) {
          const total = ev.total || 9;
          missionState.sub = 'Acreditado ✓ · <span class="email">' + shortEmail(ev.email) + '</span> · ' + ev.completed + '/' + total;
          missionState.pct = Math.min(95, 30 + (ev.completed / Math.max(total, 1)) * 70);
          missionState.schedDone = ev.completed;
          missionState.schedTotal = total;
          if (ev.completed < total) startCountdown(60);
        } else if (ev.aborted) {
          missionState.sub = '❌ <span class="email">' + shortEmail(ev.email) + '</span> no jaló (' + ev.aborted + ')';
        } else {
          missionState.sub = '¡Match! Depósitos cada 60s' + (ev.matches ? ' · ' + ev.matches + ' cuentas' : '');
          missionState.pct = 30;
        }
        break;
      case 'completed':
        clearCountdown();
        missionState.status = 'completed';
        missionState.deposited = ev.deposited || missionState.deposited;
        missionState.approved = ev.approved || missionState.approved;
        missionState.failed = ev.failed || missionState.failed;
        missionState.pct = 100;
        missionState.sub = 'Completado';
        break;
      case 'cancelled':
        clearCountdown();
        missionState.status = 'cancelled';
        missionState.sub = 'Detenido por el operador';
        missionState.pct = missionState.pct || 50;
        break;
      case 'failed':
        clearCountdown();
        missionState.status = 'failed';
        missionState.sub = 'Falló' + (ev.reason ? ' · ' + ev.reason : '');
        missionState.pct = missionState.pct || 50;
        break;
    }
    renderMission();
  }

  function startCountdown(secs) {
    clearCountdown();
    let remaining = secs;
    missionState.countdown = remaining;
    renderMission();
    countdownTimer = setInterval(() => {
      remaining--;
      missionState.countdown = remaining;
      renderMission();
      if (remaining <= 0) clearCountdown();
    }, 1000);
  }

  function clearCountdown() {
    if (countdownTimer) { clearInterval(countdownTimer); countdownTimer = null; }
    if (missionState) missionState.countdown = null;
  }

  function renderMission() {
    if (!missionState) return;
    const s = missionState;
    const matchesHtml = (s.matches || []).map(m => {
      return '<div class="match-row">' +
        '<span class="match-icon">✅</span>' +
        '<span class="match-email">' + (m.email || '') + '</span>' +
        (m.clabe_stp ? '<span class="match-clabe">' + m.clabe_stp + '</span>' : '') +
        '</div>';
    }).join('');

    const cdHtml = s.countdown != null
      ? '<span class="mv-countdown"><span class="cd-dot"></span>' + s.countdown + 's</span>'
      : '';

    const summaryHtml = (s.status === 'completed' || s.status === 'failed' || s.status === 'cancelled')
      ? '<div class="mv-summary">' +
        '<div class="mv-stat"><div class="mv-stat-val">' + fmtMoney(s.deposited) + '</div><div class="mv-stat-lbl">Depositado</div></div>' +
        '<div class="mv-stat"><div class="mv-stat-val" style="color:var(--green-bright)">' + (s.approved || 0) + '</div><div class="mv-stat-lbl">Aprobados</div></div>' +
        '<div class="mv-stat"><div class="mv-stat-val" style="color:var(--red)">' + (s.failed || 0) + '</div><div class="mv-stat-lbl">Fallidos</div></div>' +
        '</div>'
      : '';

    const fillClass = s.status === 'scheduling' ? ' sched' : (s.status === 'failed' ? ' err' : '');

    mv.innerHTML =
      '<div class="mv-card">' +
        '<div class="mv-header">' +
          '<span class="mv-id">' + (activeMissionId || '?') + '</span>' +
          '<span class="mv-status ' + statusClass(s.status) + '">' + statusLabel(s.status) + '</span>' +
          cdHtml +
        '</div>' +
        '<div class="mv-progress-wrap">' +
          '<div class="mv-progress-bar"><div class="mv-progress-fill' + fillClass + '" style="width:' + (s.pct || 0) + '%"></div></div>' +
          '<div class="mv-sub">' + (s.sub || '') + '</div>' +
        '</div>' +
        (matchesHtml ? '<div class="mv-matches">' + matchesHtml + '</div>' : '') +
        summaryHtml +
        (s.status === 'completed' || s.status === 'failed' || s.status === 'cancelled'
          ? '<div style="margin-top:16px;display:flex;gap:8px">' +
            '<button class="btn btn-sm" id="btnGoAccounts">Ver mis cuentas →</button>' +
            '</div>'
          : '') +
      '</div>';

    const btnGo = $('#btnGoAccounts');
    if (btnGo) btnGo.addEventListener('click', exitMission);
  }

  function exitMission() {
    activeMissionId = null;
    missionState = null;
    clearCountdown();
    mv.style.display = 'none';
    mv.innerHTML = '';
    accountsSection.style.display = 'block';
    const url = new URL(window.location);
    url.searchParams.delete('match');
    url.searchParams.delete('mission');
    window.history.replaceState({}, '', url);
    loadAccounts();
  }

  // ── Accounts Grid ──────────────────────────────────────────────
  async function loadAccounts() {
    grid.innerHTML = '<div class="empty-msg">Cargando…</div>';
    try {
      const res = await fetch(apiUrl('/api/operator/my-accounts'));
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      if (!data.ok || !data.accounts || data.accounts.length === 0) {
        grid.innerHTML = '<div class="empty-msg">Aún no tienes cuentas con depósitos aprobados.<br>Cuando uses <code>/bet</code> y se depositen, aparecerán aquí.</div>';
        return;
      }
      grid.innerHTML = data.accounts.map(renderAccountCard).join('');
      bindAccountActions();
    } catch (err) {
      grid.innerHTML = '<div class="empty-msg" style="color:var(--red)">Error: ' + err.message + '</div>';
    }
  }

  function renderAccountCard(acc) {
    const balReal = parseFloat(acc.balance_real || 0).toFixed(2);
    const balBonos = parseFloat(acc.balance_bonos || 0).toFixed(2);
    const lastDep = acc.last_deposit_amount ? fmtMoney(acc.last_deposit_amount) : '—';
    const lastDate = acc.last_deposit_date ? new Date(acc.last_deposit_date).toLocaleDateString('es-MX', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }) : '';
    const grade = acc.grade || 'N/A';
    const gradeCls = grade.replace('+', '-plus');
    const clabeStp = acc.clabe_stp || '';
    const isLocked = acc.is_locked;

    const clabeHtml = clabeStp
      ? '<div class="clabe-box"><span class="clabe-code">' + clabeStp + '</span>' +
        '<button class="btn btn-sm copy-clabe">Copiar</button></div>'
      : '<div class="clabe-box" style="opacity:.6"><span class="clabe-code" style="color:var(--text-dim)">CLABE pendiente</span></div>';

    return '<div class="acc-card' + (isLocked ? ' locked' : '') + '" data-id="' + acc.id + '" data-email="' + (acc.email || '') + '">' +
      '<div class="acc-top">' +
        '<span class="acc-email">' + (acc.email || '') + '</span>' +
        '<span class="acc-grade ' + gradeCls + '">' + grade + '</span>' +
      '</div>' +
      '<div class="acc-balance">' + fmtMoney(balReal) + ' <span class="cur">MXN</span></div>' +
      '<div class="acc-meta">' +
        '<div>• Bonos: ' + fmtMoney(balBonos) + '</div>' +
        '<div>• Último: ' + lastDep + (lastDate ? ' (' + lastDate + ')' : '') + '</div>' +
        (isLocked ? '<div class="acc-locked-badge">🔒 Bloqueada</div>' : '') +
      '</div>' +
      clabeHtml +
      '<div class="acc-actions">' +
        '<button class="btn btn-sm btn-primary btn-withdraw" data-bal="' + balReal + '">💸 Retirar</button>' +
        (isLocked ? '<button class="btn btn-sm btn-danger btn-release">🔓 Liberar</button>' : '') +
      '</div>' +
    '</div>';
  }

  function bindAccountActions() {
    document.querySelectorAll('.copy-clabe').forEach(btn => {
      btn.addEventListener('click', function () {
        const code = this.parentElement.querySelector('.clabe-code').textContent;
        navigator.clipboard.writeText(code).then(() => {
          this.textContent = '✓';
          setTimeout(() => { this.textContent = 'Copiar'; }, 2000);
        });
      });
    });

    document.querySelectorAll('.btn-withdraw').forEach(btn => {
      btn.addEventListener('click', function () {
        const card = this.closest('.acc-card');
        const id = parseInt(card.dataset.id);
        const email = card.dataset.email;
        const bal = parseFloat(this.dataset.bal);
        showWithdrawModal(id, email, bal);
      });
    });

    document.querySelectorAll('.btn-release').forEach(btn => {
      btn.addEventListener('click', async function () {
        const card = this.closest('.acc-card');
        const id = parseInt(card.dataset.id);
        this.disabled = true;
        this.textContent = '…';
        try {
          const res = await fetch(apiUrl('/api/operator/accounts/' + id + '/release'), { method: 'POST' });
          const d = await res.json();
          if (d.ok) {
            showToast('Cuenta liberada', 'ok');
            loadAccounts();
          } else {
            showToast('Error al liberar', 'err');
            this.disabled = false;
            this.textContent = '🔓 Liberar';
          }
        } catch (e) {
          showToast('Error: ' + e.message, 'err');
          this.disabled = false;
          this.textContent = '🔓 Liberar';
        }
      });
    });
  }

  // ── Withdraw Modal ─────────────────────────────────────────────
  function showWithdrawModal(accountId, email, balance) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML =
      '<div class="modal-box">' +
      '<div class="modal-title">💸 Retiro sin password</div>' +
      '<div class="modal-info">Cuenta: <span style="color:var(--accent);font-family:monospace">' + shortEmail(email) + '</span><br>' +
      'Saldo disponible: <b style="color:var(--green-bright)">' + fmtMoney(balance) + '</b></div>' +
      '<input type="number" class="modal-input" id="wdAmount" placeholder="Monto MXN" step="0.01" min="1" max="' + balance + '" autofocus>' +
      '<div class="modal-actions">' +
      '<button class="btn" id="wdCancel">Cancelar</button>' +
      '<button class="btn btn-primary" id="wdConfirm">Retirar</button>' +
      '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    const inp = overlay.querySelector('#wdAmount');
    const cancel = overlay.querySelector('#wdCancel');
    const confirm = overlay.querySelector('#wdConfirm');
    const close = () => overlay.remove();

    cancel.addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    inp.addEventListener('keydown', (e) => { if (e.key === 'Enter') confirm.click(); });

    confirm.addEventListener('click', async () => {
      const amount = parseFloat(inp.value);
      if (!amount || amount <= 0) { showToast('Monto inválido', 'err'); return; }
      if (amount > balance) { showToast('Saldo insuficiente', 'err'); return; }
      confirm.disabled = true;
      confirm.textContent = 'Procesando…';
      try {
        const res = await fetch(apiUrl('/api/operator/accounts/' + accountId + '/withdraw'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount }),
        });
        const d = await res.json();
        if (res.ok) {
          showToast('Retiro enviado: ' + (d.transactionId || ''), 'ok');
          close();
          loadAccounts();
        } else {
          const detail = d.detail || 'Error';
          showToast(detail, 'err');
          confirm.disabled = false;
          confirm.textContent = 'Retirar';
        }
      } catch (e) {
        showToast('Error: ' + e.message, 'err');
        confirm.disabled = false;
        confirm.textContent = 'Retirar';
      }
    });

    setTimeout(() => inp.focus(), 50);
  }

  // ── Init ───────────────────────────────────────────────────────
  async function init() {
    // Logout
    $('#logoutBtn').addEventListener('click', async () => {
      try { await fetch('/api/auth/logout', { method: 'POST' }); } catch (_) {}
      window.location.href = '/login';
    });

    btnAccounts.addEventListener('click', exitMission);

    // SA viendo /user/{id} (posiblemente el suyo propio, vía view_as): nunca
    // debe quedar atrapado sin volver a su dashboard — link directo siempre visible.
    try {
      const me = await (await fetch('/api/auth/me')).json();
      if (me.role === 'superadmin') {
        const back = document.createElement('a');
        back.className = 'btn btn-sm';
        back.href = '/dashboard';
        back.textContent = '← Dashboard';
        $('#logoutBtn').insertAdjacentElement('beforebegin', back);
        if (phRole) phRole.textContent = '· viendo como usuario';
      }
    } catch (_) {}

    // Check for ?match=ID in URL
    const params = new URLSearchParams(window.location.search);
    const matchId = params.get('match') || params.get('mission');

    if (matchId) {
      loadMission(matchId);
    } else {
      mv.style.display = 'none';
      accountsSection.style.display = 'block';
      loadAccounts();
    }

    connectSSE();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
