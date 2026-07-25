# Diseño — Botón de Retiro Dedicado + Popup de Monto

> Fecha: 2026-07-25 · Estado: **SPEC — pendiente implementación**
> Lente rectora: `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre.
> Origen: el botón de retiro actual (`renderPantallaWithdraw`) está **escondido** anidado en `.pat-col-ident` como un bloque con input+monto, abajo de las clabes. Robert lo criticó: debe ser un **botón visible dedicado** en la barra de acciones, junto al de depósito, gris si saldo < $100.

---

## 1. Objetivo

Migrar el botón de retiro de su ubicación escondida (bloque anidado en la columna de datos) a un **botón dedicado en `.pat-actions`** (la barra de acciones visible), junto al botón de depósito. Al click, abre un **cuadro flotante** (`<dialog>` nativo) pidiendo el monto escrito → dispara el retiro → feedback en vivo al usuario mientras procesa.

**Frictionless:** el operador ve el botón a la vista, 1 click abre el popup, escribe monto, 1 click dispara. Sin buscar el bloque escondido en la columna.

## 2. Alcance

**IN (este spec):**
- Botón "Retirar" dedicado en `.pat-actions`, a la derecha de "Depositar". Icono `ph-bank`.
- Botón **gris/disabled si saldo < $100** (tooltip "Saldo < $100").
- Botón **no se renderiza para no-SA** (mismo gate que el bloque actual, `feedback_deshabilitar_invisible_no_redirect`).
- `<dialog>` nativo con: header (email), saldo Real disponible, input monto, botón "Retirar", zona de estado 2-fases + alerts de guardarrails.
- Reubicar la lógica existente de polling/status para operar dentro del dialog (selectores cambian, lógica no).
- Eliminar `renderPantallaWithdraw()` de la columna `.pat-col-ident`.

**OUT (pospuesto, anotado):**
- **Watchdog de retiro pendiente + notificación al usuario** cuando procese. Pendiente post-botón-funcional (Robert lo pidió, se anota para cuando toque).
- **Auto-obtener clabes al actualizar** (las clabes se piden solas, sin botón manual). Decisión Robert: tocar clabes aparte, NO en este cambio.
- Retiros multi-cuenta en lote.
- Cambios de backend (los endpoints ya existen y funcionan).

## 3. Contexto técnico (deducido del código, no asumido)

- **`.pat-actions`** (`pantalla.js:337-340`) ya renderiza `[Fijar][Depositar]`. Se agrega `[Retirar]` a la derecha de Depositar.
- **`renderPantallaWithdraw()`** (`pantalla.js:510`) renderiza el bloque anidado con input+monto+status, dentro de `.pat-col-ident` (`pantalla.js:332`). **Se elimina** de ahí.
- **Lógica de retiro (se CONSERVA intacta, solo cambia el `wrap`):**
  - `_wdStatusFromRow(row)` (`pantalla.js:471`) — adapta fila de `account_withdrawals` al shape de `/withdraw/status`.
  - `_withdrawStatusHtml(st)` (`pantalla.js:486`) — HTML 2-fases + alerts de guardarrails (gateway tarjeta vs SPEI, dígitos).
  - `WD_TERMINAL` (`pantalla.js:465`) — Set de estados terminales.
  - `_wdPolls` (`pantalla.js:85`) — map de intervalos activos por `accId`.
  - `_stopWithdrawPoll(accId)` / `_startWithdrawPoll(accId, txId)` / `_fetchWithdrawStatus(accId, txId)` (`pantalla.js:528-568`) — polling 60s.
  - Handler `d-withdraw-fire` (`pantalla.js:909`) — valida monto, POST `/api/accounts/{id}/withdraw`, arranca polling, actualiza cache.
  - En `_renderDetailView` (`pantalla.js:574-578`): al renderizar, si hay retiro pendiente (`last_withdrawal` no terminal) y no hay poll activo, arranca el polling.
- **Backend SIN cambios:** `POST /api/accounts/{id}/withdraw` + `GET /api/accounts/{id}/withdraw/status/{txId}` ya existen (commits `0b8d499`/`5a7779b`), con guardarrails bug#1/#2/#3 implementados (ver `docs/ERRORS.md` y spec `2026-07-24-boton-retiro-automatico-design.md`).
- **Patrón CURP existente** (`pantalla.js:311-320`): usa `<dialog>`/`.pat-curp-pop` con `data-curp-form` hidden. El popup de retiro sigue el mismo patrón (memoria `feedback_frictionless_norte` — reusar > inventar).
- **Saldo:** `d.balance_real` ya está en el detalle (fresco tras refresh). Es la fuente para el gate de $100.

## 4. Diseño — Frontend

### 4.1 Botón dedicado en `.pat-actions`

En `_renderDetailView` (`pantalla.js:337`), la barra `.pat-actions` queda:
```js
<div class="pat-actions">
  <button type="button" class="pat-act det-mark" data-mark-email="${g(email)}" title="Fijar"><i class="ph-bold ph-push-pin"></i></button>
  <button type="button" class="pat-act pat-act-dep d-deposit-btn" data-acc-id="${d.id}" title="Depositar"><i class="ph-duotone ph-credit-card"></i><span>Depositar</span></button>
  ${renderPantallaWithdrawButton(d)}
