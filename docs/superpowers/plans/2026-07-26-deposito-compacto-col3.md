# Depósito compacto conviviendo con retiro en col 3 — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Montar un panel de depósito compacto (estilo `pat-*`, igual lenguaje visual que el retiro) dentro de `.pat-col-stage` de La Pantalla, apilado debajo del panel de retiro, que reusa el motor existente de `depos.js` (mismo `_dx`, mismas `runSingle/runScheduled/runMulti`, mismos endpoints) sin duplicar lógica ni tocar backend.

**Architecture:** `depos.js` pasa de tener un único destino de render (`el`, la ventana flotante) a tener DOS destinos posibles para el MISMO motor singleton: `el` (flotante, sin cambios, sigue sirviendo el multi-select bulk de la tabla) y `elC` (compacto, nuevo, montado dentro de `.pat-col-stage` vía un slot que pantalla.js gestiona igual que ya gestiona `#depStage`). Un flag `_dx.target` decide a cuál de los dos apunta `qs()` en cada momento. El botón "Depositar" de `.pat-actions` deja de abrir el popup — dispara directo (mismo patrón que `.d-withdraw-fire`). La mutua exclusión con una misión bulk corriendo en paralelo la resuelve el `:has(#depStage:not([hidden]))` que YA EXISTE en CSS (se extiende al panel de depósito compacto) — mientras hay CUALQUIER misión corriendo (float o compacta), el escenario animado toma la columna completa y oculta ambos paneles compactos, así que un `_dx.accounts` "equivocado" (perteneciente a la misión bulk) nunca se ve pintado en el panel de la cuenta abierta. Cuando no hay misión corriendo, un reseed condicional en `mountCompact()` re-sincroniza `_dx` a la cuenta que La Pantalla tiene abierta.

**Tech Stack:** Vanilla JS (sin framework), CSS con `:has()`, templates HTML nativos (`<template>`), SSE/fetch existentes — nada nuevo.

## Global Constraints

- **Backend intocable**: cero cambios en `deposits.py`, endpoints, `depos_logic.js` (reglas puras). Todo el trabajo es DOM/JS/CSS en `static/`.
- **No reutilizar el diseño visual de `depos.css`** (banner, saludo rotativo, `.duo` 2 columnas) para el panel compacto — sí se reutilizan las clases estructurales (`chip`, `chip-x`, `amt-preset`, `hdot`) porque las funciones de `depos.js` las generan tal cual; se re-skinnean por CSS scoped a `.pat-dep-stage` en `pantalla.css`, sin tocar `depos.css`.
- **Multi-select bulk de tabla intacto**: `openDepositModal(null, {ids:[...]})` (`app.js:6192`) sigue abriendo la ventana flotante sin cambios de comportamiento.
- **Un solo motor (`_dx`), dos destinos de render** — NO se crea una segunda instancia del engine (ver decisión validada — evita duplicar 500+ líneas de un motor que hoy es singleton real; "+Otro depósito" es un stub, no hay paralelismo real que soportar).
- **Convención de medición real**: ningún breakpoint px inventado; donde se necesite overflow, usar el mismo patrón `overflow-y:auto` / `.pat-cramped` ya existente en el repo (`feedback_ui_ancla_medida_no_pixel_inventado`).
- **Bitácora obligatoria** (`botmex-bitacora`): antes del commit final, actualizar `docs/FRONTEND.md` (nueva sección) y `NEXT-SESSION.md` (cierre).

---

### Task 1: Template + CSS del panel compacto (inertes, sin JS)

**Files:**
- Modify: `static/index.html` (agregar `<template id="deposCompactTpl">` junto a `#deposTpl`, línea ~1046)
- Modify: `static/pantalla.css` (nuevas reglas `.pat-dep-*`, después del bloque `.pat-wd-*` en línea ~576; extender la regla `:has()` de exclusión mutua en línea ~569; agregar `overflow-y:auto` a `.pat-col-stage` línea ~614-620; agregar `:disabled` a `.pat-act-dep` línea ~422-429)

