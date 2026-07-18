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
    // solo re-renderiza si seguimos mostrando la misma cuenta.
    fetch(`/api/accounts/${id}/details`)
      .then(r => { if (!r.ok) throw new Error(`HTTP ${r.status}`); return r.json(); })
      .then(data => {
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
    const curpTag = curpStored ? '' : (curpCalc ? ' <span class="est">est</span>' : '');

    const balance = d.balance_total != null ? d.balance_total : (d.balance_real || 0);
    const grade = d.grade || null;
    const gCls = (typeof gradeClass === 'function') ? gradeClass(grade) : '';

    // Tinte de La Pantalla por GRADE (Robert 2026-07-10, campo): data-grade en la
    // raíz retinta bordes/glow/CTA/saldo vía las mismas CSS vars (--pat-gold family),
    // ver pantalla.css. Se pone en CADA render (cache-hit y fetch fresco) para que
    // nunca quede desfasado si el grade cambió entre aperturas.
    const patRoot = $('#pantalla');
    if (patRoot) patRoot.dataset.grade = gCls || 'U';

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
      </div>
      <div class="pat-columns">
        <div class="pat-col-ident">
          <div class="pat-combo-line" style="--i:1">
            <button type="button" class="pat-combo d-copy" data-copy="${g(combo)}" title="Copiar">${g(combo)}</button>
          </div>
          <div class="pat-balance" style="--i:2">${money(balance)}</div>
          <div class="pat-ident-div" style="--i:3"></div>
          ${renderPantallaSaved(d)}
        </div>
        ${renderPantallaTxns(d)}
        <div class="pat-col-stage" id="patStageSlot"></div>
      </div>
      <div class="pat-actions">
        <button type="button" class="pat-act det-mark" data-mark-email="${g(email)}" title="Fijar"><i class="ph-bold ph-push-pin"></i></button>
        <button type="button" class="pat-act pat-act-dep d-deposit-btn" data-acc-id="${d.id}" title="Depositar"><i class="ph-duotone ph-credit-card"></i><span>Depositar</span></button>
      </div>`;
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
    const u = (window.state && state.user) || null;
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
    const sign = m.kind === 'withdrawal' ? '−' : (m.state === 'ok' ? '+' : '');
    const title = m.reason ? ` title="${g(m.reason)}"` : '';
    return `<div class="pat-mv ${cls}" data-mv-idx="${idx}" style="--j:${pos}"${title}>
      <div class="pat-mv-row">
        <span class="pat-mv-t">${g(_mvTime(m))}</span>
        <span class="pat-mv-src ${_mvSrcCls(m)}" title="${g(_mvSrcLabel(m))}">${_mvSrcBadge(m)}</span>
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
    // Ya viene ordenado desc por el backend (_mv_sort_key); sort defensivo por si
    // el string "when" (YYYY-MM-DD HH:MM:SS) llega desordenado de algún caller viejo.
    const sorted = movs.slice().sort((a, b) => String((b || {}).when || '').localeCompare(String((a || {}).when || '')));
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
  // (#patStageSlot). El slot se recrea en cada render del detalle (innerHTML), pero
  // #depStage es el MISMO nodo (movido del panel, no clonado) → una animación en curso
  // sobrevive al re-render. En reposo #depStage va hidden (zona derecha vacía); una
  // misión de depósito lo enciende (depos.js).
  function _mountStage() {
    const slot = document.getElementById('patStageSlot');
    const stage = document.getElementById('depStage');
    if (slot && stage && stage.parentNode !== slot) slot.appendChild(stage);
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

  function _renderDetailView(d, animate) {
    const { detail } = els();
    if (!detail) return false;
    try {
      const liquid = animate ? ' pat-liquid' : '';
      const gVar = (d.grade || 'U').replace('+', 'Plus');
      detail.innerHTML = `<div class="pat-wrap${liquid}" data-grade="${gVar}">${renderPantallaHead(d)}</div>`;
      _mountStage();               // re-parenta el escenario de depósito a la zona derecha
      _syncIdentWidth();           // ancla --pat-ident-w a la medida REAL de la columna (form CURP la usa)
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
    if (dep && dep.dataset.accId) {
      e.preventDefault();
      if (typeof window.openDepositModal === 'function') window.openDepositModal(parseInt(dep.dataset.accId));
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
          const u = (window.state && state.user) || {};
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

    // ── CURP: guardar validado manualmente (mismo endpoint/regex que el acordeón viejo) ──
    const curpToggle = e.target.closest('[data-curp-toggle]');
    if (curpToggle) {
      e.preventDefault();
      const form = _patRoot.querySelector('[data-curp-form]');
      if (!form) return;
      form.hidden = !form.hidden;
      if (!form.hidden) {
        const input = form.querySelector('[data-curp-input]');
        input.value = curpToggle.dataset.curpToggle || '';
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

  window.Pantalla = { open, close, showTxn, back };
})();
