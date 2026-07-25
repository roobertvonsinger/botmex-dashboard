# Botón de Retiro Dedicado + Popup de Monto — Implementation Plan

> **Para ejecutar con `/Smartexe`** sobre este plan. Pasos con checkbox `- [ ]`.
> Spec de origen: `docs/superpowers/specs/2026-07-25-boton-retiro-dedicado-design.md` (leer COMPLETO — es el contrato).

**Goal:** Migrar el botón de retiro de su ubicación escondida (bloque anidado en `.pat-col-ident`) a un botón dedicado visible en `.pat-actions` (derecha de Depositar), gris/disabled si saldo < $100, que al click abre un popup pidiendo monto → dispara retiro → feedback en vivo.

**Architecture:** Frontend puro. Botón nuevo en la barra de acciones + popup inline (patrón `hidden` toggle, igual que el popup de CURP existente) con input de monto + estado 2-fases. La lógica de polling/status/alerts de retiro se conserva intacta — solo cambian los selectores del `wrap` (de `.pat-wd` al popup). Backend sin cambios (endpoints `/withdraw` + `/withdraw/status` ya existen con guardarrails bug#1/#2/#3).

**Tech Stack:** JS vanilla (sin framework), CSS con variables `oklch`, pytest para tests de lógica pura en `pantalla_logic.test.js` (Node `assert`/`require`), deploy Docker a KVM4.

## Global Constraints (verbatim del spec + verificación)

- **SA-only:** el botón no se renderiza para `role !== 'superadmin'` (memoria `feedback_deshabilitar_invisible_no_redirect`).
- **Gris/disabled si `balance_real < 100`** (tooltip "Saldo < $100").
- **Patrón popup:** `<div class="pat-form pat-wd-pop" hidden>` con toggle de atributo `hidden` — **NO `<dialog>` nativo** (corrección del spec tras verificar anclajes: el popup de CURP L311-319 usa `hidden` toggle, no `showModal`; se reusa el patrón existente, `feedback_no_falsos_tradeoffs`).
- **Sin variable `--pat-bg-glass`:** no existe. Glassmorphism inline con `backdrop-filter: blur(16px)` (igual que `.pat-curp-pop` L549) + background multicapa `oklch` copiado de `.pantalla-sheet` L205-209.
- **Variables CSS disponibles:** `--pat-gold` (L30), `--pat-edge` (L32), `--pat-edge-h` (L33), `--text`, `--text-dim`, `--font-mono`.
- **Reusa data-class `d-withdraw-fire`** en el botón del popup (el handler existe en L909, solo cambia el `wrap`).
- **Polling 60s fijo** (`WD_POLL_MS`, L562) — nunca menos, no alimentar rate-limit (guardarrail concurrencia).
- **Backend NO se toca.** Bot Telegram (monorepo) NO se toca (`feedback_no_monorepo`).
- **Monto mínimo $100** (validación frontend, ya en handler L917).
- **2-fases, no "entregado"** con `status:6` (guardarrail bug#2, ya en `_withdrawStatusHtml` L493).

## File Structure

| Archivo | Responsabilidad | Cambio |
|---|---|---|
| `static/pantalla.js` | Render de La Pantalla + handlers | + función botón, + popup inline, + handler abrir, adaptar `d-withdraw-fire`/`_fetchWithdrawStatus`. Eliminar `renderPantallaWithdraw`. |
| `static/pantalla.css` | Estilos de La Pantalla | + `.pat-act-wd`, `.pat-wd-pop`, `.pat-wd-head/balance`. Reusa `.pat-wd-row/amt/line/alert` existentes. |
| `static/pantalla_logic.test.js` | Tests de lógica pura (Node assert) | + tests de `_withdrawBtnState(d, role)`. |

---

## ORQUESTACIÓN (ley `feedback_planes_orquestacion`)

### Modelos por subagente
- **Sonnet 5** (`claude-sonnet-5`) — Tasks 1-5: implementación JS+CSS (patrones ya establecidos, lógica clara). Default.
- **Haiku 4.5** (`claude-haiku-4-5-20251001`) — Task 6: deploy + smoke HTTP (md5) + smoke funcional + medición `getBoundingClientRect`. Mecánico. `[modelo: Haiku]`.
- **Opus** — NO requerido (no hay decisiones arquitectónicas difíciles; el diseño ya está cerrado en el spec).

### Goals medibles
- Task 1: `_withdrawBtnState` cubre 4 estados (render/no-render, disabled/activo, 3 tooltips) → tests GREEN.
- Task 6: botón "Retirar" visible en `.pat-actions` (screenshot), gris si < $100, `getBoundingClientRect` del popup sin overflow, retiro de $1 end-to-end con 3 guardarrails verificados.

### Loops con condición de salida
- **TDD RED→GREEN** (Task 1): test falla (función no existe) → implemento → test pasa. Salida: `pytest pantalla_logic.test.js` verde.
- **Deploy→verify→measure** (Task 6): md5 servido == repo (salida: coinciden) → `getBoundingClientRect` popup sin overflow vertical (salida: `bottom ≤ sheet.bottom`).

### Vigilancia anti-cuelgue
- **TDD:** al 2º fallo de un test → `superpowers:systematic-debugging` (root cause, no re-parchar).
- **Visual:** si a la 3ª medición `getBoundingClientRect` no cumple → PARAR, reportar número real vs esperado (no iterar en silencio).
- **Deploy:** si `docker exec ... import` falla 2× → leer `docker logs` antes de reintentar (memoria `feedback_verificar_deploy_proceso_vivo`).
- **Tope iteraciones visuales:** máx 3 ciclos de ajuste CSS medido; al 4º, parar y pedir screenshot a Robert.

---

## Task 1: TDD — función pura `_withdrawBtnState(d, role)` [modelo: Sonnet]

**Lógica testeable:** decide si el botón se renderiza, si está disabled, y qué tooltip mostrar. Extraída del render para testear sin DOM.

**Files:**
- Modify: `static/pantalla.js` (añadir función cerca de `WD_TERMINAL`, L465)
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

- [ ] **Step 1: Escribir tests que fallan**

Añadir al final de `static/pantalla_logic.test.js` (tras el último test, antes del cierre del módulo si lo hay):

```js
const { _withdrawBtnState, WD_TERMINAL } = require('./pantalla.js');

function _wdRow(status) {
  return status == null ? null : { status_api: status, gateway: null, last_modified_utc: null };
}

// Helper: cuenta con saldo y last_withdrawal opcional
function _acc(balance, lastWd) {
  return { balance_real: balance, last_withdrawal: lastWd };
}

test('no-SA: no renderiza botón', () => {
  const s = _withdrawBtnState(_acc(500, null), 'user');
  assert.strictEqual(s.render, false);
  assert.strictEqual(s.disabled, true);
});

test('SA saldo >= 100 sin retiro: botón activo, tooltip Retirar', () => {
  const s = _withdrawBtnState(_acc(500, null), 'superadmin');
  assert.strictEqual(s.render, true);
  assert.strictEqual(s.disabled, false);
  assert.strictEqual(s.tooltip, 'Retirar');
});

test('SA saldo < 100: botón gris/disabled, tooltip Saldo < $100', () => {
  assert.strictEqual(_withdrawBtnState(_acc(99.99, null), 'superadmin').disabled, true);
  assert.strictEqual(_withdrawBtnState(_acc(99.99, null), 'superadmin').tooltip, 'Saldo < $100');
  assert.strictEqual(_withdrawBtnState(_acc(0, null), 'superadmin').tooltip, 'Saldo < $100');
});

test('SA saldo >= 100 con retiro pendiente: tooltip Retiro en curso', () => {
  const s = _withdrawBtnState(_acc(500, _wdRow('pending')), 'superadmin');
  assert.strictEqual(s.disabled, false);
  assert.strictEqual(s.tooltip, 'Retiro en curso…');
});

test('SA saldo >= 100 con retiro terminal: tooltip Retirar (no en curso)', () => {
  const s = _withdrawBtnState(_acc(500, _wdRow('successful')), 'superadmin');
  assert.strictEqual(s.tooltip, 'Retirar');
});
```

- [ ] **Step 2: Correr tests para verificar que fallan**

Run: `node --test static/pantalla_logic.test.js` (o `pytest` si el repo lo orquesta; verificar cómo corren los tests `.test.js` existentes con `grep -rn "pantalla_logic" package.json conftest.py` primero).
Expected: FAIL — `_withdrawBtnState is not a function` (la función no existe aún).

- [ ] **Step 3: Implementar `_withdrawBtnState` en `static/pantalla.js`**

Insertar tras `WD_TERMINAL` (L465), antes de `_wdStatusFromRow` (L471):

```js
// Estado del botón de retiro dedicado (lógica pura testeable, sin DOM).
// Devuelve {render, disabled, tooltip} para que renderPantallaWithdrawButton
// solo arme el HTML; la decisión vive acá testeable.
function _withdrawBtnState(d, role) {
  if (role !== 'superadmin') return { render: false, disabled: true, tooltip: '' };
  const balance = parseFloat(d && d.balance_real || 0) || 0;
  if (balance < 100) return { render: true, disabled: true, tooltip: 'Saldo < $100' };
  const st = _wdStatusFromRow(d && d.last_withdrawal);
  const pending = !!st && !WD_TERMINAL.has(st.status);
  return { render: true, disabled: false, tooltip: pending ? 'Retiro en curso…' : 'Retirar' };
}
```

- [ ] **Step 4: Correr tests para verificar que pasan**

Run: mismo comando del Step 2.
Expected: PASS — 5 tests nuevos verdes.

- [ ] **Step 5: Commit**

```bash
git add static/pantalla.js static/pantalla_logic.test.js
git commit -m "feat(retiro): _withdrawBtnState — estado del botón dedicado (TDD)

Lógica pura testeable: render/disabled/tooltip según role, saldo y
retiro pendiente. Extraída del render para testear sin DOM."
```

---

## Task 2: Botón dedicado en `.pat-actions` + eliminar bloque anidado [modelo: Sonnet]

**Files:**
- Modify: `static/pantalla.js` L332 (eliminar llamada), L510-526 (eliminar función), L337-340 (agregar botón)

**Interfaces:**
- Consumes: `_withdrawBtnState(d, role)` (Task 1), `window.state.user`, `g()` (escaper), `d.id`.
- Produces: `renderPantallaWithdrawButton(d)` — devuelve string HTML del botón.

- [ ] **Step 1: Escribir `renderPantallaWithdrawButton(d)`**

Reemplazar la función `renderPantallaWithdraw(d)` (L510-526) completa por:

```js
function renderPantallaWithdrawButton(d) {
  const u = (window.state && state.user) || {};
  const st_ = _withdrawBtnState(d, u.role);
  if (!st_.render) return '';
  const g = window.esc || (s => s);
  const dis = st_.disabled ? ' disabled' : '';
  return `<button type="button" class="pat-act pat-act-wd d-withdraw-open" data-acc-id="${g(d.id)}" title="${g(st_.tooltip)}"${dis}><i class="ph-duotone ph-bank"></i><span>Retirar</span></button>`;
}
```

- [ ] **Step 2: Agregar el botón en `.pat-actions` (L339-340)**

En `renderPantallaHead`, reemplazar el cierre de `.pat-actions` (L337-340):

```js
      <div class="pat-actions">
        <button type="button" class="pat-act det-mark" data-mark-email="${g(email)}" title="Fijar"><i class="ph-bold ph-push-pin"></i></button>
        <button type="button" class="pat-act pat-act-dep d-deposit-btn" data-acc-id="${g(d.id)}" title="Depositar"><i class="ph-duotone ph-credit-card"></i><span>Depositar</span></button>
        ${renderPantallaWithdrawButton(d)}
      </div>`;
```

- [ ] **Step 3: Eliminar la llamada al bloque anidado (L332)**

Borrar la línea `${renderPantallaWithdraw(d)}` de `.pat-col-ident` (L332). Queda:

```js
          ${renderPantallaSaved(d)}
          ${renderPantallaClabes(d)}
        </div>
```

- [ ] **Step 4: Verificar que no quedan referencias al bloque viejo**

Run: `grep -n "renderPantallaWithdraw\b" static/pantalla.js` (sin `Button`).
Expected: sin resultados (la función vieja fue reemplazada por `renderPantallaWithdrawButton` en Step 1).

- [ ] **Step 5: Smoke de carga (sin deploy)**

Run: `node -e "const m=require('./static/pantalla.js')"` (o el mecanismo del repo; si `pantalla.js` no es módulo Node puro, saltar y validar en Task 6 con deploy).
Expected: sin errores de sintaxis.

- [ ] **Step 6: Commit**

```bash
git add static/pantalla.js
git commit -m "feat(retiro): botón dedicado en .pat-actions, elimina bloque anidado

El botón de retiro deja de vivir escondido en .pat-col-ident; ahora es
un botón visible junto al de depósito. Usa _withdrawBtnState para el
estado disabled/tooltip."
```

---

## Task 3: Popup inline `.pat-wd-pop` + handler abrir [modelo: Sonnet]

**Files:**
- Modify: `static/pantalla.js` — popup en `renderPantallaHead` (cerca de L340, tras `.pat-actions`), nueva función `_openWithdrawPopup`, handler `d-withdraw-open` en listener L788+.

**Interfaces:**
- Consumes: `_cacheGet(accId)`, `_currentId`, `money()` (app.js), `_wdStatusFromRow`, `_withdrawStatusHtml`, `_startWithdrawPoll`, `_currentId`.
- Produces: `<div class="pat-form pat-wd-pop" data-wd-pop hidden>` en el DOM de La Pantalla; `_openWithdrawPopup(accId, cache)`.

- [ ] **Step 1: Añadir el popup inline al template de `renderPantallaHead`**

Tras el cierre de `.pat-actions` (L340), dentro del template devuelto, añadir:

```js
      <div class="pat-form pat-wd-pop" data-wd-pop hidden>
        <span class="pat-wd-head"><span class="pat-sv-emo">🏧</span> Retirar — <span data-wd-email></span></span>
        <div class="pat-wd-balance">Saldo Real: <b data-wd-balance></b></div>
        <input class="pat-input pat-wd-amount" type="number" min="100" step="0.01" placeholder="monto (min $100)" data-wd-amount>
        <div class="pat-form-err" data-wd-err hidden></div>
        <div class="pat-wd-status"></div>
        <div class="pat-form-row">
          <button type="button" class="pat-btn pat-btn-ghost" data-wd-cancel>Cancelar</button>
          <button type="button" class="pat-btn pat-btn-save d-withdraw-fire" data-wd-fire>Retirar</button>
        </div>
      </div>`;
```

- [ ] **Step 2: Escribir `_openWithdrawPopup(accId, cache)`**

Insertar cerca de `_resumeWithdrawPollIfPending` (L573-580):

```js
function _openWithdrawPopup(accId, cache) {
  const pop = document.querySelector('[data-wd-pop]');
  if (!pop) return;
  const g = window.esc || (s => s);
  const emailEl = pop.querySelector('[data-wd-email]');
  const balEl = pop.querySelector('[data-wd-balance]');
  const amtEl = pop.querySelector('[data-wd-amount]');
  const errEl = pop.querySelector('[data-wd-err]');
  const statusEl = pop.querySelector('.pat-wd-status');
  if (emailEl && cache) emailEl.textContent = cache.email || '';
  if (balEl && cache) balEl.textContent = money(cache.balance_real || 0);
  if (amtEl) { amtEl.value = ''; amtEl.disabled = false; }
  if (errEl) errEl.hidden = true;
  if (statusEl) {
    const st = _wdStatusFromRow(cache && cache.last_withdrawal);
    statusEl.innerHTML = st ? _withdrawStatusHtml(st) : '';
    if (st && !WD_TERMINAL.has(st.status) && !_wdPolls[accId]) {
      _startWithdrawPoll(accId, cache.last_withdrawal.transaction_id);
    }
  }
  pop.hidden = false;
  if (amtEl) amtEl.focus();
}
```

- [ ] **Step 3: Escribir `_closeWithdrawPopup()`**

Junto a `_openWithdrawPopup`:

```js
function _closeWithdrawPopup() {
  const pop = document.querySelector('[data-wd-pop]');
  if (pop) pop.hidden = true;
}
```

- [ ] **Step 4: Añadir handler `d-withdraw-open` en el listener de `#pantalla`**

Tras el bloque `d-deposit-btn` (L803), antes de `det-mark`:

```js
    const wdOpen = e.target.closest('.d-withdraw-open');
    if (wdOpen && !wdOpen.disabled) {
      e.preventDefault();
      const accId = parseInt(wdOpen.dataset.accId) || _currentId;
      const cache = _cacheGet(accId);
      _openWithdrawPopup(accId, cache);
      return;
    }
    const wdCancel = e.target.closest('[data-wd-cancel]');
    if (wdCancel) {
      e.preventDefault();
      _closeWithdrawPopup();
      return;
    }
```

- [ ] **Step 5: Commit**

```bash
git add static/pantalla.js
git commit -m "feat(retiro): popup de monto .pat-wd-pop + handler abrir/cerrar

Popup inline con hidden toggle (patrón CURP). Pide monto escrito, muestra
saldo Real + estado 2-fases. Se abre con .d-withdraw-open, cierra con
Cancelar/ESC (listener exists)."
```

---

## Task 4: Adaptar handler `d-withdraw-fire` + `_fetchWithdrawStatus` al popup [modelo: Sonnet]

**Files:**
- Modify: `static/pantalla.js` L909-950 (handler fire), L533-559 (`_fetchWithdrawStatus`).

**Interfaces:**
- Consumes: `[data-wd-pop]` (popup del Task 3), `cache.last_withdrawal`, `transaction_id`.
- Cambio: `wrap` antes era `.pat-wd[data-acc]`, ahora es `[data-wd-pop]`.

- [ ] **Step 1: Adaptar handler `d-withdraw-fire` (L909-950)**

El handler actual hace `const wrap = wdFire.closest('.pat-wd')`. Cambiar para resolver el popup:

Localizar (L909-916):
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
      const wrap = document.querySelector('[data-wd-pop]');
      const accId = _currentId;
      const input = wrap && wrap.querySelector('[data-wd-amount]');
```

El resto del handler (L917-950) se conserva: validación monto ≥ 100, `wdFire.disabled = true`, `input.disabled = true`, `statusEl.innerHTML`, `fetch POST /api/accounts/${accId}/withdraw`, actualización de `cache.last_withdrawal`, `_renderDetailView(cache, false)` (NOTA: al re-renderizar el popup se resetea a `hidden` — ver Step 2), `toast`, `_startWithdrawPoll`.

- [ ] **Step 2: Evitar que el re-render cierre el popup tras disparar**

El handler actual llama `_renderDetailView(cache, false)` (L939) tras actualizar el cache. Eso re-monta el popup con `hidden` por default (lo cierra). Para que el usuario vea el estado "en proceso", tras el re-render re-abrir el popup:

Localizar (L932-942 aprox.):
```js
        const cache = _cacheGet(accId);
        if (cache) {
          cache.last_withdrawal = {
            transaction_id: data.transactionId, reference: data.reference, amount: data.amount,
            account_digits: data.accountDigits, institution_name: data.institutionName,
            status_api: null, gateway: null, last_modified_utc: null,
          };
          if (_currentId === accId) _renderDetailView(cache, false);
        }
```

Añadir tras el `_renderDetailView` (antes del toast):
```js
          _openWithdrawPopup(accId, cache);
```

- [ ] **Step 3: Adaptar `_fetchWithdrawStatus` (L533-559)**

Localizar la resolución de `wrap` (L534):
```js
  async function _fetchWithdrawStatus(accId, txId) {
    const wrap = document.querySelector(`.pat-wd[data-acc="${accId}"]`);
```

Reemplazar por:
```js
  async function _fetchWithdrawStatus(accId, txId) {
    const wrap = document.querySelector('[data-wd-pop]');
```

El resto (L535-558) se conserva: `statusEl`, `st`, toggle `alert`/`pending`, `done`, rehabilitar `input`/`btn`, `_stopWithdrawPoll`, actualizar `cache.last_withdrawal`.

- [ ] **Step 4: Verificar consistencia de selectores**

Run: `grep -n "\.pat-wd\b\|\[data-acc=" static/pantalla.js | grep -v "pat-wd-"`
Expected: sin referencias a `.pat-wd[data-acc]` (todas migradas a `[data-wd-pop]`).

- [ ] **Step 5: Commit**

```bash
git add static/pantalla.js
git commit -m "fix(retiro): handler fire + polling operan sobre el popup .pat-wd-pop

Migración de selectores: wrap ahora es [data-wd-pop] (no .pat-wd).
Tras disparar, re-abre el popup para mostrar estado en proceso en vez
de cerrarlo al re-renderizar."
```

---

## Task 5: CSS — `.pat-act-wd` + `.pat-wd-pop` [modelo: Sonnet]

**Files:**
- Modify: `static/pantalla.css` — tras `.pat-act-dep:hover` (L426) para el botón; tras `.pat-curp-pop[hidden]` (L552) para el popup.

**Interfaces:**
- Consumes: `--pat-gold`, `--pat-edge`, `--text`, `--text-dim`, `--font-mono`, patrón `.pat-form` base.
- Reusa: `.pat-wd-row`, `.pat-wd-amt`, `.pat-wd-line`, `.pat-wd-alert` (L841-851, ya existen).

- [ ] **Step 1: Añadir `.pat-act-wd` tras `.pat-act-dep:hover` (L426)**

```css
.pat-act-wd {
  color: #08090c; background: var(--pat-gold); border-color: transparent;
  box-shadow: 0 0 12px -6px var(--pat-gold), 0 1px 2px oklch(0 0 0 / 0.25);
}
.pat-act-wd:hover:not(:disabled) {
  filter: brightness(1.08);
}
.pat-act-wd:disabled {
  opacity: .4; cursor: not-allowed; background: var(--pat-edge); color: var(--text-dim);
  box-shadow: none;
}
.pat-act-wd:disabled:hover { transform: none; filter: none; }
```

- [ ] **Step 2: Añadir `.pat-wd-pop` y sub-reglas tras `.pat-curp-pop[hidden]` (L552)**

```css
/* Popup de retiro — variant de .pat-curp-pop, glassmorphism de La Pantalla */
.pat-wd-pop[hidden] { display: none; }
.pat-wd-pop {
  position: absolute; right: 18px; bottom: 58px; z-index: 7;
  min-width: 240px;
  display: flex; flex-direction: column; gap: 6px;
  padding: 14px 16px;
  border: 1px solid var(--pat-edge);
  border-radius: 12px;
  background: linear-gradient(oklch(0.04 0.015 160 / 0.34), oklch(0.12 0.015 160 / 0.66));
  backdrop-filter: blur(16px) saturate(1.2);
  -webkit-backdrop-filter: blur(16px) saturate(1.2);
  box-shadow: 0 8px 32px -8px oklch(0 0 0 / 0.5);
  color: var(--text);
}
.pat-wd-head { font-size: 12px; font-weight: 600; display: flex; gap: 5px; align-items: center; }
.pat-wd-balance { font-size: 10.5px; color: var(--text-dim); }
.pat-wd-balance b { color: var(--pat-gold); font-family: var(--font-mono); }
.pat-wd-pop .pat-input { width: 100%; }
.pat-wd-status { margin-top: 4px; }
.pat-wd-status:empty { display: none; }
```

- [ ] **Step 3: Verificar que no hay colisiones**

Run: `grep -n "^\.pat-wd-pop\|^\.pat-act-wd" static/pantalla.css`
Expected: 1 ocurrencia de `.pat-act-wd` y 1 de `.pat-wd-pop[hidden]` + 1 de `.pat-wd-pop {`.

- [ ] **Step 4: Commit**

```bash
git add static/pantalla.css
git commit -m "style(retiro): .pat-act-wd botón dorado + .pat-wd-pop popup glass

Botón mismo lenguaje que .pat-act-dep (dorado, glow), gris si disabled.
Popup glassmorphism (blur 16px) consistente con La Pantalla, anclado
sobre la barra de acciones."
```

---

## Task 6: Deploy + smoke HTTP + funcional + validación visual [modelo: Haiku]

**Files:**
- Sin cambios de código (verificación + deploy).

**Interfaces:**
- Consumes: todos los tasks anteriores.

- [ ] **Step 1: Deploy a KVM4**

```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"; HOST="root@100.77.154.31"
scp -i "$KEY" static/pantalla.js static/pantalla.css $HOST:/docker/betmexico/code/web/static/
ssh -i "$KEY" $HOST 'docker restart betmexico-web'
```

- [ ] **Step 2: Smoke HTTP — md5 servido == repo (memoria `feedback_verify_http_response_after_deploy`)**

```bash
# md5 local
md5sum static/pantalla.js static/pantalla.css
# md5 prod (vía Traefik, el puerto 8080 no está publicado)
curl -s https://botmexico.com.mx/static/pantalla.js | md5sum
curl -s https://botmexico.com.mx/static/pantalla.css | md5sum
# confirmar proceso vivo
ssh -i "$KEY" $HOST 'docker inspect -f "{{.State.StartedAt}}" betmexico-web'
```
Expected: md5 local == md5 prod para ambos archivos. `StartedAt` > mtime del deploy.

- [ ] **Step 3: Verificar que el botón aparece en el HTML servido**

```bash
curl -s https://botmexico.com.mx/static/pantalla.js | grep -c "pat-act-wd\|d-withdraw-open\|pat-wd-pop"
```
Expected: ≥ 3 (botón + handler + popup presentes en el bundle servido).

- [ ] **Step 4: Validación visual (screenshot anotado por Robert)**

Pedir a Robert screenshot de La Pantalla de una cuenta con saldo ≥ $100 (ej. `msaidrzz`) logueado como SA. Verificar:
- Botón "Retirar" visible a la derecha de "Depositar" en `.pat-actions`.
- Click abre el popup `.pat-wd-pop` con input de monto + saldo Real + botón "Retirar".
- Medir `getBoundingClientRect` del popup en consola del navegador:
  ```js
  const pop = document.querySelector('[data-wd-pop]'); pop.hidden=false;
  const r = pop.getBoundingClientRect(); const sheet = document.querySelector('.pantalla-sheet').getBoundingClientRect();
  console.log('popup.bottom', r.bottom, 'sheet.bottom', sheet.bottom, 'overflow', r.bottom - sheet.bottom);
  ```
  Expected: `overflow ≤ 0` (popup no rebasa la sheet hacia abajo).

- [ ] **Step 5: Verificar gris si saldo < $100**

Abrir La Pantalla de una cuenta con saldo < $100 (o pedir a Robert cual cumple). Verificar:
- Botón "Retirar" renderizado con `disabled` + estilo gris.
- Click no abre popup.
- Tooltip "Saldo < $100" al hover.

- [ ] **Step 6: Smoke funcional — retiro de $1 en cuenta de prueba**

> **NO $100.** Usar monto $1 para validar el flujo end-to-end sin riesgo grande (decisión del spec §9). Coordinar con Robert para elegir cuenta de prueba.

1. Abrir La Pantalla de la cuenta de prueba (SA, saldo ≥ $1).
2. Click "Retirar" → escribir `1` → "Retirar".
3. Verificar en el popup: "Disparando…" → polling → estado terminal.
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
git log --oneline -6  # confirmar los commits de Tasks 1-5
git push origin feat/boton-retiro-automatico
git fetch origin main
git merge-base --is-ancestor origin/main HEAD && \
  git push origin feat/boton-retiro-automatico:main
```
Expected: fast-forward limpio a main.

- [ ] **Step 8: Reporte denso**

Reportar a Robert:
- Sistema: web ✓/✗ · bot ✓/⛔ · health ✓/✗.
- Botón: visible ✓/✗ · gris si < $100 ✓/✗ · popup abre ✓/✗.
- Smoke $1: disparado ✓/✗ · 3 guardarrails ✓/✗ · bitácora ✓/✗.
- Merge: main en `<hash>`.

---

## Self-Review del plan

**Cobertura del spec:**
- §1 Objetivo (botón dedicado + popup monto) → Tasks 2-3. ✓
- §2.1 Botón en `.pat-actions` derecha de Depositar + ph-bank → Task 2 Step 2. ✓
- §2.1 Gris si < $100 → Task 1 (`_withdrawBtnState`) + Task 5 (`.pat-act-wd:disabled`). ✓
- §2.1 No-SA no renderiza → Task 1 (`render:false`). ✓
- §2.2 `<dialog>` nativo → **CORREGIDO** a `hidden` toggle (Task 3, anclaje verificado: CURP no es dialog nativo). Documentado en Global Constraints.
- §2.2 Header email + saldo + input + estado + alerts → Task 3 Step 1. ✓
- §2.3 Handler `d-withdraw-open` → Task 3 Step 4. ✓
- §2.4 Handler `d-withdraw-fire` reusa data-class → Task 4 Step 1. ✓
- §2.5 Polling dentro del popup → Task 4 Step 3. ✓
- §2.6 Eliminar `renderPantallaWithdraw` → Task 2 Steps 1,3. ✓
- §5 CSS `.pat-act-wd` + `.pat-wd-dialog` → Task 5 (renombrado `.pat-wd-pop` por corrección de patrón). ✓
- §6 Estados del botón → Task 1 (tabla de estados en tests). ✓
- §7 Flujo retiro → Tasks 3-4 + smoke Task 6. ✓
- §8 Guardarrails (backend, no tocar) → Global Constraints. ✓
- §9 Pruebas → Task 1 (TDD) + Task 6 (smoke HTTP, funcional, visual). ✓
- §10 No-go (clabes, watchdog, backend, monorepo, multi-cuenta) → Global Constraints. ✓

**Placeholder scan:** sin TBD/TODO/"manejar errores apropiadamente". Cada step tiene código o comando real. ✓

**Consistencia de tipos/nombres:**
- `_withdrawBtnState(d, role)` — mismo nombre en Task 1 (def) y Task 2 (consume). ✓
- `renderPantallaWithdrawButton(d)` — Task 2 def + uso en `.pat-actions`. ✓
- `[data-wd-pop]` selector — Task 3 (popup) + Task 4 (handlers fire/poll). ✓
- `_openWithdrawPopup(accId, cache)` / `_closeWithdrawPopup()` — Task 3 def + Task 4 Step 2 (uso). ✓
- `d.withdraw-fire` data-class — conservado del código existente, no renombrado. ✓
- `money()` (app.js) — asumido existente (usado ya en `renderPantallaHead` L328 para balance). ✓

**Alcance:** un solo plan ejecutable (frontend puro, ~6 tasks). No requiere partirse. ✓

**Nota:** el `_resumeWithdrawPollIfPending` (L573-580) existente sigue llamándose en `_renderDetailView` (L745) — al re-renderizar tras disparar, reanuda el polling si hay pendiente. Consistente con Task 4 Step 2 (re-abrir popup). No se toca.