**Interfaces:**
- Produce: `<template id="deposCompactTpl">` con wrapper `<div id="depCompact" class="pat-dep-stage">` e ids internos `accCount`, `accChips`, `cardCount`, `cardChips`, `amtManual`, `amtInput`, `amtPresets`, `amtNote`, `modeText`, `repsBox`, `segDisp`, `repUp`, `repDn`, `runrow`, `abort` — mismos ids que ya consumen `depos.js`'s `qs()` (`renderAccounts`, `renderCards`, `setPresets`, `refreshMode`, `drawReps`), para que Task 2/3 los reutilicen sin tocar esas funciones.
- Consume: nada (Task 1 es puro markup/CSS, no ejecuta JS todavía — el `<template>` no se clona hasta Task 3).

- [ ] **Step 1: Agregar el `<template>` en index.html**

En `static/index.html`, justo DESPUÉS de la línea `</template>` que cierra `#deposTpl` (línea 1046, antes de `<div id="deposRoot" ...>`), insertar:

```html
<!-- Panel de depósito COMPACTO — mismo motor de depos.js, montado dentro de La
     Pantalla (.pat-col-stage) en vez de la ventana flotante. Sin banner/saludo/
     duo-columnas (ver docs/superpowers/specs/2026-07-26-deposito-compacto-col3-design.md).
     Mismos ids internos que #deposTpl para que depos.js los reutilice sin cambios. -->
<template id="deposCompactTpl">
<div id="depCompact" class="pat-dep-stage">
  <span class="pat-dep-head"><span class="pat-sv-emo">💳</span> Depositar <span class="pat-dep-mode" id="modeText"></span></span>
  <div class="pat-dep-row">
    <span class="pat-dep-label">Cuentas <span class="pat-dep-cnt" id="accCount">1</span></span>
    <div class="pat-dep-chips" id="accChips"></div>
  </div>
  <div class="pat-dep-row">
    <span class="pat-dep-label">Tarjetas <span class="pat-dep-cnt" id="cardCount">0</span></span>
    <div class="pat-dep-chips" id="cardChips"></div>
  </div>
  <div class="pat-dep-row pat-dep-amt-row">
    <div class="pat-dep-amt dis" id="amtManual"><span>$</span><input id="amtInput" value="50" inputmode="numeric" aria-label="Monto manual" class="pat-input pat-input-mono"></div>
    <div class="pat-dep-presets" id="amtPresets"></div>
  </div>
  <div class="pat-dep-note" id="amtNote"></div>
  <div class="pat-dep-reps hide" id="repsBox">
    <span class="pat-dep-label">Reps</span>
    <div class="pat-dep-seg" id="segDisp"></div>
    <button type="button" class="pat-btn pat-btn-ghost" id="repUp" aria-label="Subir">&#9650;</button>
    <button type="button" class="pat-btn pat-btn-ghost" id="repDn" aria-label="Bajar">&#9660;</button>
  </div>
  <div class="pat-dep-runrow" id="runrow">
    <button type="button" class="pat-btn pat-btn-ghost" id="abort">Abortar</button>
  </div>
  <button type="button" class="newproc pat-dep-newproc"><span class="plus">+</span> Otro depósito</button>
</div>
</template>
```

- [ ] **Step 2: Agregar el slot de montaje en `.pat-col-stage` (pantalla.js)**

Este paso técnicamente edita `pantalla.js`, pero se hace aquí (junto al template) porque es un solo `<div>` de anclaje sin lógica. En `static/pantalla.js`, función `renderPantallaHead`, la sección `.pat-col-stage` (línea 345-348) dice:

```js
        <div class="pat-col-stage">
          ${renderPantallaWithdrawStage(d)}
          <div id="patStageSlot"></div>
        </div>
```

Cambiar a:

```js
        <div class="pat-col-stage">
          ${renderPantallaWithdrawStage(d)}
          <div id="patStageSlot"></div>
          <div id="patDepSlot"></div>
        </div>
```

- [ ] **Step 3: CSS del panel compacto en `pantalla.css`**

Extender la regla de exclusión mutua existente (línea 569) — de:

```css
.pat-col-stage:has(#depStage:not([hidden])) .pat-wd-stage { display: none; }
```

a:

```css
.pat-col-stage:has(#depStage:not([hidden])) .pat-wd-stage,
.pat-col-stage:has(#depStage:not([hidden])) .pat-dep-stage { display: none; }
```

Justo después del bloque `.pat-wd-status:empty { display: none; }` (línea 576), agregar el bloque nuevo:

