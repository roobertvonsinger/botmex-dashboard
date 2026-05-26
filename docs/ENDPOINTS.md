# ENDPOINTS — tabla maestra del backend

> Generado por inventario el 2026-05-11. Actualizar SIEMPRE al agregar/modificar/borrar un endpoint (la skill `botmex-bitacora` lo recuerda).

## Routers activos

| Router | Prefix | Source | Incluido en app |
|---|---|---|---|
| `_prewarm_router` | `/api/prewarm` | `prewarm.py` | ✅ `app.py:165` |
| `_deposits_router` | `/api/deposits` | `deposits.py` | ✅ `app.py:166` |
| `cards` | `/api/cards` | `web_routes_cards.py` | ❌ NO incluido (legacy) |
| `missions` | `/api/missions` | `web_routes_missions.py` | ❌ NO incluido (legacy) |
| `logs` | `/api/logs` | `web_routes_logs.py` | ❌ NO incluido (legacy) |
| `notifications` | `/api/notifications` | `web_routes_notifications.py` | ❌ NO incluido (legacy) |

> Los routers "NO incluidos" tienen código completo pero no están publicados. Sus endpoints existen en disco pero el frontend NO los puede llamar. Ver `AUDIT.md` para gap analysis.

---

## Auth

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/login` | Página de login | público | — | HTML `login.html` | `app.py:176` |
| GET | `/` | Dashboard (root) | público (redirige a `/login` si no hay sesión) | — | HTML `index.html` | `app.py:183` |
| GET | `/favicon.ico` | Favicon | público | — | 204 No Content | `app.py:171` |
| POST | `/api/auth/login` | Iniciar sesión | público | `{telegram_id, password}` | `{ok, user, set_cookie bmx_auth}` | `app.py:205` |
| POST | `/api/auth/set-password` | Setear/cambiar password | require_session | `{old_password?, new_password}` | `{ok}` | `app.py:234` |
| POST | `/api/auth/logout` | Cerrar sesión | require_session | — | `{ok}` (invalida cookie) | `app.py:262` |
| GET | `/api/auth/me` | Datos del usuario actual | require_session | — | `{telegram_id, username, role, display}` | `app.py:270` |

## Health & Diagnóstico

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/health` | Healthcheck básico | público | — | `{ok, db, accounts}` | `app.py:281` |
| GET | `/api/health/full` | Healthcheck completo (CapMonster, proxies, WSai) | require_session | — | `{checks: [...]}` | `app.py:948` |
| GET | `/api/health/last` | Último healthcheck cacheado | require_session | — | `{ts, summary}` | `app.py:1159` |
| POST | `/api/health/dismiss` | Marcar issue como dismisseada | superadmin | `{kind}` | `{ok}` | `app.py:1164` |

## Cuentas

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/accounts` | Listar cuentas con filtros | require_session | query: `status, search, limit, offset` | `{rows, total}` | `app.py:291` |
| POST | `/api/accounts/refresh` | Forzar re-check de cuentas seleccionadas | require_session | `{account_ids}` | `{queued}` | `app.py:859` |
| POST | `/api/accounts/{account_id}/lock` | Lock manual (con duración) | require_session | `{minutes}` | `{ok, locked_until}` | `app.py:1365` |
| POST | `/api/accounts/{account_id}/unlock` | Liberar lock | require_session | — | `{ok}` | `app.py:1458` |
| POST | `/api/accounts/publish` | Publicar cuenta(s) al pool | require_session | `{account_ids}` | `{ok, count}` | `app.py:1402` |
| POST | `/api/accounts/hide-all` | Despublicar todas | require_session | — | `{ok, count}` | `app.py:1421` |
| GET | `/api/accounts/{account_id}/cards-pipe` | Pipe puro de tarjetas (copy-paste) | require_session | — | `{pipes: ["num\|exp\|cvv"]}` | `app.py:1513` |
| GET | `/api/accounts/{account_id}/notes-summary` | Resumen para iconito de fila | require_session | — | `{count, mine}` | `app.py:1542` |
| GET | `/api/accounts/{account_id}/details` | Detalle completo (modal) — incluye `cards`, `transactions`, `deposit_attempts`, `notes` | require_session | — | `{...}` | `app.py:1571` |
| POST | `/api/accounts/{account_id}/notes` | Crear nota | require_session | `{text}` | `{ok, id}` | `app.py:1657` |
| DELETE | `/api/accounts/{account_id}/notes/{note_id}` | Borrar nota (superadmin) | superadmin | — | `{ok}` | `app.py:1709` |
| POST | `/api/accounts/{account_id}/curp` | Guardar CURP validado | require_session | `{curp}` | `{ok}` | `app.py:1694` |
| POST | `/api/accounts/combos` | Devolver `email:password` de IDs (para copy masivo) | require_session | `{ids}` | `{combos: [{id, email, password}]}` | `app.py:1729` |

## Pool

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/pool/accounts` | Cuentas publicadas en pool (no-SA) | require_session | — | `{rows}` | `app.py:1436` |

