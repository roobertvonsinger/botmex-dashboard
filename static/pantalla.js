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

  // ─────────────────────────── render: detalle premium ───────────────────────────
  // Layout horizontal (identidad+saldo | transacciones en 2 columnas), SIN scroll.
  // Nada de incrustar el renderDetail viejo: esto es contenido nativo de La Pantalla.

  const MV_CAP = 6;   // filas visibles por columna (sin scroll); el resto → "+N más"

  function renderPantallaHead(d) {
    const g = window.esc || (s => s);
    const money = window.fmtMoney || (v => `$${(v || 0).toFixed(2)}`);
    const pat = _pat();
    const ageFrom = pat._ageFrom || (() => null);
    const dmy = pat._dmy || (() => null);

    const bdate = d.birthdate ? String(d.birthdate).split('T')[0].split(' ')[0] : null;
    const age = ageFrom(bdate);
    const nombre = (d.fullname && d.fullname !== 'N/A') ? g(d.fullname) : null;

    // Combo email:password — junto, sin enmascarar (feedback_no_masking).
    const email = d.email || '';
    const pass = d.password || d.pass || '';
    const combo = pass ? `${email}:${pass}` : email;

    const estado = (window.PantallaLogic && d.address) ? window.PantallaLogic.estadoFrom(d.address) : null;

    const curpStored = (d.curp && d.curp !== 'N/A') ? d.curp : null;
    const curpCalc = (!curpStored && typeof computeCurp === 'function') ? computeCurp(d.fullname, bdate, d.address) : null;
    const curpShown = curpStored || curpCalc || null;
    const curpTag = curpStored ? '' : (curpCalc ? ' <span class="est">est</span>' : '');

    const balance = d.balance_total != null ? d.balance_total : (d.balance_real || 0);
    const grade = d.grade || null;
    const gCls = (typeof gradeClass === 'function') ? gradeClass(grade) : '';

    return `
      <div class="pat-idrow">
        ${nombre ? `<span class="pat-name">${nombre}${age != null ? ` · ${age} años` : ''}</span>` : ''}
        ${grade ? `<span class="grade ${gCls}" title="Grade ${g(grade)}">${g(grade)}</span>` : ''}
      </div>
      <div class="pat-combo-line">
        <button type="button" class="pat-combo d-copy" data-copy="${g(combo)}" title="Copiar">${g(combo)}</button>
      </div>
      <div class="pat-body">
        <div class="pat-ident">
          <div class="pat-balance">${money(balance)}</div>
          <div class="pat-meta">
            ${estado ? `<span class="pat-meta-item"><i class="ph-duotone ph-map-pin"></i> ${g(estado)}</span>` : ''}
            ${bdate ? `<span class="pat-meta-item dim"><i class="ph-duotone ph-cake"></i> ${g(dmy(bdate) || bdate)}</span>` : ''}
            ${curpShown ? `<span class="pat-meta-item dim"><i class="ph-duotone ph-identification-card"></i> <button type="button" class="pat-curp d-copy" data-copy="${g(curpShown)}" title="Copiar CURP">${g(curpShown)}</button>${curpTag}</span>` : ''}
          </div>
        </div>
        ${renderPantallaTxns(d)}
      </div>`;
  }

  // ── Transacciones: 2 columnas compactas, colores intuitivos, sin scroll ──

  function _mvResultCls(m) {
    if ((m.reason || '').toUpperCase().includes('3DS')) return 'threeds';
    return ({ ok: 'ok', fail: 'fail', pending: 'pending', wd: 'wd' })[m.state] || 'ok';
  }
  function _mvDesc(m) {
    const g = window.esc || (s => s);
    if ((m.reason || '').toUpperCase().includes('3DS')) return 'Verificación 3DS';
    if (m.state === 'fail') return 'Rechazado (banco)';
    const base = m.kind === 'withdrawal' ? 'Retiro' : 'Depósito';
    const extra = m.method ? ` · ${g(m.method)}` : (m.who ? ` · ${g(m.who)}` : '');
    return base + extra;
  }
  function _mvTime(m) {
    const w = String(m.when || '');
    const md = w.match(/^(\d{2}\/\d{2})/);      // "DD/MM/YYYY HH:MM" → "DD/MM"
    return md ? md[1] : (w.slice(0, 5) || '—');
  }
  function _mvLine(m, idx) {
    const g = window.esc || (s => s);
    const money = window.fmtMoney || (v => `$${(v || 0).toFixed(2)}`);
    const cls = _mvResultCls(m);
    const sign = m.kind === 'withdrawal' ? '−' : (m.state === 'ok' ? '+' : '');
    return `<div class="pat-mv ${cls}" data-mv-idx="${idx}">
      <span class="pat-mv-t">${g(_mvTime(m))}</span>
      <span class="pat-mv-d">${g(_mvDesc(m))}</span>
      <span class="pat-mv-a">${sign}${money(m.amount)}</span>
    </div>`;
  }
  function _mvColumn(rows) {
    if (!rows.length) return `<div class="pat-mv-empty">Sin movimientos.</div>`;
    const shown = rows.slice(0, MV_CAP).map(x => _mvLine(x.m, x.i)).join('');
    const more = rows.length > MV_CAP ? `<div class="pat-mv-more">+${rows.length - MV_CAP} más</div>` : '';
    return shown + more;
  }

  function renderPantallaTxns(d) {
    const movs = Array.isArray(d.movimientos) ? d.movimientos : [];
    const withIdx = movs.map((m, i) => ({ m, i }));
    const bot = withIdx.filter(x => x.m && x.m.source === 'dashboard');
    const bet = withIdx.filter(x => !(x.m && x.m.source === 'dashboard'));
    return `
      <div class="pat-txns">
        <div class="pat-txn-col">
          <div class="pat-txn-h"><i class="ph-fill ph-lightning"></i> Botmexico <span class="cnt">${bot.length}</span></div>
          ${_mvColumn(bot)}
        </div>
        <div class="pat-txn-col">
          <div class="pat-txn-h"><i class="ph-duotone ph-globe-hemisphere-west"></i> BetMexico <span class="cnt">${bet.length}</span></div>
          ${_mvColumn(bet)}
        </div>
      </div>`;
  }

  function _renderDetailView(d) {
    const { detail } = els();
    if (!detail) return;
    try {
      detail.innerHTML = `<div class="pat-wrap">${renderPantallaHead(d)}</div>`;
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

  // Combo copiable tipo liga: el copiado real lo hace el handler global (.d-copy);
  // aquí solo el feedback visual (parpadeo verde "copiado") al click en el texto.
  document.addEventListener('click', e => {
    const combo = e.target.closest('.pat-combo, .pat-curp');
    if (!combo) return;
    combo.classList.add('copied');
    setTimeout(() => combo.classList.remove('copied'), 900);
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