```css
/* Panel de depósito compacto — mismo motor de depos.js (window.Depos.mountCompact),
   montado en #patDepSlot. Estructura reusa las clases que renderAccounts/renderCards/
   setPresets ya generan (chip, chip-x, amt-preset, hdot) — se re-skinnean AQUÍ, scoped
   a .pat-dep-stage, para NO tocar depos.css (spec: no reutilizar el look del panel viejo). */
.pat-dep-stage {
  display: flex; flex-direction: column; gap: 7px;
  padding: 12px 4px 4px 0; margin-top: 4px;
  border-top: 1px solid var(--pat-edge);
  color: var(--text);
}
.pat-dep-head { font-size: 12px; font-weight: 600; display: flex; gap: 5px; align-items: center; }
.pat-dep-mode { font-weight: 400; color: var(--text-dim); font-size: 10px; margin-left: auto; }
.pat-dep-row { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.pat-dep-label { font-size: 10px; color: var(--text-dim); flex: 0 0 auto; }
.pat-dep-cnt { font-family: var(--font-mono); font-size: 9.5px; color: var(--text-muted); }
.pat-dep-chips { display: flex; flex-wrap: wrap; gap: 4px; flex: 1 1 auto; }
.pat-dep-stage .chip {
  background: oklch(0.80 0.085 160 / 0.08); border: 1px solid var(--pat-edge);
  border-radius: 20px; padding: 2px 8px; font-size: 10px;
  display: inline-flex; align-items: center; gap: 4px;
}
.pat-dep-stage .chip-x { cursor: pointer; opacity: .6; }
.pat-dep-stage .chip-x:hover { opacity: 1; color: var(--danger); }
.pat-dep-amt-row { gap: 8px; }
.pat-dep-stage .amt-preset {
  border: 1px solid var(--pat-edge); border-radius: 6px; padding: 2px 8px;
  font-family: var(--font-mono); font-size: 10.5px; cursor: pointer;
}
.pat-dep-stage .amt-preset.on { background: var(--pat-gold-soft); color: var(--pat-gold); border-color: var(--pat-edge-h); }
.pat-dep-amt.dis input { opacity: .45; pointer-events: none; }
.pat-dep-presets { display: flex; gap: 4px; flex-wrap: wrap; }
.pat-dep-note { font-size: 9.5px; color: var(--text-faint); }
.pat-dep-reps { display: flex; align-items: center; gap: 6px; }
.pat-dep-reps.hide { display: none; }
.pat-dep-runrow { display: none; }
.pat-dep-runrow.on { display: flex; gap: 6px; }
.pat-dep-newproc {
  align-self: flex-start; background: transparent; border: 1px dashed var(--pat-edge);
  color: var(--text-dim); font-size: 9.5px; padding: 2px 8px; border-radius: 6px; cursor: pointer;
}
.pat-dep-newproc:hover { color: var(--pat-gold); border-color: var(--pat-gold); }
```

- [ ] **Step 4: Overflow vertical + disabled del botón de disparo**

En el bloque `.pat-col-stage` (línea 614-620), agregar `overflow-y: auto` (mismo patrón que `.pat-txn-col`, sin inventar breakpoint):

```css
.pat-col-stage {
  flex: 1 1 0; min-width: 380px; min-height: 0;
  display: flex; flex-direction: column; justify-content: center;
  padding-left: 22px;
  border-left: 1px solid var(--pat-edge);
  box-shadow: -1px 0 16px -12px var(--pat-gold-soft);
  overflow-y: auto;
}
```

Después de `.pat-act-wd:disabled:hover { transform: none; filter: none; }` (línea 436), agregar el mismo tratamiento para el botón de depósito (se deshabilita mientras una misión compacta corre — Task 3/4):

```css
.pat-act-dep:disabled { opacity: .4; cursor: not-allowed; background: var(--pat-edge); color: var(--text-dim); box-shadow: none; }
.pat-act-dep:disabled:hover { background: var(--pat-edge); box-shadow: none; }
```

Y eliminar la regla ya obsoleta con el nuevo diseño (línea 437-440 — el comentario que la explica y la regla):

```css
/* Con el panel de depósitos abierto, La Pantalla oculta SU botón "Depositar" — no debe
   haber dos botones de depósito a la vez (Robert 2026-07-17). Reaparece al cerrar el
   panel (efecto "se movió del detalle al panel"). */
body.depos-open .pat-act-dep { display: none; }
```

