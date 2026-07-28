# Frontend — mapa operativo

> Vanilla JS (sin framework). Archivos principales: `static/app.js` (~3,500+ líneas), `static/depos.js` + `depos_logic.js` + `depos.css` (modal v8), `static/depos_window.js` (ventana flotante), `static/activity_logic.js` (lógica pura de actividad — testeable con `node`).
> Mantener este mapa vivo cuando se agreguen/quiten secciones o handlers.

## Layout general

```
+------------------------------------------------------------+
| topbar: COLAPSADA en desktop (2026-06-29) · hamburger en mobile |
+----+--------------------------------------------------------+
| s  |  main section (cambia según nav):                      |
| i  |   - accounts                                           |
| d  |   - activity                                           |
| e  |   - pool                                               |
| b  |   - notifications                                      |
| a  |   - logs (SA)                                          |
| r  |   - admin panel (SA)                                   |
+----+--------------------------------------------------------+
| cmdBar (visible cuando hay selección): Depositar · Lock ... |
+------------------------------------------------------------+
```

## Branding / logo

- **Logo del dashboard** (sidebar `.sb-brand` + favicon): `static/assets/botmexico_logo.png`.
  - Desde 2026-06-26: osito-mascota "Depp-oso" con jersey de la selección + "botmexico.com.mx" tricolor, fondo transparente real (476×218). Reemplazó el emblema hacker previo (respaldo en `static/assets/botmexico_logo_hacker_prev.png`).
  - Fuente/recortes en `docs/mockups/assets-depos/` (`logo_principal.png` = recortado sin marca de agua Gemini; `logo_principal_v2_transparent.png` = ancho original con alfa).
  - Tamaño en sidebar: `.sb-brand img { width: 158px }` (`static/style.css`; reducido de 190px el 2026-06-29 al compactar el sidebar para que entre sin scroll). El glow verde lo da un `drop-shadow` CSS.
  - **Distinto** del avatar del panel de depósitos (`depos_avatar.png` / osito busto del modal) — ese es branding "Depos", no el logo global.

- **Cenefa superior** (`.cenefa`, `index.html` primer hijo de `<body>`) — 2026-06-29. Banda delgada full-width (`--cenefa-h: 30px`) en el "top del top" con el wordmark `botmexico.com.mx` en colores de la bandera (`.g` verde / `.w` blanco / `.r` rojo) + glow verde, flanqueado por 2 puntos rojos (`.cenefa-dot`). **Recreado en texto/CSS, NO raster** — nítido a cualquier ancho, sin distorsión, theme-aware (Robert pidió "con la segunda imagen": ese PNG no estaba como asset; el wordmark CSS es fiel a la marca y mejor para una banda delgada). `.shell` pasó a `height: calc(100vh - var(--cenefa-h))`; el `.dep-drawer` y el sidebar-drawer mobile arrancan en `top: var(--cenefa-h)`. Si Robert quiere el raster exacto: dejar el PNG en `static/assets/` y cambiar `.cenefa` por un `<img>`.

## Secciones (vías `showSection(name)` — app.js:926)

| Sección | Container HTML | Render | Endpoint inicial |
|---|---|---|---|
| `accounts` | `#accountsMain` | `renderTable()` (app.js:450) | `GET /api/accounts` |
| `activity` | `#activityMain` | `renderActivity()` (app.js:809) | `GET /api/activity` |
| `pool` | `#poolMain` | `reloadPool()` (app.js:948) | `GET /api/pool/accounts` |
| `notifications` | `#notificationsMain` | `renderNotifs()` (app.js:906) | (estado in-memory `notifications[]`) |

## Sidebar — status pills (`.sb-status`)

> Viven en el SIDEBAR (`.sb-status`), no en la topbar. La 🔔 de la topbar se eliminó 2026-06-29 (Notificaciones está en el nav izq; el badge sigue en `#navNotifBadge`).

| Pill | ID | Endpoint | Actualizado en | Significado |
|---|---|---|---|---|
| xCAPTCHA | `#stCap` | `/api/health/full` (cada N min) | `loadHealthFull()` | Saldo CapMonsterCloud (USD) |
| Proxies | `#stProxy` | `/api/health/full` | `loadHealthFull()` | Estado proxy MX |
| WSai | `#stWsai` | `/api/superadmin/kpis` | dentro de KPIs | Calls disponibles WebScraping.ai |

## Detalle de cuenta — panel INLINE (acordeón) — 2026-05-28

> **Rediseño completo 2026-05-28**: reemplaza el modal centrado `#detModalOverlay`
> por un panel que se despliega INLINE debajo de la fila (acordeón en `#accTable`).
> El `#detModalOverlay` quedó inerte (no se borró). Diseño v14: Satoshi (Fontshare)
> + iconos Phosphor (duotone/bold/fill, vía `<link>` en index.html), tokens oklch.

**Apertura/cierre**: `openDetailModal(id)` (toggle) → `_injectExpandedDetail(rebuild)`.
- El panel se inyecta como `<tr class="acc-detail-row"><td colspan=N>` con `_expandedNode`
  PRESERVADO entre re-renders de `renderTable` (no se reconstruye en cada SSE → no se
  resetea estado DOM). `rebuild=true` solo en acciones explícitas (abrir/fetch/paginar/notas).
- **Clave de hit-testing**: dentro de la tabla, solo los `<button>` reciben clicks fiables
  (divs/spans/summary "caen" a la `<table>`). Por eso TODO lo interactivo del panel es
  `<button>`: En uso, copiar CURP/tarjeta (`.d-copy`), expandir transacción (`.mhead[data-mv-toggle]`),
  paginador (`.mv-pg`), validar CURP (`.curp-validate-btn`).
- Micro-animaciones: `panelOpen`/`panelClose` (JS añade `.closing` antes de remover).
- SSE diferido: `_liveReload()` evita reconstruir la tabla mientras el panel está abierto
  (los reload de lock/unlock/deposit de otros operadores se aplican al cerrar).

**Endpoint**: `GET /api/accounts/{id}/details` → `{...persona, cards, transactions, deposit_attempts, notes, movimientos}`

**Layout v14** (`renderDetail`):
- **Barra superior**: datos (ancho = columna de movimientos, flex:5) + cluster derecho (flex:3) con **Depositar** + **En uso** (toggle amarillo, lock 2h/unlock). Datos: nombre grande + edad chica (· N) a la derecha · Dirección (completa) · Nacimiento · CURP (mono, copiable, + botón validar gob.mx que también edita/guarda).
  - **Punto de grade** (`.grade-dot`, fix 2026-07-09): junto al nombre, SOLO color (sin letra) — refuerzo visual del grade de la cuenta usando el mismo mapeo de color que la barrita `.grade-bar-cell` de la fila (A=verde, B=azul, C=ámbar, D=rojo, A+=verde brillante con glow). Tooltip on-hover muestra la letra (`title="Grade X"`); Robert pidió explícitamente que NO se muestre como texto visible.
- **2 columnas**: izquierda **Movimientos** (unificados `d.movimientos`: nuestros con ⚡ + "quién" inline + expand revela tarjeta + estado Approved/Rejected/3DS a la derecha; de la página con 🌐), paginador interno 10/pág (`_mvPage`). Derecha **Guardado** (💳 tarjetas + 📝 notas en filas, colapsable, con Agregar; auto-guarda tarjeta al aprobar).
  - **Etiqueta de estado** (`_mvDesc`/`_mvResultCls` en `pantalla.js`, fix 2026-07-06): `"Rechazado (banco)"` (rojo) **SOLO** cuando `state==='fail'` (backend `status='rejected'` = rechazo REAL de banco). Los no-banco (rate-limit/infra/cuenta/nuestro lado) llegan como `state==='incomplete'` → `"No aplicado"` (neutral); el motivo real (ej. "rate-limit 429") va en el expand. Un `state` desconocido pinta neutral, nunca "aprobado". Ver `docs/ERRORS.md` 2026-07-06.
- Estado por color SOLO en el ícono (montos en blanco uniforme); fallidas: "Depósito" + ícono en rojo, resto igual.
- CURP estimado: `computeCurp()` + `_detectStateCode()` (fix 2026-05-28: "COL"=Colonia ya no se confunde con Colima; "MEX"→MC).

## Drawer Depósito (`#depDrawer`) — 2026-05-25

> Reemplaza al ex-modal centrado `#depModalOverlay`. **No bloqueante**: el dashboard
> atrás sigue interactuable mientras el drawer está abierto. Slide-in 260ms desde
> el borde derecho. Ancho fijo 420px (100vw en mobile <600px). Z-index 150.
>
> El **mini-pill flotante** `#depMissionPill` (abajo-derecha) aparece si el drawer
> se cierra durante una misión activa (scheduled o matchmaker). Click reabre.
> La misión sigue corriendo en backend aunque el drawer esté cerrado.

**Collapse / expand (rail mode)** — 2026-05-26 (`#depDrawerCollapseBtn` `»` ↔ `«`):
- Click en el `»` del header → drawer se contrae a un rail de 36px; el contenido se oculta y el body sigue empujado pero solo en 36px.
- Click en el `«` del rail → vuelve a 420px.
- Estado persistente en `localStorage['depDrawerCollapsed']` (`'1'` / `'0'`).
- Al abrir el drawer desde una acción explícita (botón Depositar / Nueva misión / reabrir pill), si estaba colapsado se auto-expande — Robert no se queda viendo un rail vacío sin saber por qué.
- CSS: clase `dep-drawer-collapsed` en `#depDrawer` + `body`. Hace `display:none` a `title/tabs/close/body/footer` y deja solo el botón de expand visible.

**Cancel de misión scheduled** — 2026-05-26 (`#depSchedCancel` `⏹ Cancelar misión`):
- Mientras `_schedActive` está vivo, el footer del drawer reemplaza `#depExec` (Ejecutar) por `#depSchedCancel` (rojo, danger). TDAH-friendly: el botón de aborto es siempre visible, no escondido.
- Click → `confirm()` → `POST /api/deposits/scheduled/{sched_id}/cancel` → backend hace `task.cancel()`, el loop sale por `CancelledError` y emite `scheduled_cancelled`.
- El handler SSE `_schedOnCancelled` muestra "⏹ Misión cancelada", limpia timers y restaura el botón Ejecutar.

**Rehidratación de misión scheduled al recargar** — 2026-05-26, **motor cambiado a v8 el 2026-07-26**:
- Tras `loadMe()` + `reload()` + `connectSSE()`, el init llama `window.rehydrateDepos()` (motor v8, `depos.js`) con
  fallback a `rehydrateActiveScheduled()` (drawer legacy) SOLO si `window.rehydrateDepos` no cargó.
  **`rehydrateActiveScheduled()` ya NO es el call site real** — quedó como fallback de carga, no se debe volver a
  cablear como default (ver `docs/ERRORS.md` §"Rehydrate de misión Programada SIEMPRE reabría el drawer viejo").
- `window.rehydrateDepos` (`depos.js`, alias de `rehydrateScheduled()`) hace fetch a
  `GET /api/deposits/scheduled/list`, prioriza la misión del operador actual (`state.user.telegram_id`) sobre
  `active[0]` si hay varias activas (SA ve todas), y llama `window.openDepos({accounts:[...]})` — reabre el popup
  flotante v8 (o el panel compacto si `_dx.target==='compact'` ya estaba montado), no el drawer legacy.
- Backend trackea `current_iter` en `_active_schedules[sid]["current_iter"]` (actualizado por el loop antes de cada iter). Sin esto, el frontend mostraba "0/N" hasta que llegara el primer `scheduled_phase` post-refresh.
- Justificación TDAH: el operador puede recargar (intencional o accidentalmente) y NO perder de vista la misión. El flujo conductual se mantiene — sigue siendo obvio qué está corriendo.

3 modos seleccionables con tabs `#depModeSeg .dep-drawer-tab`:

| Modo | Estado interno | Endpoint | Handler |
|---|---|---|---|
| `single` | `_depMode = 'single'` | `POST /api/deposits/execute-stream` (SSE) | `executeDeposit()` SINGLE branch + `_handleExecStreamEvent()` — live phase stepper `#depStepper` (4 pasos: login/begin/submit/check) |
| `multi` | `_depMode = 'multi'` | `POST /api/deposits/multi/stream` (SSE) | `executeMatchmaker()` |
| `schedule` | `_depMode = 'schedule'` | `POST /api/deposits/scheduled/create` | `executeScheduled(pipe, amount)` |

**Inputs principales**:
- `#depCardPipe` — single/schedule (1 tarjeta `num|MM/YY|CVV`)
- `#depMultiPool` — multi (textarea con N tarjetas, 1 por línea)
- `#depCustomAmount` — monto custom (`#depAmounts` tiene presets)
- `#depScheduleBlock` — solo schedule, número de repeticiones

**Output / Match view**:
- `#depResult` — resultado del single/schedule
- `#depMatchView` + `#depFeed` — feed live del matchmaker SSE

## Modal Depósitos v8 (`#depos`, C1) — DEFAULT

Componente vanilla autocontenido (`static/depos.js` + `depos_logic.js` + `depos.css`). Clona `#deposTpl` en `#deposRoot`. **Default desde 2026-06-28** (commit `ae40021`); opt-out con `localStorage.deposV8='0'` (escape hatch al drawer viejo). Lógica pura testeada en `DeposLogic`.

### Cableado de eventos backend↔frontend (depos.js) — contrato y fixes 2026-06-28

El panel mapea por `ev.type` (streams single/multi) y `ev.kind` (bus `/api/events`, scheduled). Desajustes de nombre/índice rompen el panel sin tocar el motor. Reglas vigentes:

- **SINGLE** (`runSingle`, stream `/execute-stream`): `phase`→escena+%+label (`DeposLogic.mapPhaseToScene`/`phaseToPct`); `done`→acreditado/real-rejection/error. **Balance "después"**: el provisional (`fromBal+amount`) NO pisa el balance fresco — `account_refreshed` (bus) llega ANTES del `done` del stream (el wrapper hace `await deposit_task` que espera el refresh, deposits.py:1272 vs 1420); flag `_dx.balRefreshed` lo protege (L2).
- **MATCHMAKER** (`runMulti`, stream `/multi/stream`): cada `trying` crea/reusa la fila por email en `_mmRows` (reuso evita filas huérfanas en reintentos). **Todo evento terminal limpia su fila** o el spinner-dorado queda colgado: `match`/`account_aplus`→ok, `rejected`→wait|borra, `account_dead`→wait, **`account_cooling`→`skip` "en pausa ~Nm"** (anti-rate-limit Capa 3 — sin este case la fila quedaba colgada), **`velocity_skip`→`skip` "saltada"**, `error`→borra, `retry`/`login_retry`→escena retry. `card_retired`/`cooldown` no tienen fila por cuenta.
- **SCHEDULED** (`_schedOnBus`, bus): el backend manda `iter` **1-indexed** (`iter_num = completed+1`). El frontend NO vuelve a sumar 1 (causaba off-by-one: terminaba una rep antes y ocultaba la última). `s.iter`/`s.done = ev.iter`; `schedFinish` cuando `s.done >= total`. `3DS`→premium A+ (no "fallo"); `RATE_LIMITED`→"en pausa"; rechazo real→humanizado.
- **Estados visuales** (`depos.css` `.mov-dot`/`.mov-tag`): `ok` (verde) · `wait` (dorado=en curso) · `skip` (gris neutro=terminal no-aprobado: enfriando/saltada). Añadir un `kind`/`type` nuevo en el backend ⇒ agregar su case aquí.

### Modo Auto del drawer (Task F — 2026-07-28)

Entrada: `openDepos({ mode: 'auto' })` (botón `#cmdAutoDeposit`, ver sección abajo). Contrato backend: `POST /api/deposits/auto` + SSE `kind:'auto_mission'` (ver `docs/SSE_EVENTS.md`).

- **Modo forzado:** `deriveMode(n, reps, forced)` — `forced='auto'` gana a cuentas/reps (`depos_logic.js:11`). `presetsForMode('auto')` = `[150]`, sin manual, sin reps, `cardsOnly:true`. El drawer guarda `_dx.forcedMode` y `refreshMode()` lo pasa como 3er arg.
- **UI cards-only:** `applyAutoUI(true)` pone la clase `.auto-mode` en `#depos` — CSS oculta la columna de cuentas (`.duo .col:first-child`) y toda la `.row2` (monto/reps), deja solo tarjetas + botón **🤖 GO** con glow (`@keyframes auto-glow`). Banner guía inyectado ("Pega las tarjetas y el sistema hace el resto") + título fijo "🤖 Modo Auto" (no rota greetings). Todo vía clase/DOM inyectado — `index.html` intacto.
- **Flujo:** GO → valida pipes → **preview** inline (`.auto-preview`: "Voy a buscar las mejores cuentas para estas N tarjetas. ¿Dale?") → `POST /api/deposits/auto {card_pipes}` → `mission_id` → escenas vía bus propio (`onBusEvent` → `_autoOnBus`, con buffer anti-carrera hasta tener `mission_id`, patrón `_schedOnBus`).
- **Escenas nuevas** (inyectadas en `#scene-stage` por `injectAutoScenes()` al montar, mismo patrón `.scene` + keyframes por prefijo): `#scene-matching` (`mm-*`: tarjetas a la izq, cuentas a la der, línea SVG animada `mm-draw` al match + mascota 🤖 `mm-bob`/`mm-win`) y `#scene-scheduling` (`sc-*`: progress bar + countdown 60s reutilizando `startSchedCountdown`/`#etaSeg`). Resumen final reusa `#scene-done` ("Se depositaron $X en Y cuentas · Z aprobados, W fallidos").
- **Stop:** el `#abort` existente (siempre visible durante el run vía `runrow.on`) → `POST /api/deposits/auto/{mission_id}/cancel` (branch `_dx.auto` en `onAbort`). Cancel cooperativo del orquestador.
- **app.js:** `connectSSE` tiene un `else if (ev.kind === 'auto_mission')` solo para notifs de hitos terminales (🤖 completada / ❌ falló / 🛑 detenida); la fila del feed entra por el `pushActivityEvent()` genérico.

**Chips de cuentas/tarjetas — interacción (2026-06-27):**
- Cada chip = `<span class="chip">` con `[.txt.copyable, .chip-x]` (cuentas además llevan `.hdot` de grado al inicio).
- **Copiar:** SOLO el `.txt` es `.copyable` (lleva `data-copy`=combo/pipe). Click en el texto → copia al portapapeles (`showToast('copiado')`). El listener vive en `el` y resuelve `e.target.closest('.copyable')`. Hover del texto → verde (`--aqua`) = señal de copiable.
- **Quitar (tachita `×`):** `.chip-x` es zona propia con hit-area cómoda (`padding:4px 6px`, `margin-left:auto`). Quita el ítem **solo de la misión en curso** (muta `_dx.accounts`/`_dx.cards` en memoria + re-render). **NO toca la BD** — cero fetch DELETE. `title` lo aclara al operador.
  - Cuentas: listener en `#accChips` → lee `data-copy` del `.txt[data-copy]` → filtra `_dx.accounts` por email → `renderAccounts()` + `refreshMode()`.
  - Tarjetas: listener en `#cardChips` → `data-idx` de la X → `_dx.cards.splice(idx,1)` → `renderCards()`.
- **Por qué texto-copia y no toda-la-cápsula:** cuando toda la cápsula era `.copyable`, el área de copiar competía con la tachita (13px) y la volvía inusable. Separar zonas libera la X. Render en `renderAccounts()`/`renderCards()` usa `createElement`/`textContent` (seguro ante comillas/`<>` en passwords).

### Ventana manipulable (`static/depos_window.js`) — 2026-06-27

El modal v8 es una **ventana flotante libre** (sin backdrop bloqueante; se usa el dashboard detrás). Controlador en `depos_window.js` (vanilla, patrón adaptado de Rita). Spec: `docs/superpowers/specs/2026-06-27-ventana-flotante-depositos-design.md`.

- **3 estados:** `float` (movible + resize por bordes) · `left` / `right` (acoplada a la tabla). Sin maximizar/minimizar.
- **Geometría pura** en `window.DeposWindowGeo` (testeable: `node static/depos_window.test.js`, 32 casos): `clamp`, `floatBounds`, `edgesAt`/`cursorFor`, `resizeRect`, `dockRect`, `dockWidthFromPointer`, `snapZone`.
- **Zona de arrastre = el header** (`.head`: banner/personaje + greeting bocadillo se mantienen, compactos en modo ventana). Los **controles** (`.dw-ctl`: `.dw-dock-l` / `.dw-dock-r` / `.dw-close`) flotan en la esquina sup-der (`injectWindow()`). El `newproc` ("Otro depósito") se oculta en ventana para ganar espacio. Todo el contenido se compacta (`#depos.dw-on`) para caber sin scroll en flotante y acoplado.
- **Drag**: por la barra; `position:fixed`+`left/top`; cancela animaciones en vuelo; snap-hint (`.dw-hint`) al acercar a un lado; al soltar en zona de snap → acopla. **Resize**: proximidad de bordes (8px) solo en float, min 360×500, clamp a viewport. **Transiciones suprimidas** durante drag/resize (tracking nítido).
- **Dock acotado a la tabla**: el panel se confina a `#accDockZone` (wrapper de `filterbar`+`tablewrap`+`pagebar` en `#accountsMain`; las cards de arriba y el sidebar NO se tocan). Comprime la zona vía `#accDockZone.dock-l/.dock-r{padding:var(--dock-w)}` (animado en `style.css`). **Divisor** (`.dw-divider`) en el borde interno recorre el ancho del split (min/max, deja ≥240px a la tabla).
- **Sin scroll** (regla de Robert): `.bmx` es flex column `overflow:hidden`; `.journey`/`.scene-stage` toman el espacio (flex), `.mov` recorta (`overflow:hidden`, antes tenía `overflow:auto`). El min-size garantiza que el contenido cabe.
- **Persistencia**: estado + geometría en `localStorage.deposWin`. `openDepos` → `_win.show()` (aplica lo guardado); `closeDepos` → `_win.hide()` (suelta la compresión, conserva estado). Click-fuera ya NO cierra (es ventana): cierra por `.dw-close` o Esc.
- **Degradación**: si `depos_window.js` no carga, el modal abre sin la ventana (no se rompe).

## Command Bar (`#cmdBar`)

Visible cuando `selectedIds.size > 0`. Actualizado por `updateCmdBar()` (app.js:602).

| Botón | ID | Acción |
|---|---|---|
| 💳 Depositar | `#cmdDeposit` | Abre modal depósito (single si 1, multi si 2-5) |
| 🔒 Lock Nh | `#cmdLock` + `#cmdLockHours` | Lock por N horas (default 2h, click cambia) |
| 📤 Trastienda | `#cmdTrastienda` | Toggle visibilidad pool |
| 🎁 Liberar | `#cmdRelease` | Asignar a operador (SA) |
| Deseleccionar | `#cmdDeselect` | Limpia `selectedIds` |
| (count) | `#cmdSelCount` | número de cuentas seleccionadas |
| (stats) | `#cmdStats` | suma total potencial / status mixto |

## Botón Modo Auto (`#cmdAutoDeposit`)

Vive en `.pb-center` de la `.pagebar` (NO en `.pb-actions` — siempre visible, con o sin selección), como sibling de `<span id="pbPages">` para sobrevivir los re-renders del paginador (`innerHTML`). Solo SA: gate `state.user?.role !== 'superadmin'` → toast; si no `openDepos({ mode: 'auto' })`. Estilo `.act-auto` (gradiente verde + keyframes `autoGlow`); override `.pagebar.has-sel .pb-center .act-auto { opacity: 1 }` para que el dimming de `.pb-center` (`.has-sel` → `opacity .45`) no lo apague con selección activa.

## Tabla principal (`#accTable`)

**Render**: `renderTable()` (app.js:450).
**Source**: `state.rows[]` (todas) o `getVisible()` (filtradas).

**Handler global** (app.js:2034 — `#accTable.click`):
| Target | Acción |
|---|---|
| `.row-ic` (iconitos 💳/📝/+) | 💳/📝 abren el **acordeón viejo** (`openDetailModal` — acceso a EDICIÓN de tarjetas/notas + validar CURP); `+` = quick-add note |
| `th.th-sort` | Ordena por columna |
| `td.combo` (celda + `<b>`) | **Click izquierdo abre La Pantalla** (ya NO copia — fix 2026-07-03; el copiado del combo vive DENTRO de La Pantalla). Se le quitó `d-copy`/`data-combo`. |
| Fila (click simple) | **Abre La Pantalla** (`window.Pantalla.open`) — Fase B |
| Fila + **Ctrl/Cmd** | Toggle esa fila en la selección múltiple (Excel) |
| Fila + **Shift** | Rango desde la última clickeada (`_selectRange`, orden visible) |
| **Arrastrar sobre filas (>6px)** | **Marquee tipo Explorer** (Fase C `initMarquee`): dibuja recuadro `.sel-marquee` y selecciona las filas que toca. `Ctrl`+arrastre = suma a la selección previa. |

**Marquee (Fase C, recuadro tipo Windows Explorer):** reintroduce el drag-select que se había retirado en Fase B, ahora reconciliado con el click→La Pantalla vía **umbral de movimiento (6px)**. Handlers globales (`mousedown`/`mousemove`/`mouseup`) en `initMarquee`: arranca solo sobre una fila de `#accTable` (no sobre `.row-ic`/botones/inputs/`.acc-detail`), ignora `Shift` (=rango). Cruzado el umbral, crea `.sel-marquee` (`position:fixed`, coords de viewport) y llama `applyBand()` que resalta las filas con solape vertical. Al soltar, `_marqueeSuppress=true` evita que el `click` sintético abra La Pantalla de la última fila tocada. Click sin mover = sigue abriendo La Pantalla.

**Retirado (Fase B):** contextmenu (click derecho), checkboxes `.rowsel`/`#selAll`, y el drag-select por **pointer** (el drag-select por mouse volvió en Fase C con umbral, ver arriba). La selección múltiple es Ctrl/Shift+Click **o** marquee.

**Columna Saldo (`td.num` / `th.num`)** — `style.css:1075`:
- `width: 128px; min-width: 128px; white-space: nowrap;`
- El ancho cabe `$X,XXX.XX` + botón ↻ (22px + 6px margen) sin wrap. Antes era 92px y con montos 4+ dígitos el botón saltaba a la línea siguiente, ensanchando la fila. Cualquier ajuste futuro debe verificar que `$99,999.99 ↻` cabe.

**Tiers visuales del saldo** — `balanceCls(v)` en `app.js:322` + `.balance.{low,mid,hot}` en `style.css:1170+` (cambio 2026-05-26):

| Rango | Clase | Render |
|---|---|---|
| `< $10`        | `.low` | Gris (`--text-muted`), peso 500, sin glow |
| `$10 – $49.99` | `.mid` | Blanco (`--text`), peso 600, sin glow |
| `≥ $50`        | `.hot` | Verde radiactivo (`oklch(0.86 0.26 142)`), peso 700, glow multi-capa + animación `balanceHotPulse` 2.6s ease-in-out infinite alternate (tintilante lento entre opacidad 0.88 ↔ 1.0 y glow tenue ↔ intenso). Respeta `prefers-reduced-motion`. |

Reemplazó el sistema viejo (`zero`/`dim-amount`/`glow` con cortes en $5/$10). Si cambian los umbrales, actualizar ambos puntos a la vez (JS + CSS docstring).

