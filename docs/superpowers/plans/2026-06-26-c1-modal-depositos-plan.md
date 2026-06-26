# C1 — Modal de depósitos unificado v8 · Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir el modal de depósito unificado v8 (UNA vista, el modo emerge de los controles) en `static/`, cableado a los 3 flujos reales que ya operan, supliendo el drawer viejo solo al llegar a paridad funcional mínima — sin romper la operación en vivo.

**Architecture:** Componente vanilla-JS nuevo y **autocontenido** (`depos.js` + `depos.css` + `depos_logic.js`) que se construye **junto al** `#depDrawer` viejo, no in-place. El modal nuevo se monta en un `#deposRoot` vacío de `index.html` (todo el DOM, incluidas las 5 escenas SVG, lo inyecta `depos.js` desde un template — no ensucia index.html). La lógica pura (derivar modo, mapear fase→escena, validar pipe) vive aparte en `depos_logic.js` con patrón UMD-lite, testeable con `node --test` sin DOM. `app.js` solo cambia en un punto: `openDepositModal()` hace branch a `openDepos()` bajo un flag de suplencia (`localStorage.deposV8`), dejando el drawer viejo como fallback hasta retirarlo.

**Tech Stack:** Vanilla JS (sin framework ni bundler — el dashboard sirve estáticos crudos), SSE (fetch+reader para streams privados, EventSource para el bus global), SVG/CSS para las escenas, `node --test` (Node v24) para la lógica pura. Backend Python/FastAPI ya existente (NO se toca en C1).

## Global Constraints

- **Repo canónico:** `repos/botmex-dashboard` (Forgejo `Robertvs/botmex-dashboard`). NO editar el monorepo BetMexico ni `Proyectos/`. El backend del bot NO se toca en C1.
- **L1 — Login único:** C1 es frontend; NUNCA inventa un camino de login. Lanza solo contra `/api/deposits/execute-stream`, `/multi/stream`, `/scheduled/create` (ya usan `gentle_login` con `allow_proxyless=False`).
- **L2 — No perder info:** todo dato útil persiste y es **copiable sin enmascarar** (combos `email:password` completos, pipes de tarjeta completos `NNNN|MM|YY|CVV`, sin `/`). Nunca masking.
- **L3 — Capas operador vs backend:** el modal NUNCA muestra al operador proxy/IP/raw `result_codes`/`gateway_response_raw`/credenciales ajenas. Errores nuestros = invisibles o humanizados (E-RED); el resultado solo si es REAL.
- **L4 — Visibilidad por rol:** el modal consume lo que el backend ya filtra por rol; no expone actividad cruzada.
- **L5 — Click → completado, trazable:** cada acción fluye de click a resultado con traza en BD (vía los endpoints existentes).
- **No romper operación:** el drawer viejo (`#depDrawer`) queda intacto y funcional durante todo C1. La suplencia es por flag, reversible al instante.
- **Degradar con gracia** lo que el backend aún NO emite: balance-before (no hay evento → usar el del row actual), badge A+/grade (no hay evento → estado neutro), fases multi por bus (B3 — innecesario: el modal lee el stream privado del POST).
- **Lógica de modo (la UI impone las reglas), copiada verbatim del mockup v8 (`refreshMode()`):**
  - `n<=1` cuenta: reps visible. `reps>1` → **Programado** (`/scheduled/create`, repetitions); `reps==1` → **Único** (`/execute-stream`). Preset `[$100]` + monto manual `$10–$499`.
  - `n>1` cuentas: reps **oculto**. **Multi** (`/multi/stream`). Presets fijos `[$10, $50, $1000(3DS)]`, sin monto manual.
- **Caps duros (backend, informativos en UI):** `DEP_MAX_PER_TXN=499` (>499 dispara 3DS), `DEP_MAX_24H=1499`/cuenta.
- **Contrato visual:** `docs/mockups/modal-deposito-unificado-v8.html` (1042 líneas, APROBADO + verificado en navegador). Es la fuente verbatim para markup/CSS/escenas SVG.

---

## Mapa de archivos

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `static/depos_logic.js` | Create | Funciones puras (sin DOM): `deriveMode`, `presetsForMode`, `mapPhaseToScene`, `phaseToPct`, `validatePipe`, `parseCombo`, `fmtMoney`. UMD-lite (browser global `DeposLogic` + `module.exports`). |
| `static/depos_logic.test.js` | Create | Tests `node --test` de las funciones puras. |
| `static/depos.css` | Create | Estilos v8 (copiados del mockup, scoped bajo `#depos`). Incluye keyframes de las 5 escenas. |
| `static/depos.js` | Create | Componente: template DOM (incl. 5 escenas SVG), state, controles, journey, cableado SSE a los 3 flujos, movimientos. Expone `window.openDepos(opts)` / `window.closeDepos()`. |
| `static/index.html` | Modify | `<link depos.css>` en head; `<div id="deposRoot">` antes del toast; `<script depos.js>` tras app.js. |
| `static/app.js` | Modify | `openDepositModal()`: branch a `openDepos()` bajo `localStorage.deposV8`; drawer viejo como fallback. |
| `docs/SSE_EVENTS.md` | Modify (Task 13) | Documentar `account_refreshed` y `scheduled_retry` (emitidos sin documentar). |