Esta regla ya no aplica: con el diseño nuevo, el popup flotante (`depos-open`) solo se usa para el multi-select bulk de OTRAS cuentas — no debe esconder el botón de depósito de la cuenta que La Pantalla tiene abierta.

- [ ] **Step 5: Commit checkpoint**

```bash
git add static/index.html static/pantalla.css static/pantalla.js
git commit -m "feat(depos): template+CSS del panel de depósito compacto en col 3 (inerte, sin JS aún)"
```

---

### Task 2: `depos.js` — doble destino de render (`el` / `elC`) vía `_dx.target`

**Files:**
- Modify: `static/depos.js:1-22` (variables de módulo), `:71-118` (funciones que usan `qs`/`refreshMode`), `:852-882` (`openDepos`)

**Interfaces:**
- Consumes: nada nuevo — reutiliza `_dx`, `qs`, `renderAccounts`, `renderCards`, `refreshMode`, `setPresets`, `drawReps` ya existentes en el archivo.
- Produces: `activeEl()` (función interna), `_dx.target` (`'float' | 'compact'`, nuevo campo de estado), `elC` (variable de módulo, `null` hasta Task 3).

- [ ] **Step 1: Declarar `elC` y `_dx.target`**

En `static/depos.js`, línea 12-22 (declaración de variables de módulo), cambiar:

```js
  let el = null;          // #depos montado
  let _mounted = false;
  let _greetTimer = null;
  let _win = null;        // controlador de ventana (depos_window.js): float / dock-izq / dock-der
  const qs = (s) => (el ? el.querySelector(s) : null);
  // El ESCENARIO (escenas + %/sub + balance) ya NO vive en el panel: se movió a
  // #depStage, que La Pantalla monta en su zona derecha (#patStageSlot). sqs() lo
  // resuelve esté donde esté (re-parenteado por pantalla.js). #mov sigue en el panel → qs().
  const sqs = (s) => { const st = document.getElementById('depStage'); return st ? st.querySelector(s) : null; };

  let _dx = { open: false, accounts: [], cards: [], reps: 1, amount: 50, mode: 'single', running: false };
```

a:

```js
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
```

Nota: `_dx = {...}` se declara con `let el = null;` arriba en el archivo (línea 7 original ya tiene `const D = window.DeposLogic;` etc. antes) — el bloque de arriba reemplaza exactamente las líneas 12-22 originales tal cual aparecen en el archivo.

- [ ] **Step 2: `openDepos()` reclama el target flotante**

En `static/depos.js`, dentro de `window.openDepos = async function (opts) {` (línea 852), la primera línea del cuerpo (línea 853, `opts = opts || {};`) — agregar justo después:

```js
  window.openDepos = async function (opts) {
    opts = opts || {};
    _dx.target = 'float';   // el operador abrió el popup flotante EXPLÍCITAMENTE: reclama el render
    mount();
```

(la línea `mount();` ya existe tal cual, solo se inserta la línea de `_dx.target` entre `opts = opts || {};` y `mount();`).

- [ ] **Step 3: Verificación manual — nada debe romperse todavía**

Este paso no tiene test automatizado (el repo no tiene suite de tests JS para `depos.js`, ver `reference_pre_existing_test_failures`). Verificación: `node --check static/depos.js` debe pasar sin errores de sintaxis.

```bash
node --check "static/depos.js"
```

Expected: sin output (exit 0).

- [ ] **Step 4: Commit checkpoint**

```bash
git add static/depos.js
git commit -m "refactor(depos): _dx.target decide el destino de render (float/compact) sin cambiar comportamiento"
```

---

### Task 3: `depos.js` — montaje del panel compacto (`mountCompact`, `rescueCompact`, `wireCompactStatic`)

**Files:**
- Modify: `static/depos.js` (nuevas funciones, después de `mount()`/`injectWindow()`, línea ~730-760; exponer en `window.Depos`, línea 850)

**Interfaces:**
- Consumes: `elC`/`_dx.target`/`activeEl()` de Task 2; `renderAccounts`, `renderCards`, `refreshMode`, `drawReps`, `resolveAccounts`, `loadSavedCards`, `refreshCap` (ya existen, sin cambios de firma).
- Produces: `window.Depos.mountCompact(d)`, `window.Depos.rescueCompact(container)` — consumidos por `pantalla.js` en Task 5.

