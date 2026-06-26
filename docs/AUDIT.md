# AUDIT — Comportamiento esperado vs actual

> Mantener vivo. Cada función con su spec + estado actual.
> Leyenda: ✅ funcional · ⚠️ parcial · ❌ roto · 🔵 pendiente

## Captura: 2026-06-26 (C1 — modal de depósitos unificado v8, frontend)

### C1 — modal v8 (`static/depos.js` + `depos_logic.js` + `depos.css`)

> Módulo NUEVO autocontenido, convive con el drawer viejo `#depDrawer`. Suplencia por flag `localStorage.deposV8='1'` en `openDepositModal` (app.js). Default OFF = operación intacta. NO toca backend.

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Lógica de modo (`deriveMode`) | 1 cuenta+reps=1→single · 1+reps>1→programado · varias→multi; la UI impone las reglas | ✅ `depos_logic.deriveMode`/`presetsForMode` (7 tests node) | ✅ verificado navegador |
| Fase backend→escena (`mapPhaseToScene`/`phaseToPct`) | 13 fases → login/form/processing/retry/done + % | ✅ `depos_logic` (6 tests); `*_retry`→escena retry | ✅ |
| Cuentas chip combo+grado | `email:password` completo (sin máscara, L2) + hdot grado | ✅ `renderAccounts` + `/api/accounts/combos` | ✅ verificado (shapes reales) |
| Tarjetas (guardadas + agregar) | pre-cargar `/cards-pipe` (single) + pegar pipe validado | ✅ `loadSavedCards`/`renderCards` + `validatePipe` | ✅ verificado |
| Cap 24h | advertencia en nota de monto (v8 no tiene barra) | ✅ `refreshCap` + `/cap-status` | ✅ verificado |
| SINGLE `/execute-stream` | fase→escena, balance before/after, movimiento, E-RED | ✅ `runSingle` + `consumeStream` | ✅ éxito verificado e2e (mock); clasificación real/nuestro (25 tests) |
| SCHEDULED `/scheduled/create` + bus | reps, countdown 7-seg, retry, abort, rehidratación | ✅ `runScheduled`/`_schedOnBus` | ⚠️ implementado + primitivas verificadas; e2e con bus real PENDIENTE de deploy |
| MULTI `/multi/stream` | animación del par activo + bitácora por par (v8 no tiene lanes) | ✅ `runMulti` | ✅ verificado e2e (mock): match→real, rechazo real→no aplicado, nuestro→invisible |
| Run controls + pill | abort cancela; **pause oculto** (sin soporte backend); pill al cerrar con misión activa | ✅ `onAbort`/`pillShow` | ✅ verificado |
| Errores humanizados (L3) | nunca result_code crudo al operador | ✅ `humanError`/`isRealRejection` (review adversarial: L1/L2/L3 CUMPLEN) | ✅ |
| Suplencia por flag | flag OFF = drawer viejo intacto; ON = v8 | ✅ branch en `openDepositModal` | ⚠️ e2e del flag PENDIENTE de deploy/dashboard real |

**Degradado con gracia (backend aún no emite):** balance-before (usa el del row), badge A+/grade live (neutro — B2), pause/resume vivo (oculto — B3), "Otro depósito" paralelo (toast — B4). Fases multi por bus (B3) innecesarias: el modal lee el stream privado del POST.

---

## Captura: 2026-06-25 (SP-1: eliminación /execute + archivado 7 módulos)

### SP-1 — Unificación login/depósito

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| `/api/deposits/execute` eliminado | ✅ endpoint fuga-proxyless borrado — nadie lo consumía; UI usa `/execute-stream` | ✅ eliminado en SP-1 | ✅ |
| `/execute-stream` como único single | ✅ transporte SSE con fases live + `gentle_login` | ✅ desde SP-1 | ✅ |
| `/multi/stream` y `/scheduled/create` | ✅ transporte único vía `gentle_login` | ✅ | ✅ |
| 7 módulos archivados a `_legacy/` | `web_routes_deposits/missions/prewarm/cards/logs/notifications.py` + `web_watchdog.py` → `_legacy/` | ✅ commit `f973fe0` | ✅ |
| `_load_deps` retorna solo `make_pool` | ✅ dependencia simplificada — ya no inyecta `BOT_RUN_DEPOSIT` | ✅ commit `0d51a91` | ✅ |