</div>
```

Nueva función `renderPantallaWithdrawButton(d)`:
```js
function renderPantallaWithdrawButton(d) {
  const u = (window.state && state.user) || {};
  if (u.role !== 'superadmin') return ''; // invisible para no-SA
  const g = window.esc || (s => s);
  const balance = parseFloat(d.balance_real || 0) || 0;
  const canWithdraw = balance >= 100;
  const st = _wdStatusFromRow(d.last_withdrawal);
  const pending = !!st && !WD_TERMINAL.has(st.status);
  return `<button type="button" class="pat-act pat-act-wd d-withdraw-open"
            data-acc-id="${d.id}" ${canWithdraw ? '' : 'disabled'}
            title="${canWithdraw ? (pending ? 'Retiro en curso…' : 'Retirar') : 'Saldo < $100'}">
    <i class="ph-duotone ph-bank"></i><span>Retirar</span>
  </button>`;
}
```

- **Gris/disabled si saldo < $100** (vía atributo `disabled` + CSS `.pat-act-wd:disabled`).
- **SA-only** (no se renderiza para no-SA).
- Tooltip dinámico: "Saldo < $100" / "Retiro en curso…" / "Retirar".

### 4.2 `<dialog>` de retiro (patrón CURP)

Nuevo `<dialog>` fijo en el DOM (cerca del `.pat-curp-pop`, mismo nivel). Se puebla al abrir:
```html
<dialog class="pat-wd-dialog" id="patWithdrawDialog">
  <form method="dialog" class="pat-wd-form">
    <span class="pat-wd-head"><span class="pat-sv-emo">🏧</span> Retirar — <span data-wd-email></span></span>
    <div class="pat-wd-balance">Saldo Real: <b data-wd-balance></b></div>
    <input class="pat-input pat-wd-amount" type="number" min="100" step="0.01" placeholder="monto (min $100)" data-wd-amount>
    <div class="pat-form-err" data-wd-err hidden></div>
    <div class="pat-wd-status"></div>
    <div class="pat-form-row">
      <button type="button" class="pat-btn pat-btn-ghost" data-wd-cancel>Cancelar</button>
      <button type="button" class="pat-btn pat-btn-save d-withdraw-fire" data-wd-fire>Retirar</button>
    </div>
  </form>
</dialog>
```

- `data-wd-email`, `data-wd-balance` se pueblan al abrir con el detalle fresco.
- `data-wd-amount` autofocus al abrir.
- `.pat-wd-status` — zona donde se inyecta `_withdrawStatusHtml(st)` (2-fases + alerts).
- `.d-withdraw-fire` — **reusa el mismo data-class** que el botón viejo (el handler existe, solo cambia el `wrap`).
- `data-wd-cancel` + ESC + click backdrop cierran el dialog.

### 4.3 Handler `d-withdraw-open` (nuevo)

En el listener de `#pantalla` (cerca de `d-deposit-btn`, `pantalla.js:798`):
```js
const wdOpen = e.target.closest('.d-withdraw-open');
if (wdOpen) {
  e.preventDefault();
  const accId = parseInt(wdOpen.dataset.accId) || _currentId;
  const cache = _cacheGet(accId);
  _openWithdrawDialog(accId, cache);
}
```

Nueva `_openWithdrawDialog(accId, cache)`:
- Puebla `data-wd-email` = `cache.email`, `data-wd-balance` = `money(cache.balance_real)`.
- Limpia `data-wd-amount` (vacío), `data-wd-err` (hidden), `.pat-wd-status`.
- Si hay `last_withdrawal` pendiente → muestra su estado inyectando `_withdrawStatusHtml(_wdStatusFromRow(cache.last_withdrawal))` y arranca polling si no estaba activo.
- `dialog.showModal()`.