## Strip superior (`#adminPanel`) — reorg 2026-07-05 (3 cards → 2 KPIs)

> **REEMPLAZA la reorg 2026-06-29 de abajo** (histórico preservado más abajo en esta sección para contexto). El grid `.lpanel` pasó de **5 tracks** (3 cards: Actividad Live | Recientes | Pool) a **3 tracks** (2 cards + 1 `.lp-gutter`). Spec: 2 KPIs — Logs (traza técnica/operativa) + Cuentas a la mano (por-cuenta, no por-evento).

| Card | ID / `data-mod` | Contenido | Fuente |
|---|---|---|---|
| **📋 Logs** | `#lpActivity` (`data-mod="activity"`) | Feed vertical scrolleable **cronológico único** (nada pineado por tipo) con **cabeceras de día** (Hoy/Ayer/fecha MX). Agrupa `deposit_step` en traza por intento (`✓login ✓begin ✗submit → CODE`), muestra `account_touch` (`👁 {who} abrió {target}`), fallos de otras acciones. 2 idiomas por rol (ver abajo). | SSE bus `/api/events` (`_LOGS_KINDS`: incluye `deposit_step`, `account_touch`, `deposit`, etc.) |
| **📌 Cuentas a la mano** | `#lpRecientes` (`data-mod="recientes"`) | Por-cuenta (no por-evento): 2 secciones — **Pineadas ★** (marks del usuario) y **Recientes ·** (depósitos/locks/marks propios). Cada fila: **combo `email:password` copiable (protagonista, mono)** + nombre chico/suave al lado, estado (badge SOLO si bloqueada/DEAD — LIVE no muestra badge), balance, grade `[A-D]`. | `GET /api/accounts/at-hand` (`_atHandRow`/`renderRecientes`, app.js) |

**Card `Pool` ELIMINADO** (ya no existe ni como card SA ni operador). `renderPoolCard` borrado del JS. **Online** ya vivía en sidebar (`.sb-online`, solo-SA) desde la reorg anterior — sin cambio.

### 📋 Logs — 2 idiomas por rol

`_DEPOSIT_CODE_HUMANO` (app.js, extiende `_humanizeCritical`) traduce el `code` técnico de `deposit_step`/`deposit` (`RATE_LIMITED`, `LOGIN_DENIED`, `PROXY_FAILOVER_EXHAUSTED`, etc.) a lenguaje llano — mismo principio que el resto del dashboard (E-RED, capas operador vs backend): el operador NUNCA ve `result_code` crudo ni jerga interna; el SA puede ver más detalle técnico (traza completa login/begin/submit/check). Click en una fila → `Pantalla.open(id)`; el combo es copiable.

### 📋 Logs — orden cronológico + día (fix 2026-07-05)

El feed combina eventos cuyos `ts` vienen en **formatos y zonas mezclados** (medido en prod): `account_touch`/`deposit_step` en **hora MX naive** (`"2026-07-05 15:22:43"`), `deposit`/`note`/`prewarm` en **UTC naive** (`created_at`), `lock` en **UTC con tz** (`"...T21:23:10+00:00"`). El sort viejo comparaba strings crudos → el separador `'T'` (0x54) ganaba a `' '` (0x20) y los locks quedaban pineados arriba sin importar la hora. **Fix**: `_feedEpoch(ts, kind)` (app.js) colapsa todo a **epoch ms absoluto** (respeta tz explícita; los `_MX_NAIVE_KINDS` suman 6h); `renderActivityMarquee` ordena por epoch y muestra hora/día en tz MX vía `_exactHoraEp`/`_dayLabelEp`/`_mxYmd` (`Intl.DateTimeFormat` `America/Mexico_City`). Corrige de paso el `+6h` que tenían deposit/lock por interpretar su UTC como hora local. Cabecera `.lp-feed-day` se inserta al cambiar de día. Ver `docs/ERRORS.md`.

### 📋 Logs — agrupación, dedup, color y silencio de alertas (2026-07-05)

Cuatro ajustes sobre el feed (pedidos por Robert operando en prod):
- **Depósitos agrupados**: repeticiones con misma `(operador, cuenta, resultado, monto, día MX)` colapsan en **una fila representante** (la más nueva) con badge **`▸ ×N`**. Click en el badge (`[data-grp-toggle]`, `_feedExpanded` Set) despliega las repeticiones sublistadas (`.lp-feed-kid`) cada una con su hora; click en el cuerpo abre la cuenta. `deposit_step` sigue agrupándose aparte por corrida.
- **`account_touch` dedup**: en el feed, **1 por (operador, cuenta, día MX)** — no spamear "X entró a la misma cuenta". El registro completo persiste en `account_touches` (BD); es dedup de presentación.
- **Color por operador**: `_whoDot(who_color)` pinta un `●` con el color del operador (`.lp-feed-dot` + `.lp-color-*`, esquema `USER_COLORS`: RobertVS=warn, Lau=purple, Luisito=accent, Magdiel=azure) al inicio de cada fila en vista SA → ubicación visual rápida de quién hizo qué. `GET /api/activity` ahora incluye `who_color`/`who_id` en deposit/lock/note/prewarm (antes solo los eventos SSE en vivo lo traían).
- **Alertas de servicio fuera del feed y de notificaciones**: `health_warning` y `type:'alert'` (capmonster sin saldo, proxy caído) **ya no** hacen `pushNotif`/`toast` ni se inyectan como `critical_error` al feed — el polling de salud las reemitía en bucle y spameaban. El estado sigue visible en el indicador de salud del header (`stCap`). `critical_error` salió de `_LOGS_KINDS`.

### 📌 Cuentas a la mano — consumo del endpoint

`renderRecientes(data)` (app.js) recibe `{pinned, recent}` de `GET /api/accounts/at-hand` (fetch en `athand` — app.js:6050). `_atHandRow(it, {pinned})` arma cada fila; `_atHandStatus(it)` resuelve el badge de estado con prioridad **DEAD > 🔒 bloqueada > (LIVE = sin badge)**. Reemplaza a `renderRecientes` viejo (que consumía `/api/recent`, por-evento) — el nuevo endpoint resuelve `email→id` server-side, cosa que `/api/recent` no daba (evitaba que el click abriera La Pantalla directo).

**Jerarquía (2026-07-05)**: el **combo `email:password` es el protagonista** (`.lp-recent-combo`, mono, lo que el operador copia/usa); el **nombre** va chico y suave al lado (`.lp-recent-name`, sans, `--text-dim`, `max-width:40%`), solo como referencia. El badge de estado **solo habla cuando orienta**: `🔒 bloqueada` (guardarraíl) o `DEAD` (no tocar). `LIVE` es el default usable → **sin badge** (ausencia = agárrala); mostrar "LIVE" era adorno sin criterio.

### ⚠️ Regresión conocida: filtro "en uso" quedó sin acceso en la UI

El botón `#lpInUse` (toggle `state.filterInUse` — filtra la tabla a solo cuentas con lock activo) y su compañero `#lpPool` vivían **dentro del card Pool** (`static/app.js:5950-5962`, listeners aún presentes en el JS; **no se borraron**). Al eliminar el card Pool del HTML (`static/index.html`, solo quedan los 2 `.lp-card` de arriba), esos botones **ya no tienen contenedor en el DOM** → inaccesibles desde la UI. No crashea (los `addEventListener` con `?.` simplemente no encuentran el elemento); `state.filterInUse` queda permanentemente en `false`. **Pendiente**: decidir si se reubica el filtro (ej. dentro de la filterbar de Cuentas) o se retira el código muerto.

localStorage: `bmx.lpCols.v1` → `v2` y `bmx.lpOrder.v1` → `v2` (invalidan ratios de ancho / orden de módulos guardados de la era 3-columnas; `initLpResize`/`initStripReorder` limpian la key vieja al leer).

## Strip superior — reorg 2026-06-29 (histórico, superada arriba)

`#adminPanel` (`.lpanel`) pasó de **4 cards** (Online | Feed | Alertas | Pool) a **3 cards** y de ser solo-SA a **visible para todos** (contenido filtrado por rol server-side).

| Card | ID | Contenido SA | Contenido Operador | Endpoint |
|---|---|---|---|---|
| **Actividad Live** | `#lpActivity` | Todo el feed humanizado (marquesina) | Solo sus propias acciones | `GET /api/activity` |
| **Recientes** | `#lpRecientes` | Cuentas de Robert con las que interactuó | Cuentas propias (depósitos + locks + marcadas) | `GET /api/recent` |
| **Pool** | `#lpPoolCard` | Salud del pool (grid 4-stat) + botón "Gestionar pool" → `#poolMain` | "Mis stats del día" (intentos/aprobados/monto/tasa) | `GET /api/recent` stats / kpis.pool |

**Online** salió del strip → sidebar (`.sb-online`), solo-SA.

### Ajustes 2026-06-29 (3) — feedback Robert (cenefa + interacción cuentas)

- **Cenefa superior** — ver §Branding. Banda de marca delgada en el top del top.
- **Búsqueda DOMINANTE que ignora filtros** (`fetchAccounts` + `getVisible`). Con `searchQuery` activo, la consulta va con `status=all` y SIN `grade`/`cards_only` → corre sobre TODOS los registros (Robert: "la búsqueda nunca se entorpece ni por el filtro ni por la vista"). `getVisible()` también ignora `filterInUse` mientras hay query. La UI lo refleja (`_reflectSearchUI`): el buscador se ilumina (`.search.has-query`) y los filtros que ya no aplican se atenúan (`body.searching`). Filtros propios de búsqueda = pendiente futuro.
- **Botón X en el buscador** (`#searchClear`): aparece con query, limpia + `reload()` + devuelve el foco al input (`_clearSearch`, también con `Esc`). Restaura la vista sin tocar los filtros previos.
- **Botón Restaurar reubicado** (`#btnResetFilters` → dentro de `.filterbar`, junto a los filtros). Antes vivía en la `.pagebar` abajo y "nadie lo clickeaba, no se sabía qué restauraba". Ahora `.reset-btn`: atenuado en default (disabled vía `_updateResetBtn`), verde cuando hay algo que restaurar.
- **Card del strip que se salía de pantalla** — ver `docs/ERRORS.md` §"Pool card desbordada". Root cause: `availW()` en `initLpResize` no restaba el padding del `.lpanel`.

### Ajustes 2026-06-29 (2) — feedback Robert sesión limpia

- **Buscador → filterbar de Cuentas.** Salió del sidebar y se incrustó en `.filterbar` junto al `<h2>Cuentas</h2>`, antes de los filtros (`.filterbar .search.filterbar-search`). Conserva `id="searchInput"` + cableado `q=`. **Ctrl+K** ahora salta a la vista Cuentas antes de enfocar (app.js).
- **Vista única.** El toggle Simple/Detallada (`.seg[data-seg="view"]`) se **eliminó** del DOM. `state.view` queda fijo en `'detail'` para todos (antes operadores forzados a `'simple'`). La tabla siempre muestra 9 columnas (incluye `Últ. check` + `Checks`). `_detailColspan()` fallback → 9.
- **Sidebar — cajas de fondo encajadas.** Online + status se agruparon en `.sb-bottom` (margin único, gap 6px) y el `.grow` se movió ARRIBA del grupo → Online baja y queda pegado al status como un par cohesivo (antes el `.grow` los separaba con un hueco grande).
- **Divisores arrastrables del strip** (`.lp-gutter` ×2, patrón Claude Desktop). Entre Actividad↔Recientes y Recientes↔Pool. Arrastra para repartir el ancho de los cards adyacentes (min 150px c/u); **doble-click restaura**. `initLpResize()` (app.js) persiste proporciones en `localStorage['bmx.lpCols.v1']` (resiliente a resize de ventana). Grid del `.lpanel` = 5 tracks (`var(--lpc0/1/2)` con fallback fr + `--lp-gw`).
- **~~Divisor horizontal del strip (`.lp-vgutter`, ↕ row-resize, doble-click restaura)~~ — ELIMINADO 2026-07-09** (Robert: "ya no debería haber drag/collapse ni de los KPI ni de la pantalla, se quedan fijos"). En su lugar `<div class="lp-vspacer">` (10px fijo, sin interactividad) entre `.lpanel` y `#accDockZone`. El alto del panel ya no se arrastra ni persiste en `localStorage` — lo fija `initLpVResize()` UNA vez al cargar vía `ANCHOR_H` (ver sección "La Pantalla" más abajo: alineado con `#sbSectionSistema`). Detalle completo + `window.KpiPanel` reducido en la sección de La Pantalla.
  - **Sin distorsión**: `.lp-recent-row { flex-shrink:0; min-height:19px }` — las filas mantienen altura y el contenedor las **recorta** (antes se aplastaban → texto distorsionado). `.lp-feed-rows`/`.lp-alert-rows` = `flex:1; min-height:0` con **fade `mask-image`** abajo (recorte estético).
  - **Micro-animación suave**: `transition: height var(--ease)` en `.lpanel`; durante el drag se añade `.lp-resizing` (transition:none = tracking directo). El dblclick anima el reset al default.
  - `.lp-card` = `overflow:hidden; min-height:0`.
- **Fluidez estándar.** Tokens `--ease-fast`/`--ease`/`--ease-curve` en `:root` (mismo curvado que depos.css `--t-fast`/`--t`). Aplicados con feedback táctil (`:active` scale/translate) a `.nav`, `.seg button`, `.seg-btn`, `.ico-btn`.

### Ajustes 2026-06-29 (3) — refinamiento de diseño (auditoría → prod)

Derivado de la auditoría doble (anti-burnout TDAH + diseñador senior premium; mockup en `docs/mockups/2026-06-29-main-view-refined.html`). Piezas de mayor impacto / menor riesgo, **aditivas y reversibles** (puro CSS/markup/render, cero backend):

