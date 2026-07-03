/* ═══════════════════════════════════════════════════════════════════════════
   pantalla.js — "La Pantalla" (Task 4: click derecho → abre + cabecera + 2
   secciones de transacciones). El cableado fino de los 9 controles llega en
   Task 6; la sub-vista de detalle de un movimiento (scene) llega en Task 7.

   Reusa SIEMPRE que puede: window.__pat (helpers privados expuestos por
   app.js), window.PantallaLogic (pantalla_logic.js) y los globales de app.js
   (esc, fmtMoney, parseTs, fmtAbs, fmtAbsYear, computeCurp).
   ═══════════════════════════════════════════════════════════════════════════ */
(function () {
  'use strict';

  const $ = sel => document.querySelector(sel);

  // Cache local por si window.__pat.detailDataCache no está disponible por
  // algún motivo (defensivo; en condiciones normales reusamos el de app.js).
  const _localCache = {};

  let _closeTimer = null;
  let _lastMode = 'detail';

  function _pat() { return window.__pat || {}; }

  function _cacheGet(id) {
    const shared = _pat().detailDataCache;
    if (shared && shared[id]) return shared[id];
    return _localCache[id] || null;
  }
  function _cacheSet(id, data) {
    const shared = _pat().detailDataCache;
    if (shared) shared[id] = data;
    else _localCache[id] = data;
  }

  // ── Elementos del marco (ya existen en index.html — Task 3) ──
  function els() {
    return {
      root: $('#pantalla'),
      detail: $('#pantallaDetail'),
      txn: $('#pantallaTxn'),
      scene: $('#pantallaScene'),
      log: $('#pantallaLog'),
    };
  }

  // ── Medir .lpanel y setear --pantalla-h para cubrir exactamente el strip ──
  function _sizeToStrip() {
    const root = $('#pantalla');
    const lpanel = $('.lpanel');
    if (!root || !lpanel) return;
    const rect = lpanel.getBoundingClientRect();
    if (rect.height > 0) root.style.setProperty('--pantalla-h', rect.height + 'px');
  }

  // ─────────────────────────── open / close ───────────────────────────

  let _currentId = null;

  function open(id, mode) {
    mode = mode || 'detail';
    id = parseInt(id);
    if (!id) return;
    const { root } = els();
    if (!root) return;

    _currentId = id;
    clearTimeout(_closeTimer);

    _sizeToStrip();

    // Pinta de inmediato si hay cache; si no, estado de carga mínimo.
    const cached = _cacheGet(id);
    if (cached) {
      _renderDetailView(cached);
    } else {
      const { detail } = els();
      if (detail) detail.innerHTML = `<div class="pat-loading"><span class="dep-spinner"></span> Cargando…</div>`;
    }

    setMode(mode);

    root.hidden = false;
    root.setAttribute('aria-hidden', 'false');
    root.classList.remove('pantalla-out');
    root.classList.add('pantalla-in');
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        root.classList.add('pantalla-on');
        root.classList.remove('pantalla-in');
      });
    });

    // Fetch fresco (siempre, para no mostrar datos viejos por mucho rato) —
    // solo re-renderiza si seguimos mostrando la misma cuenta.
    fetch(`/api/accounts/${id}/details`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(data => {
        _cacheSet(id, data);
        if (_currentId === id && !root.hidden) _renderDetailView(data);
      })
      .catch(err => {
        if (_currentId !== id || root.hidden) return;
        if (!cached) {
          const { detail } = els();
          if (detail) detail.innerHTML = `<div class="pat-error">Error: ${window.esc ? esc(err.message) : err.message}</div>`;
        }
      });
  }

  function close() {
    const { root } = els();
    if (!root || root.hidden) return;
    root.classList.remove('pantalla-on');
    root.classList.add('pantalla-out');
    clearTimeout(_closeTimer);
    _closeTimer = setTimeout(_finishClose, 260);
    root.addEventListener('animationend', _finishClose, { once: true });
  }

  function _finishClose() {
    clearTimeout(_closeTimer);
    const { root } = els();
    if (!root) return;
    root.hidden = true;
    root.setAttribute('aria-hidden', 'true');
    root.classList.remove('pantalla-out');
    _currentId = null;
  }

  function setMode(mode) {
    const { root, detail, txn, scene } = els();
    if (!root) return;
    _lastMode = mode;
    root.dataset.mode = mode;
    if (detail) detail.hidden = mode !== 'detail';
    if (txn) txn.hidden = mode !== 'txn';
    if (scene) scene.hidden = mode !== 'scene';
  }

  // Task 7 rellena el contenido rico; aquí solo el esqueleto de transición
  // para no romper nada si algo dispara showTxn/back antes de tiempo.
  function showTxn(mv) {
    const { txn } = els();
    if (txn && !txn.dataset.patFilled) {
      txn.innerHTML = `<div class="pat-stub">Detalle de movimiento — Task 7</div>`;
    }
    setMode('txn');
  }
  function back() {
    setMode('detail');
  }

  // ─────────────────────────── render: cabecera ───────────────────────────

  function renderPantallaHead(d) {
    const g = window.esc || (s => s);
    const money = window.fmtMoney || (v => `$${(v || 0).toFixed(2)}`);
    const pat = _pat();
    const ageFrom = pat._ageFrom || (() => null);
    const dmy = pat._dmy || (() => null);

    const bdate = d.birthdate ? String(d.birthdate).split('T')[0].split(' ')[0] : null;
    const age = ageFrom(bdate);
    const nacimiento = dmy(bdate);

    const nombre = (d.fullname && d.fullname !== 'N/A') ? g(d.fullname) : null;

    // Combo email:password — junto, sin enmascarar (feedback_no_masking).
    const email = d.email || '';
    const pass = d.password || d.pass || '';
    const combo = pass ? `${email}:${pass}` : email;

    // Estado MX (solo estado, no calle completa) vía PantallaLogic.
    const estado = (window.PantallaLogic && d.address) ? window.PantallaLogic.estadoFrom(d.address) : null;

    // CURP — real o estimado (computeCurp global de app.js), igual criterio que renderDetail.
    const curpStored = (d.curp && d.curp !== 'N/A') ? d.curp : null;
    const curpCalc = (!curpStored && typeof computeCurp === 'function') ? computeCurp(d.fullname, bdate, d.address) : null;
    const curpShown = curpStored || curpCalc || null;
    const curpTag = curpStored ? '' : (curpCalc ? ' <span class="est">est</span>' : '');

    const balance = d.balance_total != null ? d.balance_total : (d.balance_real || 0);
    const grade = d.grade || null;
    const gCls = (typeof gradeClass === 'function') ? gradeClass(grade) : '';

    return `
      <div class="pat-head">
        <div class="pat-head-top">
          ${nombre ? `<span class="pat-name">${nombre}${age != null ? ` · ${age} años` : ''}</span>` : ''}
          ${grade ? `<span class="grade ${gCls}" title="Grade ${g(grade)}">${g(grade)}</span>` : ''}
        </div>
        <div class="pat-combo-row">
          <button type="button" class="pat-combo d-copy" data-copy="${g(combo)}" title="Click para copiar">${g(combo)}</button>
        </div>
        <div class="pat-balance-row">
          <span class="pat-balance">${money(balance)}</span>
        </div>
        <div class="pat-meta-row">
          ${estado ? `<span class="pat-meta-item"><i class="ph-duotone ph-map-pin"></i> ${g(estado)}</span>` : ''}
          ${nacimiento ? `<span class="pat-meta-item dim">${g(nacimiento)}</span>` : ''}
          ${curpShown ? `<span class="pat-meta-item dim">CURP: <button type="button" class="pat-curp d-copy" data-copy="${g(curpShown)}" title="Click para copiar">${g(curpShown)}</button>${curpTag}</span>` : ''}
        </div>
      </div>`;
  }

  // ─────────────────────────── render: 2 secciones ───────────────────────────

  function _renderMvRow(m, idx) {
    const pat = _pat();
    // Preferimos reusar _renderMovimiento tal cual (mismo look que el panel
    // inline) — le añadimos el wrapper con data-mv-idx para Task 7.
    if (typeof pat._renderMovimiento === 'function') {
      try {
        const html = pat._renderMovimiento(m);
        return `<div class="pat-mv-row" data-mv-idx="${idx}">${html}</div>`;
      } catch (e) {
        // cae al render propio si algo truena
      }
    }
    return _renderMvRowFallback(m, idx);
  }

  // Render propio compacto, por si _renderMovimiento no está accesible o
  // truena con esta forma de dato. Conserva los mismos campos.
  function _renderMvRowFallback(m, idx) {
    const g = window.esc || (s => s);
    const money = window.fmtMoney || (v => `$${(v || 0).toFixed(2)}`);
    const isThreeDs = (m.reason || '').toUpperCase().includes('3DS');
    const stateCls = isThreeDs ? 'mv-threeds' : ({ ok: 'mv-dep', fail: 'mv-fail', pending: 'mv-pend', wd: 'mv-wd' })[m.state] || 'mv-dep';
    const kindLabel = m.kind === 'withdrawal' ? 'Retiro' : 'Depósito';
    const sign = m.kind === 'withdrawal' ? '−' : (m.state === 'ok' ? '+' : '');
    const who = m.who ? ` · ${g(m.who)}` : '';
    const method = m.method ? ` · ${g(m.method)}` : '';
    return `<div class="pat-mv-row pat-mv-fallback ${stateCls}" data-mv-idx="${idx}">
      <span class="pat-mv-when">${g(m.when || '—')}</span>
      <span class="pat-mv-kind">${g(kindLabel)}${method}${who}</span>
      <span class="pat-mv-amt">${sign}${money(m.amount)}</span>
    </div>`;
  }

  function renderPantallaTxns(d) {
    const movs = Array.isArray(d.movimientos) ? d.movimientos : [];
    const split = window.PantallaLogic
      ? window.PantallaLogic.splitTransactions(movs)
      : { botmexico: [], betmexico: [] };

    // Índices reales dentro de d.movimientos (para que Task 7 pueda indexar
    // de vuelta al arreglo original con data-mv-idx).
    const withIdx = movs.map((m, i) => ({ m, i }));
    const botIdx = withIdx.filter(x => x.m && x.m.source === 'dashboard');
    const betIdx = withIdx.filter(x => !(x.m && x.m.source === 'dashboard'));

    const botRows = botIdx.length
      ? botIdx.map(x => _renderMvRow(x.m, x.i)).join('')
      : `<div class="pat-mv-empty">Sin transacciones de Botmexico.</div>`;
    const betRows = betIdx.length
      ? betIdx.map(x => _renderMvRow(x.m, x.i)).join('')
      : `<div class="pat-mv-empty">Sin transacciones directas en BetMexico.</div>`;

    // Envuelto en .acc-detail para heredar gratis el styling ya hecho de
    // .mitem/.mhead/.mv-*/.when/etc. (style.css) sin duplicar CSS de movimientos.
    return `
      <div class="acc-detail pat-txn-sections">
        <section class="pat-txn-sec">
          <div class="pat-txn-sec-h"><i class="ph-fill ph-lightning"></i> Botmexico <span class="cnt">${botIdx.length}</span></div>
          <div class="mlist pat-txn-list">${botRows}</div>
        </section>
        <section class="pat-txn-sec">
          <div class="pat-txn-sec-h"><i class="ph-duotone ph-globe-hemisphere-west"></i> BetMexico <span class="cnt">${betIdx.length}</span></div>
          <div class="mlist pat-txn-list">${betRows}</div>
        </section>
      </div>`;
  }

  function _renderDetailView(d) {
    const { detail } = els();
    if (!detail) return;
    try {
      detail.innerHTML = renderPantallaHead(d) + renderPantallaTxns(d);
    } catch (e) {
      console.error('[Pantalla] render failed:', e);
      detail.innerHTML = `<div class="pat-error">Error renderizando: ${window.esc ? esc(e.message) : e.message}</div>`;
    }
  }

  // ─────────────────────────── listeners ───────────────────────────

  // contextmenu sobre cualquier fila de #accTable → abre La Pantalla.
  // Capture phase + stopImmediatePropagation: gana sobre el listener legacy
  // (bubble phase, ~línea 3000 de app.js) que abre el panel inline viejo.
  // No se toca ese listener; simplemente dejamos de dejarlo correr para este
  // evento puntual, cumpliendo "aditivo, no romper lo existente".
  const accTable = $('#accTable');
  if (accTable) {
    accTable.addEventListener('contextmenu', e => {
      const tr = e.target.closest('tr[data-id]');
      if (!tr) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      open(parseInt(tr.dataset.id), 'detail');
    }, true);
  }

  // Cierre: click en cualquier [data-close] (backdrop + botón X).
  document.addEventListener('click', e => {
    if (e.target.closest('[data-close]')) close();
  });

  // Cierre: Esc global (solo si La Pantalla está visible).
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    const root = $('#pantalla');
    if (root && !root.hidden) close();
  });

  // Recalcular altura si la ventana cambia de tamaño mientras está abierta.
  window.addEventListener('resize', () => {
    const root = $('#pantalla');
    if (root && !root.hidden) _sizeToStrip();
  });

  window.Pantalla = { open, close, showTxn, back };
})();
