/* depos.js — Modal de depósitos unificado v8 (C1).
   Componente vanilla autocontenido. Clona #deposTpl en #deposRoot, expone
   window.openDepos(opts) / window.closeDepos(). Lógica pura en DeposLogic (depos_logic.js).
   Convive con el drawer viejo (#depDrawer); la suplencia es por flag (Task 11). */
(function () {
  'use strict';
  const D = window.DeposLogic;
  const root = document.getElementById('deposRoot');
  const tpl = document.getElementById('deposTpl');
  if (!root || !tpl || !D) return; // defensa: si falta algo, no rompe el dashboard

  let el = null;          // #depos montado (ventana FLOTANTE — bulk multi-select)
  let elC = null;         // #depCompact montado (panel COMPACTO — dentro de La Pantalla, Task 3)
  let _mounted = false;
  let _mountedC = false;
  let _greetTimer = null;
  let _win = null;        // controlador de ventana (depos_window.js): float / dock-izq / dock-der
  // UN SOLO motor (_dx) con DOS destinos de render posibles. _dx.target decide a cuál
  // apunta qs() en cada momento — nunca corren los dos simultáneamente (mutua exclusión
  // resuelta por :has(#depStage:not([hidden])) en pantalla.css + reseed condicional en
  // mountCompact(), ver docs/superpowers/specs/2026-07-26-deposito-compacto-col3-design.md).
  const activeEl = () => (_dx.target === 'compact' ? elC : el);
  const qs = (s) => { const r = activeEl(); return r ? r.querySelector(s) : null; };
  // El ESCENARIO (escenas + %/sub + balance) ya NO vive en el panel: se movió a
  // #depStage, que La Pantalla monta en su zona derecha (#patStageSlot). sqs() lo
  // resuelve esté donde esté (re-parenteado por pantalla.js). #mov sigue en el panel → qs().
  const sqs = (s) => { const st = document.getElementById('depStage'); return st ? st.querySelector(s) : null; };

  let _dx = { open: false, target: 'float', accounts: [], cards: [], reps: 1, amount: 50, mode: 'single', running: false };

  // ── display 7 segmentos (reps) ──
  const SEGMAP = { 0:'abcdef',1:'bc',2:'abdeg',3:'abcdg',4:'bcfg',5:'acdfg',6:'acdefg',7:'abc',8:'abcdefg',9:'abcdfg' };
  const SEGPATH = {
    a:'M5 3 L21 3 L18 6 L8 6 Z', b:'M22 4 L22 18 L19 16 L19 7 Z', c:'M22 22 L22 36 L19 33 L19 24 Z',
    d:'M5 37 L21 37 L18 34 L8 34 Z', e:'M4 22 L4 36 L7 33 L7 24 Z', f:'M4 4 L4 18 L7 16 L7 7 Z',
    g:'M6 20 L8 18 L18 18 L20 20 L18 22 L8 22 Z',
  };
  function segDigit(n) {
    const on = SEGMAP[n] || '';
    let s = '<svg class="seg-d" viewBox="0 0 26 40">';
    for (const k in SEGPATH) s += '<path class="seg' + (on.indexOf(k) >= 0 ? ' on' : '') + '" d="' + SEGPATH[k] + '"/>';
    return s + '</svg>';
  }
  function drawReps() {
    const d = qs('#segDisp'); if (!d) return;
    const t = ('0' + _dx.reps).slice(-2);
    d.innerHTML = segDigit(+t[0]) + segDigit(+t[1]);
  }

  // ── greetings rotativos (voz MX) ──
  const GREETS = [
    'Que el banco afloje',
    'Hoy se cosecha verde',
    'Calladito y bonito',
    'Tú deposita nomás',
    'Que caiga la feria',
    'Menos fe, más tarjeta',
    'Puro saldo, mi rey',
    'Aquí se deposita fino',
    'Verdecito y al tiro',
    'El billete no espera',
  ];

  // ── toast propio (vive dentro de #depos, sobre el overlay) ──
  let _toastEl = null, _toastT = null;
  function showToast(t) {
    if (!_toastEl) {
      _toastEl = document.createElement('div');
      _toastEl.className = 'toast';
      (activeEl() || el).appendChild(_toastEl);
    }
    _toastEl.textContent = t;
    _toastEl.classList.add('on');
    clearTimeout(_toastT);
    _toastT = setTimeout(() => _toastEl.classList.remove('on'), 1100);
  }

  // ── modo (la UI impone las reglas, vía DeposLogic) ──
  function modeLabel(mode, reps) {
    if (mode === 'multi') return 'Varias cuentas · una tarjeta a cada una';
    if (mode === 'scheduled') return 'Programado · ' + reps + ' depósitos · cada 60s';
    return 'Un solo depósito';
  }
  function setPresets(presets, manual) {
    const box = qs('#amtPresets'); if (!box) return;
    box.innerHTML = '';
    presets.forEach((v) => {
      const b = document.createElement('div');
      b.className = 'amt-preset' + (v === _dx.amount ? ' on' : '');
      b.innerHTML = '$' + v; // ningún preset ≤$499 garantiza 3DS (cap del backend); sin tip sin medir
      b.onclick = () => {
        _dx.amount = v;
        const inp = qs('#amtInput'); if (inp) inp.value = v;
        [].forEach.call(box.children, (c) => c.classList.remove('on'));
        b.classList.add('on');
      };
      box.appendChild(b);
    });
    const am = qs('#amtManual'); if (am) am.classList.toggle('dis', !manual);
  }
  function refreshMode() {
    const n = _dx.accounts.length;
    const cc = qs('#accCount'); if (cc) cc.textContent = n;
    _dx.mode = D.deriveMode(n, _dx.reps);
    const cfg = D.presetsForMode(_dx.mode);
    const rb = qs('#repsBox'); if (rb) rb.classList.toggle('hide', !cfg.repsVisible);
    // ajustar monto al modo si el actual no aplica
    if (!cfg.manual && cfg.presets.indexOf(_dx.amount) < 0) _dx.amount = cfg.presets.length > 1 ? cfg.presets[1] : cfg.presets[0];
    if (cfg.manual && _dx.amount < 10) _dx.amount = cfg.presets[0];
    setPresets(cfg.presets, cfg.manual);
    const mt = qs('#modeText'); if (mt) mt.textContent = modeLabel(_dx.mode, _dx.reps);
    const inp = qs('#amtInput'); if (inp && cfg.manual) inp.value = _dx.amount;
    // nota de monto + advertencia de cap 24h (el v8 no tiene barra; lo reflejamos en la nota)
    const note = qs('#amtNote');
    if (note) {
      let txt = cfg.note;
      if (_dx.cap) {
        const used = Number(_dx.cap.used || 0);
        const max24 = Number(_dx.cap.max_24h || 1499);
        if (used + _dx.amount > max24) txt = '⚠ Excede el tope 24h ($' + max24 + ', usado $' + used + ')';
        else if (used > 0) txt = cfg.note + ' · usado hoy $' + used + ' / $' + max24;
      }
      note.textContent = txt;
    }
  }

  // ── cuentas (chips combo+grado). Stub Task5; resolución de password/grade en Task6 ──
  function renderAccounts() {
    const box = qs('#accChips'); if (!box) return;
    box.innerHTML = '';
    _dx.accounts.forEach((a) => {
      const combo = a.email + (a.password ? (':' + a.password) : '');
      const grade = (a.grade || '').toLowerCase();
      // SOLO el texto copia (no toda la cápsula): así la tachita queda libre y usable.
      // createElement/textContent → seguro aunque el password traiga comillas o <>.
      const chip = document.createElement('span');
      chip.className = 'chip';
      const hdot = document.createElement('span');
      hdot.className = 'hdot ' + (['a', 'b', 'c', 'd'].indexOf(grade) >= 0 ? grade : '');
      const txt = document.createElement('span');
      txt.className = 'txt copyable';
      txt.setAttribute('data-copy', combo);
      txt.textContent = combo;
      const x = document.createElement('span');
      x.className = 'chip-x';
      x.title = 'Quitar de esta misión (no se borra de la cuenta)';
      x.textContent = '×';
      chip.append(hdot, txt, x);
      box.appendChild(chip);
    });
  }

  // ── tarjetas (chips: pegadas + guardadas) ──
  function renderCards() {
    const box = qs('#cardChips'); if (!box) return;
    box.innerHTML = '';
    _dx.cards.forEach((pipe, idx) => {
      // SOLO el texto copia (no toda la cápsula): la tachita queda libre y usable.
      const chip = document.createElement('span');
      chip.className = 'chip';
      const txt = document.createElement('span');
      txt.className = 'txt copyable';
      txt.setAttribute('data-copy', pipe);
      txt.textContent = pipe;
      const x = document.createElement('span');
      x.className = 'chip-x';
      x.setAttribute('data-idx', idx);
      x.title = 'Quitar de esta misión (no se borra de la cuenta)';
      x.textContent = '×';
      chip.append(txt, x);
      box.appendChild(chip);
    });
    const add = document.createElement('span');
    add.className = 'chip chip-add';
    add.textContent = '+ agregar tarjeta';
    box.appendChild(add);
    const cc = qs('#cardCount'); if (cc) cc.textContent = _dx.cards.length;
  }
  function startAddCard(addEl) {
    const inp = document.createElement('input');
    inp.className = 'chip';
    inp.placeholder = 'NNNN|MM|YY|CVV · pega varias';
    inp.style.minWidth = '0';
    addEl.replaceWith(inp);
    inp.focus();
    let done = false;

    // Divide un texto en candidatos de tarjeta (una por línea / espacio / coma / ;).
    // Un pipe NNNN|MM|YY|CVV no tiene espacios internos → separar así es seguro.
    const splitCards = (raw) => String(raw || '').split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean);

    // Mete N candidatos SIN cortar en el primer error: entran los válidos, se cuentan
    // los inválidos (frictionless — pegar 20 y que entren los 18 buenos, no que se
    // caiga todo por 2 malos). Devuelve {added, bad}.
    const addMany = (list) => {
      let added = 0, bad = 0;
      for (const v of list) {
        if (D.validatePipe(v)) { bad++; continue; }
        const canon = D.canonicalPipe(v); // formato único NNNN|MM|YYYY|CVV
        if (_dx.cards.indexOf(canon) < 0) { _dx.cards.push(canon); added++; }
      }
      return { added, bad };
    };
    const reportMulti = (added, bad) => {
      if (!bad) return;
      showToast(added ? ('✓ ' + added + ' · ' + bad + ' inválida' + (bad > 1 ? 's' : '')) : 'Sin tarjetas válidas');
    };

    const commit = () => {
      if (done) return; done = true;
      const list = splitCards(inp.value);
      if (!list.length) { renderCards(); return; }
      // Una sola y con formato malo → mantener el input abierto para corregir.
      if (list.length === 1) {
        const err = D.validatePipe(list[0]);
        if (err) { showToast(err); done = false; inp.focus(); return; }
      }
      const { added, bad } = addMany(list);
      reportMulti(added, bad);
      renderCards();
    };

    // Pegar varias de golpe: si el portapapeles trae >1 tarjeta, commitea al instante
    // (el input se reemplaza por los chips). Pegar una sola cae al flujo normal.
    inp.addEventListener('paste', (e) => {
      const txt = ((e.clipboardData || window.clipboardData) && (e.clipboardData || window.clipboardData).getData('text')) || '';
      const list = splitCards(txt);
      if (list.length > 1) {
        e.preventDefault();
        done = true;
        const { added, bad } = addMany(list);
        reportMulti(added, bad);
        renderCards();
      }
    });
    inp.addEventListener('keydown', (e) => {
      if (e.key === 'Enter') { e.preventDefault(); commit(); }
      else if (e.key === 'Escape') { done = true; renderCards(); }
    });
    inp.addEventListener('blur', commit);
  }

  // ── resolución contra el backend (no bloquea la apertura; degrada en error) ──
  async function resolveAccounts() {
    const need = _dx.accounts.filter((a) => !a.password && a.id).map((a) => a.id);
    if (!need.length) return;
    try {
      const r = await fetch('/api/accounts/combos', {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ids: need }),
      });
      if (!r.ok) return;
      const data = await r.json();
      const map = {};
      (data.combos || []).forEach((c) => { map[c.id] = c; });
      _dx.accounts = _dx.accounts.map((a) =>
        map[a.id] ? Object.assign({}, a, { email: map[a.id].email || a.email, password: map[a.id].password }) : a);
    } catch (e) { /* red: degradar, no romper la UI */ }
  }
  async function loadSavedCards() {
    if (_dx.accounts.length !== 1 || !_dx.accounts[0].id) return;
    try {
      const r = await fetch('/api/accounts/' + _dx.accounts[0].id + '/cards-pipe');
      if (!r.ok) return;
      const data = await r.json();
      (data.cards || []).forEach((c) => { if (c.pipe && _dx.cards.indexOf(c.pipe) < 0) _dx.cards.push(c.pipe); });
      renderCards();
    } catch (e) { /* degradar */ }
  }
  async function refreshCap() {
    _dx.cap = null;
    if (_dx.accounts.length !== 1 || !_dx.accounts[0].id) return;
    try {
      const r = await fetch('/api/deposits/cap-status/' + _dx.accounts[0].id);
      if (r.ok) _dx.cap = await r.json();
    } catch (e) { /* degradar */ }
  }

  // ── agregar cuentas arrastradas desde la tabla (drag→panel, app.js) ──
  // Suma a la misión activa SIN re-abrir el modal (Robert 2026-07-17: reponer cuentas
  // arrastrando la selección de la tabla al panel). Dedup por id; resuelve
  // password/grade contra el backend en background (no bloquea el render).
  async function addAccounts(list) {
    if (!Array.isArray(list) || !list.length) return;
    let changed = false;
    list.forEach((a) => {
      const id = a && a.id;
      if (!id || _dx.accounts.some((x) => x.id === id)) return;   // ya está en la misión
      _dx.accounts.push({ id: id, email: (a.email || ('cuenta#' + id)), password: '', grade: (a.grade || '') });
      changed = true;
    });
    if (!changed) { showToast('Ya estaban en la misión'); return; }
    renderAccounts(); refreshMode();
    showToast('✓ ' + _dx.accounts.length + ' cuenta' + (_dx.accounts.length > 1 ? 's' : '') + ' en la misión');
    await resolveAccounts(); renderAccounts(); refreshMode();
    // 1 sola cuenta → carga tarjetas guardadas + cap; varias → matchmaker (sin cap por-cuenta).
    if (_dx.accounts.length === 1) { await loadSavedCards(); await refreshCap(); refreshMode(); }
  }

  // ── journey: escenas, %, sub, movimientos ──
  function setScene(k) {
    const st = sqs('#scene-stage'); if (!st) return;
    st.querySelectorAll('.scene.on').forEach((e) => e.classList.remove('on'));
    const n = sqs('#scene-' + k);
    if (n) { void n.offsetWidth; n.classList.add('on'); }
  }
  function setPct(v) { const p = sqs('#pct'); if (p) p.textContent = Math.round(v) + '%'; }
  function setSub(t, good) { const s = sqs('#sub'); if (s) { s.className = 'j-sub' + (good ? ' good' : ''); s.textContent = t; } }

  // labels humanos de fase — NUNCA result_codes crudos al operador (L3)
  const PHASE_LABEL = {
    login_start: 'Iniciando sesión', login_done: 'Sesión lista', login_reused: 'Sesión lista',
    gateway_begin: 'Preparando', gateway_begin_done: 'Orden creada',
    gateway_submit: 'Pagando', gateway_submit_done: 'Enviado',
    gateway_check: 'Confirmando', gateway_check_done: 'Confirmado',
    implicit_3ds_detected: 'Verificación 3DS', done: 'Resultado',
  };
  function phaseLabel(name) {
    if (typeof name === 'string' && name.endsWith('_retry')) return 'Reintentando';
    return PHASE_LABEL[name] || 'Procesando';
  }
  // clasificación real-vs-nuestro + humanización viven en DeposLogic (puras, testeadas)
  const isRealRejection = D.isRealRejection;
  const humanError = D.humanError;

  let _lastMov = null;
  function movRow(who, amt, state) {
    const mov = qs('#mov'); if (!mov) return;
    const r = document.createElement('div');
    r.className = 'mov-row';
    r.innerHTML = '<span class="mov-dot ' + state + '"></span>' +
      '<span class="mov-who" data-copy="' + who + '">' + who + '</span>' +
      '<span class="mov-amt">+$' + amt + '</span>' +
      '<span class="mov-tag ' + state + '">' + (state === 'ok' ? 'real' : 'en curso') + '</span>';
    mov.prepend(r);
    _lastMov = r;
    return r;
  }
  function movSetState(state, label) {
    if (!_lastMov) return;
    const dot = _lastMov.querySelector('.mov-dot'); if (dot) dot.className = 'mov-dot ' + state;
    const tag = _lastMov.querySelector('.mov-tag'); if (tag) { tag.className = 'mov-tag ' + state; tag.textContent = label || (state === 'ok' ? 'real' : 'en curso'); }
  }
  function movRemoveLast() { if (_lastMov) { _lastMov.remove(); _lastMov = null; } }

  function journeyStart() {
    // El escenario vive en La Pantalla (#depStage), ya no en el panel. Enciéndelo y, si
    // La Pantalla está cerrada, ábrela en la cuenta primaria para que el progreso tenga
    // dónde verse. Si ya está abierta, se respeta lo que el operador mira (el escenario
    // es genérico; el resultado por-cuenta va en la lista #mov del panel).
    const stg = document.getElementById('depStage'); if (stg) stg.hidden = false;
    const patRoot = document.getElementById('pantalla');
    if (patRoot && patRoot.hidden) {
      const primary = _dx.accounts[0];
      if (primary && primary.id && window.Pantalla && typeof window.Pantalla.open === 'function') {
        window.Pantalla.open(primary.id);
      }
    }
    const g = sqs('#guide'); if (g) g.classList.add('hide');
    const jb = sqs('#jbal'); if (jb) jb.style.visibility = 'visible';
    const js = sqs('#jstatus'); if (js) js.style.visibility = 'visible';
    const dep = qs('#dep'); if (dep) dep.style.display = 'none';
    const rr = qs('#runrow'); if (rr) rr.classList.add('on');
    if (_dx.target === 'compact') {
      const fireBtn = document.querySelector('.d-deposit-btn'); if (fireBtn) fireBtn.disabled = true;
    }
  }
  function journeyEnd() {
    const dep = qs('#dep'); if (dep) dep.style.display = '';
    const rr = qs('#runrow'); if (rr) rr.classList.remove('on');
    // Misión COMPACTA: openDepos() nunca corre para re-ocultar #depStage (eso solo pasa
    // al abrir el popup flotante) — sin esto, #depStage se queda visible para siempre
    // tras el primer depósito compacto y :has() oculta el panel compacto de por vida.
    if (_dx.target === 'compact') {
      const stg = document.getElementById('depStage'); if (stg) stg.hidden = true;
      const fireBtn = document.querySelector('.d-deposit-btn'); if (fireBtn) fireBtn.disabled = false;
    }
  }

  // lee un stream SSE-NL (data: {json}\n\n) y llama onEvent por cada evento
  async function consumeStream(resp, onEvent) {
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = '';
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += dec.decode(value, { stream: true });
        let idx;
        while ((idx = buf.indexOf('\n\n')) >= 0) {
          const chunk = buf.slice(0, idx);
          buf = buf.slice(idx + 2);
          const line = chunk.split('\n').find((l) => l.startsWith('data: '));
          if (!line) continue; // heartbeat :ping u otra cosa
          try { onEvent(JSON.parse(line.slice(6))); } catch (_) { /* malformado: ignorar */ }
        }
      }
    } finally {
      try { await reader.cancel(); } catch (_) {}
    }
  }

  // auto-fit: el recuadro es FIJO; el texto se escala para caber siempre en 1 línea
  function fitGreet(g) {
    let fs = 13; const min = 8;  // techo alineado a la escala CSS de .title (F6.6, antes 12px)
    g.style.fontSize = fs + 'px';
    let guard = 40;
    while (g.scrollWidth > g.clientWidth && fs > min && guard-- > 0) { fs -= 0.5; g.style.fontSize = fs + 'px'; }
  }
  // greetings rotativos: 1 vez por minuto, fade out→in (premium); timer por apertura/cierre
  function startGreet() {
    stopGreet();
    const g = qs('#greet'); if (!g) return;
    let gi = 0; g.textContent = GREETS[0]; fitGreet(g);
    _greetTimer = setInterval(() => {
      g.style.opacity = 0;
      setTimeout(() => { gi = (gi + 1) % GREETS.length; g.textContent = GREETS[gi]; fitGreet(g); g.style.opacity = 1; }, 450);
    }, 60000);
  }
  function stopGreet() { if (_greetTimer) { clearInterval(_greetTimer); _greetTimer = null; } }

  // ── bus global (/api/events): balance fresco (account_refreshed) + scheduled (Task 8) ──
  let _bus = null;
  let _busCloseTimer = null;
  function busOpen() {
    if (_busCloseTimer) { clearTimeout(_busCloseTimer); _busCloseTimer = null; } // cancela cierre pendiente
    if (_bus) return;
    try {
      _bus = new EventSource('/api/events');
      _bus.onmessage = (e) => { try { onBusEvent(JSON.parse(e.data)); } catch (_) {} };
      _bus.onerror = () => { /* sin sesión/backend: degradar en silencio */ };
    } catch (_) { _bus = null; }
  }
  function busClose() { if (_bus) { try { _bus.close(); } catch (_) {} _bus = null; } }
  // cierre diferido (deja llegar account_refreshed/eventos tardíos); cancelable por busOpen
  // al arrancar otra misión, para no borrar el estado de la nueva.
  function busCloseDeferred() {
    if (_busCloseTimer) clearTimeout(_busCloseTimer);
    _busCloseTimer = setTimeout(() => { _dx.sched = null; _dx.mm = null; busClose(); _busCloseTimer = null; }, 4000);
  }
  function onBusEvent(ev) {
    if (!ev) return;
    // balance fresco tras depósito (single/multi) — L2: jala el real de BetMexico
    if (ev.kind === 'account_refreshed' && _dx.running) {
      const target = ev.email || ev.target;
      if (_dx.accounts.some((a) => a.email === target) && ev.balance_total != null) {
        const balTo = sqs('#balTo'); if (balTo) balTo.textContent = D.fmtMoney(ev.balance_total);
        _dx.balRefreshed = true; // el bus trajo el balance REAL → el provisional no debe pisarlo (L2)
      }
    }
    if (_dx.sched && typeof _schedOnBus === 'function') _schedOnBus(ev); // Task 8
  }

  // ── SINGLE: /execute-stream ──
  async function runSingle() {
    const acc = _dx.accounts[0];
    const pipe = _dx.cards[0];
    if (!acc) { showToast('Selecciona 1 cuenta'); return; }
    if (!pipe) { showToast('Agrega una tarjeta'); return; }
    const err = D.validatePipe(pipe); if (err) { showToast(err); return; }
    const amount = _dx.amount;

    _dx.running = true; _dx.balRefreshed = false; journeyStart(); busOpen();
    const fromBal = Number(acc.balance || 0);
    const balNow = sqs('#balNow'), balTo = sqs('#balTo');
    if (balNow) balNow.textContent = D.fmtMoney(fromBal);
    if (balTo) balTo.textContent = D.fmtMoney(fromBal);
    setScene('login'); setSub('Iniciando sesión'); setPct(14);
    movRow(acc.email, amount, 'wait');

    let gotDone = false;
    try {
      const r = await fetch('/api/deposits/execute-stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: acc.id, card_pipe: pipe, amount }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      await consumeStream(r, (ev) => {
        if (ev.type === 'phase') {
          setScene(D.mapPhaseToScene(ev.name));
          const pct = D.phaseToPct(ev.name); if (pct != null) setPct(pct);
          setSub(phaseLabel(ev.name));
        } else if (ev.type === 'done') {
          gotDone = true;
          if (ev.success) {
            setScene('done'); setPct(100); setSub('Acreditado ✓', true);
            // provisional SOLO si el bus aún no trajo el balance real — account_refreshed
            // llega ANTES del done por el orden del backend (await deposit_task espera el
            // refresh), así que no pisar el fresco si ya entró. (deposits.py:1272 vs 1420)
            if (balTo && !_dx.balRefreshed) balTo.textContent = D.fmtMoney(fromBal + amount);
            movSetState('ok');
          } else {
            setScene('login');
            if (isRealRejection(ev.result_code)) { setSub(humanError(ev.result_code)); movSetState('wait', 'no aplicado'); }
            else { setSub('No se pudo, reintenta'); movRemoveLast(); } // error nuestro: invisible
          }
        } else if (ev.type === 'fatal') {
          gotDone = true; setSub('Algo falló, reintenta'); movRemoveLast();
        }
      });
      if (!gotDone) { setSub('Conexión interrumpida'); movRemoveLast(); }
    } catch (e) {
      setSub('Algo falló, reintenta'); movRemoveLast();
    } finally {
      _dx.running = false; journeyEnd();
      if (!_dx.open) pillHide();
      busCloseDeferred(); // deja llegar account_refreshed antes de cerrar (cancelable)
    }
  }

  // mini 7-seg para el ETA (countdown entre reps)
  function segMini(elm, label, n) {
    const t = ('0' + Math.max(0, Math.min(99, n))).slice(-2);
    elm.innerHTML = '<span class="lbl">' + label + '</span>' + segDigit(+t[0]) + segDigit(+t[1]);
    elm.style.display = 'flex';
  }
  let _schedCountdown = null;
  function clearSchedCountdown() { if (_schedCountdown) { clearInterval(_schedCountdown); _schedCountdown = null; } const e = sqs('#etaSeg'); if (e) e.style.display = 'none'; }
  function startSchedCountdown(sec) {
    clearSchedCountdown();
    let t = sec; const e = sqs('#etaSeg'); if (e) segMini(e, 'ETA', t);
    _schedCountdown = setInterval(() => { t -= 1; if (e) segMini(e, 'ETA', Math.max(0, t)); if (t <= 0) clearSchedCountdown(); }, 1000);
  }

  // ── SCHEDULED: /scheduled/create + eventos por el bus global ──
  async function runScheduled() {
    const acc = _dx.accounts[0];
    const pipe = _dx.cards[0];
    if (!acc) { showToast('Selecciona 1 cuenta'); return; }
    if (!pipe) { showToast('Agrega una tarjeta'); return; }
    const err = D.validatePipe(pipe); if (err) { showToast(err); return; }
    const amount = _dx.amount, reps = _dx.reps;

    _dx.running = true; journeyStart(); busOpen();
    _dx.sched = { sched_id: null, total: reps, iter: 0, done: 0, pending: [] };
    setScene('login'); setSub('Preparando…'); setPct(0);
    const fromBal = Number(acc.balance || 0);
    const balNow = sqs('#balNow'), balTo = sqs('#balTo');
    if (balNow) balNow.textContent = D.fmtMoney(fromBal);
    if (balTo) balTo.textContent = D.fmtMoney(fromBal);
    try {
      const r = await fetch('/api/deposits/scheduled/create', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_id: acc.id, card_pipe: pipe, amount, repetitions: reps }),
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      const data = await r.json();
      _dx.sched.sched_id = data.sched_id;
      _dx.sched.total = data.total || reps;
      // los eventos del run llegan por el bus (onBusEvent -> _schedOnBus). Drenar buffer de carrera.
      const buf = _dx.sched.pending; _dx.sched.pending = [];
      buf.forEach(_schedOnBus);
    } catch (e) {
      setSub('No se pudo iniciar, reintenta'); _dx.running = false; _dx.sched = null; journeyEnd(); busClose();
    }
  }

  function _schedOnBus(ev) {
    const s = _dx.sched; if (!s) return;
    // carrera: si aún no tenemos sched_id, bufferear
    if (!s.sched_id) { s.pending.push(ev); return; }
    if (ev.sched_id && ev.sched_id !== s.sched_id) return;
    const acc = _dx.accounts[0], amount = _dx.amount;
    // El backend manda `iter` 1-indexed (iter_num = completed+1) = la rep en curso /
    // recién completada. NO volver a sumar 1: hacerlo adelantaba el progreso y
    // disparaba schedFinish una rep ANTES (s.done>=total), dejando la última rep
    // corriendo invisible. (deposits.py:2186/2266)
    if (ev.kind === 'scheduled_started') {
      setSub('Preparando…');
    } else if (ev.kind === 'scheduled_phase') {
      if (ev.iter != null) s.iter = ev.iter;
      setScene(D.mapPhaseToScene(ev.name));
      const pct = D.phaseToPct(ev.name); if (pct != null) setPct(pct);
      setSub(phaseLabel(ev.name) + ' · ' + s.iter + '/' + s.total);
      clearSchedCountdown();
    } else if (ev.kind === 'scheduled') {
      if (ev.success) {
        s.done = (ev.iter != null ? ev.iter : s.done + 1); // # reps EXITOSAS (1-indexed)
        movRow(acc.email, amount, 'ok');
        setSub('Acreditado ✓ · ' + s.done + '/' + s.total, true);
        if (s.done >= s.total) schedFinish();
        else startSchedCountdown(60);
      } else if (/3DS/i.test(ev.code || '')) {
        // 3DS = cuenta premium A+ (pasarela robusta), NO un fallo (igual que el matchmaker)
        movRow(acc.email, amount, 'ok'); movSetState('ok', 'A+ · 3DS');
      } else if (ev.code === 'RATE_LIMITED') {
        movRow(acc.email, amount, 'skip'); movSetState('skip', 'en pausa');
      } else if (D.isRealRejection(ev.code)) {
        movRow(acc.email, amount, 'wait'); movSetState('wait', 'no aplicado');
      }
    } else if (ev.kind === 'scheduled_retry') {
      setScene('retry'); setSub('Reintentando · intento ' + (ev.attempt || '') + '/' + (ev.max || ''));
    } else if (ev.kind === 'scheduled_aborted') {
      // Mensaje específico: enfriamiento y 3DS NO son "fallo" — comunican estado real.
      let msg = 'Misión detenida';
      if (ev.code === 'RATE_LIMITED') msg = 'Cuenta en pausa por seguridad · reintenta luego';
      else if (/3DS/i.test(ev.code || '')) msg = 'Cuenta premium A+ ✓';
      else if (D.isRealRejection(ev.code)) msg = humanError(ev.code);
      setSub(msg); schedFinish();
    } else if (ev.kind === 'scheduled_cancelled') {
      setSub('Misión cancelada'); schedFinish();
    }
  }
  function schedFinish() {
    clearSchedCountdown();
    _dx.running = false; journeyEnd();
    if (!_dx.open) pillHide();
    busCloseDeferred();
  }

  // rehidratar una misión programada activa al cargar (se invoca bajo flag — Task 11)
  async function rehydrateScheduled() {
    try {
      const r = await fetch('/api/deposits/scheduled/list'); if (!r.ok) return;
      const data = await r.json();
      const active = (data.schedules || data.active || data || []).filter ? (data.schedules || data.active || []) : [];
      if (active && active.length) {
        const m = active[0];
        await window.openDepos({ accounts: [{ id: m.account_id, email: m.email || '', grade: '' }] });
        _dx.reps = m.total || m.repetitions || 1; drawReps(); refreshMode();
        if (m.card_pipe && _dx.cards.indexOf(m.card_pipe) < 0) { _dx.cards.push(m.card_pipe); renderCards(); }
        _dx.running = true; journeyStart(); busOpen();
        _dx.sched = { sched_id: m.sched_id, total: m.total || m.repetitions || 1, iter: m.current_iter || 0, done: m.current_iter || 0, pending: [] };
        setSub('Misión en curso · ' + (_dx.sched.iter) + '/' + _dx.sched.total);
      }
    } catch (e) { /* degradar */ }
  }
  window.rehydrateDepos = rehydrateScheduled;

  async function onAbort() {
    if (_dx.sched && _dx.sched.sched_id) {
      try { await fetch('/api/deposits/scheduled/' + _dx.sched.sched_id + '/cancel', { method: 'POST' }); } catch (_) {}
      showToast('Cancelando misión…');
    } else if (_dx.mm && _dx.mm.run_id) {
      try { await fetch('/api/deposits/multi/' + _dx.mm.run_id + '/cancel', { method: 'POST' }); } catch (_) {}
      if (_dx.mm.abort) try { _dx.mm.abort.abort(); } catch (_) {}
      showToast('Cancelando…');
    } else { _dx.cancelled = true; }
  }

  // ── MULTI (matchmaker): /multi/stream. v8 no tiene lanes: la animación central refleja
  //    el par activo más reciente; Movimientos lleva la bitácora por par. ──
  let _mmRows = {};
  function shortEmail(e) { return (e || '').split('@')[0]; }
  function mmUpdate(email, state, label) {
    const r = _mmRows[email]; if (!r) return;
    if (state === null) { r.remove(); }
    else {
      const dot = r.querySelector('.mov-dot'); if (dot) dot.className = 'mov-dot ' + state;
      const tag = r.querySelector('.mov-tag'); if (tag) { tag.className = 'mov-tag ' + state; tag.textContent = label || (state === 'ok' ? 'real' : 'en curso'); }
    }
    delete _mmRows[email];
  }
  async function runMulti() {
    const ids = _dx.accounts.map((a) => a.id).filter(Boolean);
    const cards = _dx.cards.slice();
    if (ids.length < 2) { showToast('Selecciona 2+ cuentas'); return; }
    if (!cards.length) { showToast('Agrega tarjetas al pool'); return; }
    for (const p of cards) { const e = D.validatePipe(p); if (e) { showToast(e); return; } }
    const amount = _dx.amount;

    _dx.running = true; journeyStart(); busOpen(); _mmRows = {};
    const abort = new AbortController();
    _dx.mm = { run_id: null, abort, matches: 0 };
    setScene('login'); setSub('Buscando coincidencias…'); setPct(0);
    let gotDone = false;
    try {
      const r = await fetch('/api/deposits/multi/stream', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_ids: ids, cards, amount }), signal: abort.signal,
      });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      await consumeStream(r, (ev) => {
        switch (ev.type) {
          case 'start': _dx.mm.run_id = ev.run_id; break;
          case 'trying':
            setSub('Probando · ' + shortEmail(ev.email));
            // reusa la fila del par si ya existe (un reintento re-emite `trying`):
            // así NO se acumulan filas huérfanas "en curso" en Movimientos.
            if (_mmRows[ev.email]) {
              const d = _mmRows[ev.email].querySelector('.mov-dot'); if (d) d.className = 'mov-dot wait';
              const t = _mmRows[ev.email].querySelector('.mov-tag'); if (t) { t.className = 'mov-tag wait'; t.textContent = 'en curso'; }
            } else { _mmRows[ev.email] = movRow(ev.email, amount, 'wait'); }
            break;
          case 'phase': {
            setScene(D.mapPhaseToScene(ev.name));
            const pct = D.phaseToPct(ev.name); if (pct != null) setPct(pct);
            setSub(phaseLabel(ev.name) + ' · ' + shortEmail(ev.email)); break;
          }
          case 'match': setScene('done'); setPct(100); _dx.mm.matches += 1; mmUpdate(ev.email, 'ok'); setSub('Acreditado ✓ · ' + shortEmail(ev.email), true); break;
          case 'account_aplus': setScene('done'); mmUpdate(ev.email, 'ok', 'A+ · 3DS'); setSub('Cuenta premium A+ · ' + shortEmail(ev.email), true); break;
          case 'rejected': if (D.isRealRejection(ev.code)) mmUpdate(ev.email, 'wait', 'no aplicado'); else mmUpdate(ev.email, null); break;
          case 'account_cooling': {
            // anti-rate-limit (Capa 3): la cuenta entró en enfriamiento (429). Estado
            // operativo REAL y útil (no tripa) → terminal visible, NO se deja "en curso".
            // Sin este case la fila del `trying` previo quedaba colgada para siempre.
            const lbl = 'en pausa' + (ev.cooldown_min ? ' ~' + ev.cooldown_min + 'm' : '');
            if (_mmRows[ev.email]) { mmUpdate(ev.email, 'skip', lbl); }
            else { const rr = movRow(ev.email, amount, 'skip'); const tg = rr.querySelector('.mov-tag'); if (tg) { tg.className = 'mov-tag skip'; tg.textContent = lbl; } }
            break;
          }
          case 'login_retry': setScene('retry'); setSub('Reintentando · ' + shortEmail(ev.email)); break;
          case 'retry': // transitorio (nuestro lado): se reintenta tras cooldown
            if (ev.exhausted) { mmUpdate(ev.email, null); } // agotado: invisible (L3)
            else { setScene('retry'); setSub('Reintentando · ' + shortEmail(ev.email)); }
            break;
          case 'account_dead': mmUpdate(ev.email, 'wait', humanError(ev.code)); break;
          case 'velocity_skip': mmUpdate(ev.email, 'skip', 'saltada'); break; // tarjeta muy seguida: terminal, no se queda en curso
          case 'error': mmUpdate(ev.email, null); break;                      // error nuestro: invisible (L3) + limpia la fila del trying
          case 'card_retired': case 'cooldown': break;                        // sin fila por cuenta: nada que limpiar
          case 'done': gotDone = true; setSub('Listo · ' + _dx.mm.matches + ' acreditada(s)', _dx.mm.matches > 0); break;
          case 'fatal': gotDone = true; setSub('Algo falló, reintenta'); break;
          case 'cancelled': gotDone = true; setSub('Misión cancelada'); break;
        }
      });
      if (!gotDone) setSub('Conexión interrumpida');
    } catch (e) {
      if (e.name !== 'AbortError') setSub('Algo falló, reintenta');
    } finally {
      _dx.running = false; journeyEnd();
      if (!_dx.open) pillHide();
      busCloseDeferred();
    }
  }

  function onDeposit() {
    if (_dx.running) return;
    if (_dx.mode === 'single') return runSingle();
    if (_dx.mode === 'scheduled') return runScheduled();
    if (_dx.mode === 'multi') return runMulti();
  }

  // ── montaje ──
  function mount() {
    if (_mounted) return;
    root.appendChild(tpl.content.cloneNode(true));
    el = document.getElementById('depos');
    // La 2ª columna (.duo .col) es Tarjetas; el mockup no le puso IDs — se los damos.
    const cols = el.querySelectorAll('.duo .col');
    if (cols[1]) {
      const chips = cols[1].querySelector('.chips'); if (chips) chips.id = 'cardChips';
      const cnt = cols[1].querySelector('.count'); if (cnt) cnt.id = 'cardCount';
    }
    injectWindow();
    wireStatic();
    _mounted = true;
  }

  // ── montaje del panel COMPACTO (dentro de La Pantalla) ──
  // Clona #deposCompactTpl UNA sola vez (persiste igual que #depStage — se re-parenta,
  // nunca se re-clona). Reseed de _dx SOLO si no hay misión corriendo Y la cuenta visible
  // cambió: evita pisar una misión activa (bulk float o compacta) a medio camino.
  function mountCompact(d) {
    if (!d || !d.id) return;
    const slot = document.getElementById('patDepSlot');
    if (!slot) return;
    if (!elC) {
      const tplC = document.getElementById('deposCompactTpl');
      if (!tplC) return;
      slot.appendChild(tplC.content.cloneNode(true));
      elC = document.getElementById('depCompact');
      if (!elC) return;
      wireCompactStatic();
      _mountedC = true;
    } else if (elC.parentNode !== slot) {
      slot.appendChild(elC);
    }
    const needsReseed = !_dx.running && (_dx.target !== 'compact' || !_dx.accounts.length || _dx.accounts[0].id !== d.id);
    if (needsReseed) {
      _dx.target = 'compact';
      _dx.accounts = [{ id: d.id, email: d.email || '', password: d.password || '', grade: (d.grade || '').toLowerCase() }];
      _dx.cards = []; _dx.reps = 1; _dx.amount = 50; _dx.cap = null;
      _dx.sched = null; _dx.mm = null; _dx.cancelled = false; _dx.balRefreshed = false;
      renderAccounts(); renderCards(); refreshMode(); drawReps();
      resolveAccounts().then(() => { renderAccounts(); refreshMode(); });
      loadSavedCards();
      refreshCap().then(refreshMode);
    } else if (_dx.target === 'compact') {
      // misma cuenta, solo re-pintar (p.ej. La Pantalla se re-renderizó por otro motivo)
      renderAccounts(); renderCards(); refreshMode(); drawReps();
    }
  }

  // Rescata elC de `detail` ANTES de que pantalla.js haga innerHTML= (mismo patrón que
  // _rescueStage en pantalla.js para #depStage) — si no, el wipe lo desconecta del DOM.
  function rescueCompact(detail) {
    if (elC && detail && detail.contains(elC)) document.body.appendChild(elC);
  }

  // Listeners del panel COMPACTO — subconjunto de wireStatic() (sin #dep: el disparo
  // vive en .pat-actions vía window.Depos.fireCompact; sin greet/drag-window/pause:
  // no aplican a un panel inline). Reusa las MISMAS funciones (renderAccounts,
  // renderCards, startAddCard, addAccounts) — cero lógica duplicada.
  function wireCompactStatic() {
    if (!elC) return;
    const up = elC.querySelector('#repUp'), dn = elC.querySelector('#repDn');
    if (up) up.onclick = () => { _dx.reps = Math.min(20, _dx.reps + 1); drawReps(); refreshMode(); };
    if (dn) dn.onclick = () => { _dx.reps = Math.max(1, _dx.reps - 1); drawReps(); refreshMode(); };

    const accBox = elC.querySelector('#accChips');
    if (accBox) accBox.addEventListener('click', (e) => {
      if (e.target.classList.contains('chip-x')) {
        const chip = e.target.closest('.chip');
        const txt = chip && chip.querySelector('.txt[data-copy]');
        const combo = (txt && txt.getAttribute('data-copy')) || '';
        const email = combo.split(':')[0];
        _dx.accounts = _dx.accounts.filter((a) => a.email !== email);
        renderAccounts(); refreshMode();
      }
    });

    const cardBox = elC.querySelector('#cardChips');
    if (cardBox) cardBox.addEventListener('click', (e) => {
      if (e.target.classList.contains('chip-add')) { startAddCard(e.target); return; }
      if (e.target.classList.contains('chip-x')) {
        const idx = parseInt(e.target.getAttribute('data-idx'), 10);
        if (!isNaN(idx)) { _dx.cards.splice(idx, 1); renderCards(); }
      }
    });

    elC.addEventListener('click', (e) => {
      const c = e.target.closest('.copyable');
      if (c && !e.target.classList.contains('chip-x')) {
        const v = c.getAttribute('data-copy');
        if (navigator.clipboard && v) navigator.clipboard.writeText(v);
        showToast('copiado');
      }
    });

    // drop de cuentas arrastradas desde la tabla (mismo mecanismo que el flotante)
    const DND_TYPE = 'application/x-bmx-accounts';
    const hasAccPayload = (dt) => !!dt && Array.prototype.indexOf.call(dt.types || [], DND_TYPE) >= 0;
    elC.addEventListener('dragover', (e) => {
      if (!hasAccPayload(e.dataTransfer)) return;
      e.preventDefault(); e.dataTransfer.dropEffect = 'copy';
      elC.classList.add('dw-drop-hot');
    });
    elC.addEventListener('dragleave', (e) => {
      if (!elC.contains(e.relatedTarget)) elC.classList.remove('dw-drop-hot');
    });
    elC.addEventListener('drop', (e) => {
      elC.classList.remove('dw-drop-hot');
      const raw = e.dataTransfer && e.dataTransfer.getData(DND_TYPE);
      if (!raw) return;
      e.preventDefault();
      let list; try { list = JSON.parse(raw); } catch (_) { return; }
      if (_dx.target === 'compact') addAccounts(list);
    });

    const inp = elC.querySelector('#amtInput');
    if (inp) inp.addEventListener('input', (e) => {
      const v = parseInt(e.target.value, 10);
      if (!isNaN(v)) _dx.amount = v;
    });

    const ab = elC.querySelector('#abort'); if (ab) ab.onclick = onAbort;
  }

  // El header (banner/personaje + greeting) es la zona de arrastre; los controles
  // (dock izq/der, cerrar) flotan en la esquina superior derecha. + divisor del dock.
  function injectWindow() {
    const bmx = el.querySelector('.bmx');
    if (bmx && !bmx.querySelector('.dw-ctl')) {
      const ctl = document.createElement('div');
      ctl.className = 'dw-ctl';
      // Solo la tachita de cerrar: el panel ya no se acopla a la izquierda ni se
      // desacopla (Robert 2026-07-17). El único ajuste es ensanchar con el divisor.
      ctl.innerHTML =
        '<button class="dw-btn dw-close" title="Cerrar (Esc)" aria-label="Cerrar">' +
          '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"><path d="M6 6l12 12M18 6L6 18"/></svg></button>';
      bmx.appendChild(ctl);
    }
    if (el && !el.querySelector('.dw-divider')) {
      const dv = document.createElement('div');
      dv.className = 'dw-divider';
      el.appendChild(dv);
    }
    if (window.DeposWindow && !_win) {
      _win = window.DeposWindow.init(el, {
        storageKey: 'deposWin',
        dockZoneId: 'accDockZone',
        titlebar: '.head',   // el header (personaje + greeting) ES la zona de arrastre
        onClose: () => window.closeDepos(),
      });
    }
  }

  function wireStatic() {
    drawReps();
    const up = qs('#repUp'), dn = qs('#repDn');
    if (up) up.onclick = () => { _dx.reps = Math.min(20, _dx.reps + 1); drawReps(); refreshMode(); };
    if (dn) dn.onclick = () => { _dx.reps = Math.max(1, _dx.reps - 1); drawReps(); refreshMode(); };

    // quitar cuenta (X) -> recalcula modo
    const accBox = qs('#accChips');
    if (accBox) accBox.addEventListener('click', (e) => {
      if (e.target.classList.contains('chip-x')) {
        // el data-copy vive ahora en el .txt (no en la cápsula) — leerlo de ahí
        const chip = e.target.closest('.chip');
        const txt = chip && chip.querySelector('.txt[data-copy]');
        const combo = (txt && txt.getAttribute('data-copy')) || '';
        const email = combo.split(':')[0];
        _dx.accounts = _dx.accounts.filter((a) => a.email !== email);
        renderAccounts(); refreshMode();
      }
    });

    // tarjetas: agregar (+) / quitar (x)
    const cardBox = qs('#cardChips');
    if (cardBox) cardBox.addEventListener('click', (e) => {
      if (e.target.classList.contains('chip-add')) { startAddCard(e.target); return; }
      if (e.target.classList.contains('chip-x')) {
        const idx = parseInt(e.target.getAttribute('data-idx'), 10);
        if (!isNaN(idx)) { _dx.cards.splice(idx, 1); renderCards(); }
      }
    });

    // copiar al click (combos/pipes completos, sin máscara — L2)
    el.addEventListener('click', (e) => {
      const c = e.target.closest('.copyable');
      if (c && !e.target.classList.contains('chip-x')) {
        const v = c.getAttribute('data-copy');
        if (navigator.clipboard && v) navigator.clipboard.writeText(v);
        showToast('copiado');
      }
    });

    // ── drop de cuentas arrastradas desde la tabla → suma a la misión ──
    // (dragstart lo emite app.js con el type custom; en dragover solo se pueden leer
    // los `types`, el payload real se lee en `drop`).
    const DND_TYPE = 'application/x-bmx-accounts';
    const hasAccPayload = (dt) => !!dt && Array.prototype.indexOf.call(dt.types || [], DND_TYPE) >= 0;
    el.addEventListener('dragover', (e) => {
      if (!hasAccPayload(e.dataTransfer)) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'copy';
      el.classList.add('dw-drop-hot');
    });
    el.addEventListener('dragleave', (e) => {
      if (!el.contains(e.relatedTarget)) el.classList.remove('dw-drop-hot');
    });
    el.addEventListener('drop', (e) => {
      el.classList.remove('dw-drop-hot');
      const raw = e.dataTransfer && e.dataTransfer.getData(DND_TYPE);
      if (!raw) return;
      e.preventDefault();
      let list; try { list = JSON.parse(raw); } catch (_) { return; }
      addAccounts(list);
    });

    // monto manual
    const inp = qs('#amtInput');
    if (inp) inp.addEventListener('input', (e) => {
      const v = parseInt(e.target.value, 10);
      if (!isNaN(v)) _dx.amount = v;
    });

    // greetings: el timer se gestiona en startGreet/stopGreet (openDepos/closeDepos)

    // botón depositar — router por modo (single ya cableado; scheduled/multi en Tasks 8/9)
    const dep = qs('#dep');
    if (dep) dep.onclick = onDeposit;
    // controles de run: abort cancela scheduled/multi
    const ab = qs('#abort'); if (ab) ab.onclick = onAbort;
    // pause: el backend NO tiene pause vivo (solo cancel) -> ocultamos el botón (honesto, L3).
    // Reaparecerá cuando B3 agregue pause/resume real.
    const pz = qs('#pause'); if (pz) pz.style.display = 'none';
    // "Otro depósito" en paralelo = B4 (aún no existe). No fingir la capacidad.
    const np = qs('.newproc');
    if (np) np.onclick = () => showToast('Pronto: varios depósitos en paralelo');
  }

  // ── open/close ──
  function onEsc(e) { if (e.key === 'Escape') window.closeDepos(); }

  // API pública (drag→panel desde app.js + montaje/disparo del panel compacto desde pantalla.js).
  window.Depos = {
    addAccounts: addAccounts,
    mountCompact: mountCompact,
    rescueCompact: rescueCompact,
    fireCompact: () => onDeposit(),
  };

  window.openDepos = async function (opts) {
    opts = opts || {};
    _dx.target = 'float';   // el operador abrió el popup flotante EXPLÍCITAMENTE: reclama el render
    mount();
    // reset COMPLETO de estado entre aperturas (evita movimientos/misiones stale)
    _dx.accounts = opts.accounts || (opts.ids || []).map((id) => ({ id, email: 'cuenta#' + id, password: '', grade: '' }));
    _dx.cards = []; _dx.reps = 1; _dx.amount = 50; _dx.running = false; _dx.cap = null;
    _dx.sched = null; _dx.mm = null; _dx.cancelled = false; _dx.balRefreshed = false;
    _lastMov = null; _mmRows = {};
    const movEl = qs('#mov'); if (movEl) movEl.innerHTML = '';
    setSub('Listo'); setPct(0);
    const stg = document.getElementById('depStage'); if (stg) stg.hidden = true;  // idle: zona derecha vacía hasta correr
    const jb = sqs('#jbal'); if (jb) jb.style.visibility = 'hidden';
    const jst = sqs('#jstatus'); if (jst) jst.style.visibility = 'hidden';
    const gd = sqs('#guide'); if (gd) gd.classList.remove('hide');
    // mostrar de inmediato (optimista); los datos del backend se completan en background
    renderAccounts(); renderCards(); refreshMode();
    root.classList.remove('hidden');
    root.setAttribute('aria-hidden', 'false');
    // Con el panel abierto, La Pantalla oculta SU botón "Depositar" (evita dos botones
    // de depósito a la vez — Robert 2026-07-17). El CSS lo apaga vía body.depos-open.
    document.body.classList.add('depos-open');
    if (_win) _win.show();   // aplica tamaño/ancho guardados (dock derecho)
    _dx.open = true;
    document.removeEventListener('keydown', onEsc); // evita listener duplicado si ya estaba abierto
    document.addEventListener('keydown', onEsc);
    startGreet();
    // completar contra el backend sin bloquear la apertura (frictionless)
    await resolveAccounts(); renderAccounts(); refreshMode();
    await loadSavedCards();
    await refreshCap(); refreshMode();
  };

  window.closeDepos = function () {
    root.classList.add('hidden');
    root.setAttribute('aria-hidden', 'true');
    document.body.classList.remove('depos-open');   // La Pantalla recupera su botón "Depositar"
    if (_win) _win.hide();   // suelta la compresión del dashboard (conserva el estado)
    _dx.open = false;
    document.removeEventListener('keydown', onEsc);
    stopGreet(); // no rotar greetings con el modal cerrado (evita trabajo en background)
    // si hay misión activa, la dejamos correr en background y mostramos la pill
    if (_dx.running) pillShow(); else pillHide();
  };

  // ── pill flotante: misión activa con el modal cerrado (sigue por stream/bus) ──
  let _pillEl = null;
  function pillShow() {
    if (!_pillEl) {
      _pillEl = document.createElement('div');
      _pillEl.id = 'deposPill';
      _pillEl.className = 'depos-pill';
      _pillEl.innerHTML = '<span class="dp-ic">⏳</span><span class="dp-tx mono">Misión activa</span><span class="dp-go">↗</span>';
      _pillEl.title = 'Misión activa — click para reabrir';
      _pillEl.onclick = pillReopen;
      document.body.appendChild(_pillEl);
    }
    _pillEl.querySelector('.dp-ic').textContent = _dx.sched ? '⏰' : '🎯';
    _pillEl.querySelector('.dp-tx').textContent = _dx.sched
      ? ('Programado ' + _dx.sched.done + '/' + _dx.sched.total)
      : 'Matchmaker en curso';
    _pillEl.classList.remove('hide');
  }
  function pillHide() { if (_pillEl) _pillEl.classList.add('hide'); }
  function pillReopen() {
    root.classList.remove('hidden');
    root.setAttribute('aria-hidden', 'false');
    _dx.open = true;
    document.addEventListener('keydown', onEsc);
    pillHide();
  }

  // Ventana flotante libre: el click-fuera ya NO cierra (es ventana, no modal).
  // Cierra por la tachita de la barra (.dw-close) o Esc.
})();