- **RECIENTES escaneable por estado.** `renderRecientes()` ahora pone clase por `reason`: `rec-use` (lock → "en uso", riel+chip verde), `rec-dep` (deposit → "depósito", oro), `rec-mark` (mark → "fijada", púrpura). Riel izquierdo de color + chip de estado + edad alineada a la derecha. Antes: 20 combos en mono, mismo peso → muro ilegible.
- **POOL con peso ("salud de un vistazo").** Card SA gana hero (número grande `#lpPoolHeroNum` = pool disponible) + barra de salud `#lpPoolBar` (free verde / used ámbar, poblada en `refreshKpis`). El 4-stat grid se conserva. Operador (Mis stats del día): hero+barra se ocultan en `renderPoolCard`.
- **Token `--gold`** (`oklch(0.82 0.14 85)`) — semántica de DINERO, coherente con el oro del panel de depósitos. Usado en RECIENTES depósito.
- **Calma de motion.** `@media (prefers-reduced-motion: reduce)` desactiva ticker de marquesina + pulsos (`.lp-dot.live`, `.lp-pulse`).

Cache-bust `20260629d`. Deploy KVM4 (static hot-mount) + md5 servido==repo + health 200 + marcadores verificados.

**Pendiente como propuesta (necesita ojo al pixel de Robert, NO deployado):** unificación tipográfica (reducir roles), reestilizado global de acabados. Ver el mockup.

## Actividad Live — marquesina (`#lpActivity`)

**Render**: `renderActivityMarquee()` (app.js). **Source**: `activityRows[]` (carga inicial `/api/activity` + push via SSE).

- **Dedup**: `ActivityLogic.dedupeActivity()` — key `sched_id+iter` para scheduled (colapsa el doble-evento `scheduled`/`scheduled_aborted`); key `kind+target+amount+ts_minuto` para el resto.
- **Buffer**: 30 eventos; desfilan 10 en pantalla. Animación (desfile CSS), **sin `overflow:auto`**.
- **Velocidad adaptativa** (2026-06-29): `renderActivityMarquee` fija `animationDuration = max(30, N*2.2)s` inline en `.lp-ticker-track` (antes 20s fijos = veloz con 30 eventos, imposible de clickear). Ritmo constante sin importar el # de eventos; pausa al hover (CSS) para clickear cómodo.
- **Copy humano**: `ActivityLogic.formatActivityCopy(ev, viewerIsSA)` — títulares sin jerga (ver spec §9). No-SA ve "Tú" en lugar del nombre del operador.
- **Errores críticos**: SSE `capmonster_low`/`proxy_down`/`health_warning` se convierten en `{kind:'critical_error', msg}` humanizados y se insertan en el feed.
- **Click en fila** → `openAccountByEmail(email)` → resuelve email→id (`/api/accounts?status=all&q=`) y abre `openDetailModal`. **SIN fallback a búsqueda** (Robert: "no buscarla, eso es torpe"); si no resuelve → toast "No encontré esa cuenta". **Click en header** → `showSection('activity')` (panel completo).
- Archivo de lógica pura: `static/activity_logic.js` (IIFE/UMD, testeable con `node`).

## Recientes + Marcador (`#lpRecientes`)

**Render**: `renderRecientes()`. **Source**: `GET /api/recent`.

- Lista las cuentas con las que el usuario interactuó: depositó, tiene en uso (lock activo), o **fijó** (marcó).
- **Click en la fila → copia el combo Y abre el detalle** (2026-06-29). El renglón es `.lp-recent-row.d-copy[data-email][data-copy=combo]`; el handler global de copia (capture, `app.js`) copia el combo y, al detectar `data-email`/`data-id` de cuenta, llama `openAccountByEmail`/`openDetailModal`. Mismo patrón en el **combo de la tabla** (`td.combo b[data-id]` → copia + `openDetailModal(id)`). Los `d-copy` de tarjeta/CURP/pipe NO abren detalle (no tienen id/email). Robert: "al dar click en las letras del combo, autocopia y despliega la cuenta al mismo tiempo".
- **Botón 📌 (marcador)** (`.ic-mark`): en cada fila de tabla y en el panel de detalle. Estado activo si `markedSet.has(email)`. Click → `POST /api/marks/toggle` → actualiza `markedSet` + repinta el botón + `renderRecientes()`. NO recarga la tabla (marcar no cambia visibilidad — frictionless).
- Marcar NO bloquea ni cambia `published_to_pool`. Es puro recordatorio privado.
- Sin `overflow:auto` (cabe/cicla).

## Gestor de Pool (`#poolMain`) — solo-SA

Vista partida **Fuera del pool** (`#poolOutside`) | **En el pool** (`#poolInside`). Carga via `GET /api/pool/split`.

- Cada columna: buscador propio, chips de combo `email:password` seleccionables (multi-select), barra de acción bulk.
- **Exponer** (Fuera→Dentro): pide confirmación (`confirm()`) antes de `POST /api/pool/publish {publish:true}`.
- **Sacar** (Dentro→Fuera): sin confirmación, directo.
- **"Ocultar todas"**: pide confirmación (acción masiva).
- **Drag-drop bidireccional** (HTML5 `draggable`): soltar en columna destino dispara el mismo flujo que el bulk.
- Scroll permitido aquí (sección de gestión, no card compacta).

## Feed de Actividad — panel completo (`#activityMain`)

**Render**: `renderActivity()` (app.js). **Source**: `GET /api/activity` (scoped por rol, retorna `{"feed":[...]}`).

- **Organización**: agrupado por día (Hoy / Ayer / fechas).
- **Un registro por línea**, copy humano via `ActivityLogic.formatActivityCopy`.
- **Filtros**: por tipo (depósito/lock/marca/enfriamiento/error), por operador (solo-SA — el backend ya no manda ajenos al operador), búsqueda por email.
- **Click en fila** → `openDetailModal(email)`.
- Scroll vertical permitido aquí.

**Columnas (vista tabla histórica)**: `Cuándo | Quién | Acción | Cuenta | Tarjeta | Monto | Estado` (7 cols desde 2026-05-11).

**Inputs**:
- `#actSearch` — búsqueda en email/operador/monto
- `#actOpsChips` — chips operadores activos (solo-SA)
- `#actBtnReset`, `#actBtnRefresh`
- `#actPageSize` — paginación

## Panel de depósitos — visibilidad por vista y rol (tanda 4, 2026-06-30)

`#deposRoot` es hijo directo de `<body>`. El **dock** comprime una "zona dockeable" (`#accDockZone` en Cuentas; `#logsMain`/`#activityMain` en esas vistas). **Bug anterior** (reorg 2026-06-29): al salir de Cuentas el panel pasaba a **flotante** y quedaba **encima** de la otra vista (Robert: "se queda encima de todo").

**Política nueva** — `DeposWindow.reanchorForSection(section, isSA)` aplica `DeposWindowGeo.sectionDock(section, isSA)` (lógica pura, testeada en `depos_window.test.js`):

| Vista | Operador | Superadmin |
|---|---|---|
| `accounts` | visible, dock = preferencia (default **right** = encaja en el espacio de la maqueta) | igual |
| `logs` / `activity` | **oculto** | visible, dock **left** ("sin estorbar"), zona = la vista misma |
| pool / notifications / health / admin / bin-stats | **oculto** | **oculto** |

- **Oculto = `display:none` REAL** + suelta el dock de TODAS las zonas (`clearAllZonePads`). Nunca flota encima.
- `effectiveMode()`: en logs/activity el modo efectivo es `left` sin pisar la preferencia de Cuentas (`ST.mode`). Al volver a Cuentas se recupera (default `right`).
- En logs/activity el panel queda **fijo** (no se arrastra por el header — `sectionLocked()`); el divisor de ancho sí funciona.
- El panel **no se cierra** al navegar; solo con X o Esc. `hide()` (cierre explícito) suelta todas las zonas.
- Hook en `showSection(name)` (app.js): `dw.reanchorForSection(name, state.user?.role === 'superadmin')`.
- CSS dock generalizado: `#logsMain.dock-l`/`#activityMain.dock-l` reciben el mismo `padding-left: var(--dock-w)` que `#accDockZone` (style.css).

## Tanda 4 — módulos, sidebar rail, filterbar, acabados (2026-06-30)

Feedback de Robert (AFK). Spec: `docs/superpowers/specs/2026-06-29-ui-tanda4-modulos-panel-sidebar.md`. 100% frontend, aditivo/reversible, cero backend. Cache-bust `20260630a`.

- **Strip = módulos intercambiables.** Cada `.lp-card` lleva `data-mod` (`activity`/`recientes`/`pool`) + un grip `.lp-reorder` (aparece al hover del head). Drag por el grip **intercambia (swap)** dos cards. Orden persistido en `localStorage['bmx.lpOrder.v1']`; doble-click en un grip restaura. Lógica pura `StripLogic` (`strip_logic.js` + `.test.js`, 16 casos). `initStripReorder()` (app.js) aplica el orden y recoloca los gutters **siempre entre cards** (su `data-g` por posición → el resize de `initLpResize` sigue intacto). Anchos **por slot** (posición), no por card: al reordenar cada card toma el ancho de su slot.
- **Filterbar de Cuentas reorganizada.** `💳 Con tarjeta` (`#btnCardsOnly`) y `↻ Actualizar visibles` (`#btnRefreshVisible`) subieron de la `.pagebar` a la `.filterbar` (junto a los filtros; "Actualizar visibles" justo a la derecha de Restaurar). La `.filterbar-accounts` usa `flex-wrap` + `margin-left:auto` en el primer seg (en vez de `.grow`): buscador a la izquierda, filtros a la derecha en una línea; si el ancho no alcanza (p.ej. con el panel acoplado en ventana chica) **bajan a 2ª línea sin cortarse**. Buscador `.filterbar .search` → `flex:0 1 320px; min-width:188px` (cede primero). La `.pagebar` queda solo con visibleCount · paginador · "Por página".
- **Sidebar colapsable a rail.** Botón `#sidebarToggle` (`.sb-collapse`, borde derecho del sidebar, estilo Linear/VS Code). Toggle `body.sidebar-collapsed` → `.sidebar` a **64px**: oculta labels/badges/greet/secciones/online/status; quedan iconos del nav (centrados, `font-size:0` colapsa el text-node del label, `.i` conserva su tamaño) + logo mini (40px) + avatar. Persistente `localStorage['bmx.sidebarCollapsed']`. `initSidebarCollapse()` (app.js) re-llama `DeposWindow.relayout()` al inicio y tras la transición (0.42s) para recalcular el dock.
- **Acabados premium** (`style.css`, bloque final). Grano fílmico global ultra-sutil (`body::after`, fractalNoise SVG, opacity 0.025, `pointer-events:none`); glass en `.lp-card` (velo diagonal + highlight superior + sombra de profundidad + hover lift); profundidad en cajas del sidebar; sheen en `.seg-btn`/`.seg button.on`; respiración de glow lenta en la cenefa (`@media prefers-reduced-motion: no-preference`). Cero cambios de layout.

## Tanda 5 — vista de Cuentas (2026-06-30)

- **REWORK PREMIUM (feedback Robert tras probar P4/P7).** La banda de P4 se sentía despegada/sobrepuesta, botones gigantes, filas sin compactar, info dispersa, dos barras anchas. Rediseño **medido en un harness** (`preview` sobre `static/` con el style.css real + mock) antes de portar:
  - **Barra inferior FUSIONADA** (`.pagebar`): paginador + acciones de selección en **UNA** barra. Sin selección → `pb-count` ("N de M") + paginador + "Por página". Con selección → `.pagebar.has-sel` oculta el count y muestra `.pb-actions` (botones `.act` compactos premium, con **stagger** fade+slide por hijo directo) y atenúa la paginación (`opacity .45`). La banda flotante vieja (`.cmdbar`/`.cmd-btn`) se **eliminó**; los IDs (`cmdDeposit`/`cmdLock`/`cmdTrastienda`/`cmdRelease`/`cmdDeselect`/`cmdSelCount`/`cmdStats`) se conservaron dentro de `.pb-actions` → handlers intactos. `updateCmdBar()` togglea `#pagebar.has-sel` (ya no `#cmdBar.hidden`).
  - **Botones `.act`**: 26px de alto (vs ~40 "gigantes"), `<span class="i">`+label, hover lift `var(--ease-fast)`, `.act-primary` con neón, `.act-ghost` Borrar, `.kbd` para el "2h" del Lock, `.cmd-btn-hl` para el highlight de Pool.
  - **Tabla densa + layout 2-bloques** (ajuste Robert): `tbody td { height:30px; padding:0 10px }`; `table-layout:auto` + `<colgroup>` inyectado en `renderTable`. **Saldo + Cuenta a la izquierda**; la columna **Cuenta absorbe el sobrante** (`c-cuenta: width 100%`) → el **HUECO flexible queda entre Cuenta y Últ.depósito** y **se contrae cuando el dock de depósitos se incrusta al lado** (medido en harness: 467px→162px con dock de 420px, datos siempre visibles). **Desde Últ.depósito todo va con ancho fijo, agrupado a la derecha** (pegado al borde). **Iconos en 3 columnas separadas** — orden Robert **Nota | tarjetas | pin** (`c-nota 84` / `c-cards 46` / `c-pin 40`; celdas `.ic-col`/`.ic-nota-col`); la columna "row-icons" única se eliminó. El lock-chip nunca se corta (la columna Cuenta es ancha).
  - **Selección suave + cursor**: `tbody tr { transition: background var(--ease-fast) }`; se **quitó** la barra accent del `td:first-child` (pisaba la barra de salud/grade) y el `cursor:cell` del drag (se veía feo) → `body.dragging-sel` solo bloquea `user-select`.
