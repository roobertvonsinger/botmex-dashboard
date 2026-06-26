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

  let el = null;          // #depos montado
  let _mounted = false;
  let _greetTimer = null;
  const qs = (s) => (el ? el.querySelector(s) : null);

  let _dx = { open: false, accounts: [], cards: [], reps: 1, amount: 50, mode: 'single', running: false };

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
  const GREETS = ['A depositar bonito','Que caiga el billete','Manos a la lana','Vamos por la feria',
    'Aquí se deposita fino','A llenar cuentas','Suelta el depósito','Hora de la feria','Dale al depo','A mover lana'];

  // ── toast propio (vive dentro de #depos, sobre el overlay) ──
  let _toastEl = null, _toastT = null;
  function showToast(t) {
    if (!_toastEl) {
      _toastEl = document.createElement('div');
      _toastEl.className = 'toast';
      el.appendChild(_toastEl);
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
      b.innerHTML = '$' + v + (v === 1000 ? '<span class="tip">3DS</span>' : '');
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
        const used = Number(_dx.cap.used != null ? _dx.cap.used : (_dx.cap.total || 0));
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
      const chip = document.createElement('span');
      chip.className = 'chip copyable';
      chip.setAttribute('data-copy', combo);
      chip.innerHTML = '<span class="hdot ' + (['a','b','c','d'].indexOf(grade) >= 0 ? grade : '') + '"></span>' +
        '<span class="txt">' + combo + '</span><span class="chip-x">x</span>';
      box.appendChild(chip);
    });
  }

  // ── tarjetas (chips: pegadas + guardadas) ──
  function renderCards() {
    const box = qs('#cardChips'); if (!box) return;
    box.innerHTML = '';
    _dx.cards.forEach((pipe, idx) => {
      const chip = document.createElement('span');
      chip.className = 'chip copyable';
      chip.setAttribute('data-copy', pipe);
      chip.innerHTML = '<span class="txt">' + pipe + '</span><span class="chip-x" data-idx="' + idx + '">x</span>';
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
    inp.placeholder = 'NNNN|MM|YY|CVV';
    inp.style.minWidth = '0';
    addEl.replaceWith(inp);
    inp.focus();
    let done = false;
    const commit = () => {
      if (done) return; done = true;
      const v = inp.value.trim();
      if (!v) { renderCards(); return; }
      const err = D.validatePipe(v);
      if (err) { showToast(err); done = false; inp.focus(); return; }
      if (_dx.cards.indexOf(v) < 0) _dx.cards.push(v);
      renderCards();
    };
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
    wireStatic();
    _mounted = true;
  }

  function wireStatic() {
    drawReps();
    const up = qs('#repUp'), dn = qs('#repDn');
    if (up) up.onclick = () => { _dx.reps = Math.min(15, _dx.reps + 1); drawReps(); refreshMode(); };
    if (dn) dn.onclick = () => { _dx.reps = Math.max(1, _dx.reps - 1); drawReps(); refreshMode(); };

    // quitar cuenta (X) -> recalcula modo
    const accBox = qs('#accChips');
    if (accBox) accBox.addEventListener('click', (e) => {
      if (e.target.classList.contains('chip-x')) {
        const chip = e.target.closest('.chip');
        const combo = (chip && chip.getAttribute('data-copy')) || '';
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

    // monto manual
    const inp = qs('#amtInput');
    if (inp) inp.addEventListener('input', (e) => {
      const v = parseInt(e.target.value, 10);
      if (!isNaN(v)) _dx.amount = v;
    });

    // greetings
    const g = qs('#greet');
    if (g) {
      g.textContent = GREETS[0];
      let gi = 0;
      _greetTimer = setInterval(() => {
        g.style.opacity = 0;
        setTimeout(() => { gi = (gi + 1) % GREETS.length; g.textContent = GREETS[gi]; g.style.opacity = 1; }, 320);
      }, 6000);
    }

    // botón depositar — cableado real en Fase 3
    const dep = qs('#dep');
    if (dep) dep.onclick = () => showToast('Depositar — cableado en Fase 3');
    // "Otro depósito" — B4, stub en Task 10
    const np = qs('.newproc');
    if (np) np.onclick = () => showToast('Otro depósito (B4) — pendiente');
  }

  // ── open/close ──
  function onEsc(e) { if (e.key === 'Escape') window.closeDepos(); }

  window.openDepos = async function (opts) {
    opts = opts || {};
    mount();
    _dx.accounts = opts.accounts || (opts.ids || []).map((id) => ({ id, email: 'cuenta#' + id, password: '', grade: '' }));
    _dx.cards = []; _dx.reps = 1; _dx.amount = 50; _dx.running = false; _dx.cap = null;
    // mostrar de inmediato (optimista); los datos del backend se completan en background
    renderAccounts(); renderCards(); refreshMode();
    root.classList.remove('hidden');
    root.setAttribute('aria-hidden', 'false');
    _dx.open = true;
    document.addEventListener('keydown', onEsc);
    // completar contra el backend sin bloquear la apertura (frictionless)
    await resolveAccounts(); renderAccounts(); refreshMode();
    await loadSavedCards();
    await refreshCap(); refreshMode();
  };

  window.closeDepos = function () {
    if (_dx.running) { showToast('Hay una misión en curso'); return; } // pill viene en Task 10
    root.classList.add('hidden');
    root.setAttribute('aria-hidden', 'true');
    _dx.open = false;
    document.removeEventListener('keydown', onEsc);
  };

  // click fuera del panel cierra
  root.addEventListener('click', (e) => { if (e.target === root) window.closeDepos(); });
})();