---

## Captura: 2026-06-01 (reuso de token v2 en gentle_login — anti-desperdicio captcha)

### Login — reuso de token (`login_orchestrator.gentle_login`)

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Reuso de token entre reintentos | ✅ un 406 no consume el token → reusar el mismo (rota solo IP) hasta TTL; pedir nuevo solo si edad≥100s o reusos≥8 | ✅ `test_login` directo con `captcha_token` fijo; `_TOKEN_REUSE_MAX_AGE`/`_TOKEN_MAX_REUSES` | ⚠️ supervivencia-al-406 NO observada en prod aún (test cuadró LIVE 1er intento, sin 406) |
| JWT cache fast-path (intento 0) | ✅ si hay JWT vigente, sin captcha ni POST | ✅ `_db.get_jwt_cache` + margen 60s | ✅ |
| REGLA DE ROBERT (3 razones de muerte) | ✅ solo LOGIN_DENIED/KYC_PENDING/AUTOEXCLUSION matan; resto → retry → LOGIN_RETRY_LATER | ✅ preservada en el refactor | ✅ |
| Persist JWT en LIVE | ✅ guardar en cache tras login fresco | ✅ `_persist_jwt_cache` | ✅ |
| Prefetch pool (programado/single) | ✅ 2 tokens calientes → reintento sin esperar solve | ✅ `make_pool(size=2)` + `prefetch(2)` en scheduled/single | ✅ |
| Smoke funcional (1 cuenta LIVE) | ✅ gentle_login devuelve ok/LIVE/jwt | ✅ 2026-06-01 `ok=True code=LIVE attempts=1 jwt=True` | ✅ |

## Captura: 2026-05-28 (rediseño detalle a panel INLINE + session-reuse en programados)

### Detalle de cuenta — panel inline (rediseño 2026-05-28)

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Panel inline acordeón (reemplaza modal) | ✅ se despliega bajo la fila; celda "Detalles" full-clickable; micro-animaciones open/close | ✅ `_injectExpandedDetail` + `_expandedNode` preservado entre re-renders | ✅ |
| Clicks dentro del panel (en tabla) | ✅ TODO interactivo es `<button>` (divs/spans no reciben clicks en `<table>` — caían a la tabla) | ✅ En uso/copy/expand/paginador/validar = buttons | ✅ |
| SSE no rompe el panel abierto | ✅ `_liveReload()` difiere reload de la tabla mientras hay panel abierto; aplica al cerrar | ✅ | ✅ |
| Movimientos unificados | ✅ `GET /details.movimientos` = `account_transactions` + `deposit_attempts`, ordenados, con `who` (resuelto de WEB_USERS_RAW) y flag nuestros/página | ✅ `app.py` endpoint | ✅ |
| Movimientos: paginador 10/pág | ✅ interno, no choca con paginador de tabla | ✅ `_mvPage` | ✅ |
| Expand transacción nuestra | ✅ revela tarjeta usada (pipe `\|MM\|YY\|`, copiable) + estado Approved/Rejected/3DS a la derecha | ✅ | ✅ |
| Tarjetas + Notas en "Guardado" | ✅ filas colapsables (💳/📝), Agregar tarjeta/nota; auto-guarda tarjeta al aprobar | ✅ | ✅ |
| Toggle "En uso" | ✅ amarillo, lock 2h / unlock vía endpoints existentes | ✅ | ✅ |
| Validar/corregir CURP | ✅ botón abre flujo gob.mx + edita/guarda (handler movido de `#detModalBody` al panel) | ✅ | ✅ |
| CURP estimado `_detectStateCode` | ✅ "COL"(Colonia)≠Colima; "MEX"→MC | ✅ fix 2026-05-28 | ✅ |
| Notas en buscador global | ✅ `note_text LIKE` ya estaba en `/api/accounts?q=` | ✅ | ✅ |

## Captura: 2026-05-25 (drawer lateral + fix persist cards en _record_attempt + fix SSE scheduled_phase race)

