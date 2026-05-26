# AUDIT — Comportamiento esperado vs actual

> Mantener vivo. Cada función con su spec + estado actual.
> Leyenda: ✅ funcional · ⚠️ parcial · ❌ roto · 🔵 pendiente

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

## Grading / Payment Analyzer

> Canónico: `repos/botmex-dashboard/shared/betmexico_payment_analyzer.py` (V10 desde 2026-05-22). Deploy a KVM4 reemplaza `/docker/betmexico/code/betmexico_payment_analyzer.py` directamente. NO se toca el monorepo.

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Algoritmo V10 (matriz por reglas) | A = sana (sin fail ≥60d, max 2 fails juntos, total ≤3); B = reparándose; C = masacrada hace ≥90d; D = fail <14d O ≥3 sesiones machine-gun | ✅ desde 2026-05-22 | ✅ |
| Bug parser microsegundos | `_parse_txn_date` tolera microsegundos de cualquier longitud (BD tiene `.94907` con 5 dígitos que rompía `fromisoformat` en Python <3.11) | ✅ fix V10 | ✅ |
| Backfill on-demand | `scripts/recalc_grades.py` recorre `accounts`, recalcula desde `account_transactions`, persiste grade+score | ✅ ejecutado 2026-05-22: 810/902 cambiaron | ✅ |
| Distribución post-V10 | A:145, B:300, C:142, D:307 (era A:605, B:209, C:78, D:1) | ✅ refleja realidad de pasarelas | ✅ |
| **BD viva: deposit hooks** | Login pre-deposit guarda txns + recalc grade; `_persist_final` post-intento recalc grade | ✅ `web_routes_deposits.py:160-165, 67-101` | ✅ |
| **BD viva: prewarm hooks** | `_db_save_txns_and_recalc` guarda txns + recalc grade vía BOT_SCORE_PAYMENT (V10 después del deploy 2026-05-22) | ✅ `prewarm.py:234` | ✅ |
| BD viva: watchdog | Solo actualiza balance (`fetch_mode=balance_only`). NO trae txns nuevas → grade no se recalcula desde watchdog | ⚠️ por diseño (performance) | ⚠️ |
| **Conflict 409 si cuenta lockeada por otro** | ✅ rechaza depósito; SA puede override | ✅ desde 2026-05-11 | ✅ |
| **Watchdog auto-release 27h post-deposit** | ✅ 3 notifs progresivas (T-5min, T+0, T+10min) + auto-release a T+27h | ✅ desde 2026-05-11 | ✅ |
| **Notifs filtradas por dueño del lock** | ✅ solo el operador (o SA) ve la notif | ✅ vía `target_user` en payload + filtro frontend | ✅ |
| **Botones acciones en notif (Depositar / Liberar)** | ✅ click ejecuta deposit modal o `/unlock` | ✅ desde 2026-05-11 | ✅ |

## Depósitos

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Single deposit (`/execute`) | ✅ 1 cuenta, 1 tarjeta, $1-$499. `_record_attempt` corre siempre (incluso si client disconnect mid-deposit) | ✅ desde 2026-05-21 | ✅ |
| **Single deposit con fases en vivo (`/execute-stream`)** | ✅ SSE emite `start`/`phase`/`done` para stepper UI; mismas validaciones que `/execute` (cap, velocity, auto-lock); frontend consume stream y pinta `#depStepper` con 4 fases (login/begin/submit/check) — `na` para `check` cuando `is_3ds=true` | ✅ 2026-05-15 — backend (Task 1+2) + frontend (Task 3) listos. `/execute` queda como endpoint legacy no consumido por single mode (multi/scheduled siguen usando sus endpoints) | ✅ |
| Persistir tarjeta al APPROVE (single moderno, multi, scheduled) | ✅ INSERT en `account_cards` vía `_record_attempt` cuando `status=approved` (idempotente por UNIQUE card_number) | ✅ desde 2026-05-25 — fix retroactivo: el wrapper `_run_deposit_with_phases` NUNCA llamaba a `register_card_to_account` (solo el legacy `_run_deposit` lo hacía). Resultado: tras un APPROVED por endpoints modernos, la tarjeta quedaba huérfana y el operador tenía que pegarla de nuevo. AUDIT viejo decía ✅ pero era falso para single/multi/scheduled. Fix: bloque dedicado en `_record_attempt` ([deposits.py:441](../deposits.py)). | ✅ |
| Persistir cada intento en `deposit_attempts` | ✅ con `card_pipe`, `status`, `rejection_reason` | ✅ (desde fix 2026-05-11) | ✅ |
| Loguear card al inicio del deposit | ✅ logger.info | ✅ (desde fix 2026-05-11) | ✅ |
| Multi/matchmaker SSE | ✅ N cuentas × M tarjetas, pairing greedy, cooldown 5s, velocity-skip throttle 30s, pool init dentro de try (lock release garantizado si CapMonster down) | ✅ desde 2026-05-21 | ✅ |
| Cancelar matchmaker run | ✅ POST `/multi/{id}/cancel` | ✅ | ✅ |
| Scheduled N reps cada 1 min | ✅ aborta al primer fail | ✅ | ✅ |
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
| `payment_tests` legacy escribiendo | ⚠️ era legacy del bot. Hoy `web_routes_deposits` escribe ahí + en `deposit_attempts` | ⚠️ duplicación entre tablas (no rows) | 🔵 |
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
| Histórico persistente | ❌ no implementado | ❌ | 🔵 — `web_routes_notifications.py` lo tiene pero NO está montado |

## Routers legacy NO montados

| Router | Función teórica | Acción |
|---|---|---|
| `web_routes_cards.py` (`/api/cards`) | CRUD tarjetas + ban + usage tracking | 🔵 evaluar activar |
| `web_routes_missions.py` (`/api/missions`) | Sistema misiones más completo que `/api/deposits/scheduled` | 🔵 evaluar reemplazo o coexistencia |
| `web_routes_notifications.py` (`/api/notifications`) | Notificaciones persistentes en BD | 🔵 activar (fix gap arriba) |
| `web_routes_logs.py` (`/api/logs`) | Logs con filtros avanzados | 🔵 evaluar reemplazo de `/api/logs` actual |
| `web_routes_prewarm.py` | Duplicado de `prewarm.py` actual | 🔵 borrar uno (evaluar diferencias) |
| `web_routes_watchdog.py` | Watchdog del sistema | 🔵 leer y decidir |

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
- ¿Activar `web_routes_notifications` para que las notif persistan?
- ¿Reemplazar `/api/deposits/scheduled` por `web_routes_missions` (sistema más completo)?
- ¿Cadencia para backups BD?

## Test rápido del principio operativo

> Si Robert busca lo que pasó con cuenta X hace 1 semana, puede:
> - ✅ Ver intentos del dashboard en `deposit_attempts` con `card_pipe`
> - ✅ Ver tarjetas validadas en `account_cards` con last_used + total_*
> - ✅ Ver eventos en feed `/api/activity` con filtros por who, kind, time, search
> - ✅ Ver respuesta cruda del banco en `gateway_response_raw` (cuando viene por web_routes_deposits)
> - ⚠️ NO persisten notificaciones del bell (se pierden al refresh)
> - 🔵 NO hay vista de misiones largo plazo (web_routes_missions legacy)
