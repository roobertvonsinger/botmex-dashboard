# SSE Events — bus `/api/events`

> Cada evento broadcast por el backend al frontend vía `text/event-stream`.
> Mantener vivo al agregar/quitar un broadcast kind.

> **Convención `who` / `who_color` / `who_id`** (desde 2026-05-26; `who_id` desde 2026-06-29): los broadcasts de
> tipo `activity` que llevan `who` lo envían **ya resuelto** al display name
> (`"RobertVS"`, `"Luisito"`, etc.) y acompañado de `who_color` (slug del color
> del operador) **y `who_id`** (telegram_id numérico del actor). Usar siempre `_resolve_who(operator_id)` en `deposits.py`
> en lugar de pasar el `telegram_id` crudo — si no, el feed muestra el chat_id
> numérico (ver `docs/ERRORS.md`). `who_id` es necesario para el filtrado
> server-side de SSE (`_event_visible_to`).

## Tabla de eventos

| `type` | `kind` | Disparado por | Payload | Handler frontend |
|---|---|---|---|---|
| `activity` | `deposit` | `_record_attempt()` en `deposits.py` | `{ts, who, target, amount, status, reason, duration_ms, card_pipe}` | `pushActivityEvent()` → `renderActivity()` |
| `activity` | `deposit_step` | `_wrap_deposit_step()` en `deposits.py` — envuelve el `phase_cb` de los 3 flujos (single/matchmaker/scheduled) en cada cierre de fase | `{ts, email, step, ok, code, duration_ms, who, who_color, who_id, attempt_id?/run_id?/sched_id?}`. `step` ∈ `{login, begin, submit, check}` (mapeado desde `login_done/gateway_begin_done/gateway_submit_done/gateway_check_done`). `ok` viene de login/begin (`None` en submit/check). `code` = `result_code` (submit) o `txn:{txn_status}` (check). | KPI Logs (pendiente UI) — filtrado server-side igual que cualquier `activity` vía `_event_visible_to` |
| `activity` | `scheduled_started` | `scheduled_create.loop()` ANTES de `pool.start_factory()` | `{sched_id, total, email, ts, who}` | log info — sirve como heartbeat para confirmar al frontend que la misión arrancó. Sin esto, los 5-15s del pool warm-up dejaban el modal en "Preparando…" estático sin señal de vida. |
| `activity` | `scheduled` | `scheduled_create.loop()` en `deposits.py` (summary por iter) | `{sched_id, iter, total, email, amount, success, code, ts, who}` | `pushActivityEvent()` |
| `activity` | `scheduled_phase` | `scheduled_create.loop()` via `phase_cb` → `_run_deposit_with_phases` (1 por sub-fase) | `{sched_id, iter, total, name, data, email, ts, who}`. `name` ∈ {login_start, login_done, **login_reused**, gateway_begin, gateway_begin_done, gateway_submit, gateway_submit_done, gateway_check, gateway_check_done, done}. `data` igual al de execute-stream. **iter 0** emite `login_start`/`login_done` (login real); **iter 1..N** emite `login_reused` (sesión reutilizada, sin captcha). | `pushActivityEvent()` (`_schedPhaseLabel()` formatea) |
| `activity` | `scheduled_aborted` | `scheduled_create.loop()` (al primer fail) | `{sched_id, email, code, iter, total, ts}` | `pushActivityEvent()` (chip "abortado") |
| `activity` | `scheduled_cancelled` | Cancel manual | `{sched_id, email, ts}` | `pushActivityEvent()` · modal v8 `_schedOnBus` |
| `activity` | `scheduled_retry` | `scheduled_create.loop()` ante fallo TRANSITORIO (406/captcha/proxy/504) — reintenta la misma rep, NO aborta | `{sched_id, email, iter, total, attempt, max, code, reason, ts, who}` | `pushActivityEvent()` · modal v8 `_schedOnBus` (escena retry) |
| `activity` | `account_refreshed` | `_refresh_account_after_deposit()` en `deposits.py` (single/multi, tras el intento) | `{ts, email, target, balance_real, balance_total, who}` | repinta fila/detalle · modal v8 `onBusEvent` (balance fresco before→after, L2) |
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
| `activity` | `account_touch` | `account_details()` en `app.py` (GET detalle de cuenta — `INSERT OR IGNORE` en `account_touches`, solo si fue toque NUEVO por rowcount) | `{ts, target:email, id:account_id, who, who_color, who_id}` | KPI Logs — `👁 {who} abrió {target}` |

### Visibilidad especial de `account_touch`

`_event_visible_to` trata este `kind` distinto al resto (chequeo ANTES del early-return de superadmin):

