# AUDIT — Comportamiento esperado vs actual

> Mantener vivo. Cada función con su spec + estado actual.
> Leyenda: ✅ funcional · ⚠️ parcial · ❌ roto · 🔵 pendiente

## Captura: 2026-05-11 (post-migración KVM4 + fixes BETMEX_DB + trazabilidad cards)

## Auth / Sesión

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Login con telegram_id + password | ✅ POST `/api/auth/login` set-cookie + redirect | ✅ funciona | ✅ |
| Reset/cambio de password | ✅ POST `/api/auth/set-password` | ✅ | ✅ |
| Logout limpia cookie | ✅ | ✅ | ✅ |
| Cookie expiration / refresh | ❓ comportamiento de expiración no documentado | ❓ | 🔵 |

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
| **Conflict 409 si cuenta lockeada por otro** | ✅ rechaza depósito; SA puede override | ✅ desde 2026-05-11 | ✅ |
| **Watchdog auto-release 27h post-deposit** | ✅ 3 notifs progresivas (T-5min, T+0, T+10min) + auto-release a T+27h | ✅ desde 2026-05-11 | ✅ |
| **Notifs filtradas por dueño del lock** | ✅ solo el operador (o SA) ve la notif | ✅ vía `target_user` en payload + filtro frontend | ✅ |
| **Botones acciones en notif (Depositar / Liberar)** | ✅ click ejecuta deposit modal o `/unlock` | ✅ desde 2026-05-11 | ✅ |

## Depósitos

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Single deposit (`/execute`) | ✅ 1 cuenta, 1 tarjeta, $1-$499 | ✅ | ✅ |
| **Single deposit con fases en vivo (`/execute-stream`)** | ✅ SSE emite `start`/`phase`/`done` para stepper UI; mismas validaciones que `/execute` (cap, velocity, auto-lock) | ✅ desde 2026-05-15 — backend listo, frontend pendiente (Task 3) | ⚠️ |
| Persistir tarjeta al APPROVE | ✅ INSERT en `account_cards` | ✅ (desde fix BETMEX_DB 2026-05-11) | ✅ |
| Persistir cada intento en `deposit_attempts` | ✅ con `card_pipe`, `status`, `rejection_reason` | ✅ (desde fix 2026-05-11) | ✅ |
| Loguear card al inicio del deposit | ✅ logger.info | ✅ (desde fix 2026-05-11) | ✅ |
| Multi/matchmaker SSE | ✅ N cuentas × M tarjetas, pairing greedy, cooldown | ✅ | ✅ |
| Cancelar matchmaker run | ✅ POST `/multi/{id}/cancel` | ✅ | ✅ |
| Scheduled N reps cada 1 min | ✅ aborta al primer fail | ✅ | ✅ |
| Modal scheduled NO se cierra solo | ✅ usuario decide cuándo cerrar | ✅ (desde 2026-05-11) | ✅ |
| Listar schedules activos | ✅ GET `/scheduled/list` | ✅ | ✅ |
| Cancelar schedule | ✅ POST `/scheduled/{id}/cancel` | ✅ | ✅ |
| Cap check pre-deposit | ✅ $499/intento, $1499/24h | ✅ | ✅ |

## Prewarm

| Función | Esperado | Actual | Estado |
|---|---|---|---|
| Pre-cargar JWT + balance para N cuentas | ✅ SSE stream | ✅ | ✅ |
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
