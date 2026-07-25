# Diseño — Botón de Retiro Dedicado + Panel de Monto en Col 3

> Fecha: 2026-07-25 · Estado: **SPEC v2 — pendiente implementación** (revisión 2026-07-25: popup flotante → panel en col 3)
> Lente rectora: `feedback_frictionless_norte` + `NORTE.md`. BOTMEXICO = frictionless, a prueba de desmadre.
> Origen: el botón de retiro actual (`renderPantallaWithdraw`) está **escondido** anidado en `.pat-col-ident` como un bloque con input+monto, abajo de las clabes. Robert lo criticó: debe ser un **botón visible dedicado** en la barra de acciones, junto al de depósito, gris si saldo < $100.
> **Revisión v2:** el panel de monto NO es un popup flotante — vive en la **col 3** (`.pat-col-stage#patStageSlot`), que en reposo está vacía (`#depStage` hidden). Llena el espacio desperdiciado, invita a transaccionar.

---

## 1. Objetivo

Migrar el botón de retiro de su ubicación escondida (bloque anidado en la columna de datos) a un **botón dedicado en `.pat-actions`** (la barra de acciones visible), junto al botón de depósito. El panel de monto + estado 2-fases vive en la **col 3** (`.pat-col-stage`), reusando el espacio que en reposo queda vacío (donde va la animación de depósito `#depStage`). Click en el botón dispara el retiro con el monto del input de col 3 → feedback en vivo.

**Frictionless:** el operador ve el botón + el input a la vista (sin abrir nada), escribe monto, 1 click dispara. La col 3, vacía en reposo, deja de ser espacio muerto y se vuelve la zona de feedback en vivo.

## 2. Alcance

**IN (este spec):**
- Botón "Retirar" dedicado en `.pat-actions`, a la derecha de "Depositar". Icono `ph-bank`.
- Botón **gris/disabled si saldo < $100** (tooltip "Saldo < $100").
- Botón **no se renderiza para no-SA** (mismo gate que el bloque actual, `feedback_deshabilitar_invisible_no_redirect`).
- Panel `#wdStage` en col 3 (`.pat-col-stage#patStageSlot`) con: header (email), saldo Real, input monto, zona de estado 2-fases + alerts de guardarrails. **Visible en reposo para SA** (llena el espacio vacío).
- Coexistencia `#wdStage` ↔ `#depStage` en col 3 vía CSS `:has()` puro — depósito tiene prioridad visual (lo oculta cuando hay misión de depósito).
- Reubicar la lógica existente de polling/status para operar sobre `#wdStage` (selectores cambian, lógica no).
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
- **Col 3 = `.pat-col-stage#patStageSlot`** (`pantalla.js:335`, `pantalla.css:590-605`): `min-width:380px`, flex child de `.pat-columns`. En reposo aloja `#depStage` (animación de depósito) **hidden** → la col queda vacía = el espacio desperdiciado que llena `#wdStage`.
- **`#depStage` se enciende/apaga con `stg.hidden = true/false`** (`depos.js:343` enciende, `depos.js:862` apaga). Coexistencia con `#wdStage` vía CSS `:has()`: `#patStageSlot:has(#depStage:not([hidden])) #wdStage { display:none }`. **depos.js intacto** — no se toca.
- **`_mountStage()`** (`pantalla.js:715-719`) re-parenta `#depStage` al slot en cada render del detalle. `#wdStage` vive en el template de `renderPantallaHead` (se recrea con el innerHTML, NO necesita rescue como `#depStage` porque es estático, sin estado JS).
- **`money()`** (`pantalla.js:257,489,649`): `window.fmtMoney || (v => \`$${(v||0).toFixed(2)}\`)`. Ya se usa en `.pat-balance`. Disponible en scope de `renderPantallaHead`.
- **Saldo:** `d.balance_real` ya está en el detalle (fresco tras refresh). Es la fuente para el gate de $100.

## 4. Diseño — Frontend

### 4.1 Botón dedicado en `.pat-actions`

En `renderPantallaHead` (`pantalla.js:337`), la barra `.pat-actions` queda:
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
  const st_ = _withdrawBtnState(d, (window.state && state.user || {}).role);
  if (!st_.render) return ''; // invisible para no-SA
  const g = window.esc || (s => s);
  return `<button type="button" class="pat-act pat-act-wd d-withdraw-fire" data-acc-id="${g(d.id)}"${st_.disabled ? ' disabled' : ''} title="${g(st_.tooltip)}"><i class="ph-duotone ph-bank"></i><span>Retirar</span></button>`;
}
```

- **Gris/disabled si saldo < $100** (vía atributo `disabled` + CSS `.pat-act-wd:disabled`).
- **SA-only** (no se renderiza para no-SA).
- Tooltip dinámico: "Saldo < $100" / "Retiro en curso…" / "Retirar".
- **`d-withdraw-fire` en el botón** (no `d-withdraw-open`): el botón dispara directo. No hay popup que abrir. El input de monto vive en col 3, siempre visible.

### 4.2 Panel `#wdStage` en col 3 (`.pat-col-stage#patStageSlot`)