**Endpoints/SSE que C1 consume (ya existen, verificados):**
- Single: `POST /api/deposits/execute-stream` `{account_id, card_pipe, amount}` → stream privado NL-JSON: `start`, `phase {name,data}`, `done {success,result_code,error,duration_ms}`, `fatal`.
- Multi: `POST /api/deposits/multi/stream` `{account_ids, cards, amount}` → stream privado: `start`, `trying {email,tail,attempt}`, `phase {email,tail,name,data}`, `match {email,tail,pipe,amount,duration_ms}`, `rejected {email,tail,code,...}`, `account_dead`, `login_retry`, `velocity_skip`, `card_retired`, `cooldown`, `error`, `done {matches,attempts,pending}`, `fatal`, `cancelled`. Cancel: `POST /api/deposits/multi/{run_id}/cancel`.
- Scheduled: `POST /api/deposits/scheduled/create` `{account_id, card_pipe, amount, repetitions}` → `{sched_id,total}`; eventos por **bus global** `/api/events`: `scheduled_started`, `scheduled_phase {sched_id,iter,total,name,data,email}`, `scheduled {iter,total,success,code,reason}`, `scheduled_retry {iter,attempt,max,code,reason}`, `scheduled_aborted`, `scheduled_cancelled`. List activo: `GET /api/deposits/scheduled/list`.
- Cuentas/tarjetas (single/scheduled): `GET /api/accounts/{id}/details` (tarjetas guardadas), `GET /api/deposits/cap-status/{id}` (cap 24h). Combo `email:password`: `GET /api/accounts/pass-map` / `/api/accounts/combos` (verificar firma exacta al ejecutar Task 6).
- Balance/badge post-depósito: bus `account_refreshed {email,balance_real,balance_total}`. **No hay** balance-before ni grade-live → degradar.

**Mapeo fase backend → escena v8 (define `mapPhaseToScene` / `phaseToPct`, Task 2):**

| Fases backend | Escena v8 | % |
|---------------|-----------|---|
| `login_start`, `login_done`, `login_reused` | `login` | 14 |
| `gateway_begin`, `gateway_begin_done`, `gateway_begin_retry` | `form` | 40 |
| `gateway_submit`, `gateway_submit_done` | `processing` | 70 |
| `gateway_check`, `gateway_check_done`, `gateway_check_retry` | `processing` | 82 |
| `login_retry`, `*_retry` (retry transitorio) | `retry` | (mantiene %) |
| `implicit_3ds_detected` | `processing` | 82 |
| `done` (success) | `done` | 100 |

---

## Fase 1 — Lógica pura (TDD con `node --test`)

### Task 1: `deriveMode` + `presetsForMode` (la UI impone las reglas)

**Files:**
- Create: `static/depos_logic.js`
- Test: `static/depos_logic.test.js`

**Interfaces:**
- Produces: `deriveMode(nAccounts:number, reps:number) -> 'single'|'scheduled'|'multi'`; `presetsForMode(mode) -> {presets:number[], manual:boolean, note:string, repsVisible:boolean}`. Expuestos como `DeposLogic.deriveMode` / `DeposLogic.presetsForMode` (browser) y `module.exports` (node).

- [ ] **Step 1: Write the failing test**

```js
// static/depos_logic.test.js
const test = require('node:test');
const assert = require('node:assert');
const D = require('./depos_logic.js');

test('deriveMode: 1 cuenta reps=1 -> single', () => {
  assert.equal(D.deriveMode(1, 1), 'single');
});
test('deriveMode: 1 cuenta reps>1 -> scheduled', () => {
  assert.equal(D.deriveMode(1, 5), 'scheduled');
});
test('deriveMode: 0 cuentas (vacío) -> single', () => {
  assert.equal(D.deriveMode(0, 1), 'single');
});
test('deriveMode: varias cuentas -> multi (ignora reps)', () => {
  assert.equal(D.deriveMode(3, 9), 'multi');
});
test('presetsForMode single: [100] manual, reps visible', () => {
  const p = D.presetsForMode('single');
  assert.deepEqual(p.presets, [100]);
  assert.equal(p.manual, true);
  assert.equal(p.repsVisible, true);
});
test('presetsForMode multi: [10,50,1000] sin manual, reps oculto', () => {
  const p = D.presetsForMode('multi');
  assert.deepEqual(p.presets, [10, 50, 1000]);
  assert.equal(p.manual, false);
  assert.equal(p.repsVisible, false);
});
test('presetsForMode scheduled: como single (reps visible)', () => {
  const p = D.presetsForMode('scheduled');
  assert.equal(p.repsVisible, true);
  assert.equal(p.manual, true);
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test static/depos_logic.test.js`
Expected: FAIL — `Cannot find module './depos_logic.js'`.

- [ ] **Step 3: Write minimal implementation**