## Auth / Sesión

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Login con telegram_id + password | ✅ POST `/api/auth/login` set-cookie + redirect | ✅ funciona | ✅ |
| Reset/cambio de password | ✅ POST `/api/auth/set-password` | ✅ | ✅ |
| Logout limpia cookie | ✅ | ✅ | ✅ |
| Cookie expiration / refresh | ❓ comportamiento de expiración no documentado | ❓ | 🔵 |

### Roster de usuarios (auth.py + web_auth.py)

| Username | telegram_id | Role | Notas |
|---|---|---|---|
| RobertVS | 1341812706 | superadmin | sesión persistente (10y) |
| Lau | 7599631505 | admin | |
| Luisito | 7847239854 | admin | |
| Magdiel | 1059367082 | admin | **promovido de `user` → `admin` 2026-05-22** (antes solo veía cuentas asignadas vía `account_assignments`; ahora ve todas las publicadas a la pool excepto las lockeadas por otros) |

> **Efecto colateral**: el popup "Liberar cuentas a..." (frontend `app.js:1688`) filtra por `role === 'user'`. Ya no hay usuarios con role `user` activos → la lista queda vacía. Si en el futuro hace falta un destino "user" para liberar, agregar uno o cambiar el filtro.

## Cuentas

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Tabla con filtros + paginación | ✅ | ✅ | ✅ |
| Ordenar por columna | ✅ click en `th.th-sort` | ✅ | ✅ |
| Selección masiva (checkbox + selectAll) | ✅ | ✅ | ✅ |
| Click izquierdo en combo copia | ✅ 1-click izq | ✅ (desde 2026-05-11) | ✅ |
| Botón "Seleccionar" en panel detalles | ✅ toggle sin cerrar modal | ✅ (desde 2026-05-11) | ✅ |
| Modal detalles muestra tarjetas guardadas | ✅ con pipe completo, click-para-copiar | ✅ | ✅ |
| Modal detalles muestra intentos del dashboard | ✅ tabla con cuando/monto/tarjeta/estado/razón | ✅ (desde 2026-05-11) | ✅ |
| Modal detalles muestra transacciones BetMexico | ✅ | ✅ | ✅ |
| Notas crear/leer/borrar | ✅ user crea sus notas, SA borra | ✅ | ✅ |
| CURP estimado + validable | ✅ cálculo + botón "Validar gob.mx" | ✅ | ✅ |
| Bulk lock / unlock / trastienda | ✅ | ✅ | ✅ |
| **Filtro "solo con tarjeta" en tabla principal** | ✅ botón 💳 toggle; `GET /api/accounts?cards_only=true` | ✅ desde 2026-05-11 | ✅ |
| **Lista unificada de tarjetas** | ✅ `GET /api/cards/all` (account_cards + account_notes con card, deduplicado) | ✅ desde 2026-05-11 | ✅ |
| **Auto-lock al iniciar depósito** | ✅ cuenta queda lockeada para operador (single 2h, multi 2h, scheduled 4h) | ✅ desde 2026-05-11 | ✅ |
| **Filtro lock-aware en `/api/accounts`** | ✅ non-SA solo ve libres O propias; SA ve todo | ✅ desde 2026-05-11 | ✅ |
| **Filtro published_to_pool en `/api/accounts`** | ✅ non-SA solo ve `published_to_pool=1`; SA ve todo (trastienda + pool) | ✅ (`app.py:347-348`) | ✅ |
| **Bulk unpublish 2026-05-22** | n/a — operación manual: 45 cuentas publicadas (todas `status=DEAD`) → `published_to_pool=0` para ocultarlas a admins. Total pool ahora 0 visibles a non-SA. | ✅ ejecutado en KVM4 prod | ✅ |
| **A1 · Modelo de 5 estados** | TRASTIENDA / POOL / EN_USO / RESERVADA_SA / DEAD derivados de `locked_by`+`locked_until`+`published_to_pool`. Ver `docs/ARCHITECTURE.md` §Modelo de estados. | ✅ rama `feat/sp3-a1-estados-cuentas` (11 tests verde) — **sin deploy** | ⚠️ |
| **A1 · RESERVADA_SA** | SA que lockea/deposita → `locked_until=NULL` = lock perpetuo, invisible a operadores, intocable por watchdogs; solo lo libera unlock manual del SA. | ✅ `lock_account`+`_auto_lock_for_deposit`+`unlock_account` | ⚠️ sin deploy |
| **A1 · Liberador canónico único** | `_release_account()` = el ÚNICO release automático (janitor). Atómico: limpia lock+notif_*, **republica** `published_to_pool=1`, 1 broadcast. `window_watcher` y `release_watchdog` = notificadores puros (perdieron sus releases: fase 3 muerta + caso 1 27h). | ✅ consolidación 3→1 | ⚠️ sin deploy |
| **A1 · Guardrail publish/hide** | `publish(False)`/`hide-all` no ocultan cuentas con `locked_by IS NOT NULL` (evita fantasma published=0+lock). | ✅ | ⚠️ sin deploy |
| **A1 · Backfill legacy** | `_migrate`: locks legacy sin `locked_until` → `locked_at+24h` (no toca SA). Defensivo+idempotente; medido 0 filas hoy. | ✅ | ⚠️ sin deploy |