- [ ] **Step 1: `mountCompact(d)` — clona el template una sola vez, reseed condicional**

En `static/depos.js`, justo después de la función `mount()` (que termina en la línea 730 con `_mounted = true; }`), agregar:

```js
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
```

- [ ] **Step 2: `wireCompactStatic()` — listeners scoped a `elC`**

Justo después de la función `mountCompact`/`rescueCompact` recién agregadas, agregar:

```js
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
```

- [ ] **Step 3: Exponer `mountCompact`/`rescueCompact`/`fireCompact` en `window.Depos`**

En `static/depos.js`, línea 850, cambiar:

```js
  // API pública mínima (drag→panel desde app.js).
  window.Depos = { addAccounts: addAccounts };
```

a:

```js
  // API pública (drag→panel desde app.js + montaje/disparo del panel compacto desde pantalla.js).
  window.Depos = {
    addAccounts: addAccounts,
    mountCompact: mountCompact,
    rescueCompact: rescueCompact,
    fireCompact: () => onDeposit(),
  };
```

- [ ] **Step 4: `node --check` + commit**

```bash
node --check "static/depos.js"
git add static/depos.js
git commit -m "feat(depos): mountCompact/wireCompactStatic — panel de depósito montable en La Pantalla"
```

---

### Task 4: `depos.js` — cerrar el hueco de staleness de `#depStage` para misiones compactas

**Files:**
- Modify: `static/depos.js:357-360` (`journeyStart`/`journeyEnd`)

**Interfaces:**
- Consumes: `_dx.target` (Task 2).
- Produces: ninguno nuevo — corrige un efecto secundario de `journeyEnd()`.

**Por qué este paso existe:** `openDepos()` es lo único que hoy resetea `#depStage.hidden = true` (línea 862, dentro de `window.openDepos`). Una misión disparada desde el panel COMPACTO nunca pasa por `openDepos()` — así que al terminar (`journeyEnd()`), `#depStage` se queda con `hidden=false` mostrando el último frame ("done") para siempre, y la regla CSS `:has(#depStage:not([hidden]))` (Task 1) ocultaría el panel compacto de por vida tras el PRIMER depósito. Se corrige re-ocultando `#depStage` en `journeyEnd()` SOLO cuando `_dx.target === 'compact'` — cero impacto en el flujo flotante (nunca entra a esa rama).

- [ ] **Step 1: Editar `journeyEnd()`**

En `static/depos.js`, línea 357-360, cambiar:

```js
  function journeyEnd() {
    const dep = qs('#dep'); if (dep) dep.style.display = '';
    const rr = qs('#runrow'); if (rr) rr.classList.remove('on');
  }
```

a:

```js
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
```

- [ ] **Step 2: Deshabilitar el botón de disparo mientras la misión compacta corre**

En `static/depos.js`, función `journeyStart()` (línea 338-356), localizar la línea:

```js
    const dep = qs('#dep'); if (dep) dep.style.display = 'none';
    const rr = qs('#runrow'); if (rr) rr.classList.add('on');
  }
```

y cambiar a:

```js
    const dep = qs('#dep'); if (dep) dep.style.display = 'none';
    const rr = qs('#runrow'); if (rr) rr.classList.add('on');
    if (_dx.target === 'compact') {
      const fireBtn = document.querySelector('.d-deposit-btn'); if (fireBtn) fireBtn.disabled = true;
    }
  }
```

- [ ] **Step 3: `showToast` reusa `activeEl()` en vez de `el` fijo**

En `static/depos.js`, función `showToast` (línea 59-69), cambiar `el.appendChild(_toastEl);` por `(activeEl() || el).appendChild(_toastEl);` — así el toast aparece en el panel que esté activo en ese momento:

```js
  function showToast(t) {
    if (!_toastEl) {
      _toastEl = document.createElement('div');
      _toastEl.className = 'toast';
      (activeEl() || el).appendChild(_toastEl);
    }
```

- [ ] **Step 4: `node --check` + commit**

```bash
node --check "static/depos.js"
git add static/depos.js
git commit -m "fix(depos): re-oculta #depStage al terminar misión compacta (evita panel muerto tras el 1er depósito)"
```

---

### Task 5: `pantalla.js` — rescate del slot, disparo directo del botón, sin cambios visuales rotos