```js
// static/depos_logic.js
(function (root, factory) {
  const api = factory();
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.DeposLogic = api;
})(typeof self !== 'undefined' ? self : this, function () {
  'use strict';

  // 1 cuenta + reps>1 = programado; 1 (o 0) cuenta + reps=1 = único; varias = multi.
  function deriveMode(nAccounts, reps) {
    if (nAccounts > 1) return 'multi';
    return reps > 1 ? 'scheduled' : 'single';
  }

  function presetsForMode(mode) {
    if (mode === 'multi') {
      return {
        presets: [10, 50, 1000], manual: false, repsVisible: false,
        note: 'Montos fijos para varias cuentas · $1000 fuerza 3DS',
      };
    }
    // single + scheduled comparten controles (1 cuenta)
    return {
      presets: [100], manual: true, repsVisible: true,
      note: '$100 o escribe el monto · ($10 a $499)',
    };
  }

  return { deriveMode, presetsForMode };
});
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test static/depos_logic.test.js`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add static/depos_logic.js static/depos_logic.test.js
git commit -m "feat(c1): deriveMode + presetsForMode (la UI impone las reglas, TDD verde)"
```

---

### Task 2: `mapPhaseToScene` + `phaseToPct` (fase backend → escena v8)

**Files:**
- Modify: `static/depos_logic.js`
- Modify: `static/depos_logic.test.js`

**Interfaces:**
- Produces: `mapPhaseToScene(name:string) -> 'login'|'form'|'processing'|'retry'|'done'`; `phaseToPct(name:string) -> number` (0–100, o `null` si la fase no mueve el %, ej. un retry). `DeposLogic.mapPhaseToScene` / `DeposLogic.phaseToPct`.

- [ ] **Step 1: Write the failing test**

```js
// añadir a static/depos_logic.test.js
test('mapPhaseToScene: login family', () => {
  ['login_start','login_done','login_reused'].forEach(n =>
    assert.equal(D.mapPhaseToScene(n), 'login'));
});
test('mapPhaseToScene: begin family -> form', () => {
  ['gateway_begin','gateway_begin_done','gateway_begin_retry'].forEach(n =>
    assert.equal(D.mapPhaseToScene(n), 'form'));
});
test('mapPhaseToScene: submit/check -> processing', () => {
  ['gateway_submit','gateway_submit_done','gateway_check','gateway_check_done','implicit_3ds_detected'].forEach(n =>
    assert.equal(D.mapPhaseToScene(n), 'processing'));
});
test('mapPhaseToScene: retry transitorio -> retry', () => {
  ['login_retry','gateway_check_retry'].forEach(n =>
    assert.equal(D.mapPhaseToScene(n), 'retry'));
});
test('mapPhaseToScene: done', () => {
  assert.equal(D.mapPhaseToScene('done'), 'done');
});
test('phaseToPct monotonic', () => {
  assert.equal(D.phaseToPct('login_start'), 14);
  assert.equal(D.phaseToPct('gateway_begin'), 40);
  assert.equal(D.phaseToPct('gateway_submit'), 70);
  assert.equal(D.phaseToPct('gateway_check'), 82);
  assert.equal(D.phaseToPct('done'), 100);
  assert.equal(D.phaseToPct('login_retry'), null); // retry no mueve %
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test static/depos_logic.test.js`
Expected: FAIL — `D.mapPhaseToScene is not a function`.

- [ ] **Step 3: Write minimal implementation** (insertar dentro del factory de `depos_logic.js`, antes del `return`)

```js
  const _SCENE = {
    login_start: 'login', login_done: 'login', login_reused: 'login',
    gateway_begin: 'form', gateway_begin_done: 'form', gateway_begin_retry: 'form',
    gateway_submit: 'processing', gateway_submit_done: 'processing',
    gateway_check: 'processing', gateway_check_done: 'processing',
    implicit_3ds_detected: 'processing',
    done: 'done',
  };
  function mapPhaseToScene(name) {
    if (typeof name === 'string' && name.endsWith('_retry')) return 'retry';
    return _SCENE[name] || 'login';
  }
  const _PCT = {
    login_start: 14, login_done: 14, login_reused: 14,
    gateway_begin: 40, gateway_begin_done: 40,
    gateway_submit: 70, gateway_submit_done: 70,
    gateway_check: 82, gateway_check_done: 82, implicit_3ds_detected: 82,
    done: 100,
  };
  function phaseToPct(name) {
    if (typeof name === 'string' && name.endsWith('_retry')) return null;
    return name in _PCT ? _PCT[name] : null;
  }
```

Y agregar `mapPhaseToScene, phaseToPct` al objeto del `return`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test static/depos_logic.test.js`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add static/depos_logic.js static/depos_logic.test.js
git commit -m "feat(c1): mapPhaseToScene + phaseToPct (fase backend -> escena v8, TDD verde)"
```

---

### Task 3: `validatePipe` + `parseCombo` + `fmtMoney`

**Files:**
- Modify: `static/depos_logic.js`
- Modify: `static/depos_logic.test.js`

**Interfaces:**
- Produces: `validatePipe(s:string) -> boolean` (acepta `NNNN|MM|YY|CVV` y `NNNN|MMYY|CVV`); `parseCombo(s:string) -> {email,password}|null` (split en el primer `:`); `fmtMoney(n:number) -> string` (`$1,234.56`). Reusa el regex del `validatePipe` viejo (`app.js:3896-3915`).

- [ ] **Step 1: Write the failing test**

```js
// añadir a static/depos_logic.test.js
test('validatePipe 4 partes', () => assert.equal(D.validatePipe('4111111111111111|12|30|123'), true));
test('validatePipe 3 partes (MMYY)', () => assert.equal(D.validatePipe('4111111111111111|1230|123'), true));
test('validatePipe rechaza basura', () => {
  assert.equal(D.validatePipe('hola'), false);
  assert.equal(D.validatePipe('4111|12|30'), false);
});
test('parseCombo split en primer :', () => {
  assert.deepEqual(D.parseCombo('a@b.mx:Pass:word!'), {email:'a@b.mx', password:'Pass:word!'});
});
test('parseCombo sin : -> null', () => assert.equal(D.parseCombo('nope'), null));
test('fmtMoney', () => {
  assert.equal(D.fmtMoney(512), '$512.00');
  assert.equal(D.fmtMoney(1234.5), '$1,234.50');
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node --test static/depos_logic.test.js`
Expected: FAIL — `D.validatePipe is not a function`.

- [ ] **Step 3: Write minimal implementation** (insertar en el factory)

```js
  function validatePipe(s) {
    if (typeof s !== 'string') return false;
    const p = s.trim().split('|');
    if (p.length === 4) return /^\d{13,19}$/.test(p[0]) && /^\d{1,2}$/.test(p[1]) && /^\d{2,4}$/.test(p[2]) && /^\d{3,4}$/.test(p[3]);
    if (p.length === 3) return /^\d{13,19}$/.test(p[0]) && /^\d{3,4}$/.test(p[1]) && /^\d{3,4}$/.test(p[2]);
    return false;
  }
  function parseCombo(s) {
    if (typeof s !== 'string') return null;
    const i = s.indexOf(':');
    if (i < 0) return null;
    return { email: s.slice(0, i), password: s.slice(i + 1) };
  }
  function fmtMoney(n) {
    const v = Number(n) || 0;
    return '$' + v.toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }
```

Y agregar `validatePipe, parseCombo, fmtMoney` al `return`.

- [ ] **Step 4: Run test to verify it passes**

Run: `node --test static/depos_logic.test.js`
Expected: PASS (todos).

> **Nota de ejecución:** confirmar contra `app.js:3896-3915` que el regex viejo no es más permisivo en algo que el backend espera; si difiere, ajustar el test al comportamiento real del backend (la verdad es el backend, no el regex viejo).

- [ ] **Step 5: Commit**

```bash
git add static/depos_logic.js static/depos_logic.test.js
git commit -m "feat(c1): validatePipe + parseCombo + fmtMoney (TDD verde)"
```

---

## Fase 2 — Shell visual (verificación en navegador)

### Task 4: `depos.css` — estilos v8 scoped

**Files:**
- Create: `static/depos.css`

- [ ] **Step 1: Copiar el bloque `<style>` del mockup v8**

Copiar **verbatim** el contenido entre `<style>` y `</style>` del mockup (`docs/mockups/modal-deposito-unificado-v8.html:10-565`) a `static/depos.css`. Incluye `:root` vars, layout (`.bmx`, `.head`, `.controls`, `.duo`, `.chip`, `.amt`, `.reps`, `.seg-*`, `.deposit`, `.runrow`, `.journey`, `.scene-*`, `.guide`, `.mov`, `.toast`) y **todos** los keyframes de las 5 escenas (`lg-*`, `fm-*`, `pr-*`, `rt-*`, `dn-*`).

- [ ] **Step 2: Scoping anti-colisión**

Prefijar el selector raíz para no chocar con `style.css` del dashboard. Envolver: el modal vivirá dentro de `#depos`. Cambiar las `:root{...}` por `#depos{...}` (las CSS vars quedan scoped al modal) y prefijar los selectores de nivel superior que sean genéricos (`.toast` → `#depos .toast`; el `.stage`/`.bmx`/`body{...}` del mockup que aplican al `<body>` de la demo se adaptan: `body{...}` del mockup se descarta — el fondo lo da el dashboard; en su lugar el overlay del modal lo define Task 5). Mantener los IDs de escena (`#scene-login`, etc.) — son únicos.

- [ ] **Step 3: Verificar que no rompe el dashboard**

Cargar el dashboard en preview (Task 5 añade el `<link>`). Verificación visual: el dashboard existente se ve igual (depos.css no tiene reglas que apliquen fuera de `#depos`). Si algo del dashboard cambió → un selector quedó sin scope; corregir.

- [ ] **Step 4: Commit**

```bash
git add static/depos.css
git commit -m "feat(c1): depos.css — estilos v8 scoped bajo #depos (sin colisión con style.css)"
```

---

### Task 5: `depos.js` esqueleto — template DOM, open/close, greetings, reps, lógica de modo

**Files:**
- Create: `static/depos.js`
- Modify: `static/index.html` (head: `<link>`; body: `<div id="deposRoot">`; tras app.js: `<script>`)

**Interfaces:**
- Consumes: `DeposLogic.deriveMode`, `presetsForMode` (Task 1).
- Produces: `window.openDepos(opts)` donde `opts = {ids?:number[], accounts?:[{id,email,password,grade}]}`; `window.closeDepos()`. State interno `_dx = {open, accounts:[], cards:[], reps, amount, mode, running, sched, mm}`.

- [ ] **Step 1: Markup base en index.html**

En `static/index.html` head, tras la línea 16 (`<link ... style.css>`), añadir:
```html
<link rel="stylesheet" href="/static/depos.css?v=20260626a">
```
Antes de `<!-- Toast -->` (línea ~629), añadir:
```html
<!-- Modal Depósitos v8 (C1) — montado por depos.js -->
<div id="deposRoot" class="depos-root hidden" aria-hidden="true"></div>
```
Tras `<script src="/static/app.js?...">` (línea 632), añadir:
```html
<script src="/static/depos.js?v=20260626a"></script>
```

- [ ] **Step 2: Overlay + scoping en depos.css**

Añadir a `static/depos.css`:
```css
.depos-root{position:fixed; inset:0; z-index:200; display:grid; place-items:center;
  background:rgba(4,6,10,.62); backdrop-filter:blur(4px); padding:30px 18px; overflow:auto}
.depos-root.hidden{display:none}
#depos{--void:#06070a; --void-2:#0a0c11; /* …resto de vars del :root del mockup… */}
```
(Mover aquí las CSS vars que en Task 4 quedaron en `#depos{}`.)

- [ ] **Step 3: depos.js — template + montaje + open/close**

Crear `static/depos.js`. El template es el markup **verbatim** del mockup v8 entre `<div class="stage">` y `</div><!-- stage -->` (mockup líneas 570-926), envuelto así: el contenedor exterior es `#deposRoot` (ya en index.html); dentro inyectar `<div id="depos"><aside class="bmx">…</aside></div>`. Copiar las 5 escenas SVG **verbatim** del mockup (líneas 650-912). Estructura:

```js
(function () {
  'use strict';
  const D = window.DeposLogic;
  const $ = (s, r) => (r || document).querySelector(s);
  const root = document.getElementById('deposRoot');

  const TEMPLATE = `<div id="depos"><aside class="bmx" role="dialog" aria-label="Depositar">
    <!-- …copiar verbatim del mockup v8 L573-925: header, controls, journey (5 escenas SVG), mov… -->
  </aside></div>`;

  let _dx = { open:false, accounts:[], cards:[], reps:5, amount:50, mode:'single', running:false };
  let _mounted = false;

  function mount() {
    if (_mounted) return;
    root.innerHTML = TEMPLATE;
    wireStatic();      // greetings, 7-seg, presets, modo, cerrar
    _mounted = true;
  }

  window.openDepos = function (opts) {
    opts = opts || {};
    mount();
    _dx.accounts = (opts.accounts || (opts.ids || []).map(id => ({ id, email:'', password:'', grade:'' })));
    _dx.cards = []; _dx.reps = 1; _dx.amount = 50; _dx.running = false;
    renderAccounts();        // Task 6
    refreshMode();
    root.classList.remove('hidden'); root.setAttribute('aria-hidden', 'false'); _dx.open = true;
    document.addEventListener('keydown', onEsc);
  };
  window.closeDepos = function () {
    if (_dx.running) { showToast('Hay una misión en curso'); return; } // pill viene en Task 10
    root.classList.add('hidden'); root.setAttribute('aria-hidden', 'true'); _dx.open = false;
    document.removeEventListener('keydown', onEsc);
  };
  function onEsc(e) { if (e.key === 'Escape') window.closeDepos(); }
  // click fuera del panel cierra
  root.addEventListener('click', e => { if (e.target === root) window.closeDepos(); });
  // …wireStatic, refreshMode, greetings, drawReps copiados/adaptados del mockup L930-1038…
})();
```

`wireStatic()` cablea, adaptando del mockup v8 (L930-1038): copiable→`showToast('copiado')`, 7-seg reps (`drawReps`, `repUp/repDn` con `_dx.reps`), greetings rotativos (10 frases, cada 6s), botón `#dep`/`#abort`/`#pause` (se cablean en Fase 3). `refreshMode()` usa `D.deriveMode(_dx.accounts.length, _dx.reps)` + `D.presetsForMode(mode)` para pintar presets/nota/visibilidad de reps y `#modeText`. El avatar: cambiar `src="depos_avatar.png"` → `src="/static/assets/depos_avatar.png"` en el template.

- [ ] **Step 4: Verificar en navegador**

`preview_start` (si no hay server). Abrir el dashboard. En consola: `window.openDepos({accounts:[{id:1,email:'a@b.mx',password:'x',grade:'a'},{id:2,email:'c@d.mx',password:'y',grade:'b'}]})`.
Verificación (`preview_snapshot` + `preview_screenshot`):
- El modal v8 aparece centrado, tema obsidian, avatar osito visible.
- 2 cuentas como chips → `#modeText` dice "Varias cuentas…", reps oculto, presets `[$10,$50,$1000]`.
- Quitar una cuenta (X) → recalcula a 1 cuenta, reps visible, preset `[$100]`.
- Subir reps a 5 → `#modeText` dice "Programado · 5 depósitos…".
- Greetings rotan; copiar un chip muestra toast; Esc / click-fuera cierra.

- [ ] **Step 5: Commit**

```bash
git add static/depos.js static/index.html static/depos.css
git commit -m "feat(c1): depos.js esqueleto — modal v8 monta, open/close, greetings, reps, lógica de modo (verificado navegador)"
```

---

### Task 6: Cuentas (combo+grado), tarjetas (input+guardadas), cap 24h

**Files:**
- Modify: `static/depos.js`

**Interfaces:**
- Consumes: `DeposLogic.validatePipe`, `parseCombo`.
- Produces: `renderAccounts()`, `renderCards()`, `refreshCap(accountId)` dentro de `depos.js`.

- [ ] **Step 1: Resolver combo `email:password` + grado de cada cuenta pre-seleccionada**

Al `openDepos({ids})`, si las cuentas no traen `password`/`grade`, resolverlos. **Verificar la firma real al ejecutar** (candidatos del A2.1: `GET /api/accounts/pass-map` y `/api/accounts/combos`). `renderAccounts()` pinta chips en `#accChips`: `<span class="chip copyable" data-copy="email:password"><span class="hdot {grade}"></span><span class="txt">email:password</span><span class="chip-x">x</span></span>`. Sin masking (L2). El `hdot` toma la clase del grade (`a/b/c/d`). `#accCount` = número.

- [ ] **Step 2: Tarjetas — input "+ agregar" + guardadas**

`.chip-add` ("+ agregar tarjeta") abre un input inline; al pegar un pipe válido (`D.validatePipe`) se agrega como chip copyable a `_dx.cards` y al DOM. En single/scheduled (1 cuenta), cargar tarjetas guardadas vía `GET /api/accounts/{id}/details` (reusar el shape de `refreshSavedCards`, `app.js:3811`) como chips pre-cargados con badge ✓ si aprobadas. En multi son el pool (varias tarjetas).

- [ ] **Step 3: Cap 24h (single/scheduled)**

Cuando hay 1 cuenta, `refreshCap(id)` consulta `GET /api/deposits/cap-status/{id}` y pinta una barra discreta (used/max_24h) + hora de cierre. Si el monto elegido + used > 1499 → nota de advertencia (no bloquea; el backend valida). Ocultar en multi.

- [ ] **Step 4: Verificar en navegador**

Con server corriendo y sesión real: seleccionar cuentas de la tabla → abrir modal (vía consola `openDepos({ids:[...]})` por ahora). Verificar: chips muestran `email:password` real + hdot del grado correcto; pegar una tarjeta válida la agrega, una inválida no; tarjetas guardadas aparecen (single); cap 24h pinta el valor real (comparar con `/api/deposits/cap-status/{id}` por separado). `preview_network` confirma las llamadas.

- [ ] **Step 5: Commit**

```bash
git add static/depos.js
git commit -m "feat(c1): cuentas (combo+grado), tarjetas (input+guardadas), cap 24h — datos reales (verificado navegador)"
```

---

## Fase 3 — Cableado de ejecución (navegador + datos reales)

### Task 7: SINGLE — `/execute-stream`, fase→escena, balance, movimiento, resultado

**Files:**
- Modify: `static/depos.js`

**Interfaces:**
- Consumes: `DeposLogic.mapPhaseToScene`, `phaseToPct`, `fmtMoney`.
- Produces: `runSingle()`, `setScene(k)`, `movRow(who,amt,state)`, `_consumeStream(resp, onEvent)` (helper de lectura NL-JSON reusable por multi).

- [ ] **Step 1: Helper de stream + escenas**

Portar de `depos.js` (mockup L992-1005): `setScene(k)` (toggla `.scene.on`), `movRow` (prepend a `#mov`), `setPct`. Añadir `_consumeStream(resp, onEvent)`: lee `resp.body.getReader()`, decodifica, parte por `\n`, quita prefijo `data:`, `JSON.parse`, llama `onEvent(ev)` — mismo patrón que `executeDeposit` viejo (`app.js:3924`). Manejar `CancelledError`/abort.

- [ ] **Step 2: runSingle()**

Al click en `#dep` con `mode==='single'`: validar 1 cuenta + 1 tarjeta (`D.validatePipe`) + monto. Mostrar journey (`guide.hide`, `jbal/jstatus` visibles), botón → `.runrow`. `balNow` = balance del row actual (degradado — no hay before real); `balTo` arranca igual. `fetch POST /api/deposits/execute-stream {account_id, card_pipe, amount}`, `_consumeStream`:
  - `phase {name}` → `setScene(D.mapPhaseToScene(name))`; `pct = D.phaseToPct(name)` si no es null; `#sub` = label humano de la fase (mapa interno, NUNCA result_code crudo — L3).
  - `done {success, result_code}` → si `success`: `setScene('done')`, `balTo` anima a `balNow+amount` (provisional; se reconcilia con `account_refreshed` del bus), `movRow(email, amount, 'ok')`, `#sub`='Acreditado ✓'. Si no: `setScene('login')`, mensaje humanizado (E-RED) según familia (rechazo de tarjeta = real y se muestra; error nuestro = "Reintenta en un momento"), `movRow` estado neutro.
  - `fatal` → mensaje humanizado, sin tripas.

- [ ] **Step 3: Reconciliar balance/badge con el bus**

`depos.js` se suscribe al bus global una sola vez (EventSource `/api/events`, o reusar el de app.js si expone un hook). Al `account_refreshed {email,balance_total}` de una cuenta del run activo → `balTo` = `D.fmtMoney(balance_total)` (balance FRESCO real, L2). Badge A+/grade: estado **neutro** (no hay evento — degradado; se repintará al refrescar la fila).

- [ ] **Step 4: Verificar en navegador (depósito real)**

Con sesión real + una cuenta + tarjeta de prueba: lanzar single. Verificar (`preview_screenshot` en cada fase + `preview_network`): las escenas avanzan login→form→processing→done; `#pct` sube 14→40→70→82→100; `#sub` muestra labels humanos (sin códigos crudos); al aprobar, `balTo` salta al balance fresco de `account_refreshed`; aparece un movimiento "real"; un rechazo de tarjeta muestra mensaje claro; un error nuestro NO muestra tripas. `preview_console_logs` sin errores JS.

- [ ] **Step 5: Commit**

```bash
git add static/depos.js
git commit -m "feat(c1): SINGLE cableado a /execute-stream — fase->escena, balance fresco, movimiento, E-RED (verificado navegador)"
```

---

### Task 8: SCHEDULED — `/scheduled/create` + bus, reps, countdown, retry, abort, rehidratación

**Files:**
- Modify: `static/depos.js`

**Interfaces:**
- Consumes: `runSingle` helpers (`setScene`, `movRow`), `DeposLogic.mapPhaseToScene`.
- Produces: `runScheduled()`, `_schedOnBusEvent(ev)`, `rehydrateScheduled()`.

- [ ] **Step 1: Lanzar**

Al click `#dep` con `mode==='scheduled'` (1 cuenta, reps>1): `fetch POST /api/deposits/scheduled/create {account_id, card_pipe, amount, repetitions:_dx.reps}` → `{sched_id,total}`. Guardar en `_dx.sched={sched_id,total,iter:0}`. Mostrar journey + `.runrow` (Pausar deshabilitado en scheduled — solo Abortar/Cancelar). Heartbeat: `#sub`='Preparando…' con hint rotator (copiar de `_schedShow`, `app.js:4205`) hasta el primer `scheduled_phase`.

- [ ] **Step 2: Consumir el bus (no stream privado)**

Scheduled emite por `/api/events`. En `_schedOnBusEvent(ev)` (filtrando `ev.sched_id === _dx.sched.sched_id`):
  - `scheduled_phase {name,iter,total}` → `setScene(D.mapPhaseToScene(name))`, `#pct`, `#sub`; actualizar contador iter en journey; cancelar hint rotator.
  - `scheduled {iter,total,success,code,reason}` → `movRow` (ok/fail); si `success` iniciar countdown 60s al próximo (`#etaSeg` o `#sub`); si `iter>=total` finalizar.
  - `scheduled_retry {attempt,max}` → `setScene('retry')`, `#sub`='Reintentando…' (discreto, no aborta).
  - `scheduled_aborted` → finalizar con motivo humanizado (3DS / tarjeta rechazada = real; nuestro = neutro).
  - `scheduled_cancelled` → finalizar neutro.

- [ ] **Step 3: Abort/cancel + rehidratación**

`#abort` con scheduled activo → cancelar (endpoint de cancel del scheduled; verificar ruta al ejecutar — el viejo usa `#depSchedCancel`). `rehydrateScheduled()` al cargar página: `GET /api/deposits/scheduled/list`; si hay misión activa del usuario, abrir modal en modo scheduled y re-anclar `_dx.sched` con `iter` actual (paridad con `rehydrateActiveScheduled`, `app.js:5147`). Buffer de eventos que lleguen antes de montar (patrón `_schedPendingEvents`).

- [ ] **Step 4: Verificar en navegador (misión programada real)**

Lanzar scheduled de 3 reps, monto $100, cuenta real. Verificar: heartbeat aparece <1s; cada iter avanza escenas + suma al countdown 60s; los movimientos se acumulan; un retry transitorio muestra escena retry sin abortar; recargar la página re-ancla la misión activa (rehidratación). `preview_network` confirma `/scheduled/create` y el bus `/api/events`.

- [ ] **Step 5: Commit**

```bash
git add static/depos.js
git commit -m "feat(c1): SCHEDULED cableado a /scheduled/create + bus — reps, countdown, retry, abort, rehidratación (verificado navegador)"
```

---

### Task 9: MULTI — `/multi/stream`, animación del intento activo, movimientos por par

**Files:**
- Modify: `static/depos.js`

**Interfaces:**
- Consumes: `_consumeStream`, `setScene`, `movRow`, `DeposLogic.mapPhaseToScene`.
- Produces: `runMulti()`, `cancelMulti()`.

- [ ] **Step 1: Lanzar + decisión de cableado (v8 no tiene lanes)**

Al click `#dep` con `mode==='multi'` (>1 cuenta): validar 2–5 cuentas + 1–10 tarjetas + monto fijo. `fetch POST /api/deposits/multi/stream {account_ids, cards, amount}` con AbortController. **Decisión de diseño (v8 simplificó v7):** el v8 NO tiene grid 3-col ni lanes por carril → la **animación central refleja el intento (par) activo más reciente** y **Movimientos lleva la bitácora por par** (cada `match`/`rejected` es una fila). Honesto con el paralelismo real del matchmaker.

- [ ] **Step 2: Consumir el stream privado**

`_consumeStream` con los casos del matchmaker:
  - `trying {email,tail}` → `movRow(email+'···'+tail, amount, 'wait')`; `#sub`='Probando…'.
  - `phase {email,tail,name}` → `setScene(D.mapPhaseToScene(name))`; `#modeText`/`#sub` con la cuenta activa (sin tripas).
  - `match {email,tail,amount}` → `setScene('done')` (momento dorado), `movRow` actualiza a 'ok' real, contador matches.
  - `rejected {code}` → movimiento neutro o real según familia (tarjeta rechazada = real; 406/captcha = invisible/neutro).
  - `login_retry` → `setScene('retry')` discreto; NUNCA marca cuenta muerta en UI.
  - `account_dead`, `card_retired`, `velocity_skip`, `cooldown`, `error` → reflejar en movimientos con label humano (L3); `done {matches,attempts}` → resumen final.

- [ ] **Step 3: Cancel**

`#abort` → `POST /api/deposits/multi/{run_id}/cancel` + abort del reader (paridad con `cancelMatchmaker`, `app.js:4937`). Stream sin `done` → reset limpio.

- [ ] **Step 4: Verificar en navegador (matchmaker real)**

Lanzar multi: 2 cuentas, 2 tarjetas, $50. Verificar: la animación central avanza con el par activo; cada intento agrega un movimiento; un match muestra escena dorada + movimiento real; abortar detiene limpio. `preview_console_logs` sin errores; `preview_network` confirma el stream y el cancel.

- [ ] **Step 5: Commit**

```bash
git add static/depos.js
git commit -m "feat(c1): MULTI cableado a /multi/stream — animación del par activo + movimientos por par, cancel (verificado navegador)"
```

---

### Task 10: Controles de run (pause/resume/abort) + "Otro depósito" (stub degradable)

**Files:**
- Modify: `static/depos.js`

- [ ] **Step 1: Pause/resume (scheduled/multi donde aplique)**

`#pause` togglea estado visual y, donde el backend lo soporte, pausa. **Degradación honesta:** el backend hoy solo tiene `cancel` (no pause vivo en multi — eso es B3). Si no hay pause real, el botón Pausar en scheduled/multi se **oculta** (no se finge una capacidad que no existe — L3/BANDERA); solo queda Abortar. Documentar en el commit.

- [ ] **Step 2: Pill flotante al cerrar con misión activa**

Si `closeDepos()` se llama con `_dx.running` (scheduled/multi activo) → mostrar pill flotante (reusar `#depMissionPill` existente o uno propio `#deposPill`), la misión sigue por el bus/stream; click reabre. Paridad con `_depPillShow`/`_depPillReopen` (`app.js:4119`).

- [ ] **Step 3: "Otro depósito" (botón `.newproc`)**

El v8 lo presenta como "abrir otro depósito en paralelo (pestaña)" = B4 (paralelismo de misiones), fuera del backend de C1. **Degradar:** por ahora el botón abre un nuevo `openDepos({})` vacío reemplazando el actual SOLO si no hay misión corriendo; si la hay, toast "Termina o cierra la misión actual primero". El verdadero paralelismo multi-pestaña queda para B4. Documentar.

- [ ] **Step 4: Verificar en navegador**

Verificar: con misión scheduled activa, cerrar el modal muestra pill; reabrir continúa; Abortar funciona; Pausar oculto donde no hay soporte real; "Otro depósito" respeta la guardia.

- [ ] **Step 5: Commit**

```bash
git add static/depos.js
git commit -m "feat(c1): run controls (pause donde hay soporte, abort, pill) + Otro depósito stub (B4 degradado, honesto)"
```

---

## Fase 4 — Suplencia controlada + cierre

### Task 11: Flag de suplencia en `openDepositModal()` (app.js) + paridad

**Files:**
- Modify: `static/app.js` (`openDepositModal`, `app.js:3712`)

- [ ] **Step 1: Branch bajo flag**

En `openDepositModal(accountId, opts)` (`app.js:3712`), al inicio:
```js
if (localStorage.getItem('deposV8') === '1' && window.openDepos) {
  const ids = opts && opts.ids ? opts.ids : (accountId != null ? [accountId] : []);
  return window.openDepos({ ids });
}
// …drawer viejo intacto debajo…
```
El drawer viejo queda 100% funcional cuando el flag está apagado. Activación: `localStorage.deposV8='1'` (Robert/SA lo prende para probar; default apagado = operación intacta).

- [ ] **Step 2: Verificar paridad funcional mínima (navegador, flag ON)**

Con `localStorage.deposV8='1'`, desde el flujo REAL (seleccionar cuentas en la tabla → botón Depositar): confirmar que abre el v8, y que los 3 modos lanzan y muestran progreso/resultado real:
- 1 cuenta, $100 → single aprueba y se ve el viaje + movimiento + balance fresco.
- 1 cuenta, reps 3 → programado corre y rehidrata.
- 2+ cuentas → multi corre y registra matches.
Checklist de paridad vs drawer viejo: lanzar los 3 flujos ✓, ver progreso ✓, ver resultado real ✓, feed/movimientos ✓, copiar combos/pipes ✓, sin tripas al operador ✓, sin romper con flag OFF ✓.

- [ ] **Step 3: Verificar flag OFF = operación intacta**

`localStorage.removeItem('deposV8')`, recargar → abrir depósito → abre el drawer viejo, todo funciona como antes (cero regresión visible).

- [ ] **Step 4: Commit**

```bash
git add static/app.js
git commit -m "feat(c1): suplencia controlada — openDepositModal branch a v8 bajo flag deposV8 (viejo = fallback, cero regresión)"
```

---

### Task 12: Suite de regresión + review adversarial

**Files:** (sin cambios de producto; solo verificación)

- [ ] **Step 1: Suite JS pura**

Run: `node --test static/depos_logic.test.js`
Expected: PASS (todos los tests de Tasks 1–3).

- [ ] **Step 2: Suite backend (cero regresión — C1 no toca backend)**

Run: `python -m pytest -q` (desde el repo)
Expected: misma cuenta verde que antes de C1 (C1 es frontend; no debe alterar tests backend). Si algún test toca `static/`, revisar.

- [ ] **Step 3: Review adversarial**

Despachar 1+ agentes `feature-dev:code-reviewer` sobre el diff de `static/depos*.{js,css}` + el branch de `app.js`. Foco: fugas de tripas al operador (L3), masking accidental de combos/pipes (L2 — debe estar CRUDO), cualquier camino que rompa el drawer viejo con flag OFF, leaks de EventSource/AbortController, y manejo de `CancelledError`. Aplicar lo accionable de alta confianza; descartar nits.

- [ ] **Step 4: Commit (si el review produjo fixes)**

```bash
git add -A
git commit -m "fix(c1): hardening post-review adversarial (fugas/leaks/regresión)"
```

---

### Task 13: Docs/bitácora

**Files:**
- Modify: `docs/SSE_EVENTS.md`, `MAP.md` (sección manual si aplica), `NEXT-SESSION.md`

- [ ] **Step 1: Documentar eventos emitidos-sin-documentar que C1 consume**

En `docs/SSE_EVENTS.md` agregar `account_refreshed {email,balance_real,balance_total,who}` y `scheduled_retry {sched_id,iter,total,attempt,max,code,reason}` (ambos ya se emiten; C1 los consume). Anotar que las **fases del matchmaker viajan por el stream privado del POST** (B3/bus no es requisito de C1).

- [ ] **Step 2: Bitácora (invocar skill `botmex-bitacora`)**

Reflejar en `docs/`: el módulo v8 nuevo (`depos.js/css/logic`), el flag `deposV8`, qué quedó degradado (balance-before, badge A+, pause vivo, paralelismo B4) y por qué. Actualizar `NEXT-SESSION.md`: C1 hecho tras flag/paridad; pendientes B2 (badge), B3 (pause+fases por bus), B4 (paralelismo), retiro del drawer viejo.

- [ ] **Step 3: Commit**

```bash
git add docs/ MAP.md NEXT-SESSION.md
git commit -m "docs(c1): SSE_EVENTS (account_refreshed/scheduled_retry) + bitácora módulo v8 + degradaciones"
```

---

## Notas de ejecución (no son tasks)

- **Deploy a KVM4 = AMARILLO** (stack vivo). No desplegar sin luz verde de Robert. La suplencia por flag permite mergear/deployar con `deposV8` OFF (operación intacta) y prender el flag solo para probar.
- **Merge a `main` = AMARILLO.** Cierre vía `superpowers:finishing-a-development-branch`.
- **Juicio cualitativo (¿se ve/siente como el v8?) = AMARILLO** → handoff a Robert tras la verificación en navegador; es su llamada, no se declara solo.
- **Firmas de endpoints de cuentas** (`pass-map`/`combos`/`details`/`cap-status`): verificar la real al ejecutar Task 6 (Grep en `app.py`); el plan asume los nombres vistos en el mapeo.
- **Ositos-reacción** (slide-in al resultado): NO bloqueante, fuera de C1 (reserva). Solo se usa el avatar neutro del header.

## Self-Review (hecho)

- **Cobertura del contrato v8:** header+greetings (T5) · cuentas/tarjetas/cap (T6) · monto/reps/modo (T1,T5) · journey 5 escenas (T4,T7) · balance before/after degradado (T7) · movimientos (T7) · 3 modos (T7,T8,T9) · run controls/pill (T10) · suplencia (T11). ✓
- **Degradaciones nombradas:** balance-before (T7), badge A+ (T7), pause vivo (T10), paralelismo B4 (T10), fases multi por bus B3 (innecesario, T9/T13). ✓
- **Consistencia de tipos:** `_consumeStream(resp,onEvent)` (T7) reusado por T9; `DeposLogic.*` firmas fijas en T1–T3 y consumidas igual en T5–T9; `setScene`/`movRow` definidos en T7, reusados T8/T9. ✓
- **TDD donde hay lógica** (T1–T3, node --test) + **verificación en navegador** para todo lo visual/cableado. ✓