El panel de monto + estado vive en la col 3, que en reposo está vacía (`#depStage` hidden). Se renderiza como **hijo del template de `renderPantallaHead`**, al lado de `#patStageSlot`:

```js
<div class="pat-columns">
  <div class="pat-col-ident">…</div>
  ${renderPantallaTxns(d)}
  <div class="pat-col-stage">
    ${renderPantallaWithdrawStage(d)}   <!-- NUEVO: panel de retiro (SA), o '' si no-SA -->
    <div id="patStageSlot"></div>        <!-- EXISTE: slot donde depos.js re-parenta #depStage -->
  </div>
</div>
```

Nueva función `renderPantallaWithdrawStage(d)`:
```js
function renderPantallaWithdrawStage(d) {
  const st_ = _withdrawBtnState(d, (window.state && state.user || {}).role);
  if (!st_.render) return ''; // no-SA: col 3 queda como hoy (vacía en reposo salvo misión depósito)
  const g = window.esc || (s => s);
  const money = window.fmtMoney || (v => `$${(v || 0).toFixed(2)}`);
  const st = _wdStatusFromRow(d.last_withdrawal);
  const pending = !!st && !WD_TERMINAL.has(st.status);
  const statusHtml = st ? _withdrawStatusHtml(st) : '';
  return `<div class="pat-wd-stage" data-wd-stage>
    <span class="pat-wd-head"><span class="pat-sv-emo">🏧</span> Retirar — <span class="pat-wd-email">${g(d.email || '')}</span></span>
    <div class="pat-wd-balance">Saldo Real: <b class="pat-wd-balance-v">${money(d.balance_real || 0)}</b></div>
    <input class="pat-input pat-wd-amount" type="number" min="100" step="0.01" placeholder="monto (min $100)" data-wd-amount${st_.disabled || pending ? ' disabled' : ''}>
    <div class="pat-form-err" data-wd-err hidden></div>
    <div class="pat-wd-status">${statusHtml}</div>
  </div>`;
}
```

- `#wdStage` **siempre visible en reposo para SA** — llena el espacio vacío de col 3, invita a transaccionar.
- **Coexistencia con `#depStage` vía CSS `:has()`** (§5): si hay misión de depósito (`#depStage:not([hidden])`), `#wdStage` se oculta — depósito tiene prioridad visual.
- `data-wd-amount` se **disablea (gris) si saldo < $100 o hay retiro pendiente** — el botón de `.pat-actions` también va disabled, doble reflejo del estado.
- `.pat-wd-status` — zona donde se inyecta `_withdrawStatusHtml(st)` (2-fases + alerts).
- El input se pobla en el render (no necesita handler `d-withdraw-open` de apertura) — al cambiar de cuenta, el re-render trae saldo/input frescos.

### 4.3 Handler `d-withdraw-fire` (existente, adaptado)

El handler actual (`pantalla.js:909`) opera sobre `wrap = wdFire.closest('.pat-wd')`. Se adapta:
- `wrap` = `document.querySelector('[data-wd-stage]')` (el panel de col 3).
- `accId` = `wdFire.dataset.accId` (el botón de `.pat-actions` trae `data-acc-id`) o `_currentId`.
- `input` = `wrap.querySelector('[data-wd-amount]')`.
- `statusEl` = `wrap.querySelector('.pat-wd-status')`.
- Resto idéntico: valida monto ≥ 100 (si input vacío/inválido → muestra error en `data-wd-err`), POST `/api/accounts/{id}/withdraw`, actualiza `cache.last_withdrawal`, arranca `_startWithdrawPoll(accId, data.transactionId)`, toast "🏧 Retiro disparado".
- **No hay lógica de "re-abrir popup"** — el panel ya está visible. Tras disparar, se disablea el input + el botón (vía estado `pending` en el siguiente render o imperativamente).

### 4.4 Polling sobre `#wdStage`

`_fetchWithdrawStatus(accId, txId)` (`pantalla.js:533`) se adapta:
- `wrap` = `document.querySelector('[data-wd-stage]')` (si existe; si la cuenta cambió y el panel ya no está, no actualiza DOM — pero el polling sigue para el cache).
- `statusEl` = `wrap?.querySelector('.pat-wd-status')`.
- `input`/`btn` = `wrap?.querySelector('[data-wd-amount]')` / `.d-withdraw-fire`.
- `done` = `WD_TERMINAL.has(st.status)` → si done, `_stopWithdrawPoll(accId)` + rehabilita input/btn.
- Actualiza `cache.last_withdrawal` (igual que ahora) para que el re-render muestre el estado.