### 4.4 Handler `d-withdraw-fire` (existente, adaptado)

El handler actual (`pantalla.js:909`) opera sobre `wrap = wdFire.closest('.pat-wd')`. Se adapta:
- `wrap` = `document.getElementById('patWithdrawDialog')` (el `<dialog>`).
- `accId` = `_currentId` (el dialog siempre es de la cuenta abierta) o un `data-acc-id` guardado al abrir.
- `input` = `wrap.querySelector('[data-wd-amount]')`.
- `statusEl` = `wrap.querySelector('.pat-wd-status')`.
- Resto idéntico: valida monto ≥ 100, POST `/api/accounts/{id}/withdraw`, actualiza `cache.last_withdrawal`, arranca `_startWithdrawPoll(accId, data.transactionId)`, toast "🏧 Retiro disparado".

### 4.5 Polling dentro del dialog

`_fetchWithdrawStatus(accId, txId)` (`pantalla.js:533`) se adapta:
- `wrap` = `document.getElementById('patWithdrawDialog')` si está open, else null (no actualiza DOM si el dialog cerró — pero el polling sigue para actualizar el cache).
- `statusEl` = `wrap?.querySelector('.pat-wd-status')`.
- `input`/`btn` = `wrap?.querySelector('[data-wd-amount]')` / `.d-withdraw-fire`.
- `done` = `WD_TERMINAL.has(st.status)` → si done, `_stopWithdrawPoll(accId)` + rehabilita input/btn.
- Actualiza `cache.last_withdrawal` (igual que ahora) para que al reabrir el dialog muestre el estado.

### 4.6 Eliminación del bloque anidado

- Borrar `${renderPantallaWithdraw(d)}` de `pantalla.js:332` (la columna `.pat-col-ident`).
- Borrar la función `renderPantallaWithdraw()` (`pantalla.js:510-526`) — reemplazada por `renderPantallaWithdrawButton()` + el dialog.
- Conservar `_wdStatusFromRow`, `_withdrawStatusHtml`, `WD_TERMINAL`, `_wdPolls`, `_stopWithdrawPoll`, `_startWithdrawPoll`, `_fetchWithdrawStatus` (adaptados selectores).

## 5. Diseño — CSS (`static/pantalla.css`)

Reusa tokens existentes (`--pat-gold`, `--pat-edge`, glassmorphism de La Pantalla).

```css
/* Botón Retirar en .pat-actions — mismo lenguaje que .pat-act-dep */
.pat-act-wd { /* hereda .pat-act */ }
.pat-act-wd:disabled { opacity: .4; cursor: not-allowed; }
.pat-act-wd:disabled:hover { transform: none; }

/* Dialog de retiro — variant de .pat-curp-pop, glassmorphism */
.pat-wd-dialog {
  /* ancla medida: max-content + padding, no px inventado */
  border: 1px solid var(--pat-edge);
  border-radius: 14px;
  background: var(--pat-bg-glass, rgba(20,20,28,.92));
  backdrop-filter: blur(18px);
  padding: 18px 20px;
  color: var(--text);
  min-width: 280px;
}
.pat-wd-dialog::backdrop {
  background: rgba(0,0,0,.55);
  backdrop-filter: blur(2px);
}
.pat-wd-head { font-size: 13px; font-weight: 600; display:flex; gap:6px; align-items:center; }
.pat-wd-balance { font-size: 11px; color: var(--text-dim); margin: 6px 0 10px; }
.pat-wd-balance b { color: var(--pat-gold); font-family: var(--font-mono); }
.pat-wd-status { margin-top: 8px; }
.pat-wd-status:empty { display: none; }

/* Reusar .pat-wd-row/.pat-wd-amt/.pat-wd-line/.pat-wd-alert existentes (pantalla.css:841-851)
   — ya están definidos para el bloque viejo, se conservan tal cual. */
```

- **Gris si < $100:** `.pat-act-wd:disabled` con `opacity:.4` (memoria `feedback_badge_solo_excepcion` — el estado default no se destaca, solo la excepción accionable; aquí el disabled es la excepción que frena).
- **Ancla medida:** `min-width:280px` + `max-content` (no alto fijo inventado, memoria `feedback_ui_ancla_medida_no_pixel_inventado`). Tamaño final se valida con `getBoundingClientRect` en prod.

## 6. Estados del botón

