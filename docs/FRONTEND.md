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
- **2 columnas**: izquierda **Movimientos** (unificados `d.movimientos`: nuestros con ⚡ + "quién" inline + expand revela tarjeta + estado Approved/Rejected/3DS a la derecha; de la página con 🌐), paginador interno 10/pág (`_mvPage`). Derecha **Guardado** (💳 tarjetas + 📝 notas en filas, colapsable, con Agregar; auto-guarda tarjeta al aprobar).
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

**Rehidratación de misión scheduled al recargar** — 2026-05-26 (`rehydrateActiveScheduled()`):
- Tras `loadMe()` + `reload()` + `connectSSE()`, el init llama `rehydrateActiveScheduled()`.
- Fetch `GET /api/deposits/scheduled/list`. Si hay misión activa del user (backend ya filtra para non-SA), reabre el drawer en modo schedule, llena `_depAccountIds`/`#depTargetEmail`/`#depTargetBalance` desde `state.rows`, repinta `#depCardPipe`, y llama `_schedShow(sched_id, repetitions, {currentIter, resumed: true})` para anclar la barra al iter actual sin esperar al próximo evento SSE.
- Toast informa: `↺ Misión activa reanclada · iter X/N · email`.
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

## Tabla principal (`#accTable`)

**Render**: `renderTable()` (app.js:450).
**Source**: `state.rows[]` (todas) o `getVisible()` (filtradas).

**Handler global** (app.js:2034 — `#accTable.click`):
| Target | Acción |
|---|---|
| `.row-ic` (iconitos 💳/📝/+) | Abre detalle o quick-add note |
| `th.th-sort` | Ordena por columna |
| `.rowsel` | Toggle individual de selección |
| `#selAll` | Select all visible |
| `.row-details` | Abre modal de detalles |
| `td.combo b` | **Click izquierdo copia combo `email:password`** (desde 2026-05-11) |
| Resto de la fila | Toggle selección (sin abrir modal) |

**Handler context (click derecho)** (app.js:2092 — `#accTable.contextmenu`): mantiene comportamiento de copia para usuarios habituados.

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

## Strip superior (`#adminPanel`) — reorg 2026-06-29

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
- **Divisor horizontal del strip** (`.lp-vgutter`/`.lp-vgrip`, ↕ row-resize). Entre el `.lpanel` y `#accDockZone` dentro de `#accountsMain`. Arrastra ↕ para ajustar la **altura del strip vs la tabla** (reclamar el espacio vacío de las cards para ver más cuentas); **doble-click restaura**. `initLpVResize()` (app.js) fija `height`/`min-height` inline en `#adminPanel`, persiste en `localStorage['bmx.lpHeight.v2']`.
  - **Default COMPACTO**: `.lpanel { height: 212px }` (Robert: arranca compacto, la tabla gana el resto). El v2 de la key ignora alturas guardadas viejas.
  - **Límites**: clamp `[96px, alto-TABLE_RESERVE(300)]` → la tabla **nunca desaparece** (siempre ≥300px para filterbar+tabla+pagebar).
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
  - **Tabla densa + columnas medidas**: `tbody td { height:30px; padding:0 10px }` (antes `4px 10px`); `table-layout:auto` + `<colgroup>` (clases `c-grade/c-sel/c-saldo/c-cuenta/c-dep/c-check/c-checks/c-ic`, inyectado en `renderTable`). La columna **Cuenta** se ajusta al combo (`--combo-width`, **+16ch si alguna fila visible está lockeada** para que el lock-chip no se corte); la columna **iconos** (`c-ic: width 100%`) absorbe el sobrante como margen a la derecha → **todo el contenido agrupado a la izquierda** (sin el hueco gigante que dispersaba). `td.combo`/`td.row-icons` con `overflow:visible`.
  - **Selección suave + cursor**: `tbody tr { transition: background var(--ease-fast) }`; se **quitó** la barra accent del `td:first-child` (pisaba la barra de salud/grade) y el `cursor:cell` del drag (se veía feo) → `body.dragging-sel` solo bloquea `user-select`.
- **P7 — Interacción de la tabla rediseñada (selección/copy/detalle).** Modelo nuevo pedido por Robert:
  - **Easy-copy del combo** ahora con **click IZQUIERDO** (antes copiaba por contextmenu/click derecho = "mal configurado"). Copia **toda la celda** `td.combo` (no solo el `<b>`) → fácil de atinar. Cursor `copy`.
  - **Selección** = **click izquierdo en cualquier parte de la fila** (de la columna Cuenta a la derecha, salvo el combo y controles ↻/iconos/checkbox). Togglea `row-sel`.
  - **Detalle** = **click DERECHO** en cualquier parte de la fila → `openDetailModal()` (que es un **toggle** de acordeón inline: abre/cierra). Se **eliminó la columna "Detalles"** (th + td + botón `detailsBtn`); colspan 7/9 → 6/8 (`_detailColspan()` cuenta `<td>` del DOM, se autoajusta). Los iconos 💳/📝 siguen abriendo el detalle con click izq.
  - **Drag-select**: arrastrar el mouse sobre las filas selecciona/deselecciona varias. El modo (`select`/`deselect`) lo fija el estado de la fila donde empieza el arrastre (`_dragSel`); el primer `mousemove` incluye la fila inicial; `mouseup` con movimiento setea `_suppressNextRowClick` para que el click posterior no re-togglee. `body.dragging-sel` aplica `user-select:none`. No arranca sobre el combo/controles. + el botón "Borrar selección" de la banda.
  - **Feedback premium**: barra `accent` (`box-shadow inset 3px`) a la izquierda de la fila seleccionada; cursor `copy` en combo, `cell` durante el drag.



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

## Convenciones

- **`data-copy`** en cualquier elemento → click izquierdo copia el valor. Handler global en app.js:2715.
- **`data-combo`** en `<b>` dentro de `td.combo` → click izquierdo copia. Handler en row click handler (app.js:2034).
- **`.d-copy`** clase utilitaria para elementos copiables (estilo + handler).
- **Cache-bust** en `index.html` con `?v=<timestamp>` para forzar refresh tras deploy (no requiere Ctrl+F5 normalmente).

## Pendientes / WIP conocidos

(de `AVANCES_SESION.md`)
- Tabla compacta 24px de fila (hoy 36px)
- Multi-selección drag por columna de checkboxes
- Detail panel inline `grid-template-rows: 1fr ↔ 0fr` smooth
- ~~Drawer depósitos lateral 480px~~ ✅ implementado 2026-05-25 (420px, no-bloqueante)
- ~~Mini-widget PiP para procesos en curso~~ ✅ implementado 2026-05-25 (mini-pill flotante `#depMissionPill`)
- Auditoría de glow verde residual en `style.css`

Ver `AUDIT.md` para gap-analysis spec vs actual.