### 4.5 Eliminación del bloque anidado

- Borrar `${renderPantallaWithdraw(d)}` de `pantalla.js:332` (la columna `.pat-col-ident`).
- Borrar la función `renderPantallaWithdraw()` (`pantalla.js:510-526`) — reemplazada por `renderPantallaWithdrawButton()` + `renderPantallaWithdrawStage()`.
- Conservar `_wdStatusFromRow`, `_withdrawStatusHtml`, `WD_TERMINAL`, `_wdPolls`, `_stopWithdrawPoll`, `_startWithdrawPoll`, `_fetchWithdrawStatus` (adaptados selectores).

## 5. Diseño — CSS (`static/pantalla.css`)

Reusa tokens existentes (`--pat-gold`, `--pat-edge`, glassmorphism de La Pantalla).

```css
/* Botón Retirar en .pat-actions — mismo lenguaje que .pat-act-dep */
.pat-act-wd { color: #08090c; background: var(--pat-gold); border-color: transparent;
  box-shadow: 0 0 12px -6px var(--pat-gold), 0 1px 2px oklch(0 0 0 / 0.25); }
.pat-act-wd:hover:not(:disabled) { filter: brightness(1.08); }
.pat-act-wd:disabled { opacity: .4; cursor: not-allowed; background: var(--pat-edge); color: var(--text-dim); box-shadow: none; }
.pat-act-wd:disabled:hover { transform: none; filter: none; }

/* Panel de retiro en col 3 — hereda el slot, glassmorphism de La Pantalla */
.pat-wd-stage {
  display: flex; flex-direction: column; gap: 7px;
  padding: 14px 4px 4px 0;        /* aire arriba, sin padding-right (lo da .pat-col-stage) */
  color: var(--text);
}
/* Coexistencia: si hay misión de depósito activa (#depStage visible), oculta el panel de retiro.
   depos.js no se toca — la prioridad visual la resuelve el CSS. */
#patStageSlot:has(#depStage:not([hidden])) ~ .pat-wd-stage,
.pat-col-stage:has(#depStage:not([hidden])) .pat-wd-stage { display: none; }
.pat-wd-head { font-size: 12px; font-weight: 600; display: flex; gap: 5px; align-items: center; }
.pat-wd-balance { font-size: 10.5px; color: var(--text-dim); }
.pat-wd-balance b, .pat-wd-balance-v { color: var(--pat-gold); font-family: var(--font-mono); }
.pat-wd-stage .pat-input { width: 100%; }
.pat-wd-status { margin-top: 4px; }
.pat-wd-status:empty { display: none; }

/* Reusar .pat-wd-row/.pat-wd-amt/.pat-wd-line/.pat-wd-alert existentes (pantalla.css:841-851)
   — ya están definidos para el bloque viejo, se conservan tal cual (los genera _withdrawStatusHtml). */
```

- **Gris si < $100:** `.pat-act-wd:disabled` con `opacity:.4` (memoria `feedback_badge_solo_excepcion` — el estado default no se destaca, solo la excepción accionable; aquí el disabled es la excepción que frena).
- **Coexistencia `:has()`:** depósito > retiro en col 3. Una cuenta no se deposita y retira a la vez (lock 2h lo impide), pero la regla protege de edge cases.
- **Ancla medida:** el panel **llena su slot** (`width:100%` implícito de flex child), no tiene ancho propio inventado. Alto = contenido (`gap` + padding, sin `height` fijo). Tamaño final se valida con `getBoundingClientRect` en prod (memoria `feedback_ui_ancla_medida_no_pixel_inventado`).

## 6. Estados del botón + col 3

| Condición | Botón `.pat-actions` | Col 3 (`#wdStage`) |
|---|---|---|
| No-SA | no se renderiza | no se renderiza (col 3 = como hoy) |
| SA + saldo ≥ $100 + sin retiro pendiente | activo (dorado) | panel visible, input habilitado |
| SA + saldo ≥ $100 + retiro pendiente | activo (tooltip "Retiro en curso…") | panel visible, input disabled (gris), estado 2-fases |
| SA + saldo < $100 | gris/disabled | panel visible, input disabled (gris) |
| Misión depósito corriendo | (Depositar activo) | `#depStage` visible, `#wdStage` oculto (`:has()`) |

## 7. Flujo de retiro (sin cambios funcionales)