- **P10 — Vidrio + glow casino sutil** (bloque final de `style.css`, reversible). Construye sobre los acabados de tanda 4 sin saturar: pagebar con **vidrio real** (`backdrop-filter blur+saturate`) + **filo de luz verde-oro** arriba (`.pagebar::before`, toque casino); buscador activo con aro de glow verde + corazón dorado tenue; saldo "caliente" (≥$50) con destello verde; Depositar con corazón dorado al hover sobre el neón; filterbar con vidrio. Paleta: verde (marca) + oro (`--gold-soft`, dinero). **P9 (integración del panel de depósitos incrustado) queda pendiente** — requiere ver el dock con datos reales (flujo crítico, no se toca a ciegas).
- **P1 — Buscador premium + X interna.** `.filterbar .search` más largo (`flex:0 1 400px`, antes 320; `min-width:240`, `max-width:42vw`) con fondo más presente. La X (`#searchClear`) ahora siempre visible dentro del recuadro (fondo circular `rgba(255,255,255,.09)`, 20px, hover accent + scale). Ícono `⌕` más definido (15px) que se tiñe de accent en focus/query.
- **P8 — Memoria de la vista de Cuentas por usuario.** `bmx.acctView.<username>` (localStorage) conserva **página + tamaño de página + scrollTop** de la tabla entre sesiones. `_restoreAcctState()` aplica página/tamaño antes del primer render; `_restoreAcctScroll()` repone el scroll tras el render; `_saveAcctStateSoon()` (debounce 350ms) en el scroll de `.tablewrap`, y `_saveAcctState()` en cambios de página/tamaño. No se comparte entre operadores.
- **P7 — Interacción de la tabla (⚠️ REEMPLAZADO por Fase B 2026-07-03 — ver sección "La Pantalla").** El modelo P7 (click izq = selección, click DERECHO = detalle, drag-select) quedó obsoleto. Modelo actual: **click izq simple = abrir La Pantalla**, **Ctrl/Shift+Click = selección Excel** (sin drag ni checkboxes). Lo que sigue vigente de P7: el combo copia con click izquierdo sobre `td.combo` (copia toda la celda); la barra `accent` de fila seleccionada (`row-sel`). Lo retirado: `openDetailModal` como trigger de fila, contextmenu, `_dragSel`/drag por mouse+pointer, checkboxes `.rowsel`/`#selAll`.



Feedback de Robert tras probar la tanda 4 logueado. Spec: `docs/superpowers/specs/2026-06-30-tanda5-vista-cuentas.md`. Cache-bust `20260630b`.

- **P2 — Paginación real (no esconder cuentas).** Síntoma: el contador decía "500 / 845" pero la tabla solo traía 500 → 345 LIVE escondidas. Causa raíz (medida en prod, no asumida): `fetchAccounts()` pedía `/api/accounts?limit=500` hardcoded; la paginación es **client-side** (`getPaged()` → `slice` sobre `getVisible()`), así que solo paginaba lo que llegó. Fix: constante `ACCOUNTS_FETCH_LIMIT = 2000` (el backend ya permite `le=2000`; traer 845 LIVE = ~370 KB / 8 ms, medido). El universo filtrado se trae completo y se pagina en cliente (sort/búsqueda/selección ya eran client-side). El contador `#countLabel` (`visible.length / s.live`) y la pagebar cuadran solos. **Guardarriel anti-silencio**: `state.truncated = rows.length >= ACCOUNTS_FETCH_LIMIT`; si se toca el tope, `renderPagination` añade `⚠️ tope N` con tooltip al `#pbVisibleCount` (nunca esconder en silencio — `feedback_frictionless_norte`). Hoy 845 < 2000 → no se enciende. Server-side pagination se **descartó** (rompería búsqueda dominante/sort/selección multi-página, todos client-side).
- **P4/P5 — Banda de selección rediseñada (`#cmdBar`).** Antes: `position:fixed; bottom:16px; z-index:50` → flotaba sobre todo ("se ve mal por encima"). Ahora: **en flujo**, movida dentro de `#accDockZone` **entre la tabla y el paginador**, `width:100%`, **mitad de alto** (padding `5px` vs `10px`; botones `6px 14px`), **animación de entrada** `cmdbarIn` (slide+fade 240ms, respeta `prefers-reduced-motion`), glow más delgado. Al vivir dentro de `#accDockZone` se comprime con el dock de depósitos igual que la tabla. **Labels desambiguados** (Robert: "Liberar y Publicar son ambiguos"): `🎁 Liberar`→**`🎯 Asignar`** (dirigido a UN operador), `🎁/📤`→**`🌐 Publicar a Pool` / `📥 Quitar de Pool`** (pool común = TODOS). Iconos ya no colisionan (🎯 uno vs 🌐 todos). **Depositar = toggle**: si el panel ya está abierto, el mismo botón lo cierra (`if (_depDrawerOpen) closeDepositModal()`). **Visibilidad por rol** (ya en `loadMe`): Pool/Asignar solo SA; operador ve Depositar/Lock/Borrar. **Por aplicabilidad**: la banda aparece solo con selección (`n≥1`), Depositar solo `1≤n≤5`. `cmdStats` (Σ saldo) movido a `.cmd-left`; `.cmd-right` eliminado. IDs internos sin cambio (`cmdTrastienda`/`cmdRelease`) para no romper handlers. Pendiente menor: el stat `#lpTras` del strip aún se llama "Trastienda" (coherencia con "Pool" a decidir).
- **P3 — Actualizar cuentas: operador solo 1×1, bulk solo SA.** Robert (tanda 5): "los demás usuarios NO deben poder actualizar en bulk; única opción para ellos = el botón individual de cada cuenta". (a) Frontend: `#btnRefreshVisible` oculto para no-SA en `loadMe()`. (b) **Backend gate** (`prewarm.py` `/refresh-stream`): si `role != superadmin` y `len(account_ids) > 1` → **403**. El `↻` por fila (`refreshSingleRow` → `account_ids:[1]`) pasa; cualquier bulk de no-SA se rechaza. Defensa en profundidad: el control no es solo el botón oculto, el endpoint mismo lo impide.

## Tabla principal — compactación (reorg 2026-06-29)

`tbody td` padding reducido de `8px 14px` → `4px 12px` (`style.css`). Resultado: filas más bajas, más cuentas visibles en el mismo viewport (verificado con `getBoundingClientRect`). No se eliminaron columnas.

## Conexión SSE (`connectSSE()` — app.js:1032)

EventSource a `/api/events`. Cada mensaje:
```js
const ev = JSON.parse(e.data);
if (ev.type === 'activity') pushActivityEvent(ev);
else if (ev.type === 'notification') pushNotif(...);
else if (ev.kind === 'capmonster_low') ...
```

Ver `docs/SSE_EVENTS.md` para tabla maestra de `kind` y su handler.

## State global

| Variable | Tipo | Función |
|---|---|---|
| `state` | object | `{user, rows, filter, sort, section, ...}` |
| `selectedIds` | `Set<int>` | IDs de cuentas seleccionadas |
| `activityRows` | array | Feed de actividad cacheado |
| `_actNewIds` | `Set` | Keys de eventos recién llegados (animación) |
| `notifications` | array | Notificaciones in-memory |
| `_evtSrc` | EventSource | Conexión SSE activa |
| `_depMode` | string | `'single' | 'multi' | 'schedule'` |
| `_depAccountIds` | array | IDs en el drawer de depósito |
| `_depBusy` | bool | Lock para evitar doble-submit |
| `_depMmRunId` | string | run_id del matchmaker activo (para cancelar) |
| `_depReps` | int | Repeticiones del schedule |
| `_depDrawerOpen` | bool | `true` cuando el drawer tiene `.dep-drawer-open` (controla Escape/Enter) |
| `_depPillTickTimer` | interval | Refresca el texto del mini-pill cada 1s |
| `_schedPendingEvents` | array | Buffer de `scheduled_*` que llegan antes de `_schedShow` (race fix) |
| `_schedHintTimer` | interval | Rotador de hints durante pool warm-up del scheduled |
| `_schedWatchdogTimer` | timeout | Watchdog 30s — alerta si no llega ningún `scheduled_phase` |
| `markedSet` | `Set<string>` | Emails marcados por el usuario (cargado desde `GET /api/marks` al init) |

## Helpers principales

| Función | Propósito | File:line |
|---|---|---|
| `$(sel)` | querySelector wrapper | (top del file) |
| `esc(s)` | Escapa HTML | (top) |
| `toast(msg, kind)` | Notificación temporal abajo-derecha | app.js:341 |
| `fmtMoney(n)` | `$1,234.56` | (helper) |
| `fmtAbs(ts)` | Hora absoluta `HH:MM` | (helper) |
| `fmtAgo(ts)` | Relativa `5min` `2h` | (helper) |
| `pushNotif({icon,msg})` | Agrega al bell | app.js:887 |
| `pushActivityEvent(ev)` | Inserta en feed con animación. Soporta scheduled/scheduled_phase/scheduled_aborted/scheduled_cancelled (mapea email→target) | app.js |
| `_schedPhaseLabel(name, data)` | Formatea fase del scheduled (login/begin/submit/check/done) con emoji + ✓/✗ + duración_ms | app.js |
| `ActivityLogic.dedupeActivity(events)` | Colapsa eventos duplicados; key `sched_id+iter` para scheduled / `kind+target+amount+ts_minuto` para el resto | `static/activity_logic.js` |
| `ActivityLogic.formatActivityCopy(ev, viewerIsSA)` | Genera `{icon, cls, text}` humanizado para cada evento; no-SA ve "Tú" en lugar del nombre del operador | `static/activity_logic.js` |
| `computeCurp(name, bdate, addr)` | Calcula CURP estimado (4 letras + fecha + sex + estado + verifier) | app.js:277 |
| `_splitFullname(s)` | Separa nombre/apellidos para CURP | app.js:160 |

## La Pantalla (`static/pantalla.js` + `pantalla.css`)

> Panel de detalle de cuenta que se MATERIALIZA como una lámina de vidrio ámbar translúcido sobre el strip de KPIs (`#pantalla` anclado a `#accountsMain`). Reemplaza al detalle inline viejo para ver una cuenta. Rama `feat/la-pantalla`.

**Apertura:** `window.Pantalla.open(id, mode)`. Disparador (Fase B): **click IZQUIERDO simple** en la fila de `#accTable` (sin modificadores) — **incluye la celda del combo** (fix 2026-07-03: el combo dejó de copiar; su click abre La Pantalla). También `openAccountByEmail` desde Actividad/Recientes/marquesina. Ya NO se usa contextmenu (click derecho).