| Viewer | ¿Ve el toque? |
|---|---|
| El propio actor (quien tocó la cuenta) | **NUNCA**, ni siendo superadmin — `who_id == ctx.telegram_id` corta en `False` de entrada |
| SA (viendo el toque de OTRO actor) | Sí — único que ve toques ajenos |
| Operador (viendo el toque de OTRO actor, incluido el del SA) | No — cae al filtro estándar `who_id == su telegram_id`, que es `False` |

Motivo: es un evento de vigilancia ("quién metió mano"), no de actividad propia — a nadie le sirve verse a sí mismo tocando una cuenta, y un operador no debe ver qué cuentas toca otro operador (mismo principio de separación por rol que el resto del bus).

## Tipos de eventos del matchmaker (multi/stream)

Endpoint `/api/deposits/multi/stream` devuelve eventos SSE específicos del run (NO van por `/api/events` bus):

| `type` | Payload | Significado |
|---|---|---|
| `start` | `{run_id, accounts, cards, amount}` | Match iniciado |
| `trying` | `{email, tail, attempt}` | Lanzando intento (par activo) |
| `phase` | `{email, tail, name, data}` | Sub-fase del intento activo. `name`/`data` idénticos a execute-stream (login_start, login_done, gateway_begin, etc.). Permite mostrar progreso vivo por par. |
| `match` | `{email, tail, pipe, amount, duration_ms, attempt}` | **APROBADO** — par casado (vincula tarjeta↔cuenta). La cuenta sale; la tarjeta NO se retira (sigue con otras cuentas hasta su tope de 3). |
| `account_aplus` | `{email, tail, attempt, persisted}` | **3DS** → la cuenta es premium: `grade='A+'` (pasarela robusta) y sale del run. NO penaliza tarjeta ni cuenta. `persisted:true` = escrito en BD. (Robert 2026-06-28) |
| `rejected` | `{email, tail, code, card_fails, acct_fails, attempt, card_out, acct_out}` | **DECLINE REAL** (banco/tarjeta). Strike a tarjeta Y cuenta. `card_out:true` = tarjeta retirada (3 declines reales de 3 cuentas distintas); `acct_out:true` = cuenta fuera (2 declines reales de 2 tarjetas distintas). |
| `retry` | `{email, tail, code, attempt, retrying?, exhausted?, tries, max?, ambiguous?, reason?}` | **TRANSITORIO** (gateway 50x/timeout/ERROR = nuestro lado). El par se reintenta tras cumplir su cooldown (60s, "al final de la cola"). `exhausted:true` tras `MM_MAX_PAIR_TRANSIENT` reintentos → abandona el par SIN penalizar tarjeta ni cuenta. **`ambiguous:true`** (2026-07-02): cargo AMBIGUO (`SUBMIT_ERROR`/`UNKNOWN_TXN_STATUS_n`, el cargo pudo aplicarse) → se abandona el par de inmediato SIN reintentar (evita doble cargo) ni strike; `reason` explica "revisar manual". (Robert 2026-06-28) |
| `account_dead` | `{email, code, tail, attempt, persisted}` | Cuenta DEAD persistente. `code` ∈ `{AUTOEXCLUSION, KYC_PENDING, LOGIN_DENIED}` — SOLO estos tres matan la cuenta. `persisted:true` indica que se escribió en BD. |
| `login_retry` | `{email, code, tail, attempt, retrying?, exhausted?, tries, max?}` | Login falló por NUESTRA infraestructura (406/captcha/proxy). La cuenta **NO muere** ni se penaliza en BD. Reintenta el par hasta `MM_MAX_LOGIN_RETRIES`; al agotar sale del run en memoria. `code` siempre `LOGIN_FAILED`. |
| `velocity_skip` | `{email, tail, wait_sec, distinct_count, message}` | Tarjeta ya usada en N cuentas recientes — skip sin penalizar. (Red redundante: `MM_COOLDOWN=60s` ya domina.) |
| `account_cooling` | `{email, tail?, attempt?, cooldown_min, preexisting?}` | **Anti-rate-limit Capa 3** (spec 2026-06-28): la cuenta recibió `RATE_LIMITED` (429/BAN) y entró en enfriamiento persistente (`accounts.cooldown_until`). Sale del run — NO se reintenta la cuenta caliente. `preexisting:true` = la cuenta ya estaba enfriando al iniciar el run (saltada antes de intentar). La tarjeta NO se penaliza (login falló antes del gateway). Handler frontend resetea ambos rows a idle (evita spinner pegado, como `velocity_skip`). |
| `card_retired` | `{tail, fails?, assigned?, reason}` | Tarjeta retirada. `reason`: "3 rechazos reales" (`fails`) o "tope 3 cuentas" (`assigned`). |
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
| `login_reused` | `{ok: true, duration_ms: 0, reused: true}` — **scheduled iter>0**: la sesión (JWT+proxy) de la iter 0 se reusa, NO hay login. Reemplaza al par `login_start`/`login_done` en esas iters. UI: `♻️ Sesión reutilizada`. |
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

