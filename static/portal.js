(function () {
  'use strict';

  const $ = (s) => document.querySelector(s);
  const mv = $('#missionView');
  const grid = $('#accountsGrid');
  const accountsSection = $('#accountsSection');
  const phRole = $('#phRole');

  let sse = null;
  let activeMissionId = null;
  let missionState = null;
  let userRole = null;

  // ── Withdraw status poll ──────────────────────────────────────
  // Versión simplificada del patrón de pantalla.js (WD_POLL_FAST_MS/SLOW_MS +
  // _startWithdrawPoll/_fetchWithdrawStatus): portal.js no necesita degradar a
  // "slow" ni panel de detalle, solo avisar cuando el retiro llega a terminal.
  const WD_POLL_FAST_MS = 15000;
  // Map, no variable única: un operador puede disparar retiros en más de una
  // cuenta antes de que el primero llegue a terminal (grid multi-cuenta). Con
  // un solo timer global, el segundo retiro mataba el poll del primero sin
  // avisar — el operador perdía la confirmación de aterrizaje justo en el
  // punto que la memoria del proyecto marca crítico (status:6 ≠ aterrizó).
  const wdPolls = new Map(); // accountId -> intervalId

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
    const region = $('#toastRegion') || document.body;
    const t = document.createElement('div');
    t.className = 'toast ' + (type || '');
    t.textContent = msg;
    t.setAttribute('role', 'status');
    region.appendChild(t);
    setTimeout(() => t.remove(), 3500);
  }

  function fmtMoney(n) {
    return '$' + (parseFloat(n || 0)).toFixed(2);
  }

  // El backend guarda last_deposit_date como "DD/MM/YYYY HH:MM" (formato MX
  // de BetMexico, ver app.py strptime "%d/%m/%Y %H:%M") o el sentinel 'N/A'.
  // new Date(str) lo interpreta como MM/DD/YYYY (ambiguo en JS): swapea
  // día/mes en silencio cuando día<=12, o tira "Invalid Date" cuando día>12.
  // Mismo parser que app.js (parseTs) para consistencia entre dashboard SA y portal.
  function parseMxDate(ts) {
    if (!ts || ts === 'N/A') return new Date(NaN);
    const mx = /^(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}):(\d{2})(?::(\d{2}))?$/.exec(ts);
    if (mx) { const [, dd, mm, yyyy, h, mi, ss] = mx; return new Date(+yyyy, +mm - 1, +dd, +h, +mi, +(ss || 0)); }
    const iso = /^(\d{4})-(\d{2})-(\d{2})[\sT](\d{2}):(\d{2}):(\d{2})/.exec(ts);
    if (iso) { const [, yyyy, mm, dd, h, mi, ss] = iso; return new Date(+yyyy, +mm - 1, +dd, +h, +mi, +ss); }
    return new Date(ts);
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
    if (ev.type !== 'activity') return;
    // Vista única (2026-08-05): #accountsSection ya NO se oculta mientras hay
    // misión activa (queda visible siempre, ver loadMission), así que el grid
    // debe seguir refrescándose en vivo aunque activeMissionId esté seteado.
    // El guard `!activeMissionId` de antes venía del modelo de dos pestañas
    // (983557f) donde el grid estaba oculto durante la misión — dejarlo aquí
    // congelaba saldo/lock/retiro del operador hasta que cerrara el resumen a mano.
    if (ev.kind === 'account_refreshed' || ev.kind === 'withdrawal' || ev.kind === 'withdrawal_status' || ev.kind === 'withdrawal_ready_changed') {
      loadAccounts();
      return;
    }
    if (ev.kind === 'auto_mission') {
      if (activeMissionId && ev.mission_id === activeMissionId) {
        onMissionEvent(ev);
        if (ev.status === 'completed' || ev.status === 'failed' || ev.status === 'cancelled') {
          loadAccounts();
        }
      } else if (ev.status === 'completed') {
        loadAccounts();
      }
    }
  }

  // ── Mission View ───────────────────────────────────────────────
  async function loadMission(mid) {
    activeMissionId = mid;
    accountsSection.style.display = 'block';
    mv.style.display = 'block';
    missionState = { matches: [], deposited: 0, approved: 0, failed: 0, status: 'pending' };
    renderMission();
    loadAccounts();

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

  // ── Interpolación de progreso (anti-detección) ──────────────────────────
  // El checkpoint real del backend llega en eventos discretos (cada match /
  // completed de scheduling); esto interpola visualmente ENTRE checkpoints con
  // requestAnimationFrame, para que el operador nunca vea el salto discreto
  // real (que delataría cadencia/monto). Robert, 2026-08-04.
  let _rafId = null;
  let _animFrom = 0;
  let _animTo = 0;
  let _animStart = 0;
  const ANIM_DURATION_MS = 2200; // tiempo de "viaje" visual entre checkpoints — NO ligado al intervalo real

  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

  function animateProgressTo(targetPct, onFrame) {
    if (_rafId) cancelAnimationFrame(_rafId);
    _animFrom = missionState ? (missionState.displayPct || 0) : 0;
    _animTo = Math.max(_animFrom, targetPct); // nunca retrocede visualmente
    _animStart = performance.now();
    // pct sigue guardando el checkpoint real (lo usan los fallbacks de
    // cancelled/failed); displayPct es lo único que se pinta.
    if (missionState) missionState.pct = targetPct;
    // Pestaña en segundo plano: el navegador congela requestAnimationFrame, así
    // que animar dejaría la tarjeta entera sin repintar (sub, matches, estado)
    // hasta que el operador vuelva. Nadie está viendo la transición ahí, así
    // que se salta la interpolación y se pinta el estado real de una.
    if (document.hidden) {
      if (missionState) missionState.displayPct = _animTo;
      onFrame();
      return;
    }
    let first = true;
    function step(now) {
      const elapsed = now - _animStart;
      const t = Math.min(1, elapsed / ANIM_DURATION_MS);
      const val = _animFrom + (_animTo - _animFrom) * easeOutCubic(t);
      if (missionState) missionState.displayPct = val;
      // Re-render completo solo en el primer y el último frame; los frames
      // intermedios parchan el ancho de la barra directamente para no
      // reconstruir la tarjeta entera 60 veces por segundo.
      const fill = mv.querySelector('.mv-progress-fill');
      if (first || t >= 1 || !fill) { onFrame(); first = false; }
      else { fill.style.width = val + '%'; }
      if (t < 1) { _rafId = requestAnimationFrame(step); } else { _rafId = null; }
    }
    _rafId = requestAnimationFrame(step);
  }

  function stopProgressAnim() {
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
  }

  function onMissionEvent(ev) {
    if (!missionState) missionState = { matches: [], deposited: 0, approved: 0, failed: 0, status: 'pending' };
    switch (ev.status) {
      case 'started':
      case 'matching':
        missionState.status = 'matching';
        missionState.sub = 'Buscando cuentas' + (ev.accounts ? ' · ' + ev.accounts + ' candidatas' : '…');
        animateProgressTo(15, renderMission);
        return;
      case 'logging_in':
        missionState.status = 'matching';
        missionState.sub = '🔑 Sesión: <span class="email">' + shortEmail(ev.email) + '</span> (' + (ev.current || 1) + '/' + (ev.total || '…') + ')';
        animateProgressTo(Math.min(70, 15 + ((ev.current || 1) / Math.max(ev.total || 1, 1)) * 30), renderMission);
        return;
      case 'cooldown':
        missionState.status = 'matching';
        missionState.sub = '⏳ ' + shortEmail(ev.email) + ' enfriando → siguiente…';
        break;
      case 'match':
        missionState.status = 'matching';
        missionState.matches.push({ email: ev.email, card_tail: ev.card_tail });
        missionState.sub = '✅ <span class="email">' + shortEmail(ev.email) + '</span> ↔ ' + (ev.card_tail || '');
        animateProgressTo(Math.min(85, 25 + missionState.matches.length * 15), renderMission);
        return;
      case 'awaiting_confirmation':
        missionState.status = 'awaiting_confirmation';
        missionState.sub = '⚠️ Listo para confirmar llenado';
        break;
      case 'scheduling':
        missionState.status = 'scheduling';
        if (ev.completed != null) {
          const total = ev.total || 9;
          missionState.sub = 'Acreditado ✓ · <span class="email">' + shortEmail(ev.email) + '</span> · ' + ev.completed + '/' + total;
          missionState.schedDone = ev.completed;
          missionState.schedTotal = total;
          if (ev.completed < total) startProcessingPulse();
          else clearProcessingPulse();
          animateProgressTo(Math.min(95, 30 + (ev.completed / Math.max(total, 1)) * 70), renderMission);
          return;
        } else if (ev.aborted) {
          missionState.sub = '❌ <span class="email">' + shortEmail(ev.email) + '</span> no jaló (' + ev.aborted + ')';
        } else {
          // No revelar cadencia real (Robert, 2026-08-04): nada de "cada Ns" ni
          // montos por depósito — solo que el proceso está en curso.
          missionState.sub = '¡Match! Depositando' + (ev.matches ? ' · ' + ev.matches + ' cuentas' : '');
          animateProgressTo(30, renderMission);
          return;
        }
        break;
      case 'completed':
        clearProcessingPulse();
        missionState.status = 'completed';
        missionState.deposited = ev.deposited || missionState.deposited;
        missionState.approved = ev.approved || missionState.approved;
        missionState.failed = ev.failed || missionState.failed;
        missionState.sub = 'Completado';
        animateProgressTo(100, renderMission);
        return;
      case 'cancelled':
        clearProcessingPulse();
        missionState.status = 'cancelled';
        missionState.sub = 'Detenido por el operador';
        missionState.pct = missionState.pct || 50;
        break;
      case 'failed':
        clearProcessingPulse();
        missionState.status = 'failed';
        missionState.sub = 'Falló' + (ev.reason ? ' · ' + ev.reason : '');
        missionState.pct = missionState.pct || 50;
        break;
    }
    renderMission();
  }

  // Pulso "en proceso" — a propósito SIN número de segundos ni timer atado al
  // intervalo real (Robert, 2026-08-04): el countdown exacto de 60s dejaba ver
  // la cadencia real de depósitos al operador. Solo un indicador visual de que
  // sigue trabajando, desacoplado de cualquier temporizador real.
  function startProcessingPulse() {
    if (missionState) missionState.processing = true;
    renderMission();
  }

  function clearProcessingPulse() {
    if (missionState) missionState.processing = false;
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

    // Sin número: un pulso visual de "sigue trabajando" sin revelar cadencia real.
    const cdHtml = s.processing
      ? '<span class="mv-countdown"><span class="cd-dot"></span>en curso…</span>'
      : '';

    const summaryHtml = (s.status === 'completed' || s.status === 'failed' || s.status === 'cancelled')
      ? '<div class="mv-summary">' +
        '<div class="mv-stat"><div class="mv-stat-val">' + fmtMoney(s.deposited) + '</div><div class="mv-stat-lbl">Depositado</div></div>' +
        '<div class="mv-stat"><div class="mv-stat-val" style="color:var(--green-bright)">' + (s.approved || 0) + '</div><div class="mv-stat-lbl">Cuentas Listas</div></div>' +
        '</div>'
      : '';

    const fillClass = s.status === 'scheduling' ? ' sched' : (s.status === 'failed' ? ' err' : '');

    mv.innerHTML =
      '<div class="mv-card">' +
        '<div class="mv-header">' +
          '<span class="mv-status ' + statusClass(s.status) + '">' + statusLabel(s.status) + '</span>' +
          cdHtml +
        '</div>' +
        '<div class="mv-progress-wrap">' +
          '<div class="mv-progress-bar"><div class="mv-progress-fill' + fillClass + '" style="width:' + (s.displayPct != null ? s.displayPct : (s.pct || 0)) + '%"></div></div>' +
          '<div class="mv-sub">' + (s.sub || '') + '</div>' +
        '</div>' +
        (matchesHtml ? '<div class="mv-matches">' + matchesHtml + '</div>' : '') +
        summaryHtml +
        (s.status === 'completed' || s.status === 'failed' || s.status === 'cancelled'
          ? '<div style="margin-top:16px;display:flex;gap:8px">' +
            '<button class="btn btn-sm" id="btnGoAccounts">Ocultar resumen ✕</button>' +
            '</div>'
          : '') +
      '</div>';

    const btnGo = $('#btnGoAccounts');
    if (btnGo) btnGo.addEventListener('click', exitMission);
  }

  function exitMission() {
    stopProgressAnim();
    activeMissionId = null;
    missionState = null;
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
    const _lastDateObj = parseMxDate(acc.last_deposit_date);
    const lastDate = isNaN(_lastDateObj.getTime()) ? '' : _lastDateObj.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    const grade = acc.grade || 'N/A';
    const gradeCls = grade.replace('+', '-plus');
    const clabeStp = acc.clabe_stp || '';
    const isLocked = acc.is_locked;

    const clabeHtml = clabeStp
      ? '<div class="clabe-box"><span class="clabe-code">' + clabeStp + '</span>' +
        '<button class="btn btn-sm copy-clabe">Copiar</button></div>'
      : '<div class="clabe-box" style="opacity:.6"><span class="clabe-code" style="color:var(--text-dim)">CLABE pendiente</span></div>';

    // acc.curp llega como sentinel string 'N/A' cuando BetMexico no lo tiene
    // (no null/undefined) — 'N/A' es truthy en JS, así que un check ingenuo
    // imprime literalmente "CURP: N/A" al operador en vez de ocultar la línea.
    const curpHtml = (acc.curp && acc.curp !== 'N/A') ? '<div>• CURP: ' + acc.curp + '</div>' : '';
    const wdInstHtml = acc.withdrawal_ready
      ? '<div>• Retiro: <span style="color:var(--accent)">' + (acc.withdrawal_institution || 'Aprobado') + '</span></div>'
      : '<div style="color:var(--text-dim)">• Retiro: esperando SPEI…</div>';

    // Retirar exigía SOLO withdrawal_ready — quedaba clickeable con saldo $0.00/
    // negativo (no hay nada que retirar). Robert, 2026-08-04, campo real: "retirar
    // esta disponible aun sin saldo". Gate real = SPEI aprobado Y saldo > 0.
    const wdDisabledReason = !acc.withdrawal_ready
      ? 'Esperando confirmación de SPEI en BetMexico'
      : (parseFloat(balReal) <= 0 ? 'Sin saldo disponible para retirar' : '');

    return '<div class="acc-card' + (isLocked ? ' locked' : '') + '" data-id="' + acc.id + '" data-email="' + (acc.email || '') + '">' +
      '<div class="acc-top">' +
        '<span class="acc-email">' + (acc.email || '') + '</span>' +
        '<span class="acc-grade ' + gradeCls + '">' + grade + '</span>' +
      '</div>' +
      '<div class="acc-balance">' + fmtMoney(balReal) + ' <span class="cur">MXN</span></div>' +
      '<div class="acc-meta">' +
        (parseFloat(balBonos) > 0 ? '<div>• Bonos: ' + fmtMoney(balBonos) + '</div>' : '') +
        '<div>• Último: ' + lastDep + (lastDate ? ' (' + lastDate + ')' : '') + '</div>' +
        curpHtml +
        wdInstHtml +
        (isLocked ? '<div class="acc-locked-badge">🔒 Bloqueada</div>' : '') +
      '</div>' +
      clabeHtml +
      '<div class="acc-actions">' +
        '<button class="btn btn-sm btn-primary btn-withdraw"' +
          (wdDisabledReason ? ' disabled title="' + wdDisabledReason + '"' : '') +
          ' data-bal="' + balReal + '">💸 Retirar</button>' +
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

  function stopWithdrawPoll(accountId) {
    const t = wdPolls.get(accountId);
    if (t) { clearInterval(t); wdPolls.delete(accountId); }
  }

  async function fetchWithdrawStatus(accountId, txId) {
    try {
      const res = await fetch(apiUrl('/api/accounts/' + accountId + '/withdraw/status/' + txId));
      if (!res.ok) return;
      const st = await res.json();
      const terminal = st.status === 'successful' || st.status === 'completed' || st.status === 'failed';
      if (terminal) {
        stopWithdrawPoll(accountId);
        // bug#2 (memoria del proyecto): status:6 de BetMexico != aterrizó en el
        // banco. Mismo copy que pantalla.js (SA) — nunca "liberado"/"entregado".
        if (st.status === 'failed') {
          showToast('❌ Retiro falló', 'err');
        } else {
          showToast('✅ Retiro procesado — confirma en tu banco', 'ok');
        }
        const alerts = st.alerts || {};
        if (alerts.gatewayMismatch) {
          showToast('⚠️ BetMexico mandó el retiro a TARJETA, no a SPEI', 'err');
        }
        if (alerts.digitsMismatch) {
          showToast('⚠️ El retiro fue a dígitos distintos a la cuenta esperada', 'err');
        }
        loadAccounts();
      }
    } catch (_) { /* best-effort, el próximo tick reintenta */ }
  }

  function startWithdrawPoll(accountId, txId) {
    stopWithdrawPoll(accountId);
    fetchWithdrawStatus(accountId, txId);
    const t = setInterval(() => fetchWithdrawStatus(accountId, txId), WD_POLL_FAST_MS);
    wdPolls.set(accountId, t);
  }

  // ── Withdraw Modal ─────────────────────────────────────────────
  function showWithdrawModal(accountId, email, balance) {
    const trigger = document.activeElement;
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML =
      '<div class="modal-box">' +
      '<div class="modal-title">💸 Retirar</div>' +
      '<div class="modal-info">Cuenta: <span style="color:var(--accent);font-family:monospace">' + shortEmail(email) + '</span><br>' +
      'Saldo disponible: <b style="color:var(--green-bright)">' + fmtMoney(balance) + '</b></div>' +
      '<input type="number" class="modal-input" id="wdAmount" placeholder="Monto MXN" step="0.01" min="0.01" max="' + balance + '" autofocus>' +
      '<div class="modal-actions">' +
      '<button class="btn" id="wdCancel">Cancelar</button>' +
      '<button class="btn btn-primary" id="wdConfirm">Retirar</button>' +
      '</div>' +
      '</div>';
    document.body.appendChild(overlay);

    const inp = overlay.querySelector('#wdAmount');
    const cancel = overlay.querySelector('#wdCancel');
    const confirm = overlay.querySelector('#wdConfirm');
    const close = () => {
      overlay.remove();
      document.removeEventListener('keydown', onKeydown);
      if (trigger && typeof trigger.focus === 'function') trigger.focus();
    };
    const onKeydown = (e) => { if (e.key === 'Escape') close(); };

    cancel.addEventListener('click', close);
    overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    document.addEventListener('keydown', onKeydown);
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
          if (d.transactionId) startWithdrawPoll(accountId, d.transactionId);
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

  // ── auto-reload por versión ──────────────────────────────────────
  // Mismo mecanismo que el dashboard SA (app.js): una pestaña del portal
  // abierta desde antes de un deploy no vuelve a pedir portal.html sola,
  // así que nunca ve el JS/CSS nuevo hasta un Ctrl+Shift+R manual. Compara
  // la versión servida al cargar contra la actual del server y se recarga.
  //
  // A diferencia de app.js, aquí SÍ puede haber una misión /bet en curso
  // (progress bar + SSE en vivo) — recargar a media misión sería el mismo
  // tipo de bug que este fix corrige, solo que al revés (interrupción en
  // vez de staleness). Se pospone mientras la misión no llegue a un status
  // terminal; el siguiente check (5min o próximo visibilitychange) reintenta.
  function _missionActive() {
    return !!(activeMissionId && missionState &&
      !['completed', 'failed', 'cancelled'].includes(missionState.status));
  }

  async function _checkVersion() {
    if (!window.BMX_VERSION || _missionActive()) return;
    try {
      const r = await fetch('/api/version', { cache: 'no-store' });
      const { v } = await r.json();
      if (v && v !== window.BMX_VERSION) {
        showToast('🔄 Nueva versión — actualizando…', 'ok');
        setTimeout(() => location.reload(), 1200);
      }
    } catch {}
  }
  document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible') _checkVersion();
  });
  setInterval(_checkVersion, 5 * 60_000);
})();