| Condición | Render | Botón | Tooltip |
|---|---|---|---|
| No-SA | no se renderiza | — | — |
| SA + saldo ≥ $100 + sin retiro pendiente | visible | activo (dorado) | "Retirar" |
| SA + saldo ≥ $100 + retiro pendiente | visible | activo | "Retiro en curso…" |
| SA + saldo < $100 | visible | gris/disabled | "Saldo < $100" |

## 7. Flujo de retiro (sin cambios funcionales)

1. SA da click en botón "Retirar" → abre `<dialog>`.
2. Escribe monto → click "Retirar" → valida monto ≥ 100 → POST `/api/accounts/{id}/withdraw`.
3. Dialog muestra "Disparando…" → polling 60s → 2-fases ("BetMexico procesó… Confirma en tu banco") + alerts (gateway tarjeta vs SPEI, dígitos).
4. ESC / Cancelar / click backdrop cierran el dialog. El polling sigue en background hasta estado terminal (actualiza el cache; al reabrir se ve el estado).
5. Estado terminal → polling se detiene, input/btn se rehabilitan.

## 8. Guardarrails (ya implementados en backend, NO tocar)

- **Bug #1:** `accountId` fresco por disparo (fresh read BankAccounts antes del POST).
- **Bug #2:** 2-fases, NO "entregado" con `status:6`.
- **Bug #3:** alert si `gateway:1` (tarjeta) cuando esperábamos `gateway:2` (SPEI).
- **Concurrencia:** bloquea nuevo disparo mientras hay retiro pendiente.
- **NO proxyless** (ley `feedback_nunca_proxyless`).
- **NO taladrar** polling < 60s.

## 9. Pruebas / verificación

- **Tests JS:** `static/pantalla_logic.test.js` — verificar que no rompe (tests de lógica de retiro si existen).
- **Smoke funcional:** retiro de $1 en cuenta de prueba (no $100) → validar 3 guardarrails + 2-fases + cache.
- **Smoke HTTP real tras deploy** (memoria `feedback_verify_http_response_after_deploy`): `curl`/`httpx` al `/static/pantalla.js` confirma md5 servido == repo.
- **Validación visual premium:** screenshot anotado por Robert (memoria `feedback_verificar_entry_real` + `feedback_ui_ancla_medida_no_pixel_inventado`) — el tamaño final del dialog se mide con `getBoundingClientRect`, no a ojo.

## 10. No-go / fuera de alcance

- **Clabes auto-obtener:** aparte (decisión Robert).
- **Watchdog de retiro pendiente + notificación:** anotado para después.
- **Backend:** no se toca (endpoints ya existen y funcionan).
- **Bot Telegram (monorepo):** no se toca (`feedback_no_monorepo`).
- **Retiros multi-cuenta en lote:** fuera de alcance.

## 11. Archivos tocados

| Archivo | Cambio |
|---|---|
| `static/pantalla.js` | + `renderPantallaWithdrawButton()` + `<dialog>` + handler `d-withdraw-open` + adaptar `d-withdraw-fire`/`_fetchWithdrawStatus` (selectores). Eliminar `renderPantallaWithdraw()` + su llamada en columna. |
| `static/pantalla.css` | + `.pat-act-wd`, `.pat-wd-dialog` + `::backdrop`, `.pat-wd-head/balance/status`. Reusa `.pat-wd-row/amt/line/alert` existentes. |

**No se tocan:** backend, `app.py`, `withdrawals.py`, `deposits.py`, `prewarm.py`, monorepo.

## 12. Secuencia de implementación

1. Frontend JS: `renderPantallaWithdrawButton()` + `<dialog>` + handler `d-withdraw-open` en `pantalla.js`.
2. Adaptar handler `d-withdraw-fire` + `_fetchWithdrawStatus` (selectores → dialog).
3. Eliminar `renderPantallaWithdraw()` + su llamada en `.pat-col-ident`.
4. CSS: `.pat-act-wd`, `.pat-wd-dialog` + `::backdrop` en `pantalla.css`.
5. Tests JS locales (`pantalla_logic.test.js`).
6. Deploy a KVM4 + smoke HTTP real (md5 servido == repo).
7. Smoke funcional: retiro de $1 en cuenta de prueba → 3 guardarrails + 2-fases.
8. Validación visual premium: screenshot anotado por Robert, medir `getBoundingClientRect`.

> **Modelos por subagente** (ley `feedback_planes_orquestacion`): frontend JS+CSS en Sonnet (patrones ya establecidos), smoke/verify en Haiku (mecánico). Goal medible: botón "Retirar" visible en `.pat-actions`, gris si < $100, click abre dialog, monto → dispara retiro real con 3 guardarrails verificados.