**Files:**
- Modify: `static/pantalla.js:780-846` (`_rescueStage`, `_mountStage`, `_renderDetailView`), `:916-921` (handler de `.d-deposit-btn`)

**Interfaces:**
- Consumes: `window.Depos.mountCompact(d)`, `window.Depos.rescueCompact(detail)`, `window.Depos.fireCompact()` (Task 3).

- [ ] **Step 1: `_rescueStage` también rescata el panel compacto**

En `static/pantalla.js`, línea 780-783:

```js
  function _rescueStage(detail) {
    const stage = document.getElementById('depStage');
    if (stage && detail.contains(stage)) document.body.appendChild(stage);
  }
```

cambiar a:

```js
  function _rescueStage(detail) {
    const stage = document.getElementById('depStage');
    if (stage && detail.contains(stage)) document.body.appendChild(stage);
    if (window.Depos && typeof window.Depos.rescueCompact === 'function') window.Depos.rescueCompact(detail);
  }
```

- [ ] **Step 2: `_mountStage` recibe `d` y monta el panel compacto**

En `static/pantalla.js`, línea 784-788:

```js
  function _mountStage() {
    const slot = document.getElementById('patStageSlot');
    const stage = document.getElementById('depStage');
    if (slot && stage && stage.parentNode !== slot) slot.appendChild(stage);
  }
```

cambiar a:

```js
  function _mountStage(d) {
    const slot = document.getElementById('patStageSlot');
    const stage = document.getElementById('depStage');
    if (slot && stage && stage.parentNode !== slot) slot.appendChild(stage);
    if (window.Depos && typeof window.Depos.mountCompact === 'function') window.Depos.mountCompact(d);
  }
```

- [ ] **Step 3: `_renderDetailView` pasa `d` a `_mountStage`**

En `static/pantalla.js`, dentro de `_renderDetailView(d, animate)` (línea 834-846), la línea:

```js
      _mountStage();               // re-parenta el escenario de depósito a la zona derecha
```

cambiar a:

```js
      _mountStage(d);              // re-parenta el escenario + monta/reseedea el panel de depósito compacto
```

- [ ] **Step 4: El botón "Depositar" de `.pat-actions` dispara directo**

En `static/pantalla.js`, dentro del listener de `_patRoot` (línea 916-921):

```js
    const dep = e.target.closest('.d-deposit-btn');
    if (dep && dep.dataset.accId) {
      e.preventDefault();
      if (typeof window.openDepositModal === 'function') window.openDepositModal(parseInt(dep.dataset.accId));
      return;
    }
```

cambiar a:

```js
    const dep = e.target.closest('.d-deposit-btn');
    if (dep && dep.dataset.accId && !dep.disabled) {
      e.preventDefault();
      if (window.Depos && typeof window.Depos.fireCompact === 'function') window.Depos.fireCompact();
      return;
    }
```

- [ ] **Step 5: `node --check` + commit**

```bash
node --check "static/pantalla.js"
git add static/pantalla.js
git commit -m "feat(pantalla): boton Depositar dispara directo al panel compacto (sin popup), rescata/monta el slot"
```

---

### Task 6: `app.js` — no abrir el popup flotante para la MISMA cuenta que ya está abierta en La Pantalla

**Files:**
- Modify: `static/app.js:4792-4829` (`openDepositModal`)

**Interfaces:**
- Consumes: `window.Pantalla.currentId` (ya expuesto, `pantalla.js:1188`).
- Produces: ninguno nuevo — agrega un guard de comportamiento.

**Por qué:** cualquier otro caller de `openDepositModal(accId)` (notif "Depositar", atajos de fila) para la MISMA cuenta que La Pantalla tiene abierta abriría el popup flotante encima del panel compacto — dos UIs de depósito para la misma cuenta a la vez. El multi-select bulk (`ids` array / `selectedIds`) NO se toca — nunca es una sola cuenta igual a `currentId` en ese path cuando hay 2+.

- [ ] **Step 1: Guard en `openDepositModal`**

En `static/app.js`, dentro de `async function openDepositModal(accountId, opts = {})` (línea 4792), después del bloque que resuelve `_ids` (línea 4796-4806) y ANTES del bloque `if (localStorage.getItem('deposV8') !== '0' ...)` (línea 4817), insertar:

```js
  // La cuenta ya está abierta en La Pantalla → el panel compacto de col 3 es la UI
  // vigente para ella (no abrir el popup flotante encima). El multi-select bulk (2+
  // ids) nunca cae aquí: _ids.length===1 lo descarta de inmediato.
  if (_ids.length === 1 && window.Pantalla && window.Pantalla.currentId === _ids[0]) {
    const stage = document.querySelector('.pat-dep-stage');
    if (stage) {
      stage.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
      toast('Usa el panel de depósito de La Pantalla', '');
      return;
    }
  }
```

- [ ] **Step 2: `node --check` + commit**

```bash
node --check "static/app.js"
git add static/app.js
git commit -m "fix(app): openDepositModal no abre el popup flotante si la cuenta ya está en La Pantalla"
```

---

### Task 7: Deploy KVM4 + verificación funcional + bitácora + cierre

**Files:**
- Modify: `docs/FRONTEND.md` (nueva sección), `NEXT-SESSION.md` (cierre de sesión)
- Deploy: `static/index.html`, `static/pantalla.js`, `static/pantalla.css`, `static/depos.js`, `static/app.js` → `/docker/betmexico/code/web/static/` (KVM4) + `docker compose restart web`

- [ ] **Step 1: Deploy a KVM4**

```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
scp -o StrictHostKeyChecking=no -i "$KEY" \
  "static/index.html" "static/pantalla.js" "static/pantalla.css" "static/depos.js" "static/app.js" \
  $HOST:/docker/betmexico/code/web/static/
ssh -o StrictHostKeyChecking=no -i "$KEY" $HOST 'docker compose -f /docker/betmexico/docker-compose.yml restart web'
```

- [ ] **Step 2: Verificar el proceso vivo tras el restart** (regla `feedback_verificar_deploy_proceso_vivo`)

```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
ssh -o StrictHostKeyChecking=no -i "$KEY" $HOST '
echo "=== StartedAt ==="; docker inspect --format "{{.State.StartedAt}}" betmexico-web
echo "=== mtime static ==="; stat -c "%y" /docker/betmexico/code/web/static/depos.js
echo "=== HEALTH ==="; docker exec betmexico-web python3 -c "import httpx;r=httpx.get(\"http://localhost:8080/api/health\",timeout=10);print(r.status_code,r.text[:140])"
'
```

Expected: `StartedAt` posterior al `mtime` de `depos.js`, health 200.

- [ ] **Step 3: Verificación visual en navegador real (Robert)**

Checklist a confirmar por Robert en su propio navegador (no en el pane headless — `requestAnimationFrame` no corre ahí, ver limitación ya documentada):
- Abrir La Pantalla de una cuenta SA-visible → debe verse el panel de retiro Y, debajo, el panel de depósito compacto (chips de la cuenta actual, monto con presets, sin banner/saludo/2-columnas).
- Con el ancho de ventana en el rango medio (~900-1400px) donde antes se activaba `.pat-cramped`, ambos paneles deben seguir visibles (apilados, sin desbordar horizontal).
- Click en "Depositar" (`.pat-actions`) con un monto preset elegido → dispara SIN abrir popup, el escenario (`#depStage`) toma la columna completa, el botón queda disabled durante la corrida.
- Al terminar (éxito o rechazo), el panel compacto reaparece (no se queda el escenario congelado tapándolo).
- Seleccionar 2+ cuentas en la tabla y disparar el multi-select bulk → debe seguir abriendo el popup flotante de siempre, sin relación con la cuenta que esté abierta en La Pantalla.

- [ ] **Step 4: Smoke funcional — depósito real de $10** (acción con dinero real — Robert ejecuta el click, no el agente)

Desde el panel compacto: 1 cuenta, tarjeta guardada o pegada, monto $10 (preset), disparar con el botón de `.pat-actions`. Confirmar:
- El modo inferido es `single` (reps=1, sin cuenta extra).
- El resultado se refleja en la columna de movimientos (col 2) sin una lista `#mov` duplicada en col 3.
- El saldo (`.pat-balance`/tabla) se actualiza vía el mismo SSE `account_refreshed` que ya usaba el popup flotante.

- [ ] **Step 5: Actualizar `docs/FRONTEND.md`**

Agregar sección nueva al final del archivo (después de la última sección existente):