## Grading / Payment Analyzer

> Canónico: `repos/botmex-dashboard/shared/betmexico_payment_analyzer.py` (V10 desde 2026-05-22). Deploy a KVM4 reemplaza `/docker/betmexico/code/betmexico_payment_analyzer.py` directamente. NO se toca el monorepo.

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Algoritmo V10 (matriz por reglas) | A = sana (sin fail ≥60d, max 2 fails juntos, total ≤3); B = reparándose; C = masacrada hace ≥90d; D = fail <14d O ≥3 sesiones machine-gun | ✅ desde 2026-05-22 | ✅ |
| Bug parser microsegundos | `_parse_txn_date` tolera microsegundos de cualquier longitud (BD tiene `.94907` con 5 dígitos que rompía `fromisoformat` en Python <3.11) | ✅ fix V10 | ✅ |
| Backfill on-demand | `scripts/recalc_grades.py` recorre `accounts`, recalcula desde `account_transactions`, persiste grade+score | ✅ ejecutado 2026-05-22: 810/902 cambiaron | ✅ |
| Distribución post-V10 | A:145, B:300, C:142, D:307 (era A:605, B:209, C:78, D:1) | ✅ refleja realidad de pasarelas | ✅ |
| **BD viva: deposit hooks** | Login pre-deposit guarda txns + recalc grade; `_persist_final` post-intento recalc grade | ✅ lógica migrada a `deposits.py` (`_run_deposit_with_phases`, `_record_attempt`) | ✅ |
| **BD viva: prewarm hooks** | `_db_save_txns_and_recalc` guarda txns + recalc grade vía BOT_SCORE_PAYMENT (V10 después del deploy 2026-05-22) | ✅ `prewarm.py:234` | ✅ |
| BD viva: watchdog | Solo actualiza balance (`fetch_mode=balance_only`). NO trae txns nuevas → grade no se recalcula desde watchdog | ⚠️ por diseño (performance) | ⚠️ |
| **Conflict 409 si cuenta lockeada por otro** | ✅ rechaza depósito; SA puede override | ✅ desde 2026-05-11 | ✅ |
| **Watchdog auto-release 27h post-deposit** | ✅ 3 notifs progresivas (T-5min, T+0, T+10min) + auto-release a T+27h | ✅ desde 2026-05-11 | ✅ |
| **Notifs filtradas por dueño del lock** | ✅ solo el operador (o SA) ve la notif | ✅ vía `target_user` en payload + filtro frontend | ✅ |
| **Botones acciones en notif (Depositar / Liberar)** | ✅ click ejecuta deposit modal o `/unlock` | ✅ desde 2026-05-11 | ✅ |

