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

  // ─────────────────────────── open / close ───────────────────────────
  // 2026-07-09 (decisión de Robert, campo): La Pantalla no tiene controles PROPIOS
  // de tamaño (sin drag, sin ResizeObserver) — pero app.js (initLpVResize → apply())
  // sí la sincroniza al alto real del panel KPI en cada cambio, así nunca queda
  // desalineada (tapando la tabla o con hueco). El default es ANCHOR_H (app.js):
  // "Sistema" a la altura de "Cuentas". Aquí solo se muestra/esconde.

  let _currentId = null;
  let _deposAutoHidden = false; // true si La Pantalla retrajo el panel de depósitos flotante (F4) — se restaura al cerrar
  // Polling de estado de retiro: 1 interval activo por cuenta (accId -> {timer, txId}).
  const _wdPolls = {};
  // Auto-fetch de clabes SPEI: una sola vez por cuenta (las clabes son FIJAS por
  // usuario — una vez obtenidas, no se re-piden). Evita spam a BeginDeposit.
  const _clabesFetched = new Set();
  // true mientras el último gesto sobre .pat-txn-col fue un drag-scroll (>6px de
  // movimiento) — el click handler de .pat-mv lo consulta para NO togglear el
  // detalle expandible al soltar tras arrastrar (initTxnScroll, más abajo).
  let _mvDragged = false;

  function open(id, mode) {
    mode = mode || 'detail';
    id = parseInt(id);
    if (!id) return;
    const { root } = els();
    if (!root) return;

    // Robert 2026-07-10, campo: "se abre brusco o parpadea raro". Causa raíz: open()
    // NO chequeaba si La Pantalla ya estaba visible — al cambiar de cuenta con la
    // pantalla ya abierta, esto volvía a correr TODA la secuencia de entrada
    // (agregaba .pantalla-in encima de un elemento que YA tenía .pantalla-on con
    // backdrop-filter:blur(34px) activo, y el double-rAF togglaba clases otra vez) →
    // repintado pesado (blur del propio filtro + backdrop-filter compitiendo) en
    // cada click de fila, no solo en la apertura real. wasHidden distingue apertura
    // en frío (dispara pat-unfurl/scanline/backdrop) de cambio de cuenta en caliente
    // (solo actualiza contenido, sin re-togglear clases de animación).
    const wasHidden = root.hidden;

    _currentId = id;
    clearTimeout(_closeTimer);
    _markSourceRow(id);

    _ensureGooFilter();     // idempotente: el filtro #pat-goo debe existir antes de animar

    // ¿Corre el cuaje líquido en esta apertura? Solo la PRIMERA vez que se
    // materializa esta cuenta (aditivo al despliegue del marco pat-unfurl).
    const firstReveal = !_liquidDone.has(id);

    // Pinta de inmediato si hay cache; si no, estado de carga mínimo.
    // Si animamos aquí (cache-hit + primera vez), marcamos ya la bandera para que
    // el re-render del fetch fresco no vuelva a cuajar.
    const cached = _cacheGet(id);
    if (cached) {
      const ok = _renderDetailView(cached, firstReveal);
      if (firstReveal && ok) _liquidDone.add(id);
    } else {
      const { detail } = els();
      if (detail) detail.innerHTML = `<div class="pat-loading"><span class="dep-spinner"></span> Cargando…</div>`;
    }

    setMode(mode);

    if (wasHidden) {
      root.hidden = false;
      root.setAttribute('aria-hidden', 'false');
      root.classList.remove('pantalla-out');
      root.classList.add('pantalla-in');
      // Con La Pantalla abierta, el panel de depósitos NUNCA comparte su franja (decisión
      // de Robert, campo: siempre dockeado debajo de la tabla mientras esto está visible).
      // Exclusión mutua real (no solo relayout ciego, root cause del pisado z-index 200 vs 40):
      // si el panel está flotando (no dockeado), se retrae — el stage de depósito en curso
      // sigue visible igual porque #depStage vive reparentado a #patStageSlot dentro de La Pantalla.
      try {
        const dw = window.DeposWindow?._instance;
        if (dw?.isOpen?.() && !dw.isDocked?.()) { dw.hide(); _deposAutoHidden = true; }
        else { dw?.relayout?.(); }
      } catch (_) {}
      requestAnimationFrame(() => {
        requestAnimationFrame(() => {
          root.classList.add('pantalla-on');
          root.classList.remove('pantalla-in');
        });
      });
    }

    // Fetch fresco (siempre, para no mostrar datos viejos por mucho rato) —
    // solo re-renderiza si seguimos mostrando la misma cuenta. Timeout explícito
    // (AbortController): sin esto, un fetch que nunca resuelve (hang de red/proxy,
    // reportado por Robert 2026-07-25: "de repente, con cualquier cuenta") deja el
    // spinner "Cargando…" pegado para siempre — nada más lo reemplaza. Con timeout,
    // al menos degrada a un error visible + reintento en vez de colgarse mudo.
    const _fetchAc = new AbortController();
    const _fetchTimeout = setTimeout(() => _fetchAc.abort(), 15000);
    fetch(`/api/accounts/${id}/details`, { signal: _fetchAc.signal })
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(data => {
        clearTimeout(_fetchTimeout);
        _cacheSet(id, data);
        if (_currentId === id && !root.hidden) {
          // Anima solo si aún no se cuajó esta cuenta (caso sin cache: el spinner
          // estuvo en pantalla y este es el primer render real → cuaja aquí).
          const doAnim = !_liquidDone.has(id);
          const ok = _renderDetailView(data, doAnim);
          if (doAnim && ok) _liquidDone.add(id);
        }
      })
      .catch(err => {
        clearTimeout(_fetchTimeout);
        if (_currentId !== id || root.hidden) return;
        if (err && err.name === 'AbortError') err = new Error('Sin respuesta del servidor (15s) — reintenta');
        if (!cached) {
          const { detail } = els();
          if (detail) detail.innerHTML = `<div class="pat-error">Error: ${window.esc ? esc(err.message) : err.message} <button type="button" class="pat-btn pat-btn-ghost" data-wd-retry-open="${id}">Reintentar</button></div>`;
        }
      });
  }

  // Glow fila-fuente ↔ detalle abierto (Robert, campo: "la cuenta en vista de
  // detalles debería brillar para que se sepa que esa es la seleccionada").
  // Distinta semántica de .row-sel (selección múltiple): esto es "la que veo",
  // una sola a la vez, se mueve con open() al cambiar de cuenta en caliente.
  function _markSourceRow(id) {
    document.querySelectorAll('.pantalla-source').forEach(el => el.classList.remove('pantalla-source'));
    const srcTr = document.querySelector(`#accTable tbody tr[data-id="${id}"]`);
    if (srcTr) srcTr.classList.add('pantalla-source');
  }
  function _clearSourceRow() {
    document.querySelectorAll('.pantalla-source').forEach(el => el.classList.remove('pantalla-source'));
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
    _clearSourceRow();
    // Cerrada La Pantalla, ningún polling de retiro debe seguir vivo en background.
    Object.keys(_wdPolls).forEach(_stopWithdrawPoll);
    // Restaura el alto ancla (ANCHOR_H) — _syncFichaHeight() lo crece mientras
    // La Pantalla está abierta, no debe quedarse crecido con la ficha cerrada.
    if (window.KpiPanel && typeof window.KpiPanel.apply === 'function') {
      window.KpiPanel.apply(window.KpiPanel.DEFAULT_H);
    }
    // Cerrada La Pantalla, el panel de depósitos puede volver a flotar si esa era
    // la preferencia del operador (el forzado a dockeado era solo mientras estaba abierta).
    try {
      const dw = window.DeposWindow?._instance;
      if (_deposAutoHidden) { dw?.show?.(); _deposAutoHidden = false; }
      else { dw?.relayout?.(); }
    } catch (_) {}
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
  // Layout horizontal (identidad+saldo | historial de movimientos), SIN scroll.
  // Nada de incrustar el renderDetail viejo: esto es contenido nativo de La Pantalla.

  // El historial ahora ES scrolleable (.pat-txn-col, rueda + click-y-jala) — ya no
  // necesita truncar a un cap fijo con "+N más"; se renderiza completo y el scroll
  // maneja el volumen. Tope duro solo para no reventar el DOM en cuentas con miles
  // de movimientos.
  const MV_CAP = 400;

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
    const curpTag = curpStored
      ? ' <span class="pat-curp-badge ok" title="Validado en RENAPO"><i class="ph-bold ph-check"></i> RENAPO</span>'
      : (curpCalc ? ' <span class="est" title="Estimado por domicilio">est</span>' : '');

    const balance = d.balance_total != null ? d.balance_total : (d.balance_real || 0);
    const grade = d.grade || null;
    const gCls = (typeof gradeClass === 'function') ? gradeClass(grade) : '';

    // --i = orden de cuaje del bloque (idrow→combo→balance→divisor→columnas txns).
    // CSS lo lee para escalonar el reveal líquido; inofensivo cuando no hay .pat-liquid.
    // Controles principales: MISMOS data-* que renderDetail (d-deposit-btn/inuse/det-mark)
    // para reusar la semántica; el cableado lo hace el listener de #pantalla (abajo).
    // 2026-07-10 (Robert, campo, 2ª ronda de imagen anotada): Estado/cumpleaños/CURP
    // SUBEN a la línea del nombre (antes vivían apilados en .pat-col-ident, ocupando
    // toda la columna) — fluyen hacia la derecha del nombre+grade. El nombre gana un
    // poco de contraste (antes casi ilegible, mismo tono que el resto de la meta).
    // La columna de datos queda: combo → saldo → divisor → guardado (tarjetas/notas)
    // directo bajo el saldo, sin el bloque de meta en medio.
    return `
      <div class="pat-topbar" style="--i:0">
        ${nombre ? `<span class="pat-name">${nombre}${age != null ? ` · ${age} años` : ''}</span>` : ''}
        ${grade ? `<span class="grade ${gCls}" title="Grade ${g(grade)}">${g(grade)}</span>` : ''}
        <div class="pat-topbar-meta">
          ${estado ? `<span class="pat-meta-item"><i class="ph-duotone ph-map-pin"></i> ${g(estado)}</span>` : ''}
          ${bdate ? `<span class="pat-meta-item dim"><i class="ph-duotone ph-cake"></i> ${g(dmy(bdate) || bdate)}</span>` : ''}
          <span class="pat-meta-item dim pat-curp-wrap"><i class="ph-duotone ph-identification-card"></i>
            ${curpShown
              ? `<button type="button" class="pat-curp d-copy" data-copy="${g(curpShown)}" title="Copiar CURP">${g(curpShown)}</button>${curpTag}`
              : ''}
            <button type="button" class="pat-curp-add" data-curp-toggle="${g(curpStored || '')}" title="${curpStored ? 'Editar CURP guardado' : 'Guardar CURP validado'}"><i class="ph-bold ${curpStored ? 'ph-pencil-simple' : 'ph-plus'}"></i>${curpStored ? '' : ' CURP'}</button>
            <div class="pat-form pat-curp-pop" data-curp-form hidden>
              <div class="pat-form-row pat-curp-state-row">
                <label class="pat-label-sm">Estado:</label>
                <select class="pat-input pat-select-sm" data-curp-state-select title="Seleccionar estado para recalcular CURP">
                  <option value="">-- Seleccionar Estado --</option>
                </select>
              </div>
              <input type="text" class="pat-input pat-input-mono" data-curp-input maxlength="18" placeholder="CURP">
              <div class="pat-form-err" data-curp-err hidden></div>
              <div class="pat-form-row">
                <a href="https://www.gob.mx/curp/" target="_blank" rel="noopener" class="pat-btn pat-btn-ghost" title="Abrir validador oficial">gob.mx ↗</a>
                <button type="button" class="pat-btn pat-btn-ghost" data-curp-cancel>Cancelar</button>
                <button type="button" class="pat-btn pat-btn-save" data-curp-save>Guardar</button>
              </div>
            </div>
          </span>
        </div>
        <button type="button" class="pat-topbar-pin det-mark" data-mark-email="${g(email)}" title="Fijar"><i class="ph-bold ph-push-pin"></i></button>
      </div>
      <div class="pat-columns">
        <div class="pat-col-ident">
          <div class="pat-combo-line" style="--i:1">
            <button type="button" class="pat-combo d-copy" data-copy="${g(combo)}" title="Copiar">${g(combo)}</button>
          </div>
          <div class="pat-balance" style="--i:2">${money(balance)}</div>
          <div class="pat-ident-div" style="--i:3"></div>
          ${renderPantallaSaved(d)}
          ${renderPantallaClabes(d)}
        </div>
        ${renderPantallaTxns(d)}
        ${renderPantallaStageCol(d)}
      </div>`;
      // "Depositar"/"Retirar" YA NO viven en una barra de acciones flotante en la
      // esquina (Robert 2026-07-28: "no se entiende qué hacen hasta allá lejos de
      // donde se ponen las cantidades") — cada botón se movió DENTRO de su propio
      // panel, junto al monto que dispara (ver renderPantallaWithdrawStage / el
      // template #deposCompactTpl). "Fijar" (única acción que sobraba sin campo al
      // que pegarse) subió a la topbar — esto también libera el hueco que
      // .pat-columns reservaba abajo para el CTA flotante (ver ACTIONS_CLEARANCE
      // en _syncFichaHeight, app.js).
      // Candadito "En uso" (lock manual) ELIMINADO de La Pantalla (Robert 2026-07-17):
      // era un 2º control de lock, redundante con el auto-lock que ya se pone al
      // DEPOSITAR (deposits.py _auto_lock_for_deposit). Como SA creaba RESERVADA_SA
      // perpetua que además trababa "sacar del pool → trastienda". Ahora el lock es UNO
      // solo (el de trabajo real) y sacar a trastienda lo libera (app.py publish).
  }

  // ── Guardado: tarjetas + notas en pequeño (columna de datos, bajo la meta) ──
  // Reusa _pipeDisplay (pipe canónico num|MM|YY|cvv, sin enmascarar) y fmtAbsYear/
  // fmtAbs (app.js). Capado (2 tarjetas + 2 notas) para no romper el sin-scroll;
  // el resto → "+N más". Tarjetas: NO hay alta/edición manual real — se guardan
  // solo al aprobarse un depósito (deposits.py); por eso acá siguen solo-lectura.
  // Notas SÍ tienen CRUD real (crear/borrar) — portado del acordeón viejo, mismos
  // endpoints (POST/DELETE /api/accounts/{id}/notes). Borrar: dueño o superadmin.
  const CARD_CAP = 2, NOTE_CAP = 2;

  function _isNoteOwner(n) {
    // `state` es un const top-level de app.js (script clásico, NO módulo): vive en el
    // scope léxico compartido entre <script> del documento, pero NUNCA cuelga de
    // `window` (eso es solo para top-level `var`). `window.state` es SIEMPRE undefined
    // — el guard con window.state hacía que esto (y _withdrawBtnState más abajo)
    // fallara para TODOS los roles, incluido superadmin. Bug de campo 2026-07-25.
    const u = state.user || null;
    if (!u) return false;
    if (u.role === 'superadmin') return true;
    return !!(n.created_by && Number(n.created_by) === Number(u.telegram_id));
  }

  function renderPantallaSaved(d) {
    const g = window.esc || (s => s);
    const cards = Array.isArray(d.cards) ? d.cards.filter(c => c && c.card_number) : [];
    const notes = Array.isArray(d.notes) ? d.notes.filter(n => n && (n.note_text || '').trim()) : [];

    const pipeOf = (typeof _pipeDisplay === 'function')
      ? _pipeDisplay
      : (raw => String(raw || '').replace(/\//g, '|'));
    const fAbsY = (typeof fmtAbsYear === 'function') ? fmtAbsYear : (s => s || '');

    let cardHtml = '';
    if (cards.length) {
      const rows = cards.slice(0, CARD_CAP).map(c => {
        const pipe = pipeOf(`${c.card_number || ''}|${c.card_expiry || ''}|${c.card_cvv || ''}`);
        const appr = c.total_approved || 0, tot = c.total_deposits || 0;
        const stat = tot > 0 ? `${appr}/${tot}` : '';
        return `<button type="button" class="pat-sv-line pat-sv-card d-copy" data-copy="${g(pipe)}" title="Copiar tarjeta">
          <span class="pat-sv-pipe">${g(pipe)}</span>
          ${stat ? `<span class="pat-sv-stat">${g(stat)}</span>` : ''}
        </button>`;
      }).join('');
      const more = cards.length > CARD_CAP ? `<span class="pat-sv-more">+${cards.length - CARD_CAP}</span>` : '';
      cardHtml = `<div class="pat-sv-group">
        <span class="pat-sv-h"><span class="pat-sv-emo">💳</span> Tarjetas<span class="pat-sv-cnt">${cards.length}</span>${more}</span>
        ${rows}
      </div>`;
    }

    const noteRows = notes.slice(0, NOTE_CAP).map(n => {
      const who = g(n.created_by_name || '—');
      const when = n.created_at ? g(fAbsY(n.created_at)) : '';
      const del = _isNoteOwner(n)
        ? `<button type="button" class="pat-sv-del" data-del-note="${n.id}" title="Borrar nota"><i class="ph-bold ph-x"></i></button>`
        : '';
      return `<div class="pat-sv-line pat-sv-note" title="${g(n.note_text)}">
        <span class="pat-sv-ntext">${g(n.note_text)}</span>
        <span class="pat-sv-nmeta">${who}${when ? ` · ${when}` : ''}</span>
        ${del}
      </div>`;
    }).join('');
    const moreNotes = notes.length > NOTE_CAP ? `<span class="pat-sv-more">+${notes.length - NOTE_CAP}</span>` : '';
    const noteHtml = `<div class="pat-sv-group">
      <span class="pat-sv-h"><span class="pat-sv-emo">📝</span> Notas${notes.length ? `<span class="pat-sv-cnt">${notes.length}</span>` : ''}${moreNotes}
        <button type="button" class="pat-sv-add" data-add-note title="Agregar nota"><i class="ph-bold ph-plus"></i></button>
      </span>
      ${noteRows}
      <div class="pat-form" data-note-form hidden>
        <textarea class="pat-textarea" data-note-input maxlength="2000" placeholder="Nota…"></textarea>
        <div class="pat-form-row">
          <button type="button" class="pat-btn pat-btn-ghost" data-note-cancel>Cancelar</button>
          <button type="button" class="pat-btn pat-btn-save" data-note-save>Guardar</button>
        </div>
      </div>
    </div>`;

    return `<div class="pat-saved" style="--i:6">${cardHtml}${noteHtml}</div>`;
  }

  // ── Clabes de depósito SPEI (NVIO + STP) — persistidas en BD, mostradas en
  // PLANO sin enmascarar (feedback_no_masking: el operador las pega en su banco).
  // Reusa el lenguaje visual de tarjetas (.pat-sv-card / d-copy): click = copia.
  // Si no hay clabes guardadas → botón "Obtener clabes" (dispara BeginDeposit vía
  // POST /clabes/refresh). Si ya están → las muestra + botón sutil para refrescar.
  // NUNCA se taladra la cuenta en cada refresh: las clabes son FIJAS por usuario.
  function renderPantallaClabes(d) {
    const g = window.esc || (s => s);
    const clabes = Array.isArray(d.clabes) ? d.clabes : [];
    const accId = d.id;
    // Integración legible: NVIO (prioridad 1) + STP (order 2/3). Badge por rail.
    const intLabel = (it) => {
      const v = String(it.integration || '').toUpperCase();
      if (v === 'NVIO') return 'NVIO';
      if (v === 'STP') return 'STP';
      return v || 'SPEI';
    };
    const rows = clabes.map(c => {
      const clabe = String(c.clabe || '');
      const blocked = c.blocked;
      const order = c.clabe_order;
      return `<button type="button" class="pat-sv-line pat-sv-card pat-clabe d-copy" data-copy="${g(clabe)}" title="Copiar clabe">
        <span class="pat-clabe-rail ${blocked ? 'blocked' : ''}">${g(intLabel(c))}${order ? `<span class="pat-clabe-ord">·${g(order)}</span>` : ''}</span>
        <span class="pat-sv-pipe pat-clabe-num">${g(clabe)}</span>
        ${blocked ? '<span class="pat-clabe-blk" title="Bloqueada">⛔</span>' : ''}
      </button>`;
    }).join('');
    const have = clabes.length > 0;
    // Botón refrescar: discreto (mismo tono que pat-sv-add). data-clabe-refresh.
    const refreshBtn = have
      ? `<button type="button" class="pat-sv-add" data-clabe-refresh="${g(accId)}" title="Volver a obtener clabes (BeginDeposit)"><i class="ph-bold ph-arrows-clockwise"></i></button>`
      : '';
    return `<div class="pat-clabes" style="--i:7">
      <span class="pat-sv-h"><span class="pat-sv-emo">🏦</span> Clabes SPEI${have ? `<span class="pat-sv-cnt">${clabes.length}</span>` : ''}${refreshBtn}</span>
      ${have ? rows : `<button type="button" class="pat-clabe-get" data-clabe-refresh="${g(accId)}"><i class="ph-bold ph-download-simple"></i> Obtener clabes</button>`}
    </div>`;
  }

  // ── Retiro automático SA-only (Task F/G) ──────────────────────────────────
  // Botón + monto + estado 2-fases. bug#2: status:6 de BetMexico != aterrizó en
  // el banco — el copy SIEMPRE dice "confirma en tu banco", nunca "entregado".
  // bug#3/bug#1: alertas si el rail salió a tarjeta o a dígitos distintos a los
  // esperados. Invisible para no-SA (feedback_deshabilitar_invisible_no_redirect).
  const WD_TERMINAL = new Set(['successful', 'completed', 'failed', 'idle']);

  // Convierte la fila cruda de account_withdrawals (último retiro conocido,
  // servido por /details) al mismo shape que devuelve GET /withdraw/status —
  // pinta algo de inmediato al reabrir La Pantalla, antes de que el poll fresco
  // confirme el estado real (detecta gatewayMismatch si gateway==1).
  function _wdStatusFromRow(row) {
    if (!row) return null;
    let status;
    if (row.status_api === 6) status = 'completed';
    else if (row.status_api != null && row.status_api < 0) status = 'failed';
    else if (row.status_api === 5 || row.status_api === 2) {
      // Si la transacción se creó hace más de 15 minutos y no resolvió, no considerarla pending infinito
      const createdMs = row.created_at ? new Date(row.created_at).getTime() : 0;
      const isStale = createdMs > 0 && (Date.now() - createdMs > 15 * 60 * 1000);
      status = isStale ? 'completed' : 'pending';
    } else {
      status = 'idle';
    }
    const isCardRefund = row.gateway === 1;
    const digitsMismatch = Boolean(row.account_digits && row.actual_digits && String(row.actual_digits).slice(-4) !== String(row.account_digits).slice(-4));
    return {
      transactionId: row.transaction_id, reference: row.reference, amount: row.amount,
      accountDigits: row.account_digits, institutionName: row.institution_name,
      transactionStatus: row.status_api,
      gateway: row.gateway, lastModifiedUtc: row.last_modified_utc,
      status, phase: status,
      alerts: { gatewayMismatch: isCardRefund, digitsMismatch: digitsMismatch },
    };
  }

  function _withdrawStatusHtml(st) {
    if (!st || st.status === 'idle') return '';
    const g = window.esc || (s => s);
    const money = window.fmtMoney || (v => `$${(v || 0).toFixed(2)}`);
    const ref = st.reference ? g(st.reference) : '';
    const isCard = st.gateway === 1 || (st.alerts && st.alerts.gatewayMismatch);
    let line;
    if (st.status === 'successful' || st.status === 'completed') {
      if (isCard) {
        line = `<span class="pat-wd-line pat-wd-warn"><i class="ph-bold ph-credit-card"></i> Retiro procesado como REEMBOLSO A TARJETA${ref ? ` (ref ${ref})` : ''}. (Se reflejará en el plástico que depositó).</span>`;
      } else {
        const dest = st.institutionName ? ` a ${g(st.institutionName)}` : '';
        const digs = st.accountDigits ? ` (···${g(st.accountDigits)})` : '';
        line = `<span class="pat-wd-line pat-wd-ok"><i class="ph-bold ph-check-circle"></i> BetMexico procesó el retiro SPEI${dest}${digs}${ref ? ` (ref ${ref})` : ''}. Confirma en tu banco.</span>`;
      }
    } else if (st.status === 'failed') {
      line = `<span class="pat-wd-line pat-wd-fail"><i class="ph-bold ph-x-circle"></i> Retiro fallido / rechazado${ref ? ` (ref ${ref})` : ''}.</span>`;
    } else {
      if (isCard) {
        line = `<span class="pat-wd-line"><span class="dep-spinner"></span> Reembolso a Tarjeta en proceso${ref ? ` (ref ${ref})` : ''}…</span>`;
      } else {
        const dest = st.institutionName ? ` a ${g(st.institutionName)}` : '';
        const digs = st.accountDigits ? ` (···${g(st.accountDigits)})` : '';
        line = `<span class="pat-wd-line"><span class="dep-spinner"></span> Retiro SPEI en proceso${dest}${digs}${ref ? ` (ref ${ref})` : ''}…</span>`;
      }
    }
    const alerts = st.alerts || {};
    let alertHtml = '';
    if (alerts.gatewayMismatch) {
      alertHtml += `<div class="pat-wd-alert">⚠️ BetMexico desvió el retiro a REEMBOLSO DE TARJETA, no a la CLABE SPEI.</div>`;
    }
    if (alerts.digitsMismatch) {
      alertHtml += `<div class="pat-wd-alert">⚠️ El retiro fue a dígitos distintos a la cuenta esperada (${g(st.accountDigits || '?')}).</div>`;
    }
    return `<div class="pat-wd-row"><span class="pat-wd-amt">${money(st.amount)}</span>${line}</div>${alertHtml}`;
  }

  // Botón de retiro dedicado en .pat-actions (derecha de Depositar). Dispara directo
  // Panel de monto + estado 2-fases en col 3 (.pat-col-stage). Visible en reposo para SA
  // (llena el espacio que antes quedaba vacío). Si hay misión de depósito (#depStage visible),
  // CSS :has() lo oculta — depos.js intacto.
  // El botón "Retirar" vive JUNTO al campo de monto (Robert 2026-07-28, campo: "no se
  // entiende qué hacen hasta allá lejos de donde se ponen las cantidades") — antes
  // disparaba desde `.pat-actions`, en la esquina, sin relación visual con su propio
  // input. Se fusiona lo que antes era renderPantallaWithdrawButton() aquí mismo.
  // Estado puro de retiro para esta cuenta — sin tocar el DOM (2026-07-28: antes
  // esto armaba su propio bloque HTML `.pat-wd-stage`; ahora Depositar/Retirar
  // comparten UN panel — ver _applyWithdrawToCompact). Muta d._wd_pending como
  // antes (otros callers lo leen).
  function _withdrawState(d) {
    const L = window.PantallaLogic || {};
    const role = (state.user || {}).role;
    const st = _wdStatusFromRow(d && d.last_withdrawal);
    d && (d._wd_pending = !!(st && st.status === 'pending'));
    const s2 = L._withdrawBtnState ? L._withdrawBtnState(d, role) : { render: false, disabled: true, tooltip: '' };
    return { s2, st, pending: !!(d && d._wd_pending) };
  }

  // Columna 3: SOLO los slots que depos.js monta — ya no arma su propio bloque de
  // retiro aquí (campo, Robert 2026-07-28, 3ª ronda: "reutilizando el cuadro de
  // texto de monto, botón depositar junto a retirar... en lugar de dos pestañas").
  // El botón/estado de retiro vive DENTRO de #deposCompactTpl (index.html) y se
  // rellena en _applyWithdrawToCompact() justo después de montar el panel.
  function renderPantallaStageCol(d) {
    return `<div class="pat-col-stage">
      <div id="patStageSlot"></div>
      <div id="patDepSlot"></div>
    </div>`;
  }

  // Rellena los elementos de retiro que YA existen en la plantilla del depósito
  // compacto (#wd, #wdBalance, #wdStatus, #wdErr) — un solo panel, un solo campo
  // de monto (#amtInput, propiedad del motor de depósitos) que ambos botones leen.
  // Se llama en cada render, después de _mountStage() (que ya clonó/montó la
  // plantilla). Idempotente: solo lectura+atributos, nunca innerHTML del panel
  // completo (eso lo hace depos.js, no lo duplicamos).
  function _applyWithdrawToCompact(d) {
    const root = document.getElementById('depCompact');
    if (!root) return;
    const g = window.esc || (s => s);
    const money = window.fmtMoney || (v => `$${(v || 0).toFixed(2)}`);
    const { s2, st, pending } = _withdrawState(d);
    const btn = root.querySelector('#wd');
    const balEl = root.querySelector('#wdBalance');
    const statusEl = root.querySelector('#wdStatus');
    if (btn) {
      btn.hidden = !s2.render;
      btn.disabled = !!s2.disabled || pending;
      btn.dataset.accId = d.id;
      btn.title = s2.tooltip || '';
    }
    if (balEl) {
      balEl.hidden = !s2.render;
      // Motivo de "Retirar" deshabilitado (p.ej. "Saldo < $100") visible SIEMPRE,
      // no solo al hover del botón (2026-08-01, auditoría: bajo presión no hay
      // tiempo de pasar el mouse para enterarse de por qué el botón no responde —
      // ver Nielsen #1 visibilidad de estado). Solo se agrega si está deshabilitado
      // por una razón real (no cuando ya está "Retirar" listo/redundante, ni
      // mientras hay un retiro en curso — ese caso ya lo cubre #wdStatus).
      const note = (s2.render && s2.disabled && s2.tooltip && !pending)
        ? ` <span class="pat-wd-balance-note">· ${g(s2.tooltip)}</span>` : '';
      balEl.innerHTML = s2.render ? `Saldo Real: <b class="pat-wd-balance-v">${money(d.balance_real || 0)}</b>${note}` : '';
    }
    if (statusEl) statusEl.innerHTML = (s2.render && st) ? _withdrawStatusHtml(st) : '';
  }

  function _stopWithdrawPoll(accId) {
    const p = _wdPolls[accId];
    if (p) { clearInterval(p.timer); delete _wdPolls[accId]; }
  }

  async function _fetchWithdrawStatus(accId, txId) {
    const wrap = document.getElementById('depCompact');
    try {
      const r = await fetch(`/api/accounts/${accId}/withdraw/status/${txId}`);
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const st = await r.json();
      if (wrap) {
        const statusEl = wrap.querySelector('#wdStatus');
        if (statusEl) statusEl.innerHTML = _withdrawStatusHtml(st);
        wrap.classList.toggle('alert', !!(st.alerts && (st.alerts.gatewayMismatch || st.alerts.digitsMismatch)));
        const done = st.status !== 'pending';
        wrap.classList.toggle('pending', !done);
        const input = wrap.querySelector('#amtInput');
        const btn = wrap.querySelector('#wd');
        if (input) input.disabled = !done;
        if (btn) btn.disabled = !done;
        if (done) {
          _stopWithdrawPoll(accId);
          // Notificación al operador: retiro completado o fallido (Task #11)
          const ref = st.reference ? ` (ref ${st.reference})` : '';
          if (st.status === 'successful' || st.status === 'completed') {
            if (window.toast) toast(`✅ Retiro completado${ref}. Confirma en tu banco.`, 'success');
          } else if (st.status === 'failed') {
            if (window.toast) toast(`❌ Retiro fallido${ref}`, 'error');
          }
          // Refresh de la cuenta para que el saldo se actualice (Task #13)
          try {
            const cr = await fetch(`/api/accounts/${accId}/details`);
            if (cr.ok) {
              const cd = await cr.json();
              const cache = _cacheGet(accId);
              if (cache) {
                Object.assign(cache, cd);
                if (_currentId === accId) _renderDetailView(cache, false);
              }
            }
          } catch (_) { /* best-effort */ }
        } else {
          // Degradar a poll lento después de 2 min, parar tras 5 min
          const poll = _wdPolls[accId];
          if (poll) {
            if (Date.now() > poll.expireAt) {
              _stopWithdrawPoll(accId);
              wrap.classList.remove('pending');
              if (input) input.disabled = false;
              if (btn) btn.disabled = false;
            } else if (Date.now() > poll.fastUntil && poll.intervalMs !== WD_POLL_SLOW_MS) {
              clearInterval(poll.timer);
              poll.intervalMs = WD_POLL_SLOW_MS;
              poll.timer = setInterval(() => _fetchWithdrawStatus(accId, txId), WD_POLL_SLOW_MS);
            }
          }
        }
      }
      const cache = _cacheGet(accId);
      if (cache) {
        cache.last_withdrawal = { ...(cache.last_withdrawal || {}), status_api: st.transactionStatus, gateway: st.gateway, last_modified_utc: st.lastModifiedUtc };
      }
    } catch (err) {
      console.warn('[Pantalla] withdraw poll falló:', err.message);
    }
  }

  // Poll dinámico: 15s durante retiro activo (el operador quiere ver progreso),
  // 60s como mínimo absoluto (guardarrail rate-limit BetMexico). Al detectar
  // estado terminal, el poll se detiene solo (ver _fetchWithdrawStatus).
  const WD_POLL_FAST_MS = 15000;
  const WD_POLL_SLOW_MS = 60000;

  function _startWithdrawPoll(accId, txId) {
    _stopWithdrawPoll(accId); // 1 solo interval activo por cuenta
    _fetchWithdrawStatus(accId, txId); // primer chequeo inmediato
    const timer = setInterval(() => _fetchWithdrawStatus(accId, txId), WD_POLL_FAST_MS);
    _wdPolls[accId] = {
      timer,
      txId,
      fastUntil: Date.now() + 2 * 60 * 1000,
      expireAt: Date.now() + 5 * 60 * 1000,
      intervalMs: WD_POLL_FAST_MS,
    };
  }

  // Reanuda el polling si La Pantalla se reabre con un retiro no-terminal (p.ej.
  // otro operador la cerró a medio proceso, o hubo reload de página).
  function _resumeWithdrawPollIfPending(d) {
    const wd = d && d.last_withdrawal;
    if (!wd || !wd.transaction_id) return;
    const st = _wdStatusFromRow(wd);
    if (st && st.status === 'pending' && !_wdPolls[d.id]) {
      _startWithdrawPoll(d.id, wd.transaction_id);
    }
  }

  // ── Transacciones: UN historial cronológico (más reciente primero), fuentes
  // Botmexico/BetMexico mezcladas pero distinguibles por fila (pill de color +
  // ícono, mismo par que ya usaba el acordeón viejo: ph-lightning/ph-globe —
  // ver app.js _mvHead ~L3863) — antes se partían en 2 columnas por fuente, lo
  // que rompía el orden temporal real que el backend ya entrega (movimientos
  // viene pre-ordenado desc, ver app.py _mv_sort_key). Ahora que La Pantalla
  // tiene todo el ancho disponible para una sola lista, cada fila lleva más
  // detalle (operador, tarjeta, motivo en el title) en vez de repartir el
  // espacio en 2 columnas angostas. */

  function _mvResultCls(m) {
    if ((m.reason || '').toUpperCase().includes('3DS')) return 'threeds';
    return ({ ok: 'ok', fail: 'fail', pending: 'pending', wd: 'wd', incomplete: 'pending' })[m.state] || 'pending';
  }
  function _mvSrcCls(m) {
    return m.source === 'dashboard' ? 'pat-mv-src--dash' : 'pat-mv-src--bet';
  }
  function _mvSrcBadge(m) {
    return m.source === 'dashboard'
      ? '<i class="ph-fill ph-lightning"></i>'
      : '<i class="ph-duotone ph-globe-hemisphere-west"></i>';
  }
  function _mvSrcLabel(m) {
    return m.source === 'dashboard' ? 'Botmexico' : 'BetMexico';
  }
  function _mvDesc(m) {
    const g = window.esc || (s => s);
    let base;
    if ((m.reason || '').toUpperCase().includes('3DS')) base = 'Verificación 3DS';
    else if (m.state === 'fail') base = 'Rechazado (banco)';   // SOLO rechazo REAL de banco
    else if (m.state === 'incomplete') base = 'No aplicado';   // rate-limit/infra/cuenta — motivo en el detalle
    else base = m.kind === 'withdrawal' ? 'Retiro' : 'Depósito';
    const bits = [];
    if (m.method) bits.push(g(m.method));
    if (m.who) bits.push(g(m.who));                              // operador que lo disparó (solo dashboard)
    if (m.card_pipe) bits.push(`···${g(String(m.card_pipe).replace(/\|.*/, '').slice(-4))}`);  // últimos 4 de la tarjeta usada
    return bits.length ? `${base} · ${bits.join(' · ')}` : base;
  }
  // Fecha COMPLETA de la transacción. `when` llega en ISO ("YYYY-MM-DD HH:MM:SS")
  // desde /details → el regex viejo (esperaba "DD/MM") fallaba y pintaba "2026-".
  // fmtAbsYear (app.js, scope global compartido) da "03 jul 03:42" (mismo año) o
  // "03 jul 24, 03:42" (año viejo) — año condicional, corto y legible.
  function _mvTime(m) {
    const w = String(m.when || '');
    if (!w) return '—';
    if (typeof fmtAbsYear === 'function') { const f = fmtAbsYear(w); if (f) return f; }
    const iso = w.match(/^(\d{4})-(\d{2})-(\d{2})[ T](\d{2}):(\d{2})/);   // fallback ISO → "DD/MM HH:MM"
    if (iso) return `${iso[3]}/${iso[2]} ${iso[4]}:${iso[5]}`;
    return w.slice(0, 10);
  }
  // pos = posición dentro del historial (0-based) → alimenta --j (stagger corto
  // del cuaje entre filas). idx sigue siendo el índice GLOBAL para data-mv-idx.
  // Detalle expandible al click de la fila. Solo los movimientos del propio
  // dashboard (m.who/m.card_pipe) traen algo que mostrar — el eco de BetMexico no
  // carga esos campos (lo dice el spec: "por lo menos las hechas en Botmexico").
  // Tarjeta SIN enmascarar (memoria: pipe puro, copiado rápido es prioridad).
  function _mvExpand(m) {
    const g = window.esc || (s => s);
    const rows = [];
    if (m.who) rows.push(`<div class="pat-mv-exp-row"><span class="k">Operador</span><span class="v">${g(m.who)}</span></div>`);
    if (m.card_pipe) rows.push(`<div class="pat-mv-exp-row"><span class="k">Tarjeta</span><span class="v pat-mv-exp-copy d-copy" data-copy="${g(m.card_pipe)}" title="Click para copiar">${g(m.card_pipe)}</span></div>`);
    if (m.reason) rows.push(`<div class="pat-mv-exp-row"><span class="k">Motivo</span><span class="v">${g(m.reason)}</span></div>`);
    if (!rows.length) rows.push(`<div class="pat-mv-exp-row"><span class="v dim">Eco de BetMexico — sin detalle interno.</span></div>`);
    return `<div class="pat-mv-exp"><div class="pat-mv-exp-in">${rows.join('')}</div></div>`;
  }
  function _mvLine(m, idx, pos) {
    const g = window.esc || (s => s);
    const money = window.fmtMoney || (v => `$${(v || 0).toFixed(2)}`);
    const cls = _mvResultCls(m);
    const srcCls = _mvSrcCls(m);
    const sign = m.kind === 'withdrawal' ? '−' : (m.state === 'ok' ? '+' : '');
    const title = m.reason ? ` title="${g(m.reason)}"` : '';
    return `<div class="pat-mv ${cls} ${srcCls}" data-mv-idx="${idx}" style="--j:${pos}"${title}>
      <div class="pat-mv-row">
        <span class="pat-mv-t">${g(_mvTime(m))}</span>
        <span class="pat-mv-src ${srcCls}" title="${g(_mvSrcLabel(m))}">${_mvSrcBadge(m)}</span>
        <span class="pat-mv-d">${g(_mvDesc(m))}</span>
        <span class="pat-mv-a">${sign}${money(m.amount)}</span>
      </div>
      ${_mvExpand(m)}
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
    // Ya viene ordenado desc por el backend (_mv_sort_key), pero ese sort normaliza
    // "T"→espacio antes de comparar (BetMexico manda "...T07:43:59", dashboard manda
    // "...  09:00:09"). Este sort "defensivo" comparaba el `when` CRUDO — 'T' (0x54)
    // > ' ' (0x20) en ASCII/localeCompare, así que CUALQUIER movimiento de BetMexico
    // salía "más reciente" que uno del dashboard del mismo día sin importar la hora
    // real, reventando el orden que el backend ya entregaba bien (bug de campo
    // 2026-08-06, confirmado con cuenta luisoz6666@gmail.com: 3 rechazos a las
    // 09:00/08:08/08:07 aparecían DESPUÉS de depósitos SPEI de 07:43/06:45).
    // Fix: normalizar igual que el backend antes de comparar.
    const _mvSortWhen = m => String((m || {}).when || '').replace('T', ' ');
    const sorted = movs.slice().sort((a, b) => _mvSortWhen(b).localeCompare(_mvSortWhen(a)));
    const rows = sorted.map((m, i) => ({ m, i }));

    // El header (.pat-txn-h) YA NO vive dentro del área scrolleable — antes se iba
    // con el scroll (desaparecía el rótulo "Movimientos" al bajar la lista). Ahora
    // es hermano fijo de .pat-txn-col, arriba de la columna (2026-07-09, campo).
    if (!rows.length) {
      return `<div class="pat-col-txns">
        <div class="pat-txn-h"><i class="ph-duotone ph-clock-counter-clockwise"></i> Movimientos</div>
        <div class="pat-txn-col" style="--i:4"><div class="pat-mv-empty">Sin movimientos todavía.</div></div>
      </div>`;
    }
    return `<div class="pat-col-txns">
      <div class="pat-txn-h"><i class="ph-duotone ph-clock-counter-clockwise"></i> Movimientos <span class="cnt">${rows.length}</span></div>
      <div class="pat-txn-col" style="--i:4">
        ${_mvColumn(rows)}
      </div>
    </div>`;
  }

  // animate: aplica la escritura líquida (.pat-liquid) SOLO cuando corresponde.
  // La bandera _liquidDone garantiza un único pase por cuenta: el re-render del
  // fetch fresco (o una re-apertura cacheada) llega con animate=false y no brinca.
  // Devuelve true si pintó el detalle real (false si tronó y solo mostró
  // .pat-error) — el llamador usa esto para NO marcar _liquidDone en un
  // render fallido; si no, al reabrir con datos ya buenos nunca se ve el
  // cuaje líquido (la bandera quedó puesta sobre un render que nunca ocurrió).
  // Monta (re-parenta) el ESCENARIO de depósito #depStage en su zona derecha
  // (#patStageSlot). El slot se recrea en cada render del detalle (innerHTML) —
  // #depStage sobrevive SOLO porque _renderDetailView llama _rescueStage() ANTES
  // de ese innerHTML (si no, el innerHTML= desconecta #depStage del documento —
  // como era hijo del slot viejo — y getElementById('depStage') ya no lo
  // encuentra: root cause de "la animación del depósito a veces no sale", campo
  // 2026-07-19. Bastaba con que CUALQUIER cuenta se re-renderizara una 2ª vez
  // con el escenario ya montado adentro para que quedara huérfano el resto de
  // la sesión). En reposo #depStage va hidden (zona derecha vacía); una misión
  // de depósito lo enciende (depos.js).
  function _rescueStage(detail) {
    const stage = document.getElementById('depStage');
    if (stage && detail.contains(stage)) document.body.appendChild(stage);
    if (window.Depos && typeof window.Depos.rescueCompact === 'function') window.Depos.rescueCompact(detail);
  }
  function _mountStage(d) {
    const slot = document.getElementById('patStageSlot');
    const stage = document.getElementById('depStage');
    if (slot && stage && stage.parentNode !== slot) slot.appendChild(stage);
    if (window.Depos && typeof window.Depos.mountCompact === 'function') window.Depos.mountCompact(d);
  }

  // Ancla --pat-ident-w a la medida REAL (getBoundingClientRect) de .pat-col-ident,
  // NO a un px inventado (feedback_ui_ancla_medida_no_pixel_inventado). El form de
  // CURP (data-curp-form) vive fuera de .pat-col-ident (necesita más aire que el
  // combo para su input+botones) pero Robert pidió que su borde derecho termine
  // exactamente donde termina esa columna (línea amarilla, campo 2026-07-10) — sin
  // esto, al ser hijo directo de .pat-wrap (flex-column, stretch) se estiraba al
  // ancho COMPLETO de la sheet. rAF: mide después de que el layout real asentó.
  function _syncIdentWidth() {
    requestAnimationFrame(() => {
      const wrap = document.querySelector('.pat-wrap');
      const ident = wrap && wrap.querySelector('.pat-col-ident');
      if (!wrap || !ident) return;
      const w = ident.getBoundingClientRect().width;
      if (w > 0) wrap.style.setProperty('--pat-ident-w', `${Math.round(w)}px`);
    });
  }

  // Detecta si las 3 columnas caben lado a lado midiendo el ancho REAL
  // (scrollWidth vs clientWidth de .pat-columns), no un breakpoint px inventado
  // (feedback_ui_ancla_medida_no_pixel_inventado). Sin esto, entre mobile (≤767px)
  // y desktop ancho el stage se desbordaba y quedaba invisible, clippeado por
  // overflow:hidden de .pantalla-sheet (bug de campo 2026-07-26, ver pantalla.css
  // §.pat-cramped). Se re-mide en cada render Y en cada resize de ventana —
  // el mismo ancho de ventana puede caber o no según qué tan largo sea el combo
  // de la cuenta abierta (.pat-col-ident es max-content).
  function _syncColumnsFit() {
    requestAnimationFrame(() => {
      const wrap = document.querySelector('.pat-wrap');
      const cols = wrap && wrap.querySelector('.pat-columns');
      if (!wrap || !cols) return;
      const cramped = cols.scrollWidth > cols.clientWidth + 1;
      wrap.classList.toggle('pat-cramped', cramped);
    });
  }

  let _columnsFitResizeWired = false;
  function _wireColumnsFitResize() {
    if (_columnsFitResizeWired) return;
    _columnsFitResizeWired = true;
    window.addEventListener('resize', () => {
      if (document.querySelector('.pat-wrap')) _syncColumnsFit();
    });
  }

  // Alto dinámico de la ficha (2026-07-27/28, campo). Las 3 columnas (datos |
  // depósito/retiro | historial) viven en UNA sola fila de .pat-columns (grid,
  // ver pantalla.css, 4ª ronda 2026-07-28: historial dejó de ser una fila propia
  // abajo). Por eso la ficha ya NO suma la altura de movimientos aparte — toma
  // el MÁXIMO de las 3 columnas, igual que antes hacía solo con ident/stage.
  // Historial sigue siendo la única con scroll propio (.pat-txn-col), así que no
  // necesita declarar su scrollHeight completo — TXNS_MIN solo le da un piso.
  function _syncFichaHeight() {
    requestAnimationFrame(() => {
      if (!window.KpiPanel || typeof window.KpiPanel.apply !== 'function') return;
      const wrap = document.querySelector('.pat-wrap');
      const ident = wrap && wrap.querySelector('.pat-col-ident');
      const stage = wrap && wrap.querySelector('.pat-col-stage');
      const txns = wrap && wrap.querySelector('.pat-col-txns');
      const topbar = wrap && wrap.querySelector('.pat-topbar');
      if (!wrap || !ident || !stage || !txns) return;
      const SHEET_INSETS = 18 + 14;    // .pantalla-sheet top+bottom (pantalla.css)
      const WRAP_GAP = 9;              // .pat-wrap gap (pantalla.css)
      const ROW_GAP = 14;              // .pat-columns row-gap (grid) — solo aplica apilado
      const TXNS_MIN = 120;            // piso visible de movimientos (su scroll propio hace el resto)
      // Modo apilado (.pat-cramped, las 3 no caben lado a lado): la fila es la
      // SUMA (una debajo de otra), no el máximo — a diferencia del modo lado a
      // lado. Sin esto, la ficha crecía poco y stage/txns (overflow-y:auto +
      // min-height:0) se comprimían por debajo de su contenido real.
      const cramped = wrap.classList.contains('pat-cramped');
      const rowH = cramped
        ? ident.scrollHeight + ROW_GAP + stage.scrollHeight + ROW_GAP + Math.max(txns.scrollHeight, TXNS_MIN)
        : Math.max(ident.scrollHeight, stage.scrollHeight, TXNS_MIN);
      const topbarH = topbar ? Math.ceil(topbar.getBoundingClientRect().height) : 0;
      const ACTIONS_CLEARANCE = 8;     // .pat-columns margin-bottom (ya no hay CTA flotante que despejar)
      const needed = topbarH + WRAP_GAP + rowH + ACTIONS_CLEARANCE + SHEET_INSETS;
      // SOFT_CAP: techo duro (campo, Robert 2026-07-28: "mira lo gigante que está,
      // empuja todo"). El "sin scroll obligatorio" de 2026-07-27 se relaja — más
      // allá de este techo, identidad/escenario absorben el resto con SU PROPIO
      // overflow-y:auto (ya lo tenían, pantalla.css .pat-col-ident/.pat-col-stage)
      // en vez de inflar la ficha entera hasta tapar la tabla de cuentas. Cuentas
      // con muchas tarjetas/notas ocasionalmente necesitarán ese scroll propio —
      // aceptable: el costo lo paga la cuenta rara, no cada apertura.
      const SOFT_CAP = 480;
      const focusCap = typeof window.KpiPanel.focusMaxH === 'function' ? window.KpiPanel.focusMaxH() : window.KpiPanel.maxH();
      const cap = Math.min(SOFT_CAP, focusCap);
      const h = Math.min(Math.max(Math.ceil(needed), window.KpiPanel.DEFAULT_H), cap);
      window.KpiPanel.apply(h);
    });
  }
  let _fichaHeightResizeWired = false;
  function _wireFichaHeightResize() {
    if (_fichaHeightResizeWired) return;
    _fichaHeightResizeWired = true;
    window.addEventListener('resize', () => {
      const root = document.getElementById('pantalla');
      if (document.querySelector('.pat-wrap') && root && !root.hidden) _syncFichaHeight();
    });
  }

  function _renderDetailView(d, animate) {
    const { detail } = els();
    if (!detail) return false;
    try {
      _rescueStage(detail);        // saca #depStage de `detail` ANTES del wipe de abajo (ver _rescueStage)
      const liquid = animate ? ' pat-liquid' : '';
      detail.innerHTML = `<div class="pat-wrap${liquid}">${renderPantallaHead(d)}</div>`;
      _mountStage(d);              // re-parenta el escenario + monta/reseedea el panel de depósito compacto
      _applyWithdrawToCompact(d);  // rellena botón/saldo/estado de retiro DENTRO del mismo panel (2026-07-28)
      _syncIdentWidth();           // ancla --pat-ident-w a la medida REAL de la columna (form CURP la usa)
      _syncColumnsFit();           // marca .pat-cramped si las 3 columnas no caben lado a lado
      _wireColumnsFitResize();     // re-mide al redimensionar la ventana
      _syncFichaHeight();          // crece la ficha si identidad+escenario no caben sin scroll
      _wireFichaHeightResize();
      _resumeWithdrawPollIfPending(d);
      // Auto-fetch clabes SPEI si no existen (Task #14): una sola vez por cuenta.
      // Las clabes son FIJAS por usuario — BeginDeposit no duplica, solo devuelve
      // las mismas. Se dispara en background, sin bloquear el render.
      const clabesArr = Array.isArray(d.clabes) ? d.clabes : [];
      if (clabesArr.length === 0 && d.id && !_clabesFetched.has(d.id)) {
        _clabesFetched.add(d.id);
        const autoAccId = d.id;
        fetch(`/api/accounts/${autoAccId}/clabes/refresh`, { method: 'POST' })
          .then(r => r.ok ? r.json() : null)
          .then(data => {
            if (data && data.clabes && data.clabes.length > 0) {
              const cache = _cacheGet(autoAccId);
              if (cache) { cache.clabes = data.clabes; _renderDetailView(cache, false); }
              if (window.toast) toast(`🏦 ${(data.clabes || []).length} clabes SPEI obtenidas`, 'success');
            }
          })
          .catch(() => {}); // silencioso: si falla, el botón manual queda disponible
      }
      return true;
    } catch (e) {
      console.error('[Pantalla] render failed:', e);
      detail.innerHTML = `<div class="pat-error">Error renderizando: ${window.esc ? esc(e.message) : e.message}</div>`;
      return false;
    }
  }

  // ─────────────────────────── listeners ───────────────────────────

  // Fase B — El trigger para abrir La Pantalla desde la tabla es el CLICK IZQUIERDO
  // simple (sin modificadores), manejado en el click handler de #accTable en app.js
  // (`window.Pantalla.open`). Ctrl/Shift+Click hacen selección tipo Excel. Ya no se
  // usa contextmenu (click derecho).

  // Cierre: SOLO (a) click en [data-close] = backdrop (clic FUERA del sheet, sobre
  // el vidrio difuminado alrededor) o el botón X de la esquina. Click DENTRO del
  // sheet ya nunca cierra — antes un click en espacio "limpio" del sheet lo cerraba
  // y sacaba al operador a media interacción (Robert 2026-07-17: "que se cierre
  // solamente al click fuera de la pantalla o en la tachita"). Click en otra parte
  // del dashboard (p.ej. otra fila) tampoco cierra: solo cambia de cuenta.
  document.addEventListener('click', e => {
    if (e.target.closest('[data-close]')) close();
    const retryBtn = e.target.closest('[data-wd-retry-open]');
    if (retryBtn) open(parseInt(retryBtn.dataset.wdRetryOpen));
  });

  // Combo copiable tipo liga: el copiado real lo hace el handler global (.d-copy);
  // aquí solo el feedback visual (parpadeo verde "copiado") al click en el texto.
  document.addEventListener('click', e => {
    const combo = e.target.closest('.pat-combo, .pat-curp, .pat-sv-card, .pat-mv-exp-copy');
    if (!combo) return;
    combo.classList.add('copied');
    setTimeout(() => combo.classList.remove('copied'), 900);
  });

  // ── Controles principales dentro de La Pantalla (Depositar / Fijar) ──
  // Los handlers de app.js están delegados en #accTable y NO capturan dentro de
  // #pantalla; aquí cableamos reusando las funciones GLOBALES (openDepositModal,
  // toggleMark). El candadito "En uso" se eliminó (lock único = auto-lock al depositar).
  const _patRoot = $('#pantalla');
  if (_patRoot) _patRoot.addEventListener('click', async e => {
    // Click en una fila de movimiento → toggle del detalle expandible (quién,
    // tarjeta completa, motivo). No si el click cayó en la tarjeta copiable de
    // adentro (ese click copia, no debe además abrir/cerrar el detalle) ni si
    // el mousedown→mouseup vino de un drag-scroll (ver initTxnScroll, _mvDragged).
    const mv = e.target.closest('.pat-mv');
    if (mv && !e.target.closest('.pat-mv-exp-copy') && !_mvDragged) {
      mv.classList.toggle('exp');
      return;
    }
    const dep = e.target.closest('.d-deposit-btn');
    if (dep && dep.dataset.accId && !dep.disabled) {
      e.preventDefault();
      if (window.Depos && typeof window.Depos.fireCompact === 'function') window.Depos.fireCompact(parseInt(dep.dataset.accId));
      return;
    }
    const mark = e.target.closest('.det-mark');
    if (mark && mark.dataset.markEmail) {
      e.preventDefault();
      if (typeof window.toggleMark === 'function') window.toggleMark(mark.dataset.markEmail, mark);
      return;
    }
    // Candadito "En uso" ELIMINADO de La Pantalla (Robert 2026-07-17) — su handler se
    // quitó con el botón. El lock ahora es UNO solo: el auto-lock al depositar. Ver
    // renderPantallaHead + app.py (sacar a trastienda libera la RESERVADA_SA).

    // ── Notas: agregar/borrar (portado del acordeón viejo — mismos endpoints) ──
    if (e.target.closest('[data-add-note]')) {
      e.preventDefault();
      const form = _patRoot.querySelector('[data-note-form]');
      if (form) { form.hidden = !form.hidden; if (!form.hidden) form.querySelector('[data-note-input]').focus(); }
      return;
    }
    if (e.target.closest('[data-note-cancel]')) {
      e.preventDefault();
      const form = _patRoot.querySelector('[data-note-form]');
      if (form) { form.hidden = true; form.querySelector('[data-note-input]').value = ''; }
      return;
    }
    const noteSave = e.target.closest('[data-note-save]');
    if (noteSave) {
      e.preventDefault();
      const accId = _currentId;
      const form = noteSave.closest('[data-note-form]');
      const input = form && form.querySelector('[data-note-input]');
      const text = (input && input.value || '').trim();
      if (!text || !accId) return;
      noteSave.disabled = true;
      try {
        const r = await fetch(`/api/accounts/${accId}/notes`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text }) });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
        const cache = _cacheGet(accId);
        if (cache) {
          const u = state.user || {};
          const note = { id: data.id, note_text: text, created_by: u.telegram_id, created_by_name: u.display || u.username || '?', created_at: data.created_at };
          cache.notes = [note, ...(Array.isArray(cache.notes) ? cache.notes : [])];
          _renderDetailView(cache, false);
        }
        if (window.toast) toast('📝 Nota guardada', 'success');
      } catch (err) {
        if (window.toast) toast(`Error: ${err.message}`, 'error');
      } finally {
        noteSave.disabled = false;
      }
      return;
    }
    const delNote = e.target.closest('[data-del-note]');
    if (delNote) {
      e.preventDefault();
      const accId = _currentId;
      const noteId = delNote.dataset.delNote;
      if (!accId || !noteId) return;
      if (!confirm('¿Borrar esta nota?')) return;
      try {
        const r = await fetch(`/api/accounts/${accId}/notes/${noteId}`, { method: 'DELETE' });
        if (!r.ok) { const data = await r.json().catch(() => ({})); throw new Error(data.detail || `HTTP ${r.status}`); }
        const cache = _cacheGet(accId);
        if (cache && Array.isArray(cache.notes)) {
          cache.notes = cache.notes.filter(n => String(n.id) !== String(noteId));
          _renderDetailView(cache, false);
        }
        if (window.toast) toast('Nota borrada', '');
      } catch (err) {
        if (window.toast) toast(`Error: ${err.message}`, 'error');
      }
      return;
    }

    // ── Clabes: refrescar manualmente (BeginDeposit vía POST /clabes/refresh) ──
    // El operador lo dispara a propósito. NO automático en cada refresh de cuenta
    // (alimentaría el rate-limit de BetMexico; las clabes son FIJAS por usuario).
    const clabeRefresh = e.target.closest('[data-clabe-refresh]');
    if (clabeRefresh) {
      e.preventDefault();
      const accId = parseInt(clabeRefresh.dataset.clabeRefresh) || _currentId;
      if (!accId) return;
      // Deshabilita el botón + feedback de carga (evita doble-click).
      const btn = clabeRefresh.closest('button') || clabeRefresh;
      const orig = btn.innerHTML;
      btn.disabled = true;
      btn.innerHTML = '<span class="dep-spinner"></span>';
      try {
        const r = await fetch(`/api/accounts/${accId}/clabes/refresh`, { method: 'POST' });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
        const cache = _cacheGet(accId);
        if (cache) { cache.clabes = data.clabes || []; _renderDetailView(cache, false); }
        if (window.toast) toast(`🏦 ${(data.clabes || []).length} clabes obtenidas`, 'success');
      } catch (err) {
        if (window.toast) toast(`Clabes: ${err.message}`, 'error');
      } finally {
        btn.disabled = false;
        btn.innerHTML = orig;
      }
      return;
    }

    // ── Retiro automático (SA-only): dispara withdrawals.py vía POST /withdraw,
    // luego monitorea con polling 60s (G1). Bloquea el botón mientras hay uno en
    // curso (guardarrail concurrencia — bug de campo: 2do disparo puede duplicar). ──
    const wdFire = e.target.closest('.d-withdraw-fire');
    if (wdFire) {
      e.preventDefault();
      const wrap = document.getElementById('depCompact');
      const accId = parseInt(wdFire.dataset.accId) || _currentId;
      const input = wrap && wrap.querySelector('#amtInput');
      const amount = input ? parseFloat(input.value) : NaN;
      if (!accId || wdFire.disabled) return;
      if (!amount || isNaN(amount) || amount < 100) {
        // El CTA vive fijo en la esquina, pero el campo de monto puede estar fuera
        // de vista (columna scrolleable) — un toast solo no dice DÓNDE escribir.
        // Llevamos la vista al campo y lo enfocamos (campo, Robert 2026-07-27:
        // "no se donde se pone el monto de retiro").
        if (wrap) wrap.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        if (input) {
          input.focus(); input.select();
          input.classList.add('hint-target-glow');
          setTimeout(() => input.classList.remove('hint-target-glow'), 2400);
        }
        if (window.toast) toast('Escribe el monto a retirar (mín. $100) ↑', 'error');
        return;
      }
      wdFire.disabled = true;
      if (input) input.disabled = true;
      const statusEl = wrap && wrap.querySelector('#wdStatus');
      if (statusEl) statusEl.innerHTML = `<div class="pat-wd-row"><span class="dep-spinner"></span> Disparando retiro…</div>`;
      try {
        const r = await fetch(`/api/accounts/${accId}/withdraw`, {
          method: 'POST', headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ amount }),
        });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
        // BetMexico ya ejecutó el retiro real llegado aquí (200) — persisted:false es
        // un caso raro (lock de BD) donde SÍ salió pero no quedó guardado localmente.
        // NO es el mismo caso que un error: no lo pintamos como falla, avisamos aparte
        // para que el operador anote el transactionId a mano (bug de campo 2026-07-25).
        if (data.persisted === false) {
          if (window.toast) toast(`⚠️ Retiro SÍ salió (ref ${data.transactionId}) pero no se guardó local — anótalo`, 'error');
          if (statusEl) statusEl.innerHTML = `<div class="pat-wd-row pat-wd-fail"><i class="ph-bold ph-warning"></i> Retiro ejecutado, transactionId ${window.esc ? esc(data.transactionId) : data.transactionId} — no se pudo guardar, anótalo</div>`;
          return;
        }
        const cache = _cacheGet(accId);
        if (cache) {
          cache.last_withdrawal = {
            transaction_id: data.transactionId, reference: data.reference, amount: data.amount,
            account_digits: data.accountDigits, institution_name: data.institutionName,
            status_api: null, gateway: null, last_modified_utc: null,
          };
          if (_currentId === accId) _renderDetailView(cache, false);
        }
        if (window.toast) toast('🏧 Retiro disparado', 'success');
        _startWithdrawPoll(accId, data.transactionId);
      } catch (err) {
        if (window.toast) toast(`Retiro: ${err.message}`, 'error');
        wdFire.disabled = false;
        if (input) input.disabled = false;
        if (statusEl) statusEl.innerHTML = '';
      }
      return;
    }

    // ── CURP: guardar validado manualmente (mismo endpoint/regex que el acordeón viejo) ──
    const curpToggle = e.target.closest('[data-curp-toggle]');
    if (curpToggle) {
      e.preventDefault();
      const form = _patRoot.querySelector('[data-curp-form]');
      if (!form) return;
      form.hidden = !form.hidden;
      if (!form.hidden) {
        const input = form.querySelector('[data-curp-input]');
        const stateSelect = form.querySelector('[data-curp-state-select]');
        const d = _cacheGet(_currentId) || {};
        const bdate = d.birthdate ? d.birthdate.split('T')[0] : '';
        const candidates = (typeof generateCurpCandidates === 'function')
          ? generateCurpCandidates(d.fullname, bdate, d.address)
          : [];

        if (stateSelect) {
          stateSelect.innerHTML = candidates.map(c =>
            `<option value="${c.code}" ${c.isDetected ? 'selected' : ''}>${c.name} (${c.curp})</option>`
          ).join('');

          // Listener change único para actualizar el input con el candidato elegido
          stateSelect.onchange = () => {
            const selectedCode = stateSelect.value;
            const cand = candidates.find(c => c.code === selectedCode);
            if (cand && input) {
              input.value = cand.curp;
              input.classList.remove('pat-input-err');
              const err = form.querySelector('[data-curp-err]');
              if (err) err.hidden = true;
            }
          };
        }

        // Si ya hay un valor o candidato inicial, asignarlo al input
        const initialCand = candidates.find(c => c.isDetected) || candidates[0];
        input.value = curpToggle.dataset.curpToggle || (initialCand ? initialCand.curp : '');
        input.focus();
        input.classList.remove('pat-input-err');
        const err = form.querySelector('[data-curp-err]'); if (err) err.hidden = true;
      }
      return;
    }
    if (e.target.closest('[data-curp-cancel]')) {
      e.preventDefault();
      const form = _patRoot.querySelector('[data-curp-form]');
      if (form) form.hidden = true;
      return;
    }
    const curpSave = e.target.closest('[data-curp-save]');
    if (curpSave) {
      e.preventDefault();
      const accId = _currentId;
      const form = curpSave.closest('[data-curp-form]');
      const input = form && form.querySelector('[data-curp-input]');
      const errEl = form && form.querySelector('[data-curp-err]');
      const curp = (input && input.value || '').trim().toUpperCase();
      const CURP_RE = /^[A-Z]{4}\d{6}[HM][A-Z]{5}[0-9A-Z]\d$/;   // misma regex que app.py update_curp
      if (!CURP_RE.test(curp)) {
        if (errEl) { errEl.textContent = 'CURP inválido (formato de 18 caracteres)'; errEl.hidden = false; }
        if (input) input.classList.add('pat-input-err');
        return;
      }
      if (!accId) return;
      curpSave.disabled = true;
      try {
        const r = await fetch(`/api/accounts/${accId}/curp`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ curp }) });
        const data = await r.json().catch(() => ({}));
        if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
        const cache = _cacheGet(accId);
        if (cache) { cache.curp = data.curp; _renderDetailView(cache, false); }
        if (window.toast) toast('🪪 CURP guardado', 'success');
      } catch (err) {
        if (errEl) { errEl.textContent = err.message; errEl.hidden = false; }
      } finally {
        curpSave.disabled = false;
      }
      return;
    }
  });

  // Cierre: Esc global (solo si La Pantalla está visible).
  document.addEventListener('keydown', e => {
    if (e.key !== 'Escape') return;
    const root = $('#pantalla');
    if (root && !root.hidden) close();
  });

  // ── Click-y-jala para scrollear el historial (.pat-txn-col) — la rueda ya
  // funciona nativo (overflow-y:auto en CSS). Delegado en #pantalla porque
  // .pat-txn-col se re-renderiza en cada refresh de detalle (innerHTML) — un
  // listener puesto directo en el nodo se perdería al siguiente render.
  // Mismo umbral de 6px que la selección tipo Explorer del repo (app.js) para
  // distinguir un click (togglea detalle) de un drag (solo scrollea).
  (function initTxnDragScroll() {
    const root = $('#pantalla');
    if (!root) return;
    let col = null, startY = 0, startTop = 0, dragging = false;
    root.addEventListener('pointerdown', e => {
      const c = e.target.closest('.pat-txn-col');
      if (!c || e.target.closest('.pat-mv-exp-copy')) return;
      col = c; startY = e.clientY; startTop = c.scrollTop; dragging = true; _mvDragged = false;
      col.setPointerCapture?.(e.pointerId);
    });
    root.addEventListener('pointermove', e => {
      if (!dragging || !col) return;
      const dy = e.clientY - startY;
      if (!_mvDragged && Math.abs(dy) > 6) {
        _mvDragged = true;
        col.classList.add('dw-dragging');
        document.body.style.userSelect = 'none';   // evita seleccionar texto de las filas al arrastrar
      }
      if (_mvDragged) { col.scrollTop = startTop - dy; e.preventDefault(); }
    });
    const endDrag = () => {
      if (col) col.classList.remove('dw-dragging');
      document.body.style.userSelect = '';
      dragging = false; col = null;
      // El click sincrónico tras pointerup todavía necesita ver _mvDragged=true
      // (para no togglear el detalle); se limpia en el siguiente tick.
      setTimeout(() => { _mvDragged = false; }, 0);
    };
    root.addEventListener('pointerup', endDrag);
    root.addEventListener('pointercancel', endDrag);
  })();

  // ── Banda inferior: click = toggle plegar/desplegar el panel KPI (que arrastra
  // a La Pantalla vía el ResizeObserver de observeStrip). Ya NO se arrastra: el
  // control deslizable fino es el vgutter del panel KPI. ──
  // La banda inferior (plegar/desplegar) se ELIMINÓ (2026-07-09, Robert: "ya no
  // debería haber drag/collapse ni de los KPI ni de la pantalla, se quedan fijos").
  // El alto es fijo (ANCHOR_H, app.js) — nada que togglear.

  function updateAccount(accId, patch) {
    const cache = _cacheGet(accId);
    if (cache) {
      Object.assign(cache, patch);
      if (_currentId === accId) {
        _renderDetailView(cache, false);
      }
    }
  }

  // currentId expuesto para que renderTable() (app.js) pueda re-aplicar el glow
  // fila-fuente en cada re-render (SSE/sort/filtro reconstruyen el tbody y
  // borrarían la clase imperativa si no se recalcula desde acá).
  window.Pantalla = { open, close, showTxn, back, updateAccount, get currentId() { return _currentId; } };
})();
