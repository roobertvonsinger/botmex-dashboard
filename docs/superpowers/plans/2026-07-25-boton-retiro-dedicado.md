# Botón de Retiro Dedicado + Panel de Monto en Col 3 — Implementation Plan

> **Para ejecutar con `/Smartexe`** sobre este plan. Pasos con checkbox `- [ ]`.
> Spec de origen: `docs/superpowers/specs/2026-07-25-boton-retiro-dedicado-design.md` (leer COMPLETO — es el contrato).
> **Revisión v2 (2026-07-25):** el panel de monto NO es popup flotante — vive en col 3 (`.pat-col-stage#patStageSlot`), que en reposo está vacía. Llena el espacio desperdiciado.

**Goal:** Migrar el botón de retiro de su ubicación escondida (bloque anidado en `.pat-col-ident`) a un botón dedicado visible en `.pat-actions` (derecha de Depositar), gris/disabled si saldo < $100, que al click dispara el retiro con el monto del input que vive en la col 3 (zona de feedback en vivo, antes vacía en reposo).

**Architecture:** Frontend puro. Botón nuevo en la barra de acciones dispara directo (sin popup). El panel de monto + estado 2-fases vive en col 3 como `#wdStage`, coexistiendo con `#depStage` (animación de depósito) vía CSS `:has()` puro — depósito tiene prioridad visual. La lógica de polling/status/alerts de retiro se conserva intacta — solo cambian los selectores del `wrap` (de `.pat-wd` a `[data-wd-stage]`). Backend sin cambios.

**Tech Stack:** JS vanilla (IIFE en `pantalla.js`, sin `module.exports` — los tests de lógica pura viven en `pantalla_logic.test.js` que requiere `pantalla_logic.js` separado), CSS con variables `oklch`, deploy Docker a KVM4.

## Global Constraints (verbatim del spec + verificación de anclajes)

