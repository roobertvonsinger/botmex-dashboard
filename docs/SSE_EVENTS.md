# SSE Events — bus `/api/events`

> Cada evento broadcast por el backend al frontend vía `text/event-stream`.
> Mantener vivo al agregar/quitar un broadcast kind.

> **Convención `who` / `who_color`** (desde 2026-05-26): los broadcasts de
> tipo `activity` que llevan `who` lo envían **ya resuelto** al display name
> (`"RobertVS"`, `"Luisito"`, etc.) y acompañado de `who_color` (slug del color
> del operador). Usar siempre `**_resolve_who(operator_id)` en `deposits.py`
> en lugar de pasar el `telegram_id` crudo — si no, el feed muestra el chat_id
> numérico (ver `docs/ERRORS.md`).

## Tabla de eventos

| `type` | `kind` | Disparado por | Payload | Handler frontend |
|---|---|---|---|---|
| `activity` | `deposit` | `_record_attempt()` en `deposits.py` | `{ts, who, target, amount, status, reason, duration_ms, card_pipe}` | `pushActivityEvent()` → `renderActivity()` |
| `activity` | `scheduled_started` | `scheduled_create.loop()` ANTES de `pool.start_factory()` | `{sched_id, total, email, ts, who}` | log info — sirve como heartbeat para confirmar al frontend que la misión arrancó. Sin esto, los 5-15s del pool warm-up dejaban el modal en "Preparando…" estático sin señal de vida. |
| `activity` | `scheduled` | `scheduled_create.loop()` en `deposits.py` (summary por iter) | `{sched_id, iter, total, email, amount, success, code, ts, who}` | `pushActivityEvent()` |
| `activity` | `scheduled_phase` | `scheduled_create.loop()` via `phase_cb` → `_run_deposit_with_phases` (1 por sub-fase) | `{sched_id, iter, total, name, data, email, ts, who}`. `name` ∈ {login_start, login_done, gateway_begin, gateway_begin_done, gateway_submit, gateway_submit_done, gateway_check, gateway_check_done, done}. `data` igual al de execute-stream. | `pushActivityEvent()` (`_schedPhaseLabel()` formatea) |
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
| `notification` | `release_warning_5min` | `_release_watchdog_tick` (5 min antes de 24h post-deposit) | `{msg, target_user, account_id, icon:⏳, severity:info}` | `pushNotif()` filtra por `target_user` |
| `notification` | `release_available` | `_release_watchdog_tick` (24h cumplidas) | `{msg, target_user, account_id, icon:🟢, severity:warn, actions:[deposit,release]}` | `pushNotif()` con botones |
| `notification` | `release_available_again` | `_release_watchdog_tick` (24h+10min, 2do aviso) | `{msg, target_user, account_id, icon:⏰, severity:warn, actions:[deposit,release]}` | `pushNotif()` con botones |
| `notification` | `release_auto` | `_release_watchdog_tick` (27h auto-release) | `{msg, target_user, account_id, icon:🕒, severity:info}` | `pushNotif()` |
| `activity` | `unlock_auto` | `_release_watchdog_tick` (al auto-release a las 27h) | `{ts, target, id, reason}` | `pushActivityEvent()` |

## Tipos de eventos del matchmaker (multi/stream)

Endpoint `/api/deposits/multi/stream` devuelve eventos SSE específicos del run (NO van por `/api/events` bus):

| `type` | Payload | Significado |
|---|---|---|
| `start` | `{run_id, accounts, cards, amount}` | Match iniciado |
| `trying` | `{email, tail, attempt}` | Lanzando intento (par activo) |
| `phase` | `{email, tail, name, data}` | Sub-fase del intento activo. `name`/`data` idénticos a execute-stream (login_start, login_done, gateway_begin, etc.). Permite mostrar progreso vivo por par. |
| `match` | `{email, tail, pipe, amount, duration_ms, attempt}` | Aprobado — par casado |
| `rejected` | `{email, tail, code, card_fails, acct_fails?, attempt, card_only?}` | Rechazado por gateway. `card_only:true` cuando el strike es solo a la tarjeta (3DS/BANK_REJECTED). |
| `account_dead` | `{email, code, tail, attempt, persisted}` | Cuenta DEAD por LOGIN_FAILED/AUTOEXCLUSION/KYC_PENDING/3DS_UNDETECTED/SHADOW_BAN? |
| `velocity_skip` | `{email, tail, wait_sec, distinct_count, message}` | Tarjeta ya usada en N cuentas recientes — skip sin penalizar |
| `card_retired` | `{tail, fails}` | Tarjeta retirada por max fails |
| `cooldown` | `{wait}` | Esperando cooldown mínimo entre intentos |
| `error` | `{email, tail, message}` | Excepción en `attempt()` |
| `cancelled` | `{run_id}` | Cancelado por usuario |
| `done` | `{matches, attempts, pending}` | Run terminado (emitido DENTRO del try; si el generator lanza excepción, se emite `fatal` en su lugar) |
| `fatal` | `{run_id, error}` | Excepción en el generator del matchmaker. Frontend debe limpiar busy state (mismo fallback que stream-close-sin-done). Agregado 2026-05-15 (v20260515f). |

## Tipos de eventos de execute-stream (single deposit live)

Endpoint `/api/deposits/execute-stream` devuelve eventos SSE específicos del intento. NO van por `/api/events` bus (la persistencia final sí se broadcast por ese bus vía `_record_attempt` al cierre).

| `type` | Payload | Significado |
|---|---|---|
| `start` | `{attempt_id, email, amount}` | Stream iniciado. `attempt_id` para correlación. |
| `phase` | `{name, data}` | Fase del depósito. `name` ∈ `login_start, login_done, gateway_begin, gateway_begin_done, gateway_submit, gateway_submit_done, gateway_check, gateway_check_done, done`. |
| `done` | `{attempt_id, success, result_code, error, duration_ms}` | Cierre lógico — la conexión termina justo después. |
| `fatal` | `{error}` | Error fatal en el generator (no debería ocurrir; los errores de fases vienen como `phase`/`done`). |
| `:ping` | (comentario SSE, sin payload) | Heartbeat cada 2s si no hay eventos — mantiene la conexión viva pasando proxies/buffers. |

### Payloads de `phase` (data por fase)

Coinciden 1:1 con lo que emite `_run_deposit_with_phases`:

| `name` | `data` |
|---|---|
| `login_start` | `{}` |
| `login_done` | `{ok: bool, duration_ms: int, from_cache: bool}` |
| `gateway_begin` | `{}` |
| `gateway_begin_done` | `{order_id: str|None, ok: bool, duration_ms: int}` |
| `gateway_submit` | `{order_id: str}` |
| `gateway_submit_done` | `{result_code: str, is_3ds: bool, duration_ms: int}` |
| `gateway_check` | `{}` (solo si NO es 3DS) |
| `gateway_check_done` | `{txn_status: int, duration_ms: int, check_error?: str}` |
| `done` | `{success: bool, result_code: str, error: str|None}` (también emitido por el wrapper antes del `type:done` del generator) |

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
