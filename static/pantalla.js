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

  // ── Filtro goo "mercurio líquido" para texto HTML (Task 5) ──
  // index.html ya trae filtros goo SVG (lg-goo/fm-goo/…) pero viven en <svg>
  // de escenas y no son aplicables a HTML vía CSS. Inyectamos UNA sola vez un
  // <svg> oculto con #pat-goo (mismo patrón: feGaussianBlur + feColorMatrix con
  // alpha contrast) para poder hacer filter: url(#pat-goo) sobre el detalle.
  // NO se tocan los filtros existentes de index.html.
  function _ensureGooFilter() {
    if (document.getElementById('pat-goo')) return;      // idempotente
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('aria-hidden', 'true');
    svg.setAttribute('width', '0');
    svg.setAttribute('height', '0');
    svg.style.cssText = 'position:absolute;width:0;height:0;overflow:hidden;pointer-events:none';
    // stdDeviation 3.2 + alpha "0 0 0 20 -9": mismo rango viscoso que rt-goo/pr-goo.
    svg.innerHTML =
      '<defs><filter id="pat-goo" x="-30%" y="-30%" width="160%" height="160%">' +
      '<feGaussianBlur in="SourceGraphic" stdDeviation="3.2" result="b"/>' +
      '<feColorMatrix in="b" type="matrix" values="1 0 0 0 0  0 1 0 0 0  0 0 1 0 0  0 0 0 20 -9" result="goo"/>' +
      '<feBlend in="SourceGraphic" in2="goo"/>' +
      '</filter></defs>';
    document.body.appendChild(svg);
  }

  // Cuentas ya materializadas con el efecto líquido en esta sesión: el cuaje corre
  // UNA vez por cuenta (la primera apertura). Re-renders por fetch fresco o
  // re-aperturas cacheadas NO re-animan (evita brincos al refrescar datos).
  const _liquidDone = new Set();

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

    _ensureGooFilter();     // idempotente: el filtro #pat-goo debe existir antes de animar
    _sizeToStrip();

    // ¿Corre el cuaje líquido en esta apertura? Solo la PRIMERA vez que se
    // materializa esta cuenta (aditivo al despliegue del marco pat-unfurl).
    const firstReveal = !_liquidDone.has(id);

    // Pinta de inmediato si hay cache; si no, estado de carga mínimo.
    // Si animamos aquí (cache-hit + primera vez), marcamos ya la bandera para que
    // el re-render del fetch fresco no vuelva a cuajar.
    const cached = _cacheGet(id);
    if (cached) {
      _renderDetailView(cached, firstReveal);
      if (firstReveal) _liquidDone.add(id);
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
        if (_currentId === id && !root.hidden) {
          // Anima solo si aún no se cuajó esta cuenta (caso sin cache: el spinner
          // estuvo en pantalla y este es el primer render real → cuaja aquí).
          const doAnim = !_liquidDone.has(id);
          _renderDetailView(data, doAnim);
          if (doAnim) _liquidDone.add(id);
        }
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

    // --i = orden de cuaje del bloque (idrow→combo→balance→meta→columnas txns).
    // CSS lo lee para escalonar el reveal líquido; inofensivo cuando no hay .pat-liquid.
    return `
      <div class="pat-idrow" style="--i:0">
        ${nombre ? `<span class="pat-name">${nombre}${age != null ? ` · ${age} años` : ''}</span>` : ''}
        ${grade ? `<span class="grade ${gCls}" title="Grade ${g(grade)}">${g(grade)}</span>` : ''}
      </div>
      <div class="pat-combo-line" style="--i:1">
        <button type="button" class="pat-combo d-copy" data-copy="${g(combo)}" title="Copiar">${g(combo)}</button>
      </div>
      <div class="pat-body">
        <div class="pat-ident">
          <div class="pat-balance" style="--i:2">${money(balance)}</div>
          <div class="pat-meta" style="--i:3">
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
  // pos = posición DENTRO de la columna (0-based) → alimenta --j (stagger corto
  // del cuaje entre filas). idx sigue siendo el índice GLOBAL para data-mv-idx.
  function _mvLine(m, idx, pos) {
    const g = window.esc || (s => s);
    const money = window.fmtMoney || (v => `$${(v || 0).toFixed(2)}`);
    const cls = _mvResultCls(m);
    const sign = m.kind === 'withdrawal' ? '−' : (m.state === 'ok' ? '+' : '');
    return `<div class="pat-mv ${cls}" data-mv-idx="${idx}" style="--j:${pos}">
      <span class="pat-mv-t">${g(_mvTime(m))}</span>
      <span class="pat-mv-d">${g(_mvDesc(m))}</span>
      <span class="pat-mv-a">${sign}${money(m.amount)}</span>
    </div>`;
  }
  function _mvColumn(rows) {
    if (!rows.length) return `<div class="pat-mv-empty">Sin movimientos.</div>`;
    const shown = rows.slice(0, MV_CAP).map((x, pos) => _mvLine(x.m, x.i, pos)).join('');
    const more = rows.length > MV_CAP ? `<div class="pat-mv-more">+${rows.length - MV_CAP} más</div>` : '';
    return shown + more;
  }

  function renderPantallaTxns(d) {
    const movs = Array.isArray(d.movimientos) ? d.movimientos : [];
    const withIdx = movs.map((m, i) => ({ m, i }));
    const bot = withIdx.filter(x => x.m && x.m.source === 'dashboard');
    const bet = withIdx.filter(x => !(x.m && x.m.source === 'dashboard'));
    // --i 4/5: las columnas cuajan tras la cabecera. Sus .pat-mv HEREDAN este --i
    // (custom props heredan) y le suman --j para el stagger fila-a-fila.
    return `
      <div class="pat-txns">
        <div class="pat-txn-col" style="--i:4">
          <div class="pat-txn-h"><i class="ph-fill ph-lightning"></i> Botmexico <span class="cnt">${bot.length}</span></div>
          ${_mvColumn(bot)}
        </div>
        <div class="pat-txn-col" style="--i:5">
          <div class="pat-txn-h"><i class="ph-duotone ph-globe-hemisphere-west"></i> BetMexico <span class="cnt">${bet.length}</span></div>
          ${_mvColumn(bet)}
        </div>
      </div>`;
  }

  // animate: aplica la escritura líquida (.pat-liquid) SOLO cuando corresponde.
  // La bandera _liquidDone garantiza un único pase por cuenta: el re-render del
  // fetch fresco (o una re-apertura cacheada) llega con animate=false y no brinca.
  function _renderDetailView(d, animate) {
    const { detail } = els();
    if (!detail) return;
    try {
      const liquid = animate ? ' pat-liquid' : '';
      detail.innerHTML = `<div class="pat-wrap${liquid}">${renderPantallaHead(d)}</div>`;
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

  // La Pantalla SIGUE al control deslizable (vgutter): arrastrar el gutter cambia
  // la altura de .lpanel pero NO dispara window.resize → observamos .lpanel directo
  // para que La Pantalla crezca/encoja en vivo con los KPIs (más txns visibles).
  (function observeStrip() {
    const lpanel = $('.lpanel');
    if (!lpanel || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => {
      const root = $('#pantalla');
      if (root && !root.hidden) _sizeToStrip();
    });
    ro.observe(lpanel);
  })();

  window.Pantalla = { open, close, showTxn, back };
})();