## Usuarios / Asignaciones

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/users` | Listar usuarios (operadores) | superadmin | — | `{users}` | `app.py:372` |
| GET | `/api/assignments` | Listar asignaciones cuenta↔operador | superadmin | — | `{assignments}` | `app.py:384` |
| POST | `/api/assignments/assign` | Asignar cuenta a operador | superadmin | `{account_id, telegram_id}` | `{ok}` | `app.py:414` |
| POST | `/api/assignments/unassign` | Desasignar | superadmin | `{account_id, telegram_id}` | `{ok}` | `app.py:437` |

## Stats / KPIs

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/stats` | KPIs generales | require_session | query: `range` | `{kpis: {...}}` | `app.py:452` |
| GET | `/api/superadmin/kpis` | KPIs ampliados para SA | superadmin | — | `{...}` | `app.py:606` |

## Admin (controles sensibles)

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/admin/diag` | Diagnóstico completo de servicios | superadmin | — | `{checks: [...]}` | `app.py:963` |
| POST | `/api/admin/ping` | Ping a targets (betmexico.mx, capmonster, proxy) | superadmin | — | `{results}` | `app.py:998` |
| POST | `/api/admin/refresh-proxy` | Forzar rotación de proxy | superadmin | — | `{ok}` | `app.py:1023` |
| POST | `/api/admin/services/restart` | Restart de servicios (interno) | superadmin | `{service}` | `{ok}` | `app.py:1034` |
| GET | `/api/admin/export-logs` | Descargar logs | superadmin | query: `since` | file `text/plain` | `app.py:1052` |
| GET | `/api/admin/pause-state` | Estado de pausa global | superadmin | — | `{paused, since}` | `app.py:1072` |
| POST | `/api/admin/pause` | Pausar todo el sistema | superadmin | `{reason?}` | `{ok}` | `app.py:1078` |
| POST | `/api/admin/resume` | Reanudar | superadmin | — | `{ok}` | `app.py:1094` |
| POST | `/api/admin/emergency-stop` | Paro de emergencia (cancela prewarms y schedules) | superadmin | — | `{cancelled_prewarms, cancelled_schedules}` | `app.py:1104` |
| POST | `/api/admin/vps-reboot` | Reboot del VPS (1 min de delay) | superadmin | — | `{scheduled, in}` | `app.py:1143` |

## Logs

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/logs` | Tail de logs del servicio | superadmin | query: `lines` | `text/plain` | `app.py:884` |

## SSE (eventos en tiempo real)

| Método | Path | Función | Auth | Respuesta | File:line |
|---|---|---|---|---|---|
| GET | `/api/events` | Stream SSE de actividad/notificaciones | require_session | `text/event-stream` | `app.py:1504` |