**Exclusión mutua con el acordeón viejo (fix 2026-07-03):** La Pantalla y el acordeón inline (`openDetailModal`) NUNCA coexisten (antes se veían dos paneles de detalle a la vez). Abrir La Pantalla llama `closeDetailModal()`; abrir el acordeón llama `window.Pantalla.close()`. **Actualización 2026-07-04:** La Pantalla ya porta notas (CRUD) + guardar CURP (ver abajo); lo único exclusivo del acordeón era eso y las tarjetas (que no tienen alta manual en ningún lado). Retirar el acordeón viejo por completo queda como **decisión pendiente de Robert** (auditoría hallazgo #1, `reports/auditoria-la-pantalla-2026-07-03.md`).

**Selección de tabla tipo Excel (Fase B, reemplaza drag-select + checkboxes):** click simple = abrir La Pantalla; **Ctrl/Cmd+Click** = toggle esa fila en la selección múltiple; **Shift+Click** = rango desde la última fila clickeada (`_lastClickedId`, orden visible, helper `_selectRange`). El click simple en `td.combo` abre La Pantalla (ya no copia). Se retiraron: los checkboxes de 1ª columna (la `.sel-cell` quedó como **indicador**: dot accent en `tr.row-sel`), el drag-select por mouse y por pointer, y el `#selAll`.

**Layout — REDISEÑO 2026-07-09 (`renderPantallaHead`, sin scroll de página, altura FIJA):** las secciones "Layout 2026-07-04/06" de abajo describen el diseño ANTERIOR (2 zonas: datos|transacciones-a-todo-ancho) — **ya no vigente**, se dejan como historial. El diseño de abajo (`.pat-columns` flex 3-en-fila + `.pat-cramped` apilado) **TAMBIÉN quedó superado el 2026-07-27** — ver `docs/ERRORS.md` §"Retiro/Depósito de La Pantalla necesitaban scroll... rediseño a grid". Resumen del estado ACTUAL: `.pat-columns` es **CSS Grid** (`grid-template-areas: "ident stage" "txns txns"`) — identidad + escenario (retiro/depósito) SIEMPRE lado a lado arriba, sin scroll propio; movimientos baja a una fila propia abajo, ES la única zona scrolleable. La ficha crece dinámicamente en caliente (`pantalla.js` `_syncFichaHeight` + `app.js` `KpiPanel.focusMaxH`) para que esa fila de arriba quepa completa — ya no depende solo del `ANCHOR_H` estático. El resto de esta sección (`.pat-col-ident`/`.pat-col-txns`/`.pat-col-stage` con sus `flex:`/`min-width:` de 2026-07-09) describe el mecanismo VIEJO — mantenido abajo como historial de cómo se llegó aquí, no como referencia de implementación vigente.
- **`.pat-topbar`** (fila superior, full width): solo nombre·edad + grade a la izquierda, `padding-right:50px` reserva el hueco de `.pantalla-close`. Los controles (Fijar/En uso/Depositar) bajaron de aquí a `.pat-actions` (abajo).
- **`.pat-actions`** (controles: Fijar/En uso/Depositar) — `position:absolute` contra `.pat-wrap`, anclados a la **esquina inferior derecha** de La Pantalla (`right:18px; bottom:14px; z-index:6`). Cuelgan de `.pat-wrap` (NO de `.pat-topbar`): el cuaje líquido deja un transform permanente en `.pat-topbar` que lo vuelve contenedor de posicionamiento y anclaría mal los botones absolutos. La ✕ de cerrar (`.pantalla-close`) SÍ se queda arriba-derecha (convención universal de cierre).
- **`.pat-columns`** (fila, `flex:1 1 auto`) — **3 columnas reales**, cada una con su propio header fijo (no scrollea) + hairline dorado continuo de frontera:
  - **`.pat-col-ident`** (`flex:0 0 218px`): combo `email:password` → saldo 36px → estado/nac/CURP → tarjetas/notas (`renderPantallaSaved`, capado 2+2, `margin-top:auto` las pega abajo).
  - **`.pat-col-txns`** (`flex:2 1 0; min-width:380px`) — toma **2/3 del espacio libre** (reparto 2:1 con el escenario). Header `.pat-txn-h` (ícono+"Movimientos"+contador) es HERMANO fijo de `.pat-txn-col`. `.pat-txn-col` es SOLO el área `overflow-y:auto` de filas.
  - **`.pat-col-stage`** (`flex:1 1 0; min-width:340px`, `id="patStageSlot"`) — zona de animación del depósito (ver bloque "Escenario de depósito migrado" más abajo). Vacía en reposo; `min-width:340px` asegura que el guide de 4 pasos quepa sin apretarse.
- **Tarjetas/notas/CURP — edición portada (2026-07-04, sin cambios):** notas con CRUD real dentro de La Pantalla (botón `+` `[data-add-note]` → textarea `.pat-textarea` → `POST /api/accounts/{id}/notes`; borrar `[data-del-note]` → `DELETE …/notes/{note_id}`, visible solo al dueño/superadmin vía `_isNoteOwner`). CURP: guardar validado (`[data-curp-toggle]` → input `.pat-input-mono` → `POST /api/accounts/{id}/curp`, misma regex 18 chars que el backend, error inline). **Tarjetas NO tienen alta/edición manual** (no existe endpoint — se guardan solo al aprobarse un depósito, `deposits.py`); siguen solo-lectura. Clases de formulario: `.pat-form/.pat-input/.pat-textarea/.pat-btn`.
- **Transacciones (`renderPantallaTxns`) — UN historial unificado (2026-07-04, sin cambios de fondo):** una sola lista cronológica (más reciente primero; `movimientos` ya viene ordenado desc de `app.py`). Cada fila lleva un **pill de color + ícono** por fuente: **violeta** `oklch(0.72 0.16 292)` + `ph-lightning` = Botmexico (nativo), **cian** `oklch(0.74 0.13 228)` + `ph-globe-hemisphere-west` = BetMexico (importado). Tinte por resultado: verde ok / rojo fail / ámbar 3DS (`--pat-3ds`) / tenue pending·wd. Cap `MV_CAP=400` (solo backstop, el scroll maneja el volumen real).

### Escenario de depósito migrado a La Pantalla (2026-07-09)

> Antes el progreso del depósito (animaciones SVG login/captcha/processing/retry/done + `%`/subtexto + balance) vivía DENTRO del panel flotante `#depos` — Robert: "esa mini-pantallita ni se ve, está mal acomodada". Se movió (no se duplicó) a la columna derecha de La Pantalla.

- **`#depStage`** (antes `.journey` scopeado a `#depos`): host portátil re-parenteado por JS a `#patStageSlot` (`.pat-col-stage`). Trae SUS PROPIAS variables CSS (copiadas de `#depos`, `depos.css`) + reset, para renderizar idéntico fuera del panel.
- **CSS re-scopeado**: TODO el bloque de animación de `depos.css` (líneas ~182-567: `.journey/.scene-stage/.scene/.guide/#scene-login/#scene-form/#scene-processing/#scene-retry/#scene-done/.j-status`, ~285 líneas + keyframes) se reprefijó de `#depos ` a `#depStage ` (sed sobre el rango exacto, keyframes con nombres únicos `lg-/fm-/pr-/rt-/dn-` no chocan). `.mov` (lista de movimientos del panel, `#mov`) se quedó con `#depos` — NO se movió, sigue en el panel flotante.
- **`depos.js`**: `sqs(sel)` (nuevo helper) resuelve selectores dentro de `#depStage` estésea dónde esté re-parenteado (`setScene/setPct/setSub/#jbal/#balNow/#balTo/#guide/#jstatus`); `qs(sel)` (el de siempre, scopeado a `#depos`) sigue resolviendo `#mov`/controles del panel. `journeyStart()`: enciende `#depStage` (`hidden=false`) y, si La Pantalla está cerrada, la abre en la cuenta primaria de la misión (`window.Pantalla.open(primary.id)`) para que el progreso tenga dónde verse — si ya estaba abierta en otra cuenta, no se le quita el foco (el escenario es genérico, el resultado por-cuenta cae en `#mov` del panel).
- **Mini-pantalla del panel**: desapareció por completo (el `.scene-stage`/`.guide`/`.j-status` ya no se renderizan dentro de `#depos`, solo el escenario re-parenteado en La Pantalla los usa).

**Dedup de transacciones (backend, `app.py` `account_details`):** un depósito con tarjeta hecho desde el dashboard (`deposit_attempt`) también aparece como eco en `account_transactions` de BetMexico → se omite el eco (aprobados **y** rechazados), emparejando por monto + hora MX (±3 min) y consumiendo cada firma. Se conserva el registro NUESTRO (tiene operador + tarjeta). Ver `docs/ERRORS.md`.

**Acabado:** vidrio templado ámbar + detalles **perla translúcida** (reflejos nácar rosa/cian mate en esquinas + halo interno tenue). El contenido (`.pantalla-view z-index:5`) va ENCIMA del grano/acabado para no opacarse. Contorno (`text-shadow`) en todo el texto para nitidez. Cuaje líquido (`.pat-liquid`, una vez por cuenta; el filtro goo se retiró por distorsión).

> **Ajuste de campo 2026-07-06 (`.pantalla-sheet`):** vidrio **más oscuro / menos brillante / menos translúcido** por pedido operativo (se veía demasiado brillante). Dos palancas en `pantalla.css`: (1) capa base del gradiente `linear-gradient(180deg, …)` — lightness `0.17/0.115→0.15/0.10` (más oscura) y alpha `0.36/0.52→0.50/0.66` (deja ver menos los KPIs de atrás); (2) `backdrop-filter` `saturate(1.45→1.2)` (menos vividez del fondo filtrado). Solo `.pantalla-sheet`; blur, animaciones, layout y contenido intactos.
>
> **Ajuste de campo 2026-07-06 #2 (misma sesión, layout de cabecera + oscurecido extra):**
> - **Vidrio un toque más oscuro todavía**: `linear-gradient(180deg, …)` de la capa base — lightness `0.15/0.10→0.14/0.09`, alpha `0.50/0.66→0.56/0.72`.
> - **`.pat-actions` (Fijar/En uso/Depositar) se movió de `.pat-idrow` a `.pat-combo-line`** — pedido de campo: "dales su lugar, bájalos". Antes competían con el nombre en la fila 1 (altura de la fila dictada por el botón de 26px); ahora viven en la fila del combo (fila 2), su propia fila. Efecto colateral buscado: `.pat-idrow` sin actions mide solo el alto del texto → la cabecera se compacta → `.pat-body` (divisor + `.pat-txns`) arranca más arriba, justo donde termina la fila del combo — pedido: "que las transacciones se vean desde arriba, no que empiecen a mitad de pantalla".
> - **`.pat-idrow`** perdió el `padding-right:50px` (ya no tiene nada empujado a la derecha que choque con `.pantalla-close`). **`.pat-combo-line`** pasó de fila simple a `display:flex` (combo a la izquierda, `.pat-actions` a la derecha vía su `margin-left:auto` existente) y heredó ese `padding-right:50px` (reserva el hueco de la X).
> - **Ancho horizontal de `.pat-txns`**: no se tocó — `.pat-body` nunca tuvo el `padding-right` de 50px, así que las transacciones ya llegaban hasta el borde derecho real del panel (mismo ancho que la fila de botones); al no haber overlap vertical entre `.pat-combo-line` (arriba) y `.pat-body` (abajo) no hace falta reservar nada ahí.
> - Markup: `renderPantallaHead` en `pantalla.js` — el `<div class="pat-actions">` se movió a `.pat-combo-line` (commit 07-06), y luego a hijo directo de `.pat-wrap` (2026-07-10, sacado del flow normal y anclado con `position:absolute` esquina inferior derecha). Los botones conservan sus mismos `data-mark-email`/`data-inuse`/`data-acc-id`; la delegación de eventos de `#pantalla` no depende del padre, sin roturas.

**Tamaño FIJO — sin drag, sin collapse (2026-07-09, reemplaza la "persiana de 2 estados" 2026-07-04):** Robert: "ya no debería haber drag/collapse ni de los KPI ni de la pantalla, se quedan fijos". Se eliminaron por completo:
- `.pantalla-banda` (la banda inferior plegar/desplegar) y `initPantallaBanda()` — YA NO EXISTEN en `pantalla.js`.
- `.lp-vgutter`/`#lpVGutter` (el divisor arrastrable ↕ entre `.lpanel` y la tabla) — el elemento se QUITÓ de `index.html`; en su lugar un `<div class="lp-vspacer">` (10px, sin cursor/hover, solo mantiene el hueco visual) para no correr la tabla contra el panel.
- `window.KpiPanel.toggle()/expand()/collapse()/applyH()` — YA NO EXISTEN. `window.KpiPanel` quedó reducido a `{ maxH, currentH, DEFAULT_H }` (solo lectura, sin mutadores).
- `ResizeObserver` de `pantalla.js` sobre `.lpanel` (`observeStrip()`/`_sizeToStrip()`) — eliminado. `pantalla.css` ya NO tiene `--pantalla-h` variable; el alto lo fija JS una sola vez (ver abajo).

**Alto ÚNICO para ambos (panel KPI y La Pantalla) — `ANCHOR_H` (`app.js`, `initLpVResize()`):** se mide UNA vez al cargar la página, sin estimar: `PantallaLogic.anchoredPanelH({currentPanelH, filterbarTop, sistemaTop, minH})` (`pantalla_logic.js`) calcula el delta entre `#sbSectionSistema` (label "Sistema" del menú lateral) y `.filterbar-accounts` (header "Cuentas") y crece/encoge el panel para que ambos queden a la misma altura — regla exacta de Robert, campo 2026-07-09 (imagen de referencia), verificada con `getBoundingClientRect` real (no a ojo). `apply(h)` (dentro de `initLpVResize`) es la ÚNICA función que escribe el alto: fija `#adminPanel.style.height` Y `#pantalla.style.height` en el mismo golpe — invariante: nunca pueden divergir (evita que La Pantalla tape la tabla o deje hueco). `DEFAULT_H=212` sigue existiendo solo como fallback si `#sbSectionSistema`/`.filterbar-accounts` no se encuentran.

**Grade-color (2026-07-10):** el tinte de acento de La Pantalla (--pat-gold y derivados) se reescribe según el `grade` de la cuenta. `renderPantallaHead` (`pantalla.js`) setea `data-grade="APlus|A|B|C|D|U"` en `.pat-wrap`, y `pantalla.css` declara overrides por selector de atributo que cambian todas las variables derivadas (`--pat-gold`, `--pat-gold-soft`, `--pat-edge`, `--pat-edge-h`, `--pat-warm`, `--pat-tint`, `--pat-tint-2`). El mesh de fondo (`.pantalla-sheet`) NO cambia — el vidrio templado es siempre el mismo, solo el acento varía. Paleta: A+ verde vivo (h152), A verde normal (h160, default), B azul grisáceo (h235), C ámbar (warn, h75), D rojo (danger, h24), U gris neutro (h95, desaturado). `--pat-3ds` nunca se toca (es semántica de transacción, no de tema).

**Controles deslizantes que SÍ siguen vivos** (no tocados): `.lp-gutter` (ancho entre las 2 cards del panel KPI, horizontal) y los edges de resize de `depos_window` (`ns/ew-resize`). Los scrolls internos también siguen igual: `.lp-feed-rows`/`.lp-alert-rows` (cards KPI) y `.pat-txn-col` (transacciones dentro de La Pantalla).

**Fixes de campo post-persiana (2026-07-04, prod, capturas de Robert):**
- **`DEFAULT_H` (212) vs `.pantalla{min-height:288px}`:** el piso viejo (época del grip propio) ganaba sobre `--pantalla-h` y estiraba La Pantalla 76px de más al plegar, tapando la filterbar de abajo. Bajado a `min-height:96px` (mismo `MIN` de `KpiPanel`).
- **`DeposWindow` — dockeo real:** `zoneRect()` medía el rect crudo de `#accDockZone`, que envuelve la filterbar ADEMÁS de la tabla (`index.html:162-186`) → el panel dockeaba con el top en la filterbar, no en la tabla. Ahora descuenta `.filterbar-accounts` del top/height. Además: mientras La Pantalla está abierta, `effectiveMode()` fuerza dockeado (nunca `float`, aunque esa sea la preferencia guardada) — decisión de Robert, el panel de depósitos NUNCA comparte franja con La Pantalla. `defaultFloat()`/`clampFloat()` anclan contra `#accountsMain` (mismos márgenes 20/18/14px que `.pantalla-sheet`), no contra `vw()/vh()` crudos.
- **`ST.open` guard:** `relayout()`/el resize listener de `DeposWindow` llamaban `apply()` sin checar si el panel estaba realmente abierto → el `ResizeObserver` de `observeKpiForDepos` (dispara en cada toggle de La Pantalla) volvía a reservar espacio en `accDockZone` (`setZonePad`) con el panel cerrado, dejando hueco vacío en la tabla. Fix: flag `ST.open` seteado en `show()`/`hide()`.
- **Íconos 💳/📝 de fila:** llamaban `openDetailModal()` (acordeón viejo) en vez de `window.Pantalla.open()` — único camino que no pasaba por la exclusión mutua. Corregido.

**Historial scrolleable + detalle expandible (2026-07-04):** `.pat-txn-col` pasó de `overflow:hidden` + cap fijo de 12 filas (`+N más`) a `overflow-y:auto` (rueda nativa) + click-y-jala delegado en `#pantalla` (el nodo se re-renderiza en cada refresh de detalle; un listener directo se perdería) — umbral de 6px para distinguir drag de click (mismo patrón que la selección tipo Explorer). Cap subido a 400 (solo backstop). Cada fila `.pat-mv` togglea un detalle expandible al click (`grid-template-rows: 0fr↔1fr`, 180ms) con operador/tarjeta completa SIN enmascarar (copiable, `.pat-mv-exp-copy`)/motivo — solo hay sustancia real en movimientos nativos (`m.who`/`m.card_pipe`); el eco de BetMexico muestra "sin detalle interno". `_mvDragged` (module-level flag) evita que soltar un drag-scroll también togglee la fila.

### Retiro automático SA-only (`.pat-wd`, 2026-07-24)

> Botón de retiro dentro de `.pat-col-ident`, bajo `.pat-clabes` (`renderPantallaWithdraw(d)`, `pantalla.js`). Backend: `docs/ENDPOINTS.md` §"Retiros".

- **Invisible para no-SA** (no un candado — `feedback_deshabilitar_invisible_no_redirect`): `renderPantallaWithdraw` devuelve `''` si `state.user.role !== 'superadmin'`.
- **Markup:** input monto (`min=100`) + botón `.d-withdraw-fire` + `.pat-wd-status` (zona de estado). Mismo lenguaje visual que `.pat-clabes`/`.pat-form` (`.pat-input`/`.pat-btn-save`).
- **Disparo (handler delegado en `#pantalla`):** `POST /api/accounts/{id}/withdraw {amount}` → bloquea input+botón, arranca `_startWithdrawPoll(accId, transactionId)`. 409/4xx → toast de error, desbloquea.
- **Polling fijo 60s** (`_startWithdrawPoll`/`_wdPolls`, guardarrail explícito del plan — nunca menos, no alimentar rate-limit BetMexico): 1 solo `setInterval` activo por cuenta, con chequeo inmediato al disparar (no espera el primer tick). Se detiene solo (`_stopWithdrawPoll`) al llegar a estado terminal (`successful|completed|failed`) o al cerrar La Pantalla (`_finishClose` limpia TODOS los polls activos).
- **Resume al reabrir** (`_resumeWithdrawPollIfPending`, llamado desde `_renderDetailView`): si `d.last_withdrawal` (nuevo campo de `/details`, ver `docs/ENDPOINTS.md`) tiene un estado no-terminal, retoma el polling sin que el operador tenga que re-disparar.
- **Copy 2-fases (bug#2 — `feedback_status6_no_garantiza_aterrizaje`):** `transactionStatus==6` → **"BetMexico procesó el retiro… Confirma en tu banco."**, NUNCA "entregado"/"llegó".
- **Alertas (bug#1/#3):** `alerts.digitsMismatch` → borde+aviso rojo "dígitos distintos a la cuenta esperada"; `alerts.gatewayMismatch` → "mandó el retiro a TARJETA, no a SPEI". Clase `.pat-wd.alert` (borde rojo, NO ámbar — es alerta de dinero).
- **Multi-operador vía SSE:** `app.js connectSSE` escucha `kind:'withdrawal'` — si `window.Pantalla.currentId` coincide con la cuenta del evento, reabre (`Pantalla.open(id)`) para refrescar sin que ese operador tenga su propio poll corriendo (ver `docs/SSE_EVENTS.md`).
- **CSS:** bloque `.pat-wd*` en `pantalla.css`, reusa `--pat-gold`/`--danger`/`--danger-soft` ya declarados (mismo tema por-grade que el resto de La Pantalla).
- **Pendiente:** verificación visual (`getBoundingClientRect`, encaje sin overflow en `.pat-col-ident`) — no se pudo hacer en la sesión de implementación (extensión Chrome no conectada). Ver `NEXT-SESSION.md`.

## Rework de interacción 2026-07-17 (Robert, campo — panel fijo, combo, cierre, drag, tarjetas, vidrio)

Tanda de correcciones de interacción/estética pedidas operando en prod:

- **Combo de la tabla — solo el TEXTO copia:** `data-copy`/`d-copy` se movió del `<td class="combo">` al `<b class="combo-txt d-copy">` interno (`app.js` `renderTable`). Click sobre el texto del combo → copia (handler global capture, `stopPropagation`, NO abre detalle). Click en el resto de la celda (padding, badge JWT 🟢, lock-chip) → abre La Pantalla, igual que cualquier otra celda. Ctrl/Shift+Click sobre el texto sigue seleccionando (el handler global deja pasar el modificador al row-handler).
- **Panel de depósitos — SIEMPRE dockeado a la DERECHA, solo se ensancha** (`depos_window.js`): se eliminaron los modos `float` y `left`, el drag por el header y el resize por bordes. `effectiveMode()` devuelve constante `'right'`; `sectionLocked()` siempre `true`. El único ajuste es el divisor (`.dw-divider`) que recorre el ancho. `load()` ignora `mode`/`float` de localStorage (solo restaura el ancho). Se agregó `RIGHT_INSET=20` (respiro contra el borde derecho, mismo margen que `.pantalla-sheet`) aplicado en `Geo.dockRect(zone, side, dockW, inset)` y reservado en `setZonePad`. En **logs/activity** el panel ahora dockea a la **derecha** (antes izquierda): `Geo.sectionDock` → `scope:'docked-right'`. Botones `.dw-dock-l`/`.dw-dock-r` eliminados de `injectWindow` (`depos.js`); solo queda `.dw-close`. CSS: `.head` sin `cursor:grab`.
- **La Pantalla cierra SOLO por backdrop o X** (`pantalla.js`): se quitó la rama que cerraba al click en "espacio limpio" dentro del `.pantalla-sheet` (sacaba al operador a media interacción). Ahora solo cierra `[data-close]` (backdrop = click fuera del sheet, o botón ✕) y `Esc`.
- **Pegar VARIAS tarjetas de golpe** (`depos.js` `startAddCard`): el input de "+ agregar tarjeta" acepta multi-paste (separadas por línea/espacio/coma/`;`). Mete las válidas sin caerse por las inválidas (reporta `✓ N · M inválidas`). Pegar 1 sola cae al flujo normal (Enter/blur).
- **Drag de filas SELECCIONADAS → panel** (`app.js` + `depos.js`): solo las filas con `row-sel` son `draggable` (así no choca con el marquee, que arranca sobre filas NO seleccionadas). `dragstart` empaqueta `application/x-bmx-accounts` (ids+email+grade de toda la selección); el panel (`#depos`) es drop-zone (`dragover`/`drop`) y llama `window.Depos.addAccounts(list)` → suma a `_dx.accounts` (dedup), resuelve password/grade en background. Feedback visual: `body.dragging-acc` (invitación) + `#depos.dw-drop-hot` (realce).
- **Un solo botón "Depositar"** (`depos.js` + `pantalla.css`): al abrir el panel se marca `body.depos-open`, que oculta `.pat-act-dep` en La Pantalla (no dos botones a la vez). Reaparece al cerrar el panel.
- **Candadito "En uso" eliminado de La Pantalla** (`pantalla.js` + backend `app.py`): el botón `.pat-act.inuse` (lock manual) se quitó — era un 2º control del MISMO lock, redundante con el auto-lock al depositar, y como SA creaba RESERVADA_SA perpetua que trababa "sacar del pool → trastienda". El lock ahora es UNO solo (el de trabajo). Sacar a trastienda (SA) libera la RESERVADA_SA perpetua y respeta el lock temporal de operador activo. Ver `docs/ERRORS.md` §"El candadito En uso…".
- **Vidrio oscuro UNIFORME** (`pantalla.css` `.pantalla-sheet`): se quitaron las capas que oscurecían solo la izquierda y la que aclaraba izq→der hacia el tinte del grade; el oscurecido ahora es plano a lo ancho. El grade sigue tiñendo bordes/CTA, no el fondo.

## Auditoría visual/UX/a11y 2026-07-18 — F0 Fundación (tokens + contraste + focus + reduced-motion)

Plan: `docs/superpowers/plans/2026-07-18-auditoria-visual-dashboard.md` (ejecutado con `/Smartexe`, rama `feat/auditoria-visual-2026-07-18`).

- **Contraste WCAG AA** (`style.css` `:root`): `--text-muted` 0.34→0.52 alpha (2.1:1→4.5:1), `--text-dim` 0.58→0.72 (7.8:1), `--text-faint` 0.18→0.28 (solo decorativo, nunca texto), `--hairline` 0.06→0.12 (1.3:1→3.2:1), `--hairline-h` 0.10→0.20. Se agregó escala tipográfica (`--fs-9`…`--fs-28`), espaciado base 4px (`--space-1`…`--space-10`), radios, sombras (`--shadow-sm`…`--shadow-xl`) y z-index (`--z-dropdown`…`--z-coachmark`) — antes no existían como tokens.
  - 9 usos hardcoded de `rgba(255,255,255,0.06)` fuera de `:root` (badges, hovers, keyframe `rowSkip`, bin-chart border, sb-user shadow) migrados a `var(--hairline)`/`var(--hairline-h)`.
  - `depos.css`/`pantalla.css` **NO se tocaron** en sus sistemas de tokens locales escopados (`#depos{--gold:...}`, `#depStage{--gold:...}`): son universos self-contained (`--void`/`--ink`/`--aqua`/`--gold` hex) que NO heredan `:root` por diseño (comentario propio del archivo: "scoped bajo #depos para no colisionar con style.css"). El choque de nombre `--gold` NO es colisión real en cascada CSS (custom properties están scoped al selector que las declara); tocar esos valores hardcoded arriesgaba romper el look calibrado sin beneficio de contraste (son acentos decorativos, no texto). Decisión no-bloqueante, documentada.
  - Done: `grep -rnE "rgba\(255,255,255,0\.06\)|rgba\(238,240,243,0\.(34|18)\)" static/style.css static/pantalla.css static/depos.css` → 0 matches.
- **Focus visible global** (`style.css`, **al final del archivo** — no tras el primer `@media (prefers-reduced-motion)` como decía el plan original): `*:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px }` + selectores explícitos para `.ico-btn`, `.nav`, `.pg-btn`, `.pat-act`, `.sb-collapse`, `.lp-head-clickable`, `.grade`, `.lock-chip`, `.jwt-chip`, inputs/selects/botones.
  - **Verificado con Tab real** (no a ojo): la posición original del bloque perdía el empate de especificidad/orden contra ~6 reglas `:focus{outline:none}` declaradas MÁS ABAJO en el archivo (misma especificidad `input:focus` vs `input:focus-visible` → gana quien va después en la cascada). Movido al final del archivo para ganar siempre ese empate.
  - `.cenefa a` y `.sb-brand a` tienen `outline:0` INCONDICIONAL (no ligado a `:focus`, especificidad `.clase + tipo` > `*:focus-visible`) — sin indicador de foco alguno al tabular al wordmark. Fix: `.cenefa a:focus-visible, .sb-brand a:focus-visible { outline: 2px solid var(--accent) }` (empate de especificidad a favor, declarado al final).
  - El resto de inputs con `outline:none` (`.dep-input`, `.dep-textarea`, `.pool-search`, `.act-search-wrap input` vía `:focus-within` en el wrapper, `.pat-input`/`.pat-textarea` vía `border-color`, `#depos .amt input` vía `:focus-within` en `.amt`) **ya tenían indicador visible alterno** (cambio de `border-color` y/o `box-shadow`) — no son gap real, no se tocaron.
  - Confirmado con `getComputedStyle` real (Tab x1 → wordmark `outlineStyle:"solid" outlineWidth:"2px" outlineColor:"oklch(0.5 0.11 160)"`; Tab x4 → nav button ídem).
- **Reduced-motion completo**: el plan original listaba selectores basados en NOMBRES DE KEYFRAME (`.bellPulse`, `.mmBusy`, `.pecera`, `.breathe`, `.depSchedAppear`, `.depSchedShimmer`, `.dep-scheduled-row`) que **no existen como clases** en el DOM — eran nombres de `@keyframes`, no de selector. Corregido contra el código real:
  - `style.css` (junto a `.dep-spinner`): `.dep-spinner, .bell .badge, .mm-card.mm-busy, .mm-acct.mm-busy, .dep-sched-bar-fill::after` → `animation:none`; `#actTable tbody tr.act-row-new` y `.dep-sched-run` → `animation:none; opacity:1; transform:none` (eran one-shot, no infinitas, pero igual se respetan bajo reduce); `.mm-feed-row` (`mmFeedIn` 280ms) → idem.
  - `depos.css` (al final): `.sub-dot` (breathe), `#depStage .jglass::after` (pecera), `#depStage #scene-retry.on .rt-head` (rt-breathe) → `animation:none`.
  - `pantalla.css:838-871` ya tenía reduced-motion (`pat-cuaje-rm` fade 0.2s) — solo se verificó, no se tocó.

## Auditoría visual/UX/a11y 2026-07-18 — F1 Tabla (carga cognitiva + glow fila↔detalle)

**Decisión de arquitectura (desvío del plan, con criterio de Robert "resuélvelo tú"):** el plan original pedía un
chevron que abriera un "peek" reutilizando el acordeón inline viejo (`openDetailModal`/`.acc-detail-row`/
`expandedAccountId`). Verificado contra el código real: ese acordeón **es código muerto en producción** — solo
corre si `window.Pantalla` no existe (siempre existe), y el propio plan lo llama *"split-brain legacy...
superseded por pantalla.js"* en su sección "Fuera de alcance", agendado para BORRAR en Apéndice B (sesión aparte).
Construir una feature nueva sobre código marcado para borrar en la próxima pasada era exactamente el split-brain
que el plan decía evitar. **Se descartó el chevron/peek** — F1 se resolvió con:

- **Carga cognitiva 10→7 columnas** (vista `detail`, la única que existe — el toggle Simple/Detallada ya se había
  matado): `renderTable()` (`app.js:554`) compacta Nota+Tarjetas+Pin (3 `<td class="ic-col">` → 1
  `<td class="ic-col acciones-col">`, mismos botones `.row-ic` ya `inline-flex`, se acomodan solos) y Últ.check+Checks
  (2 `<td>` → 1 `<td class="check-cell">`, mismo patrón que `.dep` que ya mergea monto+antigüedad). Vista `simple`
  (legacy, casi sin uso): 8→6 `<td>`. Anchos de columna = **suma medida** de las columnas que reemplazan (170px =
  84+46+40 nota/cards/pin; 176px = 96+80 check/checks) — no son px inventados, son la suma real de lo que ya estaba
  medido. Cero cambio al modelo de interacción (plain-click→La Pantalla, Ctrl/Shift→selección, texto del combo→copia
  se preservan intactos, no se tocó ese handler).
- **Glow fila-fuente ↔ La Pantalla abierta** (Task 1.4, feature semilla de Robert: *"la cuenta en vista de detalles
  debería brillar"*): `window.Pantalla` (`pantalla.js`) expone `get currentId()`. `open(id)` llama `_markSourceRow(id)`
  (toggle imperativo instantáneo, `.pantalla-source` en `#accTable tbody tr[data-id]`); `_finishClose()` llama
  `_clearSourceRow()`. Para sobrevivir re-renders (SSE/sort/filtro reconstruyen el tbody), `renderTable()` también
  recalcula `pantalla-source` en cada `trClasses` desde `window.Pantalla.currentId` — mismo patrón dual
  (imperativo + recalculado) que ya usa `row-sel`. CSS: borde-izq 3px `var(--accent)` + `box-shadow: var(--neon-sm)`
  + fondo `var(--accent-soft)` — semántica distinta de `row-sel` (esto es "la que veo", una sola, no la selección
  múltiple). Verificado con datos inyectados en `state.rows` + `renderTable()` real (sin backend local): abre → fila
  marca `pantalla-source` (bg `oklch(0.5 0.11 160 / 0.14)`, `::before` 3px `oklch(0.5 0.11 160)`); sobrevive
  `renderTable()` forzado; cambia de cuenta (`open(2)` con `open(1)` activo) → solo la fila 2 queda marcada; `close()`
  → limpia tras la animación (verificado a los 500ms).
- **Cache-bust bump** (`index.html`): `style.css`/`depos.css`/`app.js`/`pantalla.js` → `?v=20260718a` (el navegador
  cacheaba agresivamente la versión anterior incluso con `location.reload(true)`; solo un query-string nuevo forzó
  el refresh real durante la verificación).

## Auditoría visual/UX/a11y 2026-07-18 — F2 Sidebar (3 grupos colapsables)

Reagrupados los `.nav` existentes (sin inventar secciones) en 3 grupos semánticos, mapeados contra el ROL real
(no el esquema genérico del plan — `Depósitos` no es un nav item, vive en el panel dockeado; los reales son
Cuentas/Pool/Actividad/Notificaciones/Logs/Salud/Controles/BINes):

- **Operación**: Cuentas, Pool.
- **Monitoreo**: Actividad, Notificaciones, Logs, Salud.
- **Administración**: Controles, BINes — grupo colapsado por default, y **oculto completo** (`#sbGroupAdminWrap.hidden`)
  para no-SA en `loadMe()` (`app.js`), porque sus 2 botones ya eran SA-only individualmente (`navPool`/`navAdmin`/
  `navLogs`/`navHealth`/`navBinStats` seguían con su propio `style.display='none'` por rol — el agrupado NO tocó esa
  lógica, solo la envuelve).
- **Anclaje preservado**: `#sbSectionSistema` (usado por `computeAnchorH()` en `app.js:2893` para alinear el alto
  del panel KPI con `.filterbar-accounts` — ancla medida de Robert, 2026-07-09) se movió al `<button
  class="sb-group-header">` de **Monitoreo** (el reemplazo semántico más cercano a la vieja etiqueta "Sistema").
  Como `computeAnchorH()` mide `getBoundingClientRect()` en vivo (no un píxel fijo), se auto-ajusta al nuevo layout.
- **Estado persistente**: `localStorage['sbGroups']` `{operacion, monitoreo, admin}` (default `{true,true,false}`),
  `initSidebarGroups()` (`app.js`, junto a `initSidebarCollapse`). Rail colapsado (`body.sidebar-collapsed`) ignora
  el estado de grupo — headers ocultos, todos los iconos visibles, igual que `.sb-section` antes.
- Verificado: 3 grupos con conteo correcto de `.nav` (2/4/2), toggle+persistencia en `localStorage`, gate SA/operador
  simulado, Tab real → ring de foco visible en `.sb-group-header` y en los `.nav` dentro.

## Auditoría visual/UX/a11y 2026-07-18 — F3 La Pantalla (secuencia GPU + mobile)

- **Task 3.1 (secuencia unfurl→scanline→cuaje):** verificado contra código — **ya estaba implementado**, no era un
  anclaje roto como F1. `pantalla.css:280-284` ya encadena `pat-unfurl` (0-380ms) y `pat-scan` (delay 80ms, 500ms)
  vía `animation-delay` puro CSS (una sola clase `.pantalla-on`, sin JS de por medio); `pantalla.css:816-825` ya
  escalona `pat-cuaje` por bloque con `animation-delay: calc(var(--i,0) * 0.062s)` — **el mismo valor de stagger
  (62ms) que el plan proponía**, ya tuneado en una pasada previa (comentarios fechados 2026-07-06/07-10 documentan
  reducciones de blur para bajar costo de GPU). **No se tocó** — reescribir algo ya correcto sin medir viola la
  misma ley que el plan invoca ("no estimación asumida").
  - **Bloqueado: no se pudo medir con DevTools Performance.** El panel de navegador de este entorno corre con
    `document.visibilityState === 'hidden'` incluso "fronteado" — `requestAnimationFrame` nunca dispara (confirmado:
    un rAF encadenado se colgó 30s). Sin rAF no hay animación real que perfilar. Pendiente: que Robert confirme
    "0 frame drops" con DevTools en un Chrome real si quiere el done-criterion exacto del plan.
- **Task 3.2 (responsive mobile):** `.pat-columns` es flex-row (`.pat-col-ident` max-content + `.pat-txn-col` flex:1
  + `.pat-col-stage` min-width:380px) — desbordaba garantizado bajo ~768px (el stage solo ya pide 380px). Nuevo
  `@media (max-width:767px)` en `pantalla.css`: columnas a stack vertical, `.pat-col-stage` oculto (misión activa en
  mobile → modal aparte, fuera de alcance esta sesión, ya documentado en el plan), `.pat-act`/`.pantalla-close` a
  44px (touch target, eran 26px/30px). Verificado con `resize_window` a 375×812 + estado forzado a `.pantalla-on`
  (rAF no corre en este entorno, ver arriba): `document.documentElement.scrollWidth === window.innerWidth === 375`
  (0 overflow horizontal), `flexDirection:"column"`, `stage display:"none"`, `.pat-act` height `"44px"`.
- **Task 3.3 (reduced-motion):** ya existente (`pantalla.css:838-871`, fade 200ms sin scanline/cuaje/blur) — solo
  se confirmó por lectura, no se tocó.

## Fix — columna de retiro invisible en ancho medio (2026-07-26)

- **Síntoma**: la Task 5 del botón de retiro (`.pat-wd-stage` en `.pat-col-stage`, col 3) pasaba la validación
  visual prescrita (`getBoundingClientRect` overflow vertical ≤0, ver `NEXT-SESSION.md`) pero en la práctica podía
  quedar **mayormente invisible** en ventanas de navegador comunes.
- **Causa raíz** (medida, no supuesta): F3 (arriba) solo cubrió el breakpoint mobile `≤767px` (oculta el escenario
  deliberadamente). Entre ese punto y el desktop ancho NO había breakpoint intermedio — `.pat-col-ident` (max-content,
  depende del combo de la cuenta) + `.pat-col-txns` (min 340px) + `.pat-col-stage` (min 380px) pueden sumar más ancho
  del que da `.pat-columns`, y `.pat-col-stage` se desbordaba HORIZONTAL, clippeado invisible por `overflow:hidden`
  de `.pantalla-sheet`. Medido en vivo (cuenta con combo largo, `espinoza.arellano.alberto.205@gmail.com`): overflow
  presente en viewport 1280px y 1440px (colsScrollWidth 1219 vs colsClientWidth 1138 @1440px), desaparece en 1536px+.
  Rango real de fallo varía según el largo del combo de cada cuenta — **no es un breakpoint fijo**, es contenido vs
  espacio disponible.
- **Por qué el checklist no lo agarró**: el script de validación de `NEXT-SESSION.md` solo mide overflow VERTICAL
  (`rect.bottom` vs `sheetBottom`) — nunca chequeó el eje horizontal.
- **Fix** (`pantalla.css` §`.pat-cramped`, `pantalla.js` `_syncColumnsFit`/`_wireColumnsFitResize`): mismo patrón ya
  usado para `--pat-ident-w` (medida REAL vía JS, no un breakpoint px inventado — `feedback_ui_ancla_medida_no_pixel_inventado`).
  JS mide `pat-columns.scrollWidth > clientWidth` en cada render y en cada resize de ventana; si no caben, marca
  `.pat-wrap.pat-cramped` → CSS apila las 3 columnas en vertical con scroll — **a diferencia de mobile, NO oculta
  `.pat-col-stage`** (con este ancho medio sobra aire vertical para mostrarlo completo debajo).
- **Verificación**: confirmado por lectura de código + medición manual en vivo (`botmexico.net`, KVM4 deployado). El
  toggle de clase en sí se confirmó correcto forzándolo manualmente (el panel queda 100% dentro de la sheet). La
  ejecución AUTOMÁTICA vía `requestAnimationFrame` no se pudo observar en este entorno de verificación por la misma
  limitación ya documentada arriba (rAF no dispara sin compositing) — probado con `setTimeout` equivalente, que sí
  corrió y aplicó la clase correctamente. `_syncIdentWidth` (mismo patrón rAF) ya está en producción hace semanas,
  así que en un navegador real de un operador debería comportarse igual. **Pendiente**: que Robert confirme visual
  en su propio navegador con la ventana en un ancho medio (ej. 1366×768 o 1440×900) — el `overflow ≤0` del checklist
  original ya no es suficiente, agregar chequeo horizontal a futuras validaciones de este panel.

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
`window.Depos.fireCompact()` directo (mismo patrón que `.d-withdraw-fire`), guardado con
`!dep.disabled` (Task 4 lo deshabilita mientras una misión compacta corre). `openDepositModal`
(app.js) gana un guard: si la cuenta objetivo es la misma que `window.Pantalla.currentId`
Y es una sola cuenta (nunca el multi-select bulk, que siempre tiene 2+ ids), no abre el
popup — hace scroll a `.pat-dep-stage` y avisa por toast.

Gotcha resuelto: `openDepos()` es lo único que reseteaba `#depStage.hidden=true`; una
misión compacta nunca pasa por ahí, así que `journeyEnd()` lo re-oculta manualmente
cuando `_dx.target==='compact'` (si no, el panel compacto queda oculto para siempre tras
el primer depósito, por la regla `:has()` de arriba). `showToast()` también se adaptó para
aparecer en el panel activo (`activeEl()`) en vez de siempre en el flotante.

Backend intocable (`deposits.py`, `depos_logic.js`, endpoints) — todo el trabajo vivió en
`static/index.html` (template + slot), `static/depos.js` (doble destino de render) y
`static/pantalla.js` (rescate/montaje + disparo directo). Implementado vía
`superpowers:subagent-driven-development` sobre `docs/superpowers/plans/2026-07-26-deposito-compacto-col3.md`
(spec en `docs/superpowers/specs/2026-07-26-deposito-compacto-col3-design.md`).

Pendiente de que Robert confirme en su propio navegador (ver `NEXT-SESSION.md`): ambos
paneles visibles y apilados en reposo, disparo sin popup, y un smoke funcional de $10
real desde el panel compacto.

## Convenciones

- **`data-copy`** en cualquier elemento → click izquierdo copia el valor. Handler global en app.js:2715.
- **Combo de la tabla** → el **texto** (`b.combo-txt.d-copy[data-copy]`) copia al click; el **resto de la celda** (`td.combo`) abre La Pantalla (2026-07-17). El copiado del combo también vive en La Pantalla (`.pat-combo`, botón dedicado).
- **`.d-copy`** clase utilitaria para elementos copiables (estilo + handler).
- **Cache-bust** en `index.html` con `?v=<timestamp>` para forzar refresh tras deploy (no requiere Ctrl+F5 normalmente).

## Pendientes / WIP conocidos

(de `AVANCES_SESION.md`)
- Tabla compacta 24px de fila (hoy 36px)
- ~~Multi-selección drag por columna de checkboxes~~ → **reemplazado por selección Excel (Ctrl/Shift+Click)** 2026-07-03 (Fase B)
- Detail panel inline `grid-template-rows: 1fr ↔ 0fr` smooth
- ~~Drawer depósitos lateral 480px~~ ✅ implementado 2026-05-25 (420px, no-bloqueante)
- ~~Mini-widget PiP para procesos en curso~~ ✅ implementado 2026-05-25 (mini-pill flotante `#depMissionPill`)
- Auditoría de glow verde residual en `style.css`

Ver `AUDIT.md` para gap-analysis spec vs actual.