## Depósitos

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Single deposit (`/execute`) | ❌ eliminado SP-1 (fuga proxyless; sin consumidor — UI usaba `/execute-stream`) | ❌ eliminado 2026-06-25 | ✅ (correcto eliminar) |
| **Single deposit con fases en vivo (`/execute-stream`)** | ✅ SSE emite `start`/`phase`/`done` para stepper UI; validaciones (cap, velocity, auto-lock); frontend pinta `#depStepper` con 4 fases (login/begin/submit/check) — `na` para `check` cuando `is_3ds=true` | ✅ único endpoint single desde SP-1 | ✅ |
| Persistir tarjeta al APPROVE (single moderno, multi, scheduled) | ✅ INSERT en `account_cards` vía `_record_attempt` cuando `status=approved` (idempotente por UNIQUE card_number) | ✅ desde 2026-05-25 — fix retroactivo: el wrapper `_run_deposit_with_phases` NUNCA llamaba a `register_card_to_account` (solo el legacy `_run_deposit` lo hacía). Resultado: tras un APPROVED por endpoints modernos, la tarjeta quedaba huérfana y el operador tenía que pegarla de nuevo. AUDIT viejo decía ✅ pero era falso para single/multi/scheduled. Fix: bloque dedicado en `_record_attempt` ([deposits.py:441](../deposits.py)). | ✅ |
| Persistir cada intento en `deposit_attempts` | ✅ con `card_pipe`, `status`, `rejection_reason` | ✅ (desde fix 2026-05-11) | ✅ |
| Loguear card al inicio del deposit | ✅ logger.info | ✅ (desde fix 2026-05-11) | ✅ |
| Multi/matchmaker SSE | ✅ N cuentas × M tarjetas, pairing greedy, cooldown 5s, velocity-skip throttle 30s, pool init dentro de try (lock release garantizado si CapMonster down) | ✅ desde 2026-05-21 | ✅ |
| **Taxonomía DEAD del matchmaker** | ✅ SOLO `AUTOEXCLUSION`/`KYC_PENDING` marcan `status='DEAD'` en BD. `LOGIN_FAILED` (406/captcha/proxy) emite `login_retry` SSE — sale del run en memoria, sin tocar BD ni penalizar cuenta. `3DS_UNDETECTED`/`SHADOW_BAN?` caen en `else` (strike cuenta+tarjeta, no DEAD). Un solo punto de escritura DEAD en todo el dashboard: `deposits.py:1567`. | ✅ corregido 2026-05-28 — antes `LOGIN_FAILED` mataba cuentas buenas el 100% de las veces (rama DEAD compartida con AUTOEXCLUSION). Recovery: 5 cuentas restauradas a `status='LIVE'` en prod. | ✅ |
| Cancelar matchmaker run | ✅ POST `/multi/{id}/cancel` | ✅ | ✅ |
| Scheduled N reps cada 1 min | ✅ aborta al primer fail | ✅ |
| **Scheduled: reuso de sesión (sin re-login)** | ✅ iter 0 hace login real (1 captcha) y captura `jwt`+`used_proxy`; iters 1..N reusan esa sesión vía `session_jwt`/`session_proxy` en `_run_deposit_with_phases` → **0 captchas extra**, sin latencia de login, misma IP todo el run. JWT vive ~7 días (medido en prod), run ≤20 min → seguro. Emite `login_reused` en vez de `login_start`/`login_done`. Si la sesión fallara mid-run, aborta como cualquier fail (sin re-login automático — decisión 2026-05-28). | ✅ desde 2026-05-28 | ✅ |
| **Scheduled: cadencia 1 min desde fin del depósito** | ✅ `await asyncio.sleep(60)` completo DESPUÉS de lograr el depósito (antes era `interval - elapsed` desde el inicio del intento). Robert 2026-05-28: "debe pasar 1 minuto a partir de que se logra el depósito, no a partir de que se inicia". Se eliminó toda la maquinaria de pre-refresh de captcha entre iters (ya no se necesita con reuso de sesión). | ✅ desde 2026-05-28 | ✅ | ✅ |
| **Scheduled con fases en vivo** | ✅ `scheduled_create.loop()` usa `_run_deposit_with_phases` con `phase_cb` que emite `kind:scheduled_phase` por sub-fase (login/begin/submit/check/done). Feed renderiza con `_schedPhaseLabel()`. Eventos summary `scheduled`/`scheduled_aborted`/`scheduled_cancelled` siguen igual | ✅ 2026-05-15 — Task 5 deposit-live-progress | ✅ |
| Modal scheduled NO se cierra solo | ✅ usuario decide cuándo cerrar | ✅ (desde 2026-05-11) | ✅ |
| **Drawer lateral derecho (no-bloqueante)** | ✅ reemplaza al ex-modal centrado bloqueante. Slide-in 260ms, 420px de ancho. El dashboard atrás sigue interactuable (tabla, sidebar, scroll). Tabs `⚡ Una · 👥 Multi · ⏰ Prog.` en una sola vista. Si se cierra mid-misión, queda mini-pill flotante abajo-derecha que reabre el drawer sin perder state. | ✅ desde 2026-05-25 | ✅ |
| **Feedback live durante pool warm-up del scheduled** | ✅ hint rotator (`⚡ Calentando captcha pool` → `🔑 Solicitando token` → `🚀 Levantando worker`) durante los 5-15s previos al primer `scheduled_phase`. Watchdog 30s en frontend que alerta si no llega ninguna señal. Heartbeat `kind:scheduled_started` desde backend antes de `pool.start_factory()`. Buffer de eventos pre-`_schedShow` para evitar race condition de sched_id. | ✅ desde 2026-05-25 — fix tras reporte "modal Programado se queda fijo 30s+" | ✅ |
| **SSE bus comparte estado entre módulos (fix doble-import)** | ✅ `sys.modules.setdefault("app", sys.modules[__name__])` en el entry point garantiza que `from app import _broadcast` desde `deposits.py` reutilice la instancia de `__main__`. Una sola `_sse_queues` global → broadcasts encuentran clientes. | ✅ desde 2026-05-26 — bug real causante de "Sin señal del backend (>30s)" | ✅ |
| Listar schedules activos | ✅ GET `/scheduled/list` | ✅ | ✅ |
| Cancelar schedule | ✅ POST `/scheduled/{id}/cancel` | ✅ | ✅ |
| Cap check pre-deposit | ✅ $499/intento, $1499/24h | ✅ | ✅ |