1. SA ve el botón "Retirar" en `.pat-actions` + el panel con input en col 3 (siempre visible en reposo).
2. Escribe monto en el input de col 3 → click "Retirar" en `.pat-actions` → valida monto ≥ 100 → POST `/api/accounts/{id}/withdraw`.
3. Col 3 muestra "Disparando…" → input + botón se disablean → polling 60s → 2-fases ("BetMexico procesó… Confirma en tu banco") + alerts (gateway tarjeta vs SPEI, dígitos).
4. El panel sigue visible (no se cierra). El polling actualiza el estado en `.pat-wd-status`.
5. Estado terminal → polling se detiene, input/btn se rehabilitan.

## 8. Guardarrails (ya implementados en backend, NO tocar)

- **Bug #1:** `accountId` fresco por disparo (fresh read BankAccounts antes del POST).
- **Bug #2:** 2-fases, NO "entregado" con `status:6`.
- **Bug #3:** alert si `gateway:1` (tarjeta) cuando esperábamos `gateway:2` (SPEI).
- **Concurrencia:** bloquea nuevo disparo mientras hay retiro pendiente.
- **NO proxyless** (ley `feedback_nunca_proxyless`).
- **NO taladrar** polling < 60s.

## 9. Pruebas / verificación

- **Tests JS:** `static/pantalla_logic.test.js` — tests de `_withdrawBtnState(d, role)` (lógica pura extraída del render).
- **Smoke funcional:** retiro de $1 en cuenta de prueba (no $100) → validar 3 guardarrails + 2-fases + cache.
- **Smoke HTTP real tras deploy** (memoria `feedback_verify_http_response_after_deploy`): `curl`/`httpx` al `/static/pantalla.js` confirma md5 servido == repo.
- **Validación visual premium:** screenshot anotado por Robert (memoria `feedback_verificar_entry_real` + `feedback_ui_ancla_medida_no_pixel_inventado`) — el panel en col 3 se mide con `getBoundingClientRect` (que llena el slot sin overflow), no a ojo.

## 10. No-go / fuera de alcance

- **Clabes auto-obtener:** aparte (decisión Robert).
- **Watchdog de retiro pendiente + notificación:** anotado para después.
- **Backend:** no se toca (endpoints ya existen y funcionan).
- **Bot Telegram (monorepo):** no se toca (`feedback_no_monorepo`).
- **`depos.js`:** no se toca (la coexistencia la resuelve CSS `:has()`).
- **Retiros multi-cuenta en lote:** fuera de alcance.

## 11. Archivos tocados

| Archivo | Cambio |
|---|---|
| `static/pantalla.js` | + `_withdrawBtnState()` (lógica pura) + `renderPantallaWithdrawButton()` + `renderPantallaWithdrawStage()` + `#wdStage` en col 3 + adaptar `d-withdraw-fire`/`_fetchWithdrawStatus` (selectores → `[data-wd-stage]`). Eliminar `renderPantallaWithdraw()` + su llamada en columna. |
| `static/pantalla.css` | + `.pat-act-wd`, `.pat-wd-stage`, `.pat-wd-head/balance/status`, regla `:has()` de coexistencia. Reusa `.pat-wd-row/amt/line/alert` existentes. |
| `static/pantalla_logic.test.js` | + tests de `_withdrawBtnState(d, role)`. |

**No se tocan:** backend, `app.py`, `withdrawals.py`, `deposits.py`, `depos.js`, `prewarm.py`, monorepo.

## 12. Secuencia de implementación

1. TDD: `_withdrawBtnState(d, role)` en `pantalla.js` + tests en `pantalla_logic.test.js`.
2. Frontend JS: `renderPantallaWithdrawButton()` + `renderPantallaWithdrawStage()` + `#wdStage` en col 3 en `pantalla.js`.
3. Adaptar handler `d-withdraw-fire` + `_fetchWithdrawStatus` (selectores → `[data-wd-stage]`).
4. Eliminar `renderPantallaWithdraw()` + su llamada en `.pat-col-ident`.
5. CSS: `.pat-act-wd`, `.pat-wd-stage` + regla `:has()` en `pantalla.css`.
6. Deploy a KVM4 + smoke HTTP real (md5 servido == repo).
7. Smoke funcional: retiro de $1 en cuenta de prueba → 3 guardarrails + 2-fases.
8. Validación visual premium: screenshot anotado por Robert, medir `getBoundingClientRect` del panel en col 3.

> **Modelos por subagente** (ley `feedback_planes_orquestacion`): frontend JS+CSS en Sonnet (patrones ya establecidos), smoke/verify en Haiku (mecánico). Goal medible: botón "Retirar" visible en `.pat-actions`, gris si < $100, panel de monto en col 3 (llena el slot sin overflow), click dispara retiro real con 3 guardarrails verificados.
