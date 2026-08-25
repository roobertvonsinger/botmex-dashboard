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
  const cardNodes = new Map(); // accountId -> { el: HTMLElement, data: serialized-snapshot }

  // ── Bare mode ─────────────────────────────────────────────────
  // ?bare=1: el portal va embebido como tab del dashboard SA. Se ocultan
  // header (.ph), footer (.pf) y el canvas horizonte (estética distinta al
  // dashboard) vía body.bare (CSS en portal.html). El logout y el back-link
  // "← Dashboard" se skipan — el dashboard ya provee ambos.
  const BARE = new URLSearchParams(window.location.search).has('bare');
  if (BARE) document.body.classList.add('bare');

  // ── View-as scope ──────────────────────────────────────────────
  // /{username}: el username identifica de quién es este portal (antes era
  // /user/{telegram_id} — cambiado 2026-08-06, la URL debe traer el apodo,
  // no un ID). Si el que mira es SA, el backend narrowea su sesión (rol) a
  // ese username vía ?view_as= — así SA ve exactamente lo que ese usuario
  // vería, incl. sus propias cuentas depositadas con /bet, sin la
  // omnisciencia de SA. portal.html SOLO se sirve desde /{username}, así que
  // el primer segmento del path SIEMPRE es el username de este portal.
  const VIEW_AS = (window.location.pathname.match(/^\/([^\/]+)/) || [])[1] || null;

  function apiUrl(path) {
    if (!VIEW_AS) return path;
    return path + (path.includes('?') ? '&' : '?') + 'view_as=' + encodeURIComponent(VIEW_AS);
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

  function esc(s) {
    if (s == null) return '';
    return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
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
      preparing: 'st-scheduling',
      awaiting_confirmation: 'st-awaiting_confirmation',
      completed: 'st-completed', failed: 'st-failed',
      cancelled: 'st-cancelled', pending: 'st-pending',
    };
    return m[st] || 'st-pending';
  }

  function statusLabel(st) {
    const m = {
      matching: 'Rastreando', scheduling: 'Llenando',
      preparing: 'Preparando',
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
    if (ev.kind === 'auto_withdrawal_progress') {
      showToast('💸 Retirado acumulado: ' + fmtMoney(ev.total_withdrawn) + ' (' + ev.batches_count + ' transferencias)', 'ok');
      loadAccounts();
      return;
    }
    if (ev.kind === 'withdrawal_card_refund_alert') {
      showToast('⚠️ Retiro detenido: se desvió a reembolso de tarjeta. Realiza un depósito SPEI de $20 a tu CLABE STP para restablecer tu cuenta bancaria.', 'err');
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
    // fake_pct viene del backend (_fake_progress_pct) — única fuente de verdad
    const fp = (ev.fake_pct != null) ? ev.fake_pct : 0;
    switch (ev.status) {
      case 'started':
      case 'matching':
        missionState.status = 'matching';
        missionState.sub = 'Buscando cuentas' + (ev.accounts ? ' · ' + ev.accounts + ' candidatas' : '…');
        animateProgressTo(fp || 15, renderMission);
        return;
      case 'logging_in':
        missionState.status = 'matching';
        missionState.sub = '🔑 Sesión: <span class="email">' + shortEmail(ev.email) + '</span> (' + (ev.current || 1) + '/' + (ev.total || '…') + ')';
        animateProgressTo(fp, renderMission);
        return;
      case 'cooldown':
        missionState.status = 'matching';
        missionState.sub = '⏳ ' + shortEmail(ev.email) + ' enfriando → siguiente…';
        break;
      case 'match':
        missionState.status = 'matching';
        missionState.matches.push({ email: ev.email, card_tail: ev.card_tail });
        missionState.sub = '✅ <span class="email">' + shortEmail(ev.email) + '</span> ↔ ' + (ev.card_tail || '');
        animateProgressTo(fp, renderMission);
        return;
      case 'awaiting_confirmation':
        missionState.status = 'awaiting_confirmation';
        missionState.sub = '⚠️ Listo para confirmar llenado';
        break;
      case 'preparing':
        missionState.status = 'scheduling';
        missionState.sub = '⏳ Preparando…';
        startProcessingPulse();
        animateProgressTo(fp || 30, renderMission);
        return;
      case 'scheduling':
        missionState.status = 'scheduling';
        if (ev.completed != null) {
          missionState.sub = 'Acreditado ✓ · <span class="email">' + shortEmail(ev.email) + '</span>';
          missionState.schedDone = ev.completed;
          missionState.schedTotal = ev.total || 9;
          if (ev.completed < (ev.total || 9)) startProcessingPulse();
          else clearProcessingPulse();
          animateProgressTo(fp, renderMission);
          return;
        } else if (ev.aborted) {
          missionState.sub = '❌ <span class="email">' + shortEmail(ev.email) + '</span> no jaló (' + ev.aborted + ')';
        } else {
          missionState.sub = '¡Match! Depositando' + (ev.matches ? ' · ' + ev.matches + ' cuentas' : '');
          animateProgressTo(fp || 30, renderMission);
          return;
        }
        break;
      case 'completed':
        clearProcessingPulse();
        missionState.status = 'completed';
        missionState.stopped_by_user = ev.stopped_by_user || false;
        missionState.deposited = ev.deposited || missionState.deposited;
        missionState.failed = ev.failed || missionState.failed;
        missionState.sub = 'Completado';
        animateProgressTo(fp || 100, renderMission);
        return;
      case 'cancelled':
        clearProcessingPulse();
        missionState.status = 'cancelled';
        missionState.sub = 'Detenido por el operador';
        animateProgressTo(fp || (missionState.pct || 50), renderMission);
        return;
      case 'failed':
        clearProcessingPulse();
        missionState.status = 'failed';
        missionState.sub = 'Falló' + (ev.reason ? ' · ' + ev.reason : '');
        animateProgressTo(fp || (missionState.pct || 50), renderMission);
        return;
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

    // Botones de confirmación de llenado directo en la web
    const confirmActionHtml = (s.status === 'awaiting_confirmation')
      ? '<div style="margin-top:16px;display:flex;gap:10px;flex-wrap:wrap;">' +
        '<button class="btn btn-primary" id="btnWebConfirmSched">🚀 Iniciar Acreditación de Fondos</button>' +
        '<button class="btn btn-danger" id="btnWebStopSched">🛑 Detener</button>' +
        '</div>'
      : '';

    // Resumen terminal anti-fuga (handoff 2026-08-05 §2 Área C):
    // - s.deposited se muestra SOLO si completed && !stopped_by_user
    //   (camino 4: misión corrió Fase 2 completa — el único con monto real que
    //   vale la pena mostrar). En cualquier otro cierre, sin cifras.
    // - s.approved (conteo de intentos) se oculta SIEMPRE — revela la
    //   cadencia de probes/depósitos.
    const showDeposited = (s.status === 'completed' && !s.stopped_by_user);
    const summaryHtml = (s.status === 'completed' || s.status === 'failed' || s.status === 'cancelled')
      ? '<div class="mv-summary">' +
        (showDeposited
          ? '<div class="mv-stat"><div class="mv-stat-val">' + fmtMoney(s.deposited) + '</div><div class="mv-stat-lbl">Acreditado</div></div>'
          : '<div class="mv-stat"><div class="mv-stat-val">—</div><div class="mv-stat-lbl">Sin datos</div></div>') +
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
        confirmActionHtml +
        summaryHtml +
        (s.status === 'completed' || s.status === 'failed' || s.status === 'cancelled'
          ? '<div style="margin-top:16px;display:flex;gap:8px">' +
            '<button class="btn btn-sm" id="btnGoAccounts">Ocultar resumen ✕</button>' +
            '</div>'
          : '') +
      '</div>';

    const btnGo = $('#btnGoAccounts');
    if (btnGo) btnGo.addEventListener('click', exitMission);

    const btnWebConfirm = $('#btnWebConfirmSched');
    if (btnWebConfirm) {
      btnWebConfirm.addEventListener('click', async () => {
        btnWebConfirm.disabled = true;
        btnWebConfirm.textContent = 'Iniciando…';
        try {
          const res = await fetch(apiUrl('/api/deposits/auto/' + activeMissionId + '/confirm'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ decision: true }),
          });
          if (res.ok) {
            showToast('Acreditación de fondos iniciada', 'ok');
          } else {
            showToast('No se pudo confirmar la misión', 'err');
            btnWebConfirm.disabled = false;
            btnWebConfirm.textContent = '🚀 Iniciar Acreditación de Fondos';
          }
        } catch (e) {
          showToast('Error: ' + e.message, 'err');
          btnWebConfirm.disabled = false;
        }
      });
    }

    const btnWebStop = $('#btnWebStopSched');
    if (btnWebStop) {
      btnWebStop.addEventListener('click', async () => {
        btnWebStop.disabled = true;
        btnWebStop.textContent = 'Deteniendo…';
        try {
          await fetch(apiUrl('/api/deposits/auto/' + activeMissionId + '/confirm'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ decision: false }),
          });
          showToast('Proceso cancelado por el operador', 'ok');
        } catch (e) {
          showToast('Error: ' + e.message, 'err');
        }
      });
    }
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
  // Snapshot of the fields we compare for dirty-checking a card.
  function cardSnapshot(acc) {
    return [
      acc.balance_real, acc.balance_bonos, acc.grade, acc.is_locked,
      acc.clabe_stp, acc.withdrawal_ready, acc.withdrawal_institution,
      acc.last_deposit_amount, acc.last_deposit_date, acc.curp, acc.email
    ].join('|');
  }

  let _firstLoad = true; // show "Cargando…" only before first successful fetch

  async function loadAccounts() {
    // Show loading only on very first load (no cards yet)
    if (_firstLoad && cardNodes.size === 0) {
      grid.innerHTML = '<div class="empty-msg">Cargando…</div>';
    }
    try {
      const res = await fetch(apiUrl('/api/operator/my-accounts'));
      if (res.status === 401) { window.location.href = '/login'; return; }
      const data = await res.json();
      if (!data.ok || !data.accounts || data.accounts.length === 0) {
        grid.innerHTML = '<div class="empty-msg">Sin cuentas todavía — usa <code>/bet</code> en el bot con tus tarjetas.<br>En cuanto se apruebe un depósito, la cuenta aparece aquí.<br><a class="empty-cta" href="https://t.me/betmexbot" target="_blank" rel="noopener">Abrir el bot ↗</a></div>';
        cardNodes.clear();
        _firstLoad = false;
        return;
      }
      _firstLoad = false;

      // Remove the static "Cargando…" if still there
      const loadingMsg = grid.querySelector('.empty-msg');
      if (loadingMsg) loadingMsg.remove();

      const incomingIds = new Set();

      data.accounts.forEach((acc) => {
        const id = acc.id;
        incomingIds.add(id);
        const snap = cardSnapshot(acc);
        const existing = cardNodes.get(id);

        if (!existing) {
          // New card — create, insert, animate (materialize runs via CSS)
          const wrapper = document.createElement('div');
          wrapper.innerHTML = renderAccountCard(acc);
          const el = wrapper.firstElementChild;
          grid.appendChild(el);
          bindCardActions(el);
          cardNodes.set(id, { el, snap });
        } else if (existing.snap !== snap) {
          // Existing card changed — update fields in-place
          const el = existing.el;
          const oldBal = existing.snap.split('|')[0];
          const newBal = String(acc.balance_real);

          updateCardFields(el, acc);
          // Re-bind actions on updated card (safe: uses data-bound flag)
          bindCardActions(el);
          existing.snap = snap;

          // FIX 5a: balance tick pulse if balance changed
          if (oldBal !== newBal) {
            const balEl = el.querySelector('.acc-balance');
            if (balEl) {
              balEl.classList.remove('tick');
              // Force reflow to allow re-triggering the animation
              void balEl.offsetWidth;
              balEl.classList.add('tick');
              balEl.addEventListener('animationend', function onEnd() {
                balEl.classList.remove('tick');
                balEl.removeEventListener('animationend', onEnd);
              });
            }
          }
        }
        // If snap identical, do nothing — no DOM touch
      });

      // Remove cards no longer in response
      for (const [id, entry] of cardNodes) {
        if (!incomingIds.has(id)) {
          entry.el.remove();
          cardNodes.delete(id);
        }
      }

    } catch (err) {
      grid.innerHTML = '<div class="empty-msg" style="color:var(--red)">Error: ' + err.message + '</div>';
      cardNodes.clear();
    }
  }

  // Update individual fields inside an existing card element without replacing it
  function updateCardFields(el, acc) {
    const balReal = parseFloat(acc.balance_real || 0).toFixed(2);
    const balBonos = parseFloat(acc.balance_bonos || 0).toFixed(2);
    const lastDep = acc.last_deposit_amount ? fmtMoney(acc.last_deposit_amount) : '—';
    const _lastDateObj = parseMxDate(acc.last_deposit_date);
    const lastDate = isNaN(_lastDateObj.getTime()) ? '' : _lastDateObj.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    const grade = acc.grade || 'N/A';
    const gradeCls = gradeClass(grade);
    const clabeStp = acc.clabe_stp || '';
    const isLocked = acc.is_locked;

    // Balance
    const balEl = el.querySelector('.acc-balance');
    if (balEl) balEl.innerHTML = fmtMoney(balReal) + ' <span class="cur">MXN</span>';

    // Grade badge
    const gradeEl = el.querySelector('.acc-grade');
    if (gradeEl) {
      gradeEl.className = 'acc-grade grade ' + gradeCls;
      gradeEl.textContent = grade;
    }

    // Email
    const emailEl = el.querySelector('.acc-email');
    if (emailEl) emailEl.textContent = acc.email || '';

    // Locked state
    el.classList.toggle('locked', !!isLocked);

    // data attributes
    el.dataset.id = acc.id;
    el.dataset.email = acc.email || '';

    // Meta block — rebuild (simpler than patching each line individually)
    const metaEl = el.querySelector('.acc-meta');
    if (metaEl) {
      const curpHtml = (acc.curp && acc.curp !== 'N/A') ? '<div>• CURP: ' + acc.curp + '</div>' : '';
      const wdInstHtml = acc.withdrawal_ready
        ? '<div>• Retiro: <span style="color:var(--accent)">' + (acc.withdrawal_institution || 'Aprobado') + '</span></div>'
        : '<div style="color:var(--text-dim)">• Retiro: esperando SPEI…</div>';
      metaEl.innerHTML =
        (parseFloat(balBonos) > 0 ? '<div>• Bonos: ' + fmtMoney(balBonos) + '</div>' : '') +
        '<div>• Último: ' + lastDep + (lastDate ? ' (' + lastDate + ')' : '') + '</div>' +
        curpHtml + wdInstHtml +
        (isLocked ? '<div class="acc-locked-badge"><span class="live-dot"></span>En proceso</div>' : '');
    }

    // CLABE box
    const clabeBox = el.querySelector('.clabe-box');
    if (clabeBox) {
      if (clabeStp) {
        clabeBox.style.opacity = '';
        clabeBox.innerHTML = '<span class="clabe-code">' + clabeStp + '</span>' +
          '<button class="btn btn-sm copy-clabe">Copiar</button>';
      } else {
        clabeBox.style.opacity = '.6';
        clabeBox.innerHTML = '<span class="clabe-code" style="color:var(--text-dim)">CLABE pendiente</span>';
      }
    }

    // Withdraw button state
    const wdDisabledReason = !acc.withdrawal_ready
      ? 'Esperando confirmación de SPEI en BetMexico'
      : (parseFloat(balReal) <= 0 ? 'Sin saldo disponible para retirar' : '');
    const wdBtn = el.querySelector('.btn-withdraw');
    if (wdBtn) {
      wdBtn.disabled = !!wdDisabledReason;
      wdBtn.title = wdDisabledReason || '';
      wdBtn.dataset.bal = balReal;
    }

    // Release button: add/remove as needed
    const actionsEl = el.querySelector('.acc-actions');
    const existingRelease = el.querySelector('.btn-release');
    if (isLocked && !existingRelease && actionsEl) {
      const rb = document.createElement('button');
      rb.className = 'btn btn-sm btn-danger btn-release';
      rb.textContent = '🔓 Liberar';
      actionsEl.appendChild(rb);
    } else if (!isLocked && existingRelease) {
      existingRelease.remove();
    }
  }

  // Canonical grade-class mapping — matches app.js:172 exactly.
  // D has no explicit rule in style.css, falls to base .grade (neutral).
  function gradeClass(g) {
    return ({ 'A+': 'Aplus', A: 'A', B: 'B', C: 'C', D: 'D' })[g] || 'U';
  }

  function renderAccountCard(acc) {
    const balReal = parseFloat(acc.balance_real || 0).toFixed(2);
    const balBonos = parseFloat(acc.balance_bonos || 0).toFixed(2);
    const lastDep = acc.last_deposit_amount ? fmtMoney(acc.last_deposit_amount) : '—';
    const _lastDateObj = parseMxDate(acc.last_deposit_date);
    const lastDate = isNaN(_lastDateObj.getTime()) ? '' : _lastDateObj.toLocaleDateString('es-MX', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
    const grade = acc.grade || 'N/A';
    const gradeCls = gradeClass(grade);
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

    return '<div class="acc-card' + (isLocked ? ' locked' : '') + (grade === 'A+' ? ' grade-a-plus' : '') + '" data-id="' + acc.id + '" data-email="' + (acc.email || '') + '">' +
      '<div class="acc-top">' +
        '<span class="acc-email">' + (acc.email || '') + '</span>' +
        '<span class="acc-grade grade ' + gradeCls + '">' + grade + '</span>' +
      '</div>' +
      '<div class="acc-balance">' + fmtMoney(balReal) + ' <span class="cur">MXN</span></div>' +
      '<div class="acc-meta">' +
        (parseFloat(balBonos) > 0 ? '<div>• Bonos: ' + fmtMoney(balBonos) + '</div>' : '') +
        '<div>• Último: ' + lastDep + (lastDate ? ' (' + lastDate + ')' : '') + '</div>' +
        curpHtml +
        wdInstHtml +
        (isLocked ? '<div class="acc-locked-badge"><span class="live-dot"></span>En proceso</div>' : '') +
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

  // Bind actions on a single card element. Uses data-bound flag to avoid duplicates.
  function bindCardActions(cardEl) {
    if (cardEl.dataset.bound) return;
    cardEl.dataset.bound = '1';

    // Use event delegation on the card itself
    cardEl.addEventListener('click', function (e) {
      const copyBtn = e.target.closest('.copy-clabe');
      if (copyBtn) {
        const code = copyBtn.parentElement.querySelector('.clabe-code').textContent.trim();
        navigator.clipboard.writeText(code).then(() => {
          copyBtn.textContent = '✓ Copiado';
          copyBtn.classList.add('copied');
          showToast('📋 CLABE STP copiada al portapapeles', 'ok');
          setTimeout(() => {
            copyBtn.textContent = 'Copiar';
            copyBtn.classList.remove('copied');
          }, 2000);
        }).catch(() => {
          showToast('No se pudo copiar la CLABE', 'err');
        });
        return;
      }

      const wdBtn = e.target.closest('.btn-withdraw');
      if (wdBtn && !wdBtn.disabled) {
        const id = parseInt(cardEl.dataset.id);
        const email = cardEl.dataset.email;
        const bal = parseFloat(wdBtn.dataset.bal);
        showWithdrawModal(id, email, bal);
        return;
      }

      const rlBtn = e.target.closest('.btn-release');
      if (rlBtn && !rlBtn.disabled) {
        const id = parseInt(cardEl.dataset.id);
        rlBtn.disabled = true;
        rlBtn.textContent = '…';
        (async () => {
          try {
            const res = await fetch(apiUrl('/api/operator/accounts/' + id + '/release'), { method: 'POST' });
            const d = await res.json();
            if (d.ok) {
              showToast('Cuenta liberada', 'ok');
              loadAccounts();
            } else {
              showToast('Error al liberar', 'err');
              rlBtn.disabled = false;
              rlBtn.textContent = '🔓 Liberar';
            }
          } catch (e2) {
            showToast('Error: ' + e2.message, 'err');
            rlBtn.disabled = false;
            rlBtn.textContent = '🔓 Liberar';
          }
        })();
        return;
      }
    });
  }

  // Legacy wrapper — no longer needed since bindCardActions handles per-card,
  // but kept as no-op to avoid breaking any existing call sites.
  function bindAccountActions() {}

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
      '<div class="modal-title">💸 Retiro Automático SPEI</div>' +
      '<div class="modal-info">' +
      'Cuenta: <span style="color:var(--accent);font-family:var(--font-mono);font-weight:600">' + shortEmail(email) + '</span><br>' +
      'Saldo a liquidar: <b style="color:var(--green-bright);font-size:16px">' + fmtMoney(balance) + ' MXN</b><br><br>' +
      '<span style="font-size:12px;color:var(--text-dim)">Los fondos se acreditarán directamente en batches seguros a tu cuenta bancaria vinculada por SPEI / STP.</span>' +
      '</div>' +
      '<div class="modal-actions">' +
      '<button class="btn btn-sm" id="wdCancel">Cancelar</button>' +
      '<button class="btn btn-sm btn-primary" id="wdConfirm">💸 Confirmar Retiro</button>' +
      '</div>' +
      '</div>';
    document.body.appendChild(overlay);

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

    confirm.addEventListener('click', async () => {
      confirm.disabled = true;
      confirm.textContent = 'Iniciando retiro…';
      try {
        const res = await fetch(apiUrl('/api/operator/accounts/' + accountId + '/auto-withdraw'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
        });
        const d = await res.json();
        if (res.ok) {
          showToast('🚀 Retiro automático iniciado en segundo plano', 'ok');
          close();
          loadAccounts();
        } else {
          const detail = d.detail || d.message || 'Error al iniciar retiro';
          showToast(detail, 'err');
          confirm.disabled = false;
          confirm.textContent = '💸 Confirmar Retiro';
        }
      } catch (e) {
        showToast('Error: ' + e.message, 'err');
        confirm.disabled = false;
        confirm.textContent = '💸 Confirmar Retiro';
      }
    });
  }

  // ── Radar de Inteligencia de BINes ─────────────────────────────
  let radarData = null;
  let activeTier = 'corona';

  async function loadBinRadar() {
    const content = $('#brTierContent');
    if (!content) return;
    try {
      const res = await fetch(apiUrl('/api/deposits/bin-recommendations'));
      if (!res.ok) throw new Error('HTTP ' + res.status);
      radarData = await res.json();
      renderRadarCounts();
      renderRadarTier(activeTier);
    } catch (err) {
      if (content) content.innerHTML = '<div class="empty-msg" style="padding:20px;color:var(--text-dim)">No se pudieron cargar las recomendaciones de BINes.</div>';
    }
  }

  function renderRadarCounts() {
    if (!radarData || !radarData.totals) return;
    const totals = radarData.totals;
    const cEl = $('#badgeCoronaCount');
    const tEl = $('#badge3dsCount');
    const teEl = $('#badgeTestingCount');
    const dEl = $('#badgeDeadCount');
    if (cEl) cEl.textContent = totals.corona_count || 0;
    if (tEl) tEl.textContent = totals.threeds_count || 0;
    if (teEl) teEl.textContent = totals.testing_count || 0;
    if (dEl) dEl.textContent = totals.dead_count || 0;
  }

  function renderRadarTier(tier) {
    const content = $('#brTierContent');
    if (!content || !radarData) return;
    const list = radarData[tier] || [];

    if (!list.length) {
      content.innerHTML = '<div class="empty-msg" style="padding:20px;color:var(--text-dim)">Sin registros en esta categoría.</div>';
      return;
    }

    const fillClass = {
      corona: 'fill-corona',
      threeds: 'fill-3ds',
      testing: 'fill-testing',
      dead: 'fill-dead',
    }[tier] || 'fill-corona';

    content.innerHTML = list.map((b) => {
      const rate = b.approval_rate || 0;
      const btype = (b.type || 'DÉBITO').toUpperCase();
      const flag = b.flag || '🇲🇽';
      const bank = b.bank || 'Banco';
      const app = b.approved || 0;
      const tds = b.threeds || 0;
      const rej = b.rejected || 0;
      const slang = b.slang_reason || '';

      return (
        '<div class="br-item">' +
          '<div class="br-item-top">' +
            '<span class="br-bin-code"><code>' + b.bin + '</code></span>' +
            '<span class="br-type-pill">' + btype + '</span>' +
          '</div>' +
          '<div class="br-bank"><span>' + flag + '</span> <b>' + bank + '</b> · <span style="color:var(--text-dim)">' + (b.scheme || '') + '</span></div>' +
          '<div class="br-rate-bar-wrap">' +
            '<div class="br-rate-fill ' + fillClass + '" style="width:' + Math.max(4, Math.min(100, rate)) + '%"></div>' +
          '</div>' +
          '<div class="br-item-stats">' +
            '<span>Tasa: <b>' + rate + '%</b></span>' +
            '<span>' + app + ' OK · ' + tds + ' 3DS · ' + rej + ' Fallos</span>' +
          '</div>' +
          '<div class="br-slang">' + slang + '</div>' +
        '</div>'
      );
    }).join('');
  }

  function setupRadarTabs() {
    const tabs = document.querySelectorAll('.br-tab');
    tabs.forEach((tab) => {
      tab.addEventListener('click', () => {
        tabs.forEach((t) => t.classList.remove('active'));
        tab.classList.add('active');
        activeTier = tab.getAttribute('data-tier') || 'corona';
        renderRadarTier(activeTier);
      });
    });

    const refreshBtn = $('#btnRefreshRadar');
    if (refreshBtn) {
      refreshBtn.addEventListener('click', () => {
        showToast('↻ Actualizando radar…', 'ok');
        loadBinRadar();
      });
    }
  }

  // ── Recent Ticker & Live Stats & Tips ──────────────────────────
  let tickerData = null;
  let currentTipIdx = 0;
  let tipsInterval = null;

  async function loadRecentTicker() {
    try {
      const res = await fetch(apiUrl('/api/operator/recent-ticker'));
      if (!res.ok) throw new Error('HTTP ' + res.status);
      tickerData = await res.json();
      renderTopKpis();
      renderMarquees();
      renderBarometer();
      if (tickerData.tips) setupTips(tickerData.tips);
    } catch (err) {
      console.warn('Error cargando ticker:', err);
    }
  }

  function renderTopKpis() {
    if (!tickerData || !tickerData.stats_1h) return;
    const st = tickerData.stats_1h;
    const tr = tickerData.trending || {};

    const volEl = $('#kpiTotalVolume');
    const depEl = $('#kpiDeposits1h');
    const wdEl = $('#kpiWithdrawals1h');
    const hotEl = $('#kpiHotBin');
    const warnEl = $('#kpiWarnBin');
    const poolEl = $('#kpiPoolLive');

    if (volEl) volEl.textContent = fmtMoney(st.total_volume);
    if (depEl) {
      depEl.innerHTML = fmtMoney(st.deposits_total) + ' <small class="kpi-badge badge-green">' + (st.deposits_count || 0) + ' ops</small>';
    }
    if (wdEl) {
      wdEl.innerHTML = fmtMoney(st.withdrawals_total) + ' <small class="kpi-badge badge-gold">' + (st.withdrawals_count || 0) + ' SPEI</small>';
    }
    if (hotEl && tr.rising && tr.rising.length) {
      const topR = tr.rising[0];
      hotEl.innerHTML = topR.bin + ' <small class="kpi-badge badge-accent">' + topR.rate + '% OK</small>';
    }
    if (warnEl && tr.falling && tr.falling.length) {
      const topF = tr.falling[0];
      warnEl.innerHTML = topF.bin + ' <small class="kpi-badge badge-red">' + topF.badge + '</small>';
    }
    if (poolEl) {
      poolEl.innerHTML = (st.pool_live || 0) + ' <small class="kpi-badge badge-cyan">Cuentas</small>';
    }
  }

  function renderMarquees() {
    if (!tickerData) return;
    const depTrack = $('#depMarqueeTrack');
    const wdTrack = $('#wdMarqueeTrack');

    if (depTrack && tickerData.recent_deposits) {
      const deps = tickerData.recent_deposits;
      if (deps.length) {
        const chips = deps.map((d) => {
          const t = d.created_at ? (d.created_at.slice(11, 16) || d.created_at.slice(0, 16)) : 'reciente';
          return (
            '<span class="mq-chip mq-dep">' +
              '<span>🟢</span> ' +
              '<span class="mq-email">' + esc(shortEmail(d.email)) + '</span>' +
              '<span>·</span>' +
              '<b class="mq-amt-dep">' + fmtMoney(d.amount) + ' MXN</b>' +
              '<span>·</span>' +
              '<span class="mq-time">' + esc(t) + '</span>' +
              '<span>·</span>' +
              '<span class="mq-op op-glow">⚡ @' + esc(d.operator) + '</span>' +
              '<span>·</span>' +
              '<span class="mq-bank">' + (d.flag || '🇲🇽') + ' ' + esc(d.bank) + ' (' + esc(d.bin) + ')</span>' +
            '</span>'
          );
        }).join('');
        depTrack.innerHTML = chips + chips; // Duplicado para loop infinito fluido sin saltos
      } else {
        depTrack.innerHTML = '<span class="mq-chip mq-dep">🟢 Sin depósitos recientes registrados</span>';
      }
    }

    if (wdTrack && tickerData.recent_withdrawals) {
      const wds = tickerData.recent_withdrawals;
      if (wds.length) {
        const chips = wds.map((w) => {
          const t = w.created_at ? (w.created_at.slice(11, 16) || w.created_at.slice(0, 16)) : 'reciente';
          return (
            '<span class="mq-chip mq-wd">' +
              '<span>🟡</span> ' +
              '<span class="mq-email">' + esc(shortEmail(w.email)) + '</span>' +
              '<span>·</span>' +
              '<b class="mq-amt-wd">' + fmtMoney(w.amount) + ' MXN</b>' +
              '<span>·</span>' +
              '<span class="mq-time">' + esc(t) + '</span>' +
              '<span>·</span>' +
              '<span class="mq-op op-glow-gold">💸 @' + esc(w.operator) + '</span>' +
              '<span>·</span>' +
              '<span class="mq-inst">🏦 ' + esc(w.institution) + '</span>' +
            '</span>'
          );
        }).join('');
        wdTrack.innerHTML = chips + chips; // Duplicado para loop infinito fluido
      } else {
        wdTrack.innerHTML = '<span class="mq-chip mq-wd">🟡 Sin retiros recientes registrados</span>';
      }
    }
  }

  function renderBarometer() {
    if (!tickerData || !tickerData.trending) return;
    const tr = tickerData.trending;
    const rEl = $('#chipsRising');
    const fEl = $('#chipsFalling');

    if (rEl && tr.rising) {
      rEl.innerHTML = tr.rising.map((r) => (
        '<span class="bin-chip chip-up" title="' + esc(r.bank) + '">' +
          (r.flag || '🇲🇽') + ' <b>' + esc(r.bin) + '</b> · ' + esc(r.bank) + ' <span style="color:var(--mx-green-bright);font-weight:700">' + r.rate + '%</span>' +
        '</span>'
      )).join('');
    }

    if (fEl && tr.falling) {
      fEl.innerHTML = tr.falling.map((f) => (
        '<span class="bin-chip chip-down" title="' + esc(f.issue) + '">' +
          (f.flag || '🇲🇽') + ' <b>' + esc(f.bin) + '</b> · ' + esc(f.bank) + ' <span style="color:#fda4af;font-weight:700">' + esc(f.badge) + '</span>' +
        '</span>'
      )).join('');
    }
  }

  function setupTips(tips) {
    if (!tips || !tips.length) return;
    const tipEl = $('#liveTipText');
    const dotsEl = $('#tipsDots');
    if (dotsEl) {
      dotsEl.innerHTML = tips.map((_, i) => '<span class="tips-dot ' + (i === 0 ? 'active' : '') + '"></span>').join('');
    }
    if (tipEl) tipEl.textContent = tips[0];

    if (tipsInterval) clearInterval(tipsInterval);
    tipsInterval = setInterval(() => {
      currentTipIdx = (currentTipIdx + 1) % tips.length;
      if (tipEl) {
        tipEl.style.opacity = '0';
        setTimeout(() => {
          tipEl.textContent = tips[currentTipIdx];
          tipEl.style.opacity = '1';
        }, 220);
      }
      const dots = document.querySelectorAll('.tips-dot');
      dots.forEach((d, i) => d.classList.toggle('active', i === currentTipIdx));
    }, 7000);
  }

  // ── Modal Central de Detalle de KPI ─────────────────────────────
  function setupKpiClicks() {
    const cards = document.querySelectorAll('.kpi-card');
    cards.forEach((card) => {
      card.addEventListener('click', () => {
        const type = card.getAttribute('data-kpi');
        if (type) openKpiModal(type);
      });
      card.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          const type = card.getAttribute('data-kpi');
          if (type) openKpiModal(type);
        }
      });
    });

    const closeBtn = $('#btnKpiModalClose');
    const modal = $('#kpiDetailModal');
    if (closeBtn) closeBtn.addEventListener('click', closeKpiModal);
    if (modal) {
      modal.addEventListener('click', (e) => {
        if (e.target === modal) closeKpiModal();
      });
    }
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && modal && modal.style.display !== 'none') {
        closeKpiModal();
      }
    });
  }

  function closeKpiModal() {
    const modal = $('#kpiDetailModal');
    if (modal) modal.style.display = 'none';
  }

  function openKpiModal(type) {
    const modal = $('#kpiDetailModal');
    const badge = $('#kpiModalBadge');
    const title = $('#kpiModalTitle');
    const body = $('#kpiModalBody');
    if (!modal || !body) return;

    const st = tickerData ? tickerData.stats_1h : {
      total_volume: 0, deposits_total: 0, deposits_count: 0,
      withdrawals_total: 0, withdrawals_count: 0, pool_live: 0
    };
    const deps = (tickerData && tickerData.recent_deposits) || [];
    const wds = (tickerData && tickerData.recent_withdrawals) || [];
    const tr = (tickerData && tickerData.trending) || {};

    if (type === 'volume') {
      badge.textContent = '⚡ VOLUMEN 1H · AUDITORÍA';
      badge.className = 'kpi-modal-badge badge-accent';
      title.innerHTML = '⚡ Flujo de Capital (Última Hora)';
      
      const depPct = st.total_volume > 0 ? Math.round((st.deposits_total / st.total_volume) * 100) : 50;
      const wdPct = 100 - depPct;

      body.innerHTML = `
        <div class="kpi-hero-stat hero-volume">
          <div class="kpi-hero-val" style="color:var(--accent);text-shadow:0 0 16px rgba(56,189,248,0.4)">${fmtMoney(st.total_volume)} MXN</div>
          <div class="kpi-hero-sub">Volumen combinado procesado en los últimos 60 minutos</div>
        </div>

        <div class="kpi-breakdown-bar">
          <div class="kpi-bar-labels">
            <span style="color:var(--mx-green-bright)">🟢 Depósitos: ${fmtMoney(st.deposits_total)} (${depPct}%)</span>
            <span style="color:var(--gold-bright)">🟡 Retiros: ${fmtMoney(st.withdrawals_total)} (${wdPct}%)</span>
          </div>
          <div class="kpi-bar-track">
            <div class="kpi-bar-seg-green" style="width:${depPct}%"></div>
            <div class="kpi-bar-seg-gold" style="width:${wdPct}%"></div>
          </div>
        </div>

        <div class="kpi-grid-stats">
          <div class="kpi-mini-stat">
            <span class="kpi-mini-label">Operaciones de Depósito</span>
            <span class="kpi-mini-val" style="color:var(--mx-green-bright)">${st.deposits_count || 0} tiros</span>
          </div>
          <div class="kpi-mini-stat">
            <span class="kpi-mini-label">Disparos de Retiro SPEI</span>
            <span class="kpi-mini-val" style="color:var(--gold-bright)">${st.withdrawals_count || 0} órdenes</span>
          </div>
        </div>

        <p style="font-size:12px;color:var(--text-dim);text-align:center;margin-top:12px;">
          💡 <i>El volumen contabiliza todas las transacciones aprobadas y liquidadas en pasarela.</i>
        </p>
      `;
    } else if (type === 'deposits') {
      badge.textContent = '🟢 DEPÓSITOS 1H · CORONACIONES';
      badge.className = 'kpi-modal-badge badge-green';
      title.innerHTML = '🟢 Depósitos Recientes en Pasarela';

      const depListHtml = deps.length ? deps.map(d => {
        const timeStr = d.created_at ? (d.created_at.slice(11, 16) || d.created_at.slice(0, 16)) : 'reciente';
        return `
          <div class="kpi-tx-item">
            <div class="kpi-tx-left">
              <span class="kpi-tx-email">${esc(shortEmail(d.email))}</span>
              <div class="kpi-tx-meta">
                <span>${d.flag || '🇲🇽'} <b>${esc(d.bank)}</b> (${esc(d.bin)})</span>
                <span>·</span>
                <span>${esc(timeStr)}</span>
              </div>
            </div>
            <div class="kpi-tx-right">
              <span class="kpi-tx-amt" style="color:var(--mx-green-bright)">+${fmtMoney(d.amount)} MXN</span>
              <span class="kpi-tx-op op-glow">⚡ @${esc(d.operator)}</span>
            </div>
          </div>
        `;
      }).join('') : '<div class="empty-msg" style="padding:16px;">Sin depósitos registrados en la última hora.</div>';

      body.innerHTML = `
        <div class="kpi-hero-stat hero-dep">
          <div class="kpi-hero-val" style="color:var(--mx-green-bright);text-shadow:0 0 16px rgba(16,185,129,0.4)">${fmtMoney(st.deposits_total)} MXN</div>
          <div class="kpi-hero-sub">${st.deposits_count || 0} operaciones aprobadas en menos de 1 hora</div>
        </div>

        <div style="font-weight:700;font-size:12px;color:var(--text-bright);margin-bottom:8px;display:flex;justify-content:space-between;">
          <span>ÚLTIMOS TIROS CORONADOS</span>
          <span style="color:var(--text-dim)">${deps.length} registros</span>
        </div>
        <div class="kpi-tx-list">${depListHtml}</div>
      `;
    } else if (type === 'withdrawals') {
      badge.textContent = '🟡 RETIROS 1H · LIQUIDACIÓN SPEI';
      badge.className = 'kpi-modal-badge badge-gold';
      title.innerHTML = '🟡 Retiros & Liquidaciones en Vivo';

      const wdListHtml = wds.length ? wds.map(w => {
        const timeStr = w.created_at ? (w.created_at.slice(11, 16) || w.created_at.slice(0, 16)) : 'reciente';
        return `
          <div class="kpi-tx-item">
            <div class="kpi-tx-left">
              <span class="kpi-tx-email">${esc(shortEmail(w.email))}</span>
              <div class="kpi-tx-meta">
                <span>🏦 <b>${esc(w.institution)}</b></span>
                <span>·</span>
                <span>${esc(timeStr)}</span>
              </div>
            </div>
            <div class="kpi-tx-right">
              <span class="kpi-tx-amt" style="color:var(--gold-bright)">${fmtMoney(w.amount)} MXN</span>
              <span class="kpi-tx-op op-glow-gold">💸 @${esc(w.operator)}</span>
            </div>
          </div>
        `;
      }).join('') : '<div class="empty-msg" style="padding:16px;">Sin retiros registrados en la última hora.</div>';

      body.innerHTML = `
        <div class="kpi-hero-stat hero-wd">
          <div class="kpi-hero-val" style="color:var(--gold-bright);text-shadow:0 0 16px rgba(245,158,11,0.4)">${fmtMoney(st.withdrawals_total)} MXN</div>
          <div class="kpi-hero-sub">${st.withdrawals_count || 0} retiros SPEI procesados en menos de 1 hora</div>
        </div>

        <div style="font-weight:700;font-size:12px;color:var(--text-bright);margin-bottom:8px;display:flex;justify-content:space-between;">
          <span>ÚLTIMAS LIQUIDACIONES</span>
          <span style="color:var(--text-dim)">${wds.length} registros</span>
        </div>
        <div class="kpi-tx-list">${wdListHtml}</div>
      `;
    } else if (type === 'hotbin') {
      badge.textContent = '🔥 RADAR · BINES A LA ALZA';
      badge.className = 'kpi-modal-badge badge-accent';
      title.innerHTML = '🔥 Plásticos Más Calientes del Momento';

      const risingList = (tr.rising || []).map(r => `
        <div class="kpi-tx-item" style="border-color:rgba(16,185,129,0.3)">
          <div class="kpi-tx-left">
            <span class="kpi-tx-email" style="font-size:13px;color:var(--text-bright)"><code>${r.bin}</code> · ${r.flag || '🇲🇽'} <b>${esc(r.bank)}</b></span>
            <div class="kpi-tx-meta">
              <span style="color:var(--mx-green-bright);font-weight:700">👑 ${r.badge}</span>
              <span>·</span>
              <span>${r.approved || 0} depósitos aprobados</span>
            </div>
          </div>
          <div class="kpi-tx-right">
            <button class="btn btn-sm btn-primary" onclick="copyBinToClipboard('${r.bin}')">Copiar BIN</button>
          </div>
        </div>
      `).join('');

      body.innerHTML = `
        <div class="kpi-hero-stat hero-hot">
          <div class="kpi-hero-val" style="color:#fb923c;text-shadow:0 0 16px rgba(249,115,22,0.4)">${tr.rising && tr.rising[0] ? tr.rising[0].bin : '491566'}</div>
          <div class="kpi-hero-sub">Tasa de Efectividad: <b>${tr.rising && tr.rising[0] ? tr.rising[0].rate : 75.9}%</b> · ${tr.rising && tr.rising[0] ? tr.rising[0].bank : 'Santander'}</div>
        </div>

        <div style="font-weight:700;font-size:12px;color:var(--text-bright);margin-bottom:8px;">TOP PLÁSTICOS CORONANDO DIRECTO</div>
        <div class="kpi-tx-list">${risingList || '<div class="empty-msg">Sin datos de tendencia.</div>'}</div>

        <p style="font-size:12px;color:var(--text-dim);margin-top:14px;line-height:1.45;">
          💡 <b>Tip de Operación:</b> Estos BINes tienen la menor fricción en pasarela y aprueban sin detonar retos biométricos ni 3DS.
        </p>
      `;
    } else if (type === 'safe3ds') {
      badge.textContent = '🛡️ ALERTA · EVITAR / 3DS';
      badge.className = 'kpi-modal-badge badge-red';
      title.innerHTML = '🛡️ Plásticos a la Baja & Retos 3DS';

      const fallingList = (tr.falling || []).map(f => `
        <div class="kpi-tx-item" style="border-color:rgba(244,63,94,0.3)">
          <div class="kpi-tx-left">
            <span class="kpi-tx-email" style="font-size:13px;color:#fda4af"><code>${f.bin}</code> · ${f.flag || '🇲🇽'} <b>${esc(f.bank)}</b></span>
            <div class="kpi-tx-meta">
              <span style="color:#fda4af;font-weight:700">⚠️ ${f.badge}</span>
              <span>·</span>
              <span>${esc(f.issue)}</span>
            </div>
          </div>
          <div class="kpi-tx-right">
            <span class="kpi-badge badge-red">Evitar</span>
          </div>
        </div>
      `).join('');

      body.innerHTML = `
        <div class="kpi-hero-stat hero-3ds">
          <div class="kpi-hero-val" style="color:#fda4af;text-shadow:0 0 16px rgba(244,63,94,0.4)">${tr.falling && tr.falling[0] ? tr.falling[0].bin : '551238'}</div>
          <div class="kpi-hero-sub">Alerta de Seguridad Activa · ${tr.falling && tr.falling[0] ? tr.falling[0].bank : 'HSBC'} (Antifraud 3DS)</div>
        </div>

        <div style="font-weight:700;font-size:12px;color:var(--text-bright);margin-bottom:8px;">PLÁSTICOS CON RETOS O DECLINADOS</div>
        <div class="kpi-tx-list">${fallingList || '<div class="empty-msg">Sin alertas activas.</div>'}</div>

        <p style="font-size:12px;color:#fda4af;margin-top:14px;line-height:1.45;">
          ⚠️ <b>Advertencia:</b> No desperdicies intentos con estos plásticos; la pasarela está solicitando token dinámico o rechazando de plano.
        </p>
      `;
    } else if (type === 'pool') {
      badge.textContent = '👑 POOL LIVE · DISPONIBILIDAD';
      badge.className = 'kpi-modal-badge badge-cyan';
      title.innerHTML = '👑 Pool de Cuentas Activas';

      body.innerHTML = `
        <div class="kpi-hero-stat hero-pool">
          <div class="kpi-hero-val" style="color:#67e8f9;text-shadow:0 0 16px rgba(6,182,212,0.4)">${st.pool_live || 0}</div>
          <div class="kpi-hero-sub">Cuentas con sesión LIVE listas para operar en este momento</div>
        </div>

        <div class="kpi-grid-stats">
          <div class="kpi-mini-stat">
            <span class="kpi-mini-label">Disponibilidad Inmediata</span>
            <span class="kpi-mini-val" style="color:#67e8f9">100% ONLINE</span>
          </div>
          <div class="kpi-mini-stat">
            <span class="kpi-mini-label">Protección de Sesión</span>
            <span class="kpi-mini-val" style="color:var(--mx-green-bright)">JWT Activo</span>
          </div>
        </div>

        <div style="text-align:center;margin-top:16px;">
          <button class="btn btn-primary" style="width:100%;padding:12px;" onclick="scrollToAccountsSection()">
            👑 Ver Todas las Cuentas Abajo ↓
          </button>
        </div>
      `;
    }

    modal.style.display = 'flex';
  }

  window.copyBinToClipboard = function(bin) {
    if (navigator.clipboard && bin) {
      navigator.clipboard.writeText(bin);
      showToast('📋 BIN ' + bin + ' copiado al portapapeles', 'ok');
    }
  };

  window.scrollToAccountsSection = function() {
    closeKpiModal();
    const sec = $('#accountsSection');
    if (sec) sec.scrollIntoView({ behavior: 'smooth' });
  };

  // ── Init ───────────────────────────────────────────────────────
  async function init() {
    // Logout + back-link SA: solo en página standalone. En bare (tab embebido)
    // el dashboard ya provee logout y navegación — el header (.ph) está oculto.
    if (!BARE) {
      $('#logoutBtn').addEventListener('click', async () => {
        try { await fetch('/api/auth/logout', { method: 'POST' }); } catch (_) {}
        window.location.href = '/login';
      });

      // SA viendo /{username} (posiblemente el suyo propio, vía view_as): nunca
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
    }

    setupRadarTabs();
    setupKpiClicks();
    loadBinRadar();
    loadRecentTicker();
    setInterval(loadRecentTicker, 25000);

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