## Prewarm

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Pre-cargar JWT + balance para N cuentas | ✅ SSE stream. JWT cache se invalida siempre que `details` venga vacío (silent 401). Cliente disconnect cancela tasks pendientes (no quema captchas) | ✅ desde 2026-05-21 | ✅ |
| Pause-on-deselect | ✅ cancela si el operador desmarca | ✅ | ✅ |
| Auto-stop si CapMonster < $5 | ✅ saldo warning | ✅ | ✅ |
| Force-refresh para SA | ✅ pasa cap-check | ✅ | ✅ |
| Refresh visible accounts (SSE) | ✅ POST `/refresh-stream` | ✅ | ✅ |

## Bitácora / Trazabilidad

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Feed actividad LIVE | ✅ SSE push + scrollable feed | ✅ | ✅ |
| Columna "Tarjeta" en actividad | ✅ pipe completo clickeable | ✅ (desde 2026-05-11) | ✅ |
| Histórico paginado de actividad | ✅ GET `/api/activity` con filtros | ✅ | ✅ |
| `payment_tests` legacy escribiendo | ⚠️ era legacy del bot. Hoy `deposits.py` (`_run_deposit_with_phases`) escribe en `deposit_attempts`; `payment_tests` ya no se escribe activamente | ⚠️ tabla potencialmente obsoleta | 🔵 |
| Persistir `gateway_response_raw` con info útil | ✅ JSON serializable con resultCode, orderId, etc. | ✅ `_persist_final` lo guarda | ✅ |
| 1 sola row en `deposit_attempts` por intento (sin duplicación) | ✅ | ✅ desde 2026-05-11 (consolidado en `_persist_final`) | ✅ |
| Histórico de tarjetas por cuenta (último uso, fails, status) | ✅ tabla `account_cards` con total_deposits/approved/rejected | ✅ | ✅ |

