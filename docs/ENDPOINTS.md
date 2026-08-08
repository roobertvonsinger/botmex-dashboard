# ENDPOINTS — tabla maestra del backend

> Generado por inventario el 2026-05-11. Actualizar SIEMPRE al agregar/modificar/borrar un endpoint (la skill `botmex-bitacora` lo recuerda).

## Routers activos

| Router | Prefix | Source | Incluido en app |
|---|---|---|---|
| `_prewarm_router` | `/api/prewarm` | `prewarm.py` | ✅ `app.py:165` |
| `_deposits_router` | `/api/deposits` | `deposits.py` | ✅ `app.py:166` |
| `_support_router` | `/api/support` | `support_routes.py` | ✅ `app.py` (en `try/except`: si falla el import, el dashboard arranca igual) |

> Routers legacy (`web_routes_cards/missions/logs/notifications`) archivados en `_legacy/` (SP-1). Ver sección "Módulos archivados" abajo.

---

## Auth

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/login` | Página de login (preserva `?match=`/query en el redirect post-login) | público | — | HTML `login.html` | `app.py:688` |
| GET | `/` | Root — puro gate de auth. Sin sesión → `/login`; SA → `/dashboard`; resto → `/{username}` (query preservada, p.ej. `?match={mission_id}` del handoff `/bet`) | require_session (vía redirect) | — | 302 redirect | `app.py:796` |
| GET | `/dashboard` | Dashboard SA (renombrado desde `/`, 2026-08-04) | superadmin (no-SA rebota a su propio `/{username}`) | — | HTML `index.html` | `app.py:762` |
| GET | `/{username}` | Portal `/bet` (`portal.html`), scoped por username/apodo (reemplaza `/user/{telegram_id}` desde 2026-08-06 — Robert: la URL debe traer el apodo, no un ID; DEBE ser la última ruta GET de 1 segmento en `app.py`, cualquier ruta literal nueva de 1 segmento tiene que registrarse antes). No-SA con `{username}` ajeno se canoniza al propio; SA puede navegar cualquier `{username}` (supervisión / `?view_as=` en las APIs, ahora el username directo — antes telegram_id — para ver exactamente como ese usuario). 404 si el username no existe. | require_session | — | HTML `portal.html` | `app.py:867` |
| GET | `/user/{user_id}` | Alias de compatibilidad (links viejos por telegram_id) — 302 a `/{username}` resuelto por telegram_id, o 404 si no existe | público (solo redirige) | — | 302 redirect / 404 | `app.py:803` |
| GET | `/portal` | Alias de compatibilidad — redirige a `/dashboard` (SA) o `/{username}` (resto), preserva query | require_session | — | 302 redirect | `app.py:751` |
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
| GET | `/api/version` | Versión = mtime MÁS RECIENTE entre TODOS los `FRONTEND_ASSETS` (`app.py`, lista completa de .css/.js propios servidos por index.html — 2026-07-06: antes solo trackeaba app.js+style.css, un deploy de cualquier otro asset no disparaba el auto-reload). Frontend la compara vs `window.BMX_VERSION` cada 5min/al volver a la pestaña → auto-reload sin Ctrl+Shift+R | público | — | `{v: "<mtime>"}` | `app.py:395` |

## Soporte — agente b.soporte (`support_routes.py`)

> Todos **superadmin-only** (`require_session` + guard `role == "superadmin"`).
> El cerebro es el 9router de KVM4 (OpenAI-compatible), no una API de Anthropic.
> Instrucciones del agente: `docs/AGENTE_SOPORTE.md`. Herramientas: `support_tools.py`.

| Método | Path | Función | Auth | Body / Query | Respuesta |
|---|---|---|---|---|---|
| POST | `/api/support/chat` | Turno de conversación. Corre el loop modelo↔tools. | superadmin | `{mensaje, imagen?}` (`imagen` = data URI) | **SSE** por-request (no el bus global). Ver eventos abajo. |
| POST | `/api/support/confirm` | **Único** punto donde se ejecuta una acción de escritura. Redime un token pendiente. | superadmin | `{token}` | `{ok, detalle}` · 400 si el token es desconocido, ya se usó o expiró (TTL 10 min) |
| GET | `/api/support/history` | Historial de la conversación (últimos 60). | superadmin | — | `{mensajes: [{role, content, created_at}]}` |
| DELETE | `/api/support/history` | Borra la conversación. | superadmin | — | `{borrados: N}` |
| GET | `/api/support/config` | Diagnóstico: qué router y cadena de modelos está usando. | superadmin | — | `{router, cadena, docker_proxy}` |

**Eventos del SSE de `/chat`** (una línea `data: {...}` por evento):

| `kind` | Payload | Para qué |
|---|---|---|
| `text` | `{delta}` | Texto incremental de la respuesta |
| `tool` | `{name, status: start\|done, label?, summary?}` | Chip de actividad ("consultando la BD…") |
| `table` | `{columns, rows}` | Resultado **crudo** de `consultar_bd` — Robert lo ve completo, sin máscara |
| `confirm` | `{token, label, tool}` | Pinta el botón de confirmación de una acción de escritura |
| `brief` | `{markdown}` | Informe copiable para pegar en Claude Code |
| `done` | `{model, tokens_in, tokens_out}` | Qué modelo respondió y cuánto costó (medido, no estimado) |
| `error` | `{message}` | Fallo del router o del loop |

**Gate de confirmación** — las tools de escritura (`reiniciar_servicio`, `pausar_sistema`,
`reanudar_sistema`, `desbloquear_cuenta`) **no se ejecutan** cuando el modelo las llama: dejan una
fila en `support_pending` y devuelven un token. Solo `POST /confirm` (sesión SA) las dispara, y el
token es de un solo uso. El modelo nunca sostiene el permiso — si alucina "ya lo reinicié", no pasó
nada.

**Privacidad hacia el proveedor LLM** — el resultado de `consultar_bd` se emite **crudo** a la UI
pero **redactado** al modelo (`support_tools.redact_for_model`): passwords, JWT, tokens, proxies,
`card_number` y `card_cvv` viajan como `‹oculto›`. No es enmascarar a Robert (él ve todo, y puede
copiar en 1 tap): es que la conversación pasa por un LLM de terceros.

---

## Cuentas

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/operator/my-accounts` | Cuentas con depósitos aprobados del operador actual (SA ve todas, salvo `?view_as=`). Incluye `is_locked`, `status`, `clabe_stp`, `withdrawal_ready`, `withdrawal_institution`, `curp`. **`withdrawal_institution` (2026-08-08 fix)**: si la cuenta ya tiene retiros disparados, se sobreescribe con `account_withdrawals.institution_name` del más reciente (registro inmutable por transacción) — gana sobre el cache `accounts.withdrawal_institution` (mutable, lo reescribe `account_refresh.py` en cada ciclo con su propia llamada a `get_bank_accounts`, desacoplada de cualquier retiro ya disparado; ver `docs/ERRORS.md`). Sin retiros aún, cae al cache. | require_operator_view | `?view_as={telegram_id}` (solo SA; narrowea su propia sesión a ese id, rol degradado a operator) | `{ok, accounts: [{id, email, balance_real, balance_bonos, last_deposit_amount, last_deposit_date, grade, is_locked, status, clabe_stp, withdrawal_ready, withdrawal_institution, curp}]}` | `app.py:4273` |
| POST | `/api/operator/accounts/{account_id}/release` | Libera el lock de una cuenta propia (operador) o cualquiera (SA, salvo `?view_as=`). Sin password. | require_operator_view | `?view_as=` (idem) | `{ok, account_id, released}` | `app.py` |
| POST | `/api/operator/accounts/{account_id}/withdraw` | Retiro sin password — valida ownership vía `_visible_emails`, usa JWT en BD. | require_operator_view | `{amount}`, `?view_as=` (idem) | `{transactionId, reference, accountId, accountDigits, institutionName, amount, account_email, warnings, persisted}` / 409 | `app.py` |
| GET | `/api/operator/missions` | Misiones del operador (o todas si SA, últimas 50/20; o solo las de `view_as` si se manda). | require_operator_view | `?view_as=` (idem) | `{ok, missions: [{mission_id, status, phase_detail, total_deposited, total_approved, total_failed, created_at, completed_at, operator_id}]}` | `app.py` |
| GET | `/api/accounts` | Listar cuentas con filtros | require_session | query: `status, search, limit, offset` | `{rows, total}` — fila incluye `last_updated_at` (Últ. update real, 2026-08-05) y, **solo para superadmin**, `rl_streak` (racha de rate-limit, pop SIEMPRE para non-SA — ley de capas) | `app.py:291` |
| POST | `/api/accounts/refresh` | Forzar re-check de cuentas seleccionadas | require_session | `{account_ids}` | `{queued}` | `app.py:859` |
| POST | `/api/accounts/{account_id}/lock` | Lock manual (con duración) | require_session | `{minutes}` | `{ok, locked_until}` | `app.py:1365` |
| POST | `/api/accounts/{account_id}/unlock` | Liberar lock | require_session | — | `{ok}` | `app.py:1458` |
| POST | `/api/accounts/publish` | Publicar cuenta(s) al pool | require_session | `{account_ids}` | `{ok, count}` | `app.py:1402` |
| POST | `/api/accounts/hide-all` | Despublicar todas | require_session | — | `{ok, count}` | `app.py:1421` |
| GET | `/api/accounts/{account_id}/cards-pipe` | Pipe puro de tarjetas (copy-paste) | require_session | — | `{pipes: ["num\|exp\|cvv"]}` | `app.py:1513` |
| GET | `/api/accounts/{account_id}/notes-summary` | Resumen para iconito de fila | require_session | — | `{count, mine}` | `app.py:1542` |
| GET | `/api/accounts/{account_id}/details` | Detalle completo (panel inline acordeón v14 + La Pantalla) — incluye `cards`, `transactions`, `deposit_attempts`, `notes`, `clabes`, **`movimientos`** (lista unificada dashboard+betmex: `{when, source, kind, method, amount, state, who, card_pipe, reason}`, orden DESC) y **`last_withdrawal`** (última fila de `account_withdrawals`: `{transaction_id, reference, amount, account_digits, institution_name, status_api, gateway, last_modified_utc, created_at}` o `null`) — permite pintar/retomar el estado del botón de retiro al reabrir La Pantalla | require_session | — | `{...}` | `app.py:1838` |
| POST | `/api/accounts/{account_id}/notes` | Crear nota | require_session | `{text}` | `{ok, id}` | `app.py:1657` |
| DELETE | `/api/accounts/{account_id}/notes/{note_id}` | Borrar nota (superadmin) | superadmin | — | `{ok}` | `app.py:1709` |
| POST | `/api/accounts/{account_id}/curp` | Guardar CURP validado | require_session | `{curp}` | `{ok}` | `app.py:1694` |
| POST | `/api/accounts/combos` | Devolver `email:password` de IDs (para copy masivo) | require_session | `{ids}` | `{combos: [{id, email, password}]}` | `app.py:1729` |