```markdown
## Panel de depósito compacto en La Pantalla col 3 (2026-07-26)

Motor SINGLETON de `depos.js` (`_dx`) con DOS destinos de render posibles, decididos por
`_dx.target` (`'float' | 'compact'`):
- `el` — ventana flotante original (`#depos`, `#deposTpl`), SOLO para el multi-select bulk
  de la tabla (`openDepositModal(null, {ids:[...]})`).
- `elC` — panel compacto (`#depCompact`, `#deposCompactTpl`), montado en `#patDepSlot`
  dentro de `.pat-col-stage` de La Pantalla vía `window.Depos.mountCompact(d)`, llamado
  desde `pantalla.js`'s `_mountStage(d)` en cada render de detalle.

Mutua exclusión con una misión bulk corriendo en paralelo: la regla CSS
`.pat-col-stage:has(#depStage:not([hidden])) .pat-dep-stage { display:none; }` oculta el
panel compacto mientras CUALQUIER misión (float o compacta) está corriendo — así un
`_dx.accounts` que pertenece a la misión bulk nunca se pinta en el panel de la cuenta que
La Pantalla tiene abierta. Cuando no hay misión corriendo, `mountCompact()` reseedea `_dx`
a la cuenta visible (condición: `!_dx.running && (_dx.target!=='compact' || accounts[0].id !== d.id)`).

El botón "Depositar" de `.pat-actions` (`.d-deposit-btn`) ya NO abre el popup — llama
`window.Depos.fireCompact()` directo (mismo patrón que `.d-withdraw-fire`). `openDepositModal`
(app.js) gana un guard: si la cuenta objetivo es la misma que `window.Pantalla.currentId`,
no abre el popup — hace scroll al panel compacto.

Gotcha resuelto en Task 4: `openDepos()` es lo único que reseteaba `#depStage.hidden=true`;
una misión compacta nunca pasa por ahí, así que `journeyEnd()` lo re-oculta manualmente
cuando `_dx.target==='compact'` (si no, el panel compacto queda oculto para siempre tras
el primer depósito, por la regla `:has()` de arriba).
```

- [ ] **Step 6: Cierre en `NEXT-SESSION.md`**

Agregar sección de cierre (formato consistente con cierres previos de la sesión) documentando: qué se implementó, qué quedó pendiente de que Robert confirme visualmente (Step 3) y el smoke de $10 real (Step 4) si no se hizo en la misma sesión.

- [ ] **Step 7: Commit final**

```bash
git add docs/FRONTEND.md NEXT-SESSION.md
git commit -m "docs(bitacora): panel de deposito compacto col 3 — arquitectura + gotcha de #depStage"
git push
```

---

## Self-Review

**Spec coverage:** las 6 secciones del spec (`objetivo`, `alcance`, `reglas por modo`, `layout`, `qué se corta/mantiene`, `botón único`, `automático/manual`, `testing/riesgos`) están cubiertas: Task 1 (layout+corte visual), Task 2/3 (reglas por modo intactas — `refreshMode`/`setPresets` sin tocar), Task 5 (botón único), Task 7 (testing/riesgos, incluida la fuga de estado que el spec dejaba ambigua y el advisor cerró con la regla `:has()` + reseed condicional).

**Placeholder scan:** sin TBD/TODO — cada step trae el código exacto a pegar, anclado a líneas reales leídas del archivo actual.

**Type/naming consistency:** `window.Depos.mountCompact`/`rescueCompact`/`fireCompact` se declaran en Task 3 y se consumen con los MISMOS nombres en Task 5 — verificado. `_dx.target` se inicializa en Task 2 y se lee en Task 3/4/5 con el mismo string literal (`'float'`/`'compact'`).

**Riesgo aceptado y documentado (no bloqueante):** si el operador arma una misión bulk en el popup flotante (accounts cargadas, SIN disparar aún) mientras La Pantalla está abierta en otra cuenta, y ocurre un re-render de La Pantalla en esa ventana idle (p.ej. un tick de SSE), `mountCompact()` reseedea `_dx` de vuelta a la cuenta de La Pantalla — el operador pierde la selección bulk no disparada. Es una regresión menor de UX (no de dinero: nada se dispara solo), acotada a una ventana de tiempo pequeña, y análoga al reset-total-al-reabrir que `openDepos()` ya hace hoy. Fuera de alcance para esta sesión.