## Admin / Controles SA

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Diagnóstico full | ✅ GET `/api/admin/diag` | ✅ | ✅ |
| Ping a targets | ✅ POST `/api/admin/ping` | ✅ | ✅ |
| Refresh proxy | ✅ POST `/api/admin/refresh-proxy` | ✅ | ✅ |
| Restart services | ✅ POST `/api/admin/services/restart` | ✅ | ✅ |
| Export logs | ✅ GET `/api/admin/export-logs` | ✅ | ✅ |
| Pause / Resume / Emergency stop | ✅ | ✅ | ✅ |
| VPS reboot (1min delay) | ✅ | ✅ | ✅ |
| Healthcheck full (CapMonster, proxies, WSai) | ✅ GET `/api/health/full` | ✅ | ✅ |

## Notificaciones

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Bell badge con count | ✅ icono topbar | ✅ in-memory | ⚠️ no persistente — se pierde al refresh |
| Lista de notif (modal/section) | ✅ | ✅ | ✅ |
| Mark all read | ✅ | ✅ (in-memory) | ⚠️ no persistente |
| Notificaciones críticas (CapMonster low, proxy down, etc.) | ✅ pushadas vía SSE | ✅ | ✅ |
| Histórico persistente | ❌ no implementado | ❌ | 🔵 — código en `_legacy/web_routes_notifications.py` (archivado SP-1) |

## Módulos archivados a `_legacy/` (SP-1, 2026-06-25)

| Módulo | Función original | Estado |
|---|---|---|
| `_legacy/web_routes_deposits.py` | Router HTTP de depósito single (`/execute`) | ✅ archivado — funcionalidad en `deposits.py` (`/execute-stream`) |
| `_legacy/web_routes_missions.py` | Sistema de misiones batch/scheduled | ✅ archivado — funcionalidad en `deposits.py` (`multi_stream`/`scheduled_create`) |
| `_legacy/web_routes_prewarm.py` | Router de prewarm (duplicado) | ✅ archivado — `prewarm.py` es el activo |
| `_legacy/web_routes_cards.py` | CRUD tarjetas + ban + usage tracking | ✅ archivado — `GET /api/cards/all` inline en `app.py` |
| `_legacy/web_routes_logs.py` | Logs con filtros avanzados | ✅ archivado — `GET /api/logs` inline en `app.py` |
| `_legacy/web_routes_notifications.py` | Notificaciones persistentes en BD | ✅ archivado — SSE in-memory en `app.py` |
| `_legacy/web_watchdog.py` | Watchdog de balance | ✅ archivado — watchdog de balance no reemplazado; auto-release de locks en `app.py:_release_watchdog_loop` |

## Infra / Deploy

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Deploy Docker Compose KVM4 | ✅ `/docker/betmexico/` | ✅ | ✅ |
| HTTPS auto con Let's Encrypt | ✅ via Traefik | ✅ | ✅ |
| Hot-mount de código (sin rebuild) | ✅ `./code:/app` | ✅ | ✅ |
| Hot-mount de BD | ✅ `./data:/data` | ✅ | ✅ |
| BD compartida entre bot + web | ✅ misma file | ✅ (desde fix BETMEX_DB) | ✅ |
| Auto-restart al fail | ✅ `restart: unless-stopped` | ✅ | ✅ |
| Backups BD | 🔵 no programado | ❌ | 🔵 — pendiente cron |

## Pendientes de spec confirmada (preguntar a Robert)

- ¿`payment_tests` se debería deprecar? (duplicación con `deposit_attempts`)
- ¿Desarchivar/reimplementar `_legacy/web_routes_notifications.py` para que las notif persistan?
- ¿Desarchivar/reimplementar `_legacy/web_routes_missions.py` (sistema más completo que `/api/deposits/scheduled`)?
- ¿Cadencia para backups BD?

## Test rápido del principio operativo

> Si Robert busca lo que pasó con cuenta X hace 1 semana, puede:
> - ✅ Ver intentos del dashboard en `deposit_attempts` con `card_pipe`
> - ✅ Ver tarjetas validadas en `account_cards` con last_used + total_*
> - ✅ Ver eventos en feed `/api/activity` con filtros por who, kind, time, search
> - ✅ Ver respuesta cruda del banco en `gateway_response_raw` (persistido por `deposits.py:_record_attempt`)
> - ⚠️ NO persisten notificaciones del bell (se pierden al refresh)
> - 🔵 NO hay vista de misiones largo plazo (`_legacy/web_routes_missions.py` archivado SP-1)