## Retiros (botón de retiro automático)

> `withdrawals.py` módulo aislado (5 pasos API BetMexico), tabla `account_withdrawals` (bitácora idempotente). Ver `docs/RECON_BETMEX_API.md` §"FLUJO DE RETIRO EXACTO" y guardarrails bug#1 (cuenta de retiro puede cambiar por depósito SPEI — nunca cachear), bug#2 (status:6 ≠ aterrizó en banco, reportar 2 fases), bug#3 (puede aterrizar en tarjeta en vez de SPEI). UI: botón SA-only en La Pantalla (`.pat-wd`, `pantalla.js`), polling fijo 60s + SSE (`kind:"withdrawal"`, ver `docs/SSE_EVENTS.md`).

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| POST | `/api/accounts/{account_id}/withdraw` | Dispara retiro real (PASO0-3 vía `withdrawals.execute_withdrawal`, single-shot) | superadmin | `{amount}` | `{transactionId, reference, accountId, accountDigits, institutionName, amount, account_email, warnings}` / 409 con detail específico (JWT expirado, sin cuenta aprobada, múltiples cuentas aprobadas, saldo insuficiente, retiro concurrente pendiente) | `app.py:3058` |
| GET | `/api/accounts/{account_id}/withdraw/status/{tx_id}` | Estado del retiro (PASO4 + PASO5 si status==6, guardarrails bug#1/#2/#3) | SA o operador dueño de la cuenta (ownership vía `_visible_emails`, 403 si la cuenta no está en su universo) | — | `{status: idle\|pending\|successful\|completed\|failed, phase, transactionStatus, description?, lastModifiedUtc?, gateway?, accountDigits, alerts:{gatewayMismatch, digitsMismatch}}` | `app.py:3661` |

**✅ Deployado y verificado en KVM4 (2026-07-24).** `test_withdrawals.py` (28) + `test_withdrawals_endpoints.py` (20) verdes, 0 regresión (16 fallos pre-existentes sin cambio, ver `reference_pre_existing_test_failures`). Smoke post-deploy: `POST /withdraw {amount:99999}` en cuenta real → 409 `InsufficientBalance` (llega a PASO1+PASO2 reales contra BetMexico, se detiene ANTES de PASO3 — cero dinero movido, 0 filas nuevas en `account_withdrawals`); `GET /withdraw/status/{tx_inexistente}` → 404. **Pendiente:** verificación visual del bloque `.pat-wd` en navegador (getBoundingClientRect, no se pudo hacer esta sesión — extensión Chrome no conectada) + Task I (retiro real $100, dispara Robert con click).

## Pool

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/pool/accounts` | Cuentas publicadas en pool (no-SA) | require_session | — | `{rows}` | `app.py:1436` |
| GET | `/api/pool/split` | Vista partida del pool: dentro y fuera (SA-only, 403 para otros) | superadmin | — | `{"inside":[{email,combo}], "outside":[{email,combo}]}` | `app.py` |
| POST | `/api/pool/publish` | Bulk publish/unpublish (SA-only). Hace SET `published_to_pool`. Emite SSE `pool_move`. | superadmin | `{emails:[...], publish:bool}` | `{"moved": int}` | `app.py` |

## Usuarios / Asignaciones

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/users` | Listar usuarios (operadores) | superadmin | — | `{users}` | `app.py:372` |
| GET | `/api/assignments` | Listar asignaciones cuenta↔operador | superadmin | — | `{assignments}` | `app.py:384` |
| POST | `/api/assignments/assign` | Asignar cuenta a operador | superadmin | `{account_id, telegram_id}` | `{ok}` | `app.py:414` |
| POST | `/api/assignments/unassign` | Desasignar | superadmin | `{account_id, telegram_id}` | `{ok}` | `app.py:437` |

## Marcador (privado por usuario)

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/marks` | Lista de emails marcados por el usuario logueado (privado — nadie más los ve) | require_session | — | `{"marks":[email,...]}` | `app.py` |
| POST | `/api/marks/toggle` | Marcar/desmarcar una cuenta (idempotente: inserta si no existe, borra si existe). NO toca `locked_by`, `published_to_pool` ni visibilidad. | require_session | `{email: str}` | `{"marked": bool}` | `app.py` |

> `user_key = str(telegram_id)`. Las marcas son exclusivamente un recordatorio personal del operador. No bloquean ni exponen la cuenta a nadie.

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
| GET | `/api/events` | Stream SSE de actividad/notificaciones — **filtrado server-side por rol** (cada cliente recibe solo lo visible para él; ver `docs/SSE_EVENTS.md` §Filtrado). SA con `?view_as=` recibe el stream narrowed a ese usuario. | require_operator_view | `?view_as=` (solo SA) | `text/event-stream` | `app.py` |

## Actividad

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| GET | `/api/activity` | Feed de actividad **scoped por rol**: SA ve todo; operador solo sus propios depósitos y locks. Retorna `{"feed":[...]}` (era lista bare). Cada evento incluye `who_color`/`who_id` (2026-07-05, para el punto de color por operador en el feed). | require_session | query: `limit, offset, kind, who, q` | `{"feed":[evento,...]}` | `app.py` |
| GET | `/api/recent` | Cuentas con las que el usuario interactuó recientemente (depósitos propios + locks propios + marcadas). Scoped por operador. `reason ∈ {deposit, lock, mark}`. Incluye stats del día. | require_session | — | `{"recent":[{email,combo,last_ts,reason}], "stats":{attempts,approved,amount,rate}}` | `app.py` |
| GET | `/api/accounts/at-hand` | KPI "Cuentas a la mano" (📌): pineadas (marks del usuario) + recientes (deposits/locks/marks propios), enriquecidas y resueltas email→id server-side (`/api/recent` no lo daba). Fuente única — evita 3 fetches del front. Visibilidad reusa `_visible_emails` (non-SA no ve fuera de su universo, ni cuentas marcadas fuera de él). `recent` excluye lo que ya está en `pinned` (dos listas sin solape). Cap 20 c/u. | require_session (401 sin sesión) | — | `{"pinned":[{id,email,combo,fullname,status,balance_total,balance_real,grade,locked_by,locked_until}], "recent":[{...mismo shape..., last_ts, reason}]}` | `app.py:1602` |

## Depósitos (router `/api/deposits/*`)

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
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

## Modo auto-depósito V2 (inline en `app.py`)

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| POST | `/api/deposits/auto` | Crea misión auto: valida caps (`amount` ≤ `DEP_MAX_PER_TXN`, `target_count` 1-20, total ≤ `DEP_MAX_24H`), fail-fast 429 si `_mission_sem.locked()`, planifica con `auto_deposit.plan_auto_mission` (409 si no feasible), persiste en `auto_missions` (status `pending`) y lanza `run_auto_mission` en background. Broadcast SSE `kind=auto_mission status=started`. | superadmin (403 otro rol) | `{card_pipes: ["num\|exp\|cvv",...], amount?, target_count?}` | `{mission_id, accounts_selected, total_estimated, status:"matching"}` | `app.py:3818` |
| POST | `/api/deposits/auto/{mission_id}/cancel` | Cancel cooperativo: UPDATE `status='cancelled'` solo si existe (404 si no) y no está terminal (completed/cancelled/failed → no-op idempotente). El orquestador lee el status entre iteraciones y sale limpio. | superadmin (403 otro rol) | — | `{mission_id, status, changed}` | `app.py:3858` |
| GET | `/api/deposits/auto/{mission_id}/status` | Estado de la misión (fila completa de `auto_missions`; `card_pipes`/`accounts_selected`/`matches` parseados de JSON). 404 si no existe. | require_session | — | fila `auto_missions` | `app.py:3888` |

## Prewarm (router `/api/prewarm/*`)

| Método | Path | Función | Auth | Body / Query | Respuesta | File:line |
|---|---|---|---|---|---|---|
| POST | `/api/prewarm/select` | Encender prewarm para cuentas (con SSE) | require_session | `{account_ids, force?}` | `text/event-stream` | `prewarm.py:398` |
| POST | `/api/prewarm/cancel` | Cancelar prewarm | require_session | `{account_ids}` | `{ok}` | `prewarm.py:472` |
| GET | `/api/prewarm/status` | Estado actual | require_session | — | `{...}` | `prewarm.py:486` |
| POST | `/api/prewarm/refresh-stream` | Re-check accounts (SSE). **P3 (tanda 5): no-SA solo 1 id/request** (>1 → 403); SA puede bulk | require_session | `{account_ids}` | `text/event-stream` | `prewarm.py:569` |

---

## Módulos archivados (SP-1, 2026-06-25)

Los siguientes módulos fueron movidos a `_legacy/` en SP-1. Sus endpoints ya no están disponibles. Su funcionalidad migró a los módulos activos indicados:

| Módulo archivado | Funcionalidad migrada a |
|---|---|
| `_legacy/web_routes_deposits.py` | `deposits.py` (`/execute-stream`, `/multi/stream`, `/scheduled/*`) |
| `_legacy/web_routes_missions.py` | `deposits.py` (`multi_stream` / `scheduled_create`) |
| `_legacy/web_routes_prewarm.py` | `prewarm.py` (router activo) |
| `_legacy/web_routes_cards.py` | `app.py` (`GET /api/cards/all`, inline) |
| `_legacy/web_routes_logs.py` | `app.py` (`GET /api/logs`, inline) |
| `_legacy/web_routes_notifications.py` | SSE in-memory en `app.py` |
| `_legacy/web_watchdog.py` | — (watchdog de balance no reemplazado; auto-release de locks en `app.py:_release_watchdog_loop`) |

> `/api/deposits/execute` fue **eliminado** en SP-1 (fuga proxyless, sin consumidor; el UI usa `/execute-stream`).

Ver `AUDIT.md` para decisiones pendientes.