Endpoint `/api/prewarm/refresh-stream` (SSE, "Actualizar visibles"):

| `type` | Payload | Significado |
|---|---|---|
| `start` | `{total, cap_remaining, cap_used, capmonster_balance, capmonster_warning}` | Refresh iniciado |
| `account` | `{data: {fila completa}}` | Cuenta re-logueada OK, fila repintada |
| `fail` | `{id, email, error}` | Login falló |
| `skip` | `{id, email, reason, cooldown_min?}` | Cuenta saltada. `reason`: `cap` (tope del operador), `no_password`, **`dead`** (cuarentena: DEAD, no se re-loguea), **`cooldown`** (enfriando tras rate-limit, `cooldown_min` = minutos restantes). `dead`/`cooldown` añadidos 2026-07-11 (cuarentena anti-rate-limit). |
| `done` | — | Terminado |

## `deposit_step` — logging paso a paso (Fase 2 KPI Logs, 2026-07-05)

`_wrap_deposit_step(inner_cb, *, email, actor, **ids)` (deposits.py, cerca de `_safe_phase`) envuelve el `phase_cb` de CADA uno de los 3 flujos de depósito. Reglas de diseño:
- **Nunca reemplaza el streaming local**: `inner_cb` (el callback original — encola a la queue del stream single/matchmaker, o hace el broadcast `scheduled_phase` en scheduled) se llama SIEMPRE primero e intacto.
- Broadcastea `deposit_step` SOLO en los 4 cierres de fase (`login_done`, `gateway_begin_done`, `gateway_submit_done`, `gateway_check_done`) — nunca en `*_start`/`done`. Esto evita duplicar el evento `deposit` de cierre, que sigue siendo emitido únicamente por `_record_attempt`.
- Best-effort: si `_broadcast` falla, se loguea warning y el depósito sigue sin verse afectado (try/except interno).
- Filtro de rol server-side reutiliza `_event_visible_to` sin cambios — el evento lleva `who_id` vía `_resolve_who(actor)`.
- Aplicado en los 3 call sites: `execute-stream` (single, `attempt_id`), `/multi/stream` (matchmaker, `run_id`), `scheduled_create.loop()` (scheduled, `sched_id`).

## Patrón de duplicado conocido

Cuando un scheduled falla (`success=False`), se hacen **2 broadcasts**:
1. `kind: scheduled` con `success:false` (resultado del intento)
2. `kind: scheduled_aborted` (notificación de aborto del loop)

Esto puede verse como "2 intentos" en el feed. Es UX confuso pero es 1 solo intento real.
Pendiente: consolidar en 1 evento o agrupar visualmente.

## Bus de subscripción (`/api/events`)

- Auth: `require_session` (cookie `bmx_auth`)
- Cada cliente subscribe vía `EventSource('/api/events')`
- Backend mantiene un set de clients en `app.py` (variable `_sse_queues`: lista de `(queue, ctx)`)
- `_broadcast(event)` evalúa visibilidad por cola antes de encolar: **solo entrega si `_event_visible_to(event, ctx)` es `True`**
- Reconnect automático del navegador (~3-5s)

### Filtrado server-side por rol (reorg UI 2026-06-29)

**Antes:** `_broadcast` enviaba a TODOS los clientes sin discriminar. Un admin podía recibir actividad del SA.

**Ahora:** whitelisting estricto. Reglas:
- SA (`role == "superadmin"`) siempre recibe todos los eventos.
- admin/user recibe solo eventos donde `event.who_id == su telegram_id` (o `event.who == su display` como fallback).
- Eventos de servicio dirigidos (`operator_id` / `target_user` en el payload) llegan SOLO al destinatario.
- Eventos de servicio sin actor ni destinatario (`capmonster_low`, `proxy_down`, etc.) solo al SA.
- Las acciones del SA **no aparecen** en el feed de ningún admin/operador (fix del bug "admin ve actividad de Robert").

`_sse_queues` guarda `(queue, ctx)` donde `ctx = {role, telegram_id, display}` capturado al conectar `/api/events`. `_resolve_who(val)` ahora retorna `{who, who_color, who_id}` — `who_id` es el telegram_id del actor para que `_event_visible_to` pueda filtrar por ID numérico.

### Nuevo kind: `pool_move`

| `type` | `kind` | Disparado por | Payload | Handler frontend |
|---|---|---|---|---|
| `activity` | `pool_move` | `POST /api/pool/publish` en `app.py` | `{publish: bool, count: int, who, who_id, who_color, ts}` | marquesina Actividad Live (solo SA recibe, por filtro server-side) |

`publish: true` = cuentas expuestas al pool; `false` = retiradas. Copy humano: `↘ {who} expuso N cuenta(s) al pool` / `↗ retiró N del pool`.