## Actividad

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/activity` | Feed paginado de actividad | require_session | query: `limit, offset, kind, who, q` | `{rows, total}` | `app.py:1742` |

## Depósitos (router `/api/deposits/*`)

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| POST | `/api/deposits/execute` | Single deposit (1 cuenta, 1 tarjeta) | require_session | `{account_id, card_pipe, amount, force?}` | `{success, result_code, error, duration_ms, attempt_id}` | `deposits.py:531` |
| POST | `/api/deposits/execute-stream` | Single deposit SSE (live phases: login/begin/submit/check) | require_session | `{account_id, card_pipe, amount, force?}` | `text/event-stream` (`start`/`phase`/`done`/`fatal`) | `deposits.py:648` |
| GET | `/api/deposits/cap-status/{account_id}` | Cap status de una cuenta (window 24h, sesión 10min) | require_session | — | `{caps}` | `deposits.py:823` |
| POST | `/api/deposits/multi/stream` | Matchmaker N cuentas × M tarjetas (SSE) | require_session | `{account_ids, cards, amount}` | `text/event-stream` | `deposits.py:855` |
| POST | `/api/deposits/multi/{run_id}/cancel` | Cancelar matchmaker run | require_session | — | `{ok}` | `deposits.py:1118` |
| POST | `/api/deposits/scheduled/create` | Programar N reps a 1 min de intervalo (aborta al primer fail) | require_session | `{account_id, card_pipe, amount, repetitions}` | `{sched_id, email, repetitions}` | `deposits.py:1601` |
| GET | `/api/deposits/scheduled/list` | Listar schedules activos del user (SA ve todos). Devuelve `[{sched_id, email, amount, repetitions, started_at, card_pipe, current_iter, operator_id}]` — el frontend lo usa al cargar para rehidratar el drawer si recargaron en medio de una misión. | require_session | — | array | `deposits.py:1840` |
| POST | `/api/deposits/scheduled/{sched_id}/cancel` | Cancelar un schedule (task.cancel() → loop emite `scheduled_cancelled`). Solo dueño o SA. | require_session | — | `{cancelled: sched_id}` | `deposits.py:1860` |

## Tarjetas

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/cards/all` | Lista unificada de tarjetas (account_cards + account_notes con card, dedupe por (num, email)). Pipe completo sin enmascarar. | require_session | — | `{rows: [{source, card_pipe, card_number, card_expiry, card_cvv, account_email, account_password, registered_by, registered_at, last_used_at, total_deposits, total_approved, total_rejected, status}], total}` | `app.py` |

## Histórico de depósitos

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/deposits` | Listar `deposit_attempts` | require_session | query: filtros | `{rows, total}` | `app.py:1863` |
| GET | `/api/deposits/stats` | Stats agregados | require_session | query: `range` | `{stats}` | `app.py:1892` |

## Prewarm (router `/api/prewarm/*`)

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| POST | `/api/prewarm/select` | Encender prewarm para cuentas (con SSE) | require_session | `{account_ids, force?}` | `text/event-stream` | `prewarm.py:398` |
| POST | `/api/prewarm/cancel` | Cancelar prewarm | require_session | `{account_ids}` | `{ok}` | `prewarm.py:472` |
| GET | `/api/prewarm/status` | Estado actual | require_session | — | `{...}` | `prewarm.py:486` |
| POST | `/api/prewarm/refresh-stream` | Re-check visible accounts (SSE) | require_session | `{account_ids}` | `text/event-stream` | `prewarm.py:507` |

---

## Endpoints NO incluidos (routers legacy en `web_routes_*.py`)

Los siguientes routers están **definidos pero NO montados en `app.py`**. Sus endpoints existen en código pero el dashboard NO los expone hoy:

| Router | Endpoints en código | Acción recomendada |
|---|---|---|
| `web_routes_cards.py` (`/api/cards`) | POST `/`, GET `/`, GET `/{id}`, GET `/{id}/usage`, PATCH `/{id}/notes`, POST `/{id}/ban` | Decidir si activar (sería `app.include_router(...)`). Funcionalidad: CRUD de tarjetas + tracking de uso/ban. Útil para la bitácora — recomendado activar. |
| `web_routes_missions.py` (`/api/missions`) | POST `/batch`, POST `/scheduled`, GET `/`, GET `/{id}`, POST `/{id}/pause`, POST `/{id}/resume`, POST `/{id}/stop`, GET `/{id}/stream` | Sistema de misiones más completo que `/api/deposits/scheduled/*`. Decidir si reemplazar el actual o coexistir. |
| `web_routes_logs.py` (`/api/logs`) | GET `/` | Versión más completa de logs (filtros por nivel/módulo). El `/api/logs` actual de `app.py:884` es simple tail. |
| `web_routes_notifications.py` (`/api/notifications`) | GET `/`, GET `/count`, POST `/{id}/read`, POST `/mark-all-read`, GET `/stream` | Sistema de notificaciones persistente (con BD). Actual usa solo SSE in-memory. |
| `web_routes_prewarm.py` | POST `/select`, POST `/cancel`, GET `/status` | Duplicado del actual `prewarm.py`. Probablemente borrar uno. |
| `web_routes_watchdog.py` | (TBD — leer archivo) | Watchdog del sistema |
| `web_routes_deposits.py` | Sin endpoints `@router`; solo provee `_run_deposit(...)` | Función auxiliar, no router. ✅ Usado por `deposits.py` actual. |

Ver `AUDIT.md` para decisiones pendientes.
