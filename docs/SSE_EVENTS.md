# SSE Events — bus `/api/events`

> Cada evento broadcast por el backend al frontend vía `text/event-stream`.
> Mantener vivo al agregar/quitar un broadcast kind.

## Tabla de eventos

| `type` | `kind` | Disparado por | Payload | Handler frontend |
|---|---|---|---|---|
| `activity` | `deposit` | `_record_attempt()` en `deposits.py` | `{ts, who, target, amount, status, reason, duration_ms, card_pipe}` | `pushActivityEvent()` → `renderActivity()` |
| `activity` | `scheduled` | `scheduled_create.loop()` en `deposits.py:626` | `{sched_id, iter, total, email, amount, success, code, ts, who}` | `pushActivityEvent()` |
| `activity` | `scheduled_aborted` | `scheduled_create.loop()` (al primer fail) | `{sched_id, email, code, iter, total, ts}` | `pushActivityEvent()` (chip "abortado") |
| `activity` | `scheduled_cancelled` | Cancel manual | `{sched_id, email, ts}` | `pushActivityEvent()` |
| `activity` | `lock` | `lock_account()` en `app.py` | `{ts, who, target, until}` | `pushActivityEvent()` |
| `activity` | `unlock` | `unlock_account()` | `{ts, who, target}` | `pushActivityEvent()` |
| `activity` | `unlock_auto` | Window watcher (24h auto-release) | `{ts, target}` | `pushActivityEvent()` |
| `activity` | `note` | `create_note()` en `app.py` | `{ts, who, target, text_snippet}` | `pushActivityEvent()` |
| `activity` | `bulk` | Operaciones masivas (publish, hide-all) | `{ts, who, action, count}` | `pushActivityEvent()` |
| `notification` | `capmonster_low` | Health monitor (CapMonster < $5) | `{severity:'danger', msg, balance}` | `pushNotif({icon:'💸', ...})` |
| `notification` | `proxy_down` | Health monitor (proxy MX fail) | `{severity:'danger', msg}` | `pushNotif({icon:'🔌', ...})` |
| `notification` | `prewarm_errors` | Prewarm bulk fail rate alto | `{severity:'warn', msg, count}` | `pushNotif({icon:'🔥', ...})` |
| `notification` | `global_pause` | `pause` endpoint | `{ts, who, reason}` | `pushNotif()` |
| `notification` | `global_resume` | `resume` endpoint | `{ts, who}` | `pushNotif()` |
| `notification` | `emergency_stop` | `emergency-stop` endpoint | `{ts, who, cancelled_prewarms, cancelled_schedules}` | `pushNotif()` |
| `notification` | `vps_reboot` | `vps-reboot` endpoint | `{ts, who, in}` | `pushNotif()` |

## Tipos de eventos del matchmaker (multi/stream)

Endpoint `/api/deposits/multi/stream` devuelve eventos SSE específicos del run (NO van por `/api/events` bus):

| `type` | Payload | Significado |
|---|---|---|
| `start` | `{run_id, accounts, cards, amount}` | Match iniciado |
| `attempt_start` | `{email, tail, n}` | Iniciando intento |
| `attempt_result` | `{email, tail, success, code, duration_ms}` | Resultado del intento |
| `card_retired` | `{tail, fails}` | Tarjeta retirada por max fails |
| `cancelled` | `{run_id}` | Cancelado por usuario |
| `done` | `{matches, attempts, summary}` | Run terminado |

## Tipos de eventos del prewarm

Endpoint `/api/prewarm/select` (SSE):

| `type` | Payload | Significado |
|---|---|---|
| `start` | `{accounts, cap_remaining}` | Prewarm iniciado |
| `result` | `{email, ok, code, duration_ms, balance, jwt_cached, fail_reason}` | Resultado por cuenta |
| `done` | `{cap_remaining, cap_used}` | Terminado |

## Patrón de duplicado conocido

Cuando un scheduled falla (`success=False`), se hacen **2 broadcasts**:
1. `kind: scheduled` con `success:false` (resultado del intento)
2. `kind: scheduled_aborted` (notificación de aborto del loop)

Esto puede verse como "2 intentos" en el feed. Es UX confuso pero es 1 solo intento real.
Pendiente: consolidar en 1 evento o agrupar visualmente.

## Bus de subscripción (`/api/events`)

- Auth: `require_session` (cookie `bmx_auth`)
- Cada cliente subscribe vía `EventSource('/api/events')`
- Backend mantiene un set de clients en `app.py` (variable `_event_subscribers`)
- `_broadcast(payload)` itera y hace `yield` a cada cliente conectado
- Reconnect automático del navegador (~3-5s)