- **SA-only:** el botón y el panel no se renderizan para `role !== 'superadmin'` (memoria `feedback_deshabilitar_invisible_no_redirect`).
- **Gris/disabled si `balance_real < 100`** (tooltip "Saldo < $100").
- **Panel en col 3, NO popup flotante:** `#wdStage` vive dentro de `.pat-col-stage` (junto a `#patStageSlot`), visible en reposo para SA. Llena el espacio que antes quedaba vacío.
- **Coexistencia `#wdStage` ↔ `#depStage` vía CSS `:has()`:** `#patStageSlot:has(#depStage:not([hidden]))` oculta `#wdStage`. **`depos.js` intacto** (no se toca).
- **Sin variable `--pat-bg-glass`:** no existe. El panel hereda el slot (flex child), glassmorphism de `.pantalla-sheet` ya envuelve todo.
- **Variables CSS disponibles:** `--pat-gold` (L30), `--pat-edge` (L32), `--pat-edge-h` (L33), `--text`, `--text-dim`, `--font-mono`.
- **`money()`** (`pantalla.js:257,489,649`): `window.fmtMoney || (v => \`$${(v||0).toFixed(2)}\`)`. Disponible en scope de `renderPantallaHead`.
- **Reusa data-class `d-withdraw-fire`** en el botón de `.pat-actions` (el handler existe en L909, solo cambia el `wrap`).
- **Polling 60s fijo** (`WD_POLL_MS`, L562) — nunca menos, no alimentar rate-limit.
- **Backend NO se toca.** `depos.js` NO se toca. Bot Telegram (monorepo) NO se toca (`feedback_no_monorepo`).
- **Monto mínimo $100** (validación frontend, ya en handler L917).
- **2-fases, no "entregado"** con `status:6` (guardarrail bug#2, ya en `_withdrawStatusHtml` L493).
- **Tests de lógica pura:** `pantalla_logic.test.js` requiere `pantalla_logic.js` (archivo SEPARADO de `pantalla.js`, que es una IIFE sin exports). La función `_withdrawBtnState` se añade a `pantalla_logic.js` y se exporta, Y se referencia desde `pantalla.js` vía `window.PantallaLogic` (patrón existente, ver cabecera de `pantalla.js`: "Reusa SIEMPRE... `window.PantallaLogic`").

## File Structure

| Archivo | Responsabilidad | Cambio |
|---|---|---|
| `static/pantalla_logic.js` | Lógica pura testeable (Node `require`) | + `_withdrawBtnState(d, role)` + export. |
| `static/pantalla_logic.test.js` | Tests de lógica pura (Node `assert`) | + tests de `_withdrawBtnState`. |
| `static/pantalla.js` | Render de La Pantalla + handlers (IIFE) | + `renderPantallaWithdrawButton()` + `renderPantallaWithdrawStage()` + `#wdStage` en col 3 + adaptar `d-withdraw-fire`/`_fetchWithdrawStatus`. Eliminar `renderPantallaWithdraw`. Referencia `_withdrawBtnState` vía `window.PantallaLogic`. |
| `static/pantalla.css` | Estilos de La Pantalla | + `.pat-act-wd`, `.pat-wd-stage`, `.pat-wd-head/balance`, regla `:has()`. Reusa `.pat-wd-row/amt/line/alert` existentes. |

---

## ORQUESTACIÓN (ley `feedback_planes_orquestacion`)

### Modelos por subagente
- **Sonnet 5** (`claude-sonnet-5`) — Tasks 1-4: implementación JS+CSS (patrones ya establecidos, lógica clara). Default.
- **Haiku 4.5** (`claude-haiku-4-5-20251001`) — Task 5: deploy + smoke HTTP (md5) + smoke funcional + medición `getBoundingClientRect`. Mecánico. `[modelo: Haiku]`.
- **Opus** — NO requerido (no hay decisiones arquitectónicas difíciles; el diseño ya está cerrado en el spec).

### Goals medibles
- Task 1: `_withdrawBtnState` cubre 4 estados (render/no-render, disabled/activo, 3 tooltips) → tests GREEN (5+ tests nuevos).
- Task 5: botón "Retirar" visible en `.pat-actions` (screenshot), gris si < $100, `getBoundingClientRect` del panel en col 3 sin overflow vertical, retiro de $1 end-to-end con 3 guardarrails verificados.

### Loops con condición de salida
- **TDD RED→GREEN** (Task 1): test falla (función no existe) → implemento → test pasa. Salida: `node static/pantalla_logic.test.js` verde (imprime "OK pantalla_logic").
- **Deploy→verify→measure** (Task 5): md5 servido == repo (salida: coinciden) → `getBoundingClientRect` panel sin overflow vertical (salida: `bottom ≤ sheet.bottom`).

### Vigilancia anti-cuelgue
- **TDD:** al 2º fallo de un test → `superpowers:systematic-debugging` (root cause, no re-parchar).
- **Visual:** si a la 3ª medición `getBoundingClientRect` no cumple → PARAR, reportar número real vs esperado (no iterar en silencio).
- **Deploy:** si `docker exec ... import` falla 2× → leer `docker logs` antes de reintentar (memoria `feedback_verificar_deploy_proceso_vivo`).
- **Tope iteraciones visuales:** máx 3 ciclos de ajuste CSS medido; al 4º, parar y pedir screenshot a Robert.

---

## Task 1: TDD — función pura `_withdrawBtnState(d, role)` [modelo: Sonnet]

**Lógica testeable:** decide si el botón/panel se renderiza, si está disabled, y qué tooltip mostrar. Extraída del render para testear sin DOM.

**Files:**
- Modify: `static/pantalla_logic.js` (añadir función + export)
- Test: `static/pantalla_logic.test.js`

**Interfaces:**
- Produces: `function _withdrawBtnState(d, role): { render: boolean, disabled: boolean, tooltip: string }`
  - `d.balance_real` = número|string|null (saldo Real de la cuenta)
  - `d.last_withdrawal` = fila de `account_withdrawals` o null (para detectar retiro pendiente vía `_wdStatusFromRow`)
  - `role` = string ('superadmin' | 'user' | ...)
  - Devuelve `{ render, disabled, tooltip }`:
    - `role !== 'superadmin'` → `{ render: false, disabled: true, tooltip: '' }`
    - `balance_real < 100` → `{ render: true, disabled: true, tooltip: 'Saldo < $100' }`
    - retiro pendiente (last_withdrawal no terminal) → `{ render: true, disabled: false, tooltip: 'Retiro en curso…' }`
    - else → `{ render: true, disabled: false, tooltip: 'Retirar' }`
  - **NOTA sobre `_wdStatusFromRow`:** esta función vive en `pantalla.js` (IIFE, no exportable). Para testear `_withdrawBtnState` en aislamiento, la lógica de "pendiente" se replica como helper local del test (no se importa `pantalla.js`). En `pantalla_logic.js`, `_withdrawBtnState` toma `d` con un campo precomputado `d._wd_pending` (boolean) que el render de `pantalla.js` le inyecta tras llamar `_wdStatusFromRow`. Esto desacopla la lógica pura del DOM-dependent.

**Interfaces (refinada):**
- Produces: `function _withdrawBtnState(d, role)` donde `d = { balance_real, _wd_pending }` (el render de `pantalla.js` calcula `_wd_pending` vía `_wdStatusFromRow` antes de llamarla).
  - `role !== 'superadmin'` → `{ render: false, disabled: true, tooltip: '' }`
  - `balance_real < 100` → `{ render: true, disabled: true, tooltip: 'Saldo < $100' }`
  - `_wd_pending === true` → `{ render: true, disabled: false, tooltip: 'Retiro en curso…' }`
  - else → `{ render: true, disabled: false, tooltip: 'Retirar' }`

- [ ] **Step 1: Escribir tests que fallan**

Añadir al final de `static/pantalla_logic.test.js` (tras la línea `console.log('OK pantalla_logic');` NO — antes, para que el OK final cubra todo):

```js
// ── _withdrawBtnState: estado del botón/panel de retiro dedicado (lógica pura) ──
const { _withdrawBtnState } = P;
const _acc = (balance, pending) => ({ balance_real: balance, _wd_pending: !!pending });

assert.strictEqual(_withdrawBtnState(_acc(500, false), 'user').render, false, 'no-SA no renderiza');
assert.strictEqual(_withdrawBtnState(_acc(500, false), 'user').disabled, true);

assert.strictEqual(_withdrawBtnState(_acc(500, false), 'superadmin').render, true, 'SA saldo ok renderiza');
assert.strictEqual(_withdrawBtnState(_acc(500, false), 'superadmin').disabled, false);
assert.strictEqual(_withdrawBtnState(_acc(500, false), 'superadmin').tooltip, 'Retirar');

assert.strictEqual(_withdrawBtnState(_acc(99.99, false), 'superadmin').disabled, true, 'saldo<100 disabled');
assert.strictEqual(_withdrawBtnState(_acc(99.99, false), 'superadmin').tooltip, 'Saldo < $100');
assert.strictEqual(_withdrawBtnState(_acc(0, false), 'superadmin').tooltip, 'Saldo < $100');

assert.strictEqual(_withdrawBtnState(_acc(500, true), 'superadmin').disabled, false, 'pendiente no disabled (botón activo)');
assert.strictEqual(_withdrawBtnState(_acc(500, true), 'superadmin').tooltip, 'Retiro en curso…');

assert.strictEqual(_withdrawBtnState(_acc(500, false), 'superadmin').tooltip, 'Retirar', 'sin pendiente = Retirar');
```

- [ ] **Step 2: Correr tests para verificar que fallan**

Run: `node static/pantalla_logic.test.js`
Expected: FAIL — `_withdrawBtnState is not a function` o `Cannot destructure property '_withdrawBtnState' of 'P'` (la función no está exportada aún).

- [ ] **Step 3: Implementar `_withdrawBtnState` en `static/pantalla_logic.js`**

Añadir al final de `pantalla_logic.js` (antes del `module.exports` final, o añadiéndola al objeto exportado):

```js
// ── _withdrawBtnState: estado del botón/panel de retiro dedicado (lógica pura) ──
// d.balance_real = saldo Real; d._wd_pending = true si hay retiro no-terminal (lo calcula
// el render de pantalla.js vía _wdStatusFromRow antes de llamar esta función — desacopla
// la lógica pura del DOM-dependent).
function _withdrawBtnState(d, role) {
  if (role !== 'superadmin') return { render: false, disabled: true, tooltip: '' };
  const balance = parseFloat((d && d.balance_real) || 0) || 0;
  if (balance < 100) return { render: true, disabled: true, tooltip: 'Saldo < $100' };
  if (d && d._wd_pending) return { render: true, disabled: false, tooltip: 'Retiro en curso…' };
  return { render: true, disabled: false, tooltip: 'Retirar' };
}
```

Y añadir `_withdrawBtnState` al `module.exports` de `pantalla_logic.js` (junto a `splitTransactions`, `estadoFrom`, etc.).

- [ ] **Step 4: Correr tests para verificar que pasan**

Run: `node static/pantalla_logic.test.js`
Expected: PASS — imprime `OK pantalla_logic` (los 8 asserts nuevos + los existentes).

- [ ] **Step 5: Commit**

```bash
git add static/pantalla_logic.js static/pantalla_logic.test.js
git commit -m "feat(retiro): _withdrawBtnState — estado del botón dedicado (TDD)

Lógica pura testeable: render/disabled/tooltip según role, saldo y
retiro pendiente. Extraída del render para testear sin DOM. Vive en
pantalla_logic.js (exportable), no en pantalla.js (IIFE)."
```

---

## Task 2: Botón en `.pat-actions` + panel `#wdStage` en col 3 + eliminar bloque anidado [modelo: Sonnet]

**Files:**
- Modify: `static/pantalla.js` — L332 (eliminar llamada), L510-526 (eliminar función `renderPantallaWithdraw`), L337-340 (agregar botón), L323-336 (agregar `#wdStage` en col 3).

**Interfaces:**
- Consumes: `_withdrawBtnState(d, role)` vía `window.PantallaLogic` (Task 1), `window.state.user`, `g()` (escaper), `d.id`, `d.email`, `d.balance_real`, `d.last_withdrawal`, `money()`, `_wdStatusFromRow`, `_withdrawStatusHtml`, `WD_TERMINAL`.
- Produces: `renderPantallaWithdrawButton(d)` — string HTML del botón. `renderPantallaWithdrawStage(d)` — string HTML del panel en col 3.

- [ ] **Step 1: Escribir `renderPantallaWithdrawButton(d)` en `pantalla.js`**

Reemplazar la función `renderPantallaWithdraw(d)` (L510-526) completa por DOS funciones. Insertar tras `WD_TERMINAL` (L465) o junto a las funciones de retiro existentes:

```js
// Botón de retiro dedicado en .pat-actions (derecha de Depositar). Dispara directo
// con el monto del input de col 3 — no abre popup. Gris/disabled si saldo < $100.
function renderPantallaWithdrawButton(d) {
  const L = window.PantallaLogic || {};
  const st_ = L._withdrawBtnState ? L._withdrawBtnState(d, ((window.state || {}).user || {}).role)
    : { render: false, disabled: true, tooltip: '' };
  // el render de pantalla.js calcula _wd_pending aquí mismo (desacopla de la lógica pura):
  const st = _wdStatusFromRow(d && d.last_withdrawal);
  d && (d._wd_pending = !!(st && !WD_TERMINAL.has(st.status)));
  const s2 = L._withdrawBtnState ? L._withdrawBtnState(d, ((window.state || {}).user || {}).role) : st_;
  if (!s2.render) return '';
  const g = window.esc || (s => s);
  return `<button type="button" class="pat-act pat-act-wd d-withdraw-fire" data-acc-id="${g(d.id)}"${s2.disabled ? ' disabled' : ''} title="${g(s2.tooltip)}"><i class="ph-duotone ph-bank"></i><span>Retirar</span></button>`;
}
```

- [ ] **Step 2: Escribir `renderPantallaWithdrawStage(d)` (panel en col 3)**

Junto a `renderPantallaWithdrawButton`:

```js
// Panel de monto + estado 2-fases en col 3 (.pat-col-stage). Visible en reposo para SA
// (llena el espacio que antes quedaba vacío). Si hay misión de depósito (#depStage visible),
// CSS :has() lo oculta — depos.js intacto.
function renderPantallaWithdrawStage(d) {
  const L = window.PantallaLogic || {};
  const role = ((window.state || {}).user || {}).role;
  const st = _wdStatusFromRow(d && d.last_withdrawal);
  d && (d._wd_pending = !!(st && !WD_TERMINAL.has(st.status)));
  const s2 = L._withdrawBtnState ? L._withdrawBtnState(d, role) : { render: false, disabled: true, tooltip: '' };
  if (!s2.render) return '';
  const g = window.esc || (s => s);
  const money = window.fmtMoney || (v => `$${(v || 0).toFixed(2)}`);
  const statusHtml = st ? _withdrawStatusHtml(st) : '';
  const inputDisabled = s2.disabled || (d && d._wd_pending) ? ' disabled' : '';
  return `<div class="pat-wd-stage" data-wd-stage>
    <span class="pat-wd-head"><span class="pat-sv-emo">🏧</span> Retirar — <span class="pat-wd-email">${g(d.email || '')}</span></span>
    <div class="pat-wd-balance">Saldo Real: <b class="pat-wd-balance-v">${money(d.balance_real || 0)}</b></div>
    <input class="pat-input pat-wd-amount" type="number" min="100" step="0.01" placeholder="monto (min $100)" data-wd-amount${inputDisabled}>
    <div class="pat-form-err" data-wd-err hidden></div>
    <div class="pat-wd-status">${statusHtml}</div>
  </div>`;
}
```

- [ ] **Step 3: Agregar el botón en `.pat-actions` (L337-340)**

En `renderPantallaHead`, reemplazar el cierre de `.pat-actions` (L337-340):

```js
      <div class="pat-actions">
        <button type="button" class="pat-act det-mark" data-mark-email="${g(email)}" title="Fijar"><i class="ph-bold ph-push-pin"></i></button>
        <button type="button" class="pat-act pat-act-dep d-deposit-btn" data-acc-id="${g(d.id)}" title="Depositar"><i class="ph-duotone ph-credit-card"></i><span>Depositar</span></button>
        ${renderPantallaWithdrawButton(d)}
      </div>`;
```

- [ ] **Step 4: Agregar `#wdStage` en col 3 (L335) + eliminar bloque anidado (L332)**

En `renderPantallaHead`, reemplazar el bloque `.pat-columns` (L323-336):

```js
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
        <div class="pat-col-stage">
          ${renderPantallaWithdrawStage(d)}
          <div id="patStageSlot"></div>
        </div>
      </div>
```

(Se eliminó la línea `${renderPantallaWithdraw(d)}` de `.pat-col-ident`, y `#patStageSlot` ahora convive con `renderPantallaWithdrawStage(d)` dentro de `.pat-col-stage`.)

- [ ] **Step 5: Verificar que no quedan referencias al bloque viejo**

Run: `grep -n "renderPantallaWithdraw\b" static/pantalla.js` (sin `Button` ni `Stage`).
Expected: sin resultados (la función vieja fue eliminada en Step 1).

- [ ] **Step 6: Smoke de carga (sin deploy) — verificar sintaxis**

Run: `node -e "const fs=require('fs');const s=fs.readFileSync('static/pantalla.js','utf8');new Function(s);console.log('sintaxis OK')"`
Expected: `sintaxis OK` (la IIFE no se ejecuta sin DOM, pero `new Function` parsea sin error de sintaxis).

- [ ] **Step 7: Commit**

```bash
git add static/pantalla.js
git commit -m "feat(retiro): botón en .pat-actions + panel #wdStage en col 3

El retiro deja de vivir escondido en .pat-col-ident: botón visible junto
al de depósito + panel de monto en col 3 (llena el espacio vacío en
reposo). Coexistencia con #depStage vía CSS :has() (depos.js intacto)."
```

---

## Task 3: Adaptar handler `d-withdraw-fire` + `_fetchWithdrawStatus` al panel `[data-wd-stage]` [modelo: Sonnet]

**Files:**
- Modify: `static/pantalla.js` L909-950 (handler fire), L533-559 (`_fetchWithdrawStatus`).

**Interfaces:**
- Consumes: `[data-wd-stage]` (panel del Task 2), `cache.last_withdrawal`, `transaction_id`.
- Cambio: `wrap` antes era `.pat-wd[data-acc]`, ahora es `[data-wd-stage]`.

- [ ] **Step 1: Adaptar handler `d-withdraw-fire` (L909-950)**

El handler actual hace `const wrap = wdFire.closest('.pat-wd')`. Cambiar para resolver el panel de col 3. Localizar (L909-916 aprox.):

```js
    const wdFire = e.target.closest('.d-withdraw-fire');
    if (wdFire) {
      e.preventDefault();
      const wrap = wdFire.closest('.pat-wd');
      const accId = wrap ? parseInt(wrap.dataset.acc) : _currentId;
      const input = wrap && wrap.querySelector('.pat-wd-amount');
```

Reemplazar por:

```js
    const wdFire = e.target.closest('.d-withdraw-fire');
    if (wdFire) {
      e.preventDefault();
      const wrap = document.querySelector('[data-wd-stage]');
      const accId = parseInt(wdFire.dataset.accId) || _currentId;
      const input = wrap && wrap.querySelector('[data-wd-amount]');
```

El resto del handler (L917-950) se conserva: validación monto ≥ 100, `wdFire.disabled = true`, `input.disabled = true`, `statusEl.innerHTML`, `fetch POST /api/accounts/${accId}/withdraw`, actualización de `cache.last_withdrawal`, `_renderDetailView(cache, false)` (el re-render repuebla el panel con estado pendiente), `toast`, `_startWithdrawPoll`.
- **Nota sobre `statusEl`:** si el handler actual lo resolvía como `wrap.querySelector('.pat-wd-status')`, el selector sigue válido (`[data-wd-stage]` contiene `.pat-wd-status`). Verificar tras el cambio.

- [ ] **Step 2: Eliminar la lógica de "re-abrir popup" (ya no aplica)**

El plan anterior (popup flotante) añadía `_openWithdrawPopup(accId, cache)` tras el `_renderDetailView`. **NO aplica aquí** — el panel `#wdStage` vive en el template, el re-render del detalle lo repuebla con estado fresco (input disabled + status 2-fases). Si el handler actual (L932-942) actualiza `cache.last_withdrawal` y llama `_renderDetailView(cache, false)`, eso ya repuebla el panel correctamente. **No añadir nada nuevo.** Solo verificar que `_renderDetailView` tras el disparo deja el panel visible (no lo oculta).

- [ ] **Step 3: Adaptar `_fetchWithdrawStatus` (L533-559)**

Localizar la resolución de `wrap` (L534 aprox.):

```js
  async function _fetchWithdrawStatus(accId, txId) {
    const wrap = document.querySelector(`.pat-wd[data-acc="${accId}"]`);
```

Reemplazar por:

```js
  async function _fetchWithdrawStatus(accId, txId) {
    const wrap = document.querySelector('[data-wd-stage]');
```

El resto (L535-558) se conserva: `statusEl`, `st`, toggle `alert`/`pending`, `done`, rehabilitar `input`/`btn`, `_stopWithdrawPoll`, actualizar `cache.last_withdrawal`. Verificar que `input`/`btn` se resuelven con los nuevos selectores (`[data-wd-amount]` / `.d-withdraw-fire`) si el handler los usa.

- [ ] **Step 4: Verificar consistencia de selectores**

Run: `grep -n "\.pat-wd\b\|\[data-acc=" static/pantalla.js | grep -v "pat-wd-" | grep -v "pat-wd_stage\|data-wd-stage"`
Expected: sin referencias a `.pat-wd[data-acc]` (todas migradas a `[data-wd-stage]`). Las clases `.pat-wd-row/.pat-wd-amt/.pat-wd-line/.pat-wd-alert` (status HTML) se conservan.

- [ ] **Step 5: Smoke de carga**

Run: `node -e "const fs=require('fs');const s=fs.readFileSync('static/pantalla.js','utf8');new Function(s);console.log('sintaxis OK')"`
Expected: `sintaxis OK`.

- [ ] **Step 6: Commit**

```bash
git add static/pantalla.js
git commit -m "fix(retiro): handler fire + polling operan sobre el panel [data-wd-stage]

Migración de selectores: wrap ahora es [data-wd-stage] (panel en col 3),
no .pat-wd. Sin lógica de re-abrir popup — el panel ya está visible y el
re-render del detalle lo repuebla con estado fresco."
```

---

## Task 4: CSS — `.pat-act-wd` + `.pat-wd-stage` + regla `:has()` [modelo: Sonnet]

**Files:**
- Modify: `static/pantalla.css` — tras `.pat-act-dep:hover` (L426) para el botón; tras `.pat-curp-pop[hidden]` (L552) para el panel.

**Interfaces:**
- Consumes: `--pat-gold`, `--pat-edge`, `--text`, `--text-dim`, `--font-mono`, patrón `.pat-input` base.
- Reusa: `.pat-wd-row`, `.pat-wd-amt`, `.pat-wd-line`, `.pat-wd-alert` (L841-851, ya existen — los genera `_withdrawStatusHtml`).

- [ ] **Step 1: Añadir `.pat-act-wd` tras `.pat-act-dep:hover` (L426)**

```css
.pat-act-wd {
  color: #08090c; background: var(--pat-gold); border-color: transparent;
  box-shadow: 0 0 12px -6px var(--pat-gold), 0 1px 2px oklch(0 0 0 / 0.25);
}
.pat-act-wd:hover:not(:disabled) { filter: brightness(1.08); }
.pat-act-wd:disabled { opacity: .4; cursor: not-allowed; background: var(--pat-edge); color: var(--text-dim); box-shadow: none; }
.pat-act-wd:disabled:hover { transform: none; filter: none; }
```

- [ ] **Step 2: Añadir `.pat-wd-stage` y sub-reglas tras `.pat-curp-pop[hidden]` (L552)**

```css
/* Panel de retiro en col 3 — llena el espacio vacío en reposo (SA). Glassmorphism
   lo envuelve .pantalla-sheet; aquí solo estructura + tipografía. */
.pat-wd-stage {
  display: flex; flex-direction: column; gap: 7px;
  padding: 14px 4px 4px 0;
  color: var(--text);
}
/* Coexistencia: si hay misión de depósito activa (#depStage visible en #patStageSlot),
   oculta el panel de retiro. depos.js intacto — la prioridad visual la resuelve el CSS. */
.pat-col-stage:has(#depStage:not([hidden])) .pat-wd-stage { display: none; }
.pat-wd-head { font-size: 12px; font-weight: 600; display: flex; gap: 5px; align-items: center; }
.pat-wd-email { color: var(--text-dim); font-weight: 400; }
.pat-wd-balance { font-size: 10.5px; color: var(--text-dim); }
.pat-wd-balance-v, .pat-wd-balance b { color: var(--pat-gold); font-family: var(--font-mono); }
.pat-wd-stage .pat-input { width: 100%; }
.pat-wd-status { margin-top: 4px; }
.pat-wd-status:empty { display: none; }
```

- [ ] **Step 3: Verificar que no hay colisiones**

Run: `grep -n "^\.pat-wd-stage\|^\.pat-act-wd" static/pantalla.css`
Expected: 1 `.pat-act-wd` + 1 `.pat-act-wd:hover` + 1 `.pat-act-wd:disabled` + 1 `.pat-act-wd:disabled:hover` + 1 `.pat-wd-stage` + 1 `.pat-col-stage:has(...) .pat-wd-stage`.

- [ ] **Step 4: Commit**

```bash
git add static/pantalla.css
git commit -m "style(retiro): .pat-act-wd botón dorado + .pat-wd-stage panel en col 3

Botón mismo lenguaje que .pat-act-dep (dorado, glow), gris si disabled.
Panel en col 3 llena el slot (flex child), coexistencia con #depStage vía
CSS :has() — depos.js intacto."
```

---

## Task 5: Deploy + smoke HTTP + funcional + validación visual [modelo: Haiku]

**Files:**
- Sin cambios de código (verificación + deploy).

**Interfaces:**
- Consumes: todos los tasks anteriores.

- [ ] **Step 1: Deploy a KVM4**

```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
scp -i "$KEY" static/pantalla.js static/pantalla.css static/pantalla_logic.js $HOST:/docker/betmexico/code/web/static/
ssh -i "$KEY" $HOST 'docker restart betmexico-web'
```

- [ ] **Step 2: Smoke HTTP — md5 servido == repo (memoria `feedback_verify_http_response_after_deploy`)**

```bash
# md5 local
md5sum static/pantalla.js static/pantalla.css static/pantalla_logic.js
# md5 prod (vía Traefik, el puerto 8080 no está publicado)
curl -s https://botmexico.com.mx/static/pantalla.js | md5sum
curl -s https://botmexico.com.mx/static/pantalla.css | md5sum
curl -s https://botmexico.com.mx/static/pantalla_logic.js | md5sum
# confirmar proceso vivo
ssh -i "$KEY" $HOST 'docker inspect -f "{{.State.StartedAt}}" betmexico-web'
```
Expected: md5 local == md5 prod para los 3 archivos. `StartedAt` > mtime del deploy.

- [ ] **Step 3: Verificar que el botón + panel aparecen en el JS servido**

```bash
curl -s https://botmexico.com.mx/static/pantalla.js | grep -c "pat-act-wd\|renderPantallaWithdrawStage\|data-wd-stage"
curl -s https://botmexico.com.mx/static/pantalla.js | grep -c "renderPantallaWithdraw\b"  # debe dar 0 (eliminado)
```
Expected: primero ≥ 3 (botón + panel + selector); segundo = 0 (la función vieja no existe).

- [ ] **Step 4: Validación visual (screenshot anotado por Robert)**

Pedir a Robert screenshot de La Pantalla de una cuenta con saldo ≥ $100 (ej. `msaidrzz`) logueado como SA. Verificar:
- Botón "Retirar" visible a la derecha de "Depositar" en `.pat-actions`.
- Panel `#wdStage` visible en col 3 (zona derecha) con saldo Real + input de monto + (vacío si sin retiro).
- Click en "Retirar" con input vacío → muestra error "monto mínimo $100" (no dispara).
- Medir `getBoundingClientRect` del panel en consola del navegador:
  ```js
  const pop = document.querySelector('[data-wd-stage]'); const r = pop.getBoundingClientRect();
  const sheet = document.querySelector('.pantalla-sheet').getBoundingClientRect();
  console.log('stage.bottom', r.bottom, 'sheet.bottom', sheet.bottom, 'overflow', r.bottom - sheet.bottom);
  ```
  Expected: `overflow ≤ 0` (panel no rebasa la sheet hacia abajo).

- [ ] **Step 5: Verificar gris si saldo < $100**

Abrir La Pantalla de una cuenta con saldo < $100 (o pedir a Robert cual cumple). Verificar:
- Botón "Retirar" renderizado con `disabled` + estilo gris.
- Panel `#wdStage` con input disabled (gris).
- Click no dispara.
- Tooltip "Saldo < $100" al hover del botón.

- [ ] **Step 6: Smoke funcional — retiro de $1 en cuenta de prueba**

> **NO $100.** Usar monto $1 para validar el flujo end-to-end sin riesgo grande (decisión del spec §9). Coordinar con Robert para elegir cuenta de prueba.

1. Abrir La Pantalla de la cuenta de prueba (SA, saldo ≥ $1).
2. Escribir `1` en el input de col 3 → click "Retirar" en `.pat-actions`.
3. Verificar en col 3: input + botón se disablean → "Disparando…" → polling → estado terminal.
4. Verificar los 3 guardarrails:
   - `gateway == 2` (SPEI, no tarjeta) — si `gateway:1` → alerta crítica bug#3.
   - `lastAccountDigits` coincide con `accountId` — si difieren → alerta bug#1.
   - Copy 2-fases ("BetMexico procesó… Confirma en tu banco"), NO "entregado" — bug#2.
5. Verificar bitácora en BD:
   ```bash
   ssh -i "$KEY" $HOST 'docker exec betmexico-web python3 -c "import sys;sys.path.insert(0,\"/app/web\");sys.path.insert(0,\"/app\");import app;conn=app.db();conn.row_factory=app.sqlite3.Row;r=conn.execute(\"SELECT * FROM account_withdrawals ORDER BY created_at DESC LIMIT 1\").fetchone();print(dict(r) if r else None)"'
   ```
   Expected: 1 fila con `status_api` terminal + `last_modified_utc` poblado.

- [ ] **Step 7: Commit final + merge a main (memoria `feedback_merge_en_checkpoints`)**

```bash
git log --oneline -6  # confirmar los commits de Tasks 1-4
git push origin feat/boton-retiro-automatico
git fetch origin main
git merge-base --is-ancestor origin/main HEAD && \
  git push origin feat/boton-retiro-automatico:main
```
Expected: fast-forward limpio a main.

- [ ] **Step 8: Reporte denso**

Reportar a Robert:
- Sistema: web ✓/✗ · bot ✓/⛔ · health ✓/✗.
- Botón: visible ✓/✗ · gris si < $100 ✓/✗.
- Panel col 3: visible ✓/✗ · llena el slot sin overflow ✓/✗.
- Smoke $1: disparado ✓/✗ · 3 guardarrails ✓/✗ · bitácora ✓/✗.
- Merge: main en `<hash>`.

---

## Self-Review del plan

**Cobertura del spec:**
- §1 Objetivo (botón dedicado + panel col 3) → Tasks 2-3. ✓
- §2.1 Botón en `.pat-actions` derecha de Depositar + ph-bank → Task 2 Step 3. ✓
- §2.1 Gris si < $100 → Task 1 (`_withdrawBtnState`) + Task 4 (`.pat-act-wd:disabled`). ✓
- §2.1 No-SA no renderiza → Task 1 (`render:false`). ✓
- §2.2 Panel `#wdStage` en col 3 (NO popup) → Task 2 Step 4. ✓
- §2.2 Coexistencia `#wdStage`↔`#depStage` vía `:has()` → Task 4 Step 2. ✓
- §2.2 Header email + saldo + input + estado + alerts → Task 2 Step 2. ✓
- §4.3 Handler `d-withdraw-fire` dispara directo → Task 3 Step 1. ✓
- §4.4 Polling sobre `#wdStage` → Task 3 Step 3. ✓
- §4.5 Eliminar `renderPantallaWithdraw` → Task 2 Steps 1,4. ✓
- §5 CSS `.pat-act-wd` + `.pat-wd-stage` + `:has()` → Task 4. ✓
- §6 Estados del botón + col 3 → Task 1 (tabla de estados en tests) + Task 2. ✓
- §7 Flujo retiro → Tasks 2-3 + smoke Task 5. ✓
- §8 Guardarrails (backend, no tocar) → Global Constraints. ✓
- §9 Pruebas → Task 1 (TDD) + Task 5 (smoke HTTP, funcional, visual). ✓
- §10 No-go (clabes, watchdog, backend, depos.js, monorepo, multi-cuenta) → Global Constraints. ✓

**Placeholder scan:** sin TBD/TODO/"manejar errores apropiadamente". Cada step tiene código o comando real. ✓

**Consistencia de tipos/nombres:**
- `_withdrawBtnState(d, role)` — Task 1 (def en `pantalla_logic.js`) + Task 2 (consume vía `window.PantallaLogic`). ✓
- `d._wd_pending` — Task 1 (doc) + Task 2 (lo calcula el render antes de llamar `_withdrawBtnState`). ✓
- `renderPantallaWithdrawButton(d)` / `renderPantallaWithdrawStage(d)` — Task 2 def + uso en template. ✓
- `[data-wd-stage]` selector — Task 2 (panel) + Task 3 (handlers fire/poll). ✓
- `d-withdraw-fire` data-class — conservado del código existente, en el botón de `.pat-actions`. ✓
- `money()` — asumido existente (usado ya en `renderPantallaHead` L328 para balance). ✓
- `window.PantallaLogic` — patrón existente (cabecera de `pantalla.js` lo documenta). ✓

**Alcance:** un solo plan ejecutable (frontend puro, 5 tasks). No requiere partirse. ✓

**Riesgo identificado:** `_withdrawBtnState` vive en `pantalla_logic.js` (exportable) pero el render en `pantalla.js` (IIFE) necesita `_wdStatusFromRow` (que vive en `pantalla.js`) para calcular `d._wd_pending`. El plan resuelve esto: el render calcula `_wd_pending` antes de llamar `_withdrawBtnState`, desacoplando la lógica pura del DOM-dependent. Si `pantalla_logic.js` no expone `_withdrawBtnState` correctamente, Task 2 fallará — vigilancia: verificar el `module.exports` en Task 1 Step 3.
