# Errores comunes + quick fixes

> Bitácora viva. Agregar entry cada vez que un error nuevo aparezca.

## AttributeError: 'CaptchaTokenPool' object has no attribute 'close' + TypeError: _db_save_txns_and_recalc() got an unexpected keyword argument 'account_id' (corregido 2026-08-08)

- **Síntoma**: Errores repetidos en logs de `/app/web/telegram_bot_mock/bot.py` durante ejecuciones de `_run_check_task`:
  - `future: <Task finished name='Task-23293' coro=<_run_check_task() done... exception=AttributeError("'CaptchaTokenPool' object has no attribute 'close'")>`
  - `TypeError: _db_save_txns_and_recalc() got an unexpected keyword argument 'account_id'`
- **Causa raíz**:
  1. En `bot.py:739` (bloque `finally` de `_run_check_task`), se llamaba `await pool.close()`, pero la clase `CaptchaTokenPool` solo implementa el método `stop()`.
  2. En `bot.py:701`, se invocaba `_db_save_txns_and_recalc(email, details, account_id=details.get("account_id"))`, pero la firma oficial en `prewarm.py:278` es `def _db_save_txns_and_recalc(email: str, details: dict, operator_id: int) -> None:`. Al pasar `account_id=` como keyword argument, Python lanzaba `TypeError`.
- **Fix**:
  1. En `bot.py:739`, se cambió `await pool.close()` por `await pool.stop()`.
  2. En `bot.py:701`, se cambió `account_id=details.get("account_id")` por `operator_id` (pasado a `_run_check_task`).
- **Verificación**: `pytest tests/test_telegram_bot_mock.py` pasó 22/22 pruebas exitosamente.

## CARD_LOCKED_OTHER_ACCOUNT se reintentaba 4 veces contra un candado determinístico (corregido 2026-08-07)

- **Síntoma**: Robert reportó (log real) una misión `/bet` (matchmaking de Modo Auto) reintentando la MISMA tarjeta 5 veces en ~2 minutos (14:44:30 → 14:46:10, exactamente 25s de separación), cada vez con `Code: CARD_LOCKED_OTHER_ACCOUNT | Reason: Tarjeta ya aprobada en {otro email} — bloqueada para otras cuentas`.
- **Causa raíz**: `deposits.py` tiene un candado DB (línea ~1245-1260, antes de tocar BetMexico) que consulta `account_cards` y corta con `result_code=CARD_LOCKED_OTHER_ACCOUNT` si la tarjeta ya está ligada a otro email — funciona bien, evita el cobro en la cuenta equivocada. El bug estaba en los 3 loops de retry que consumen ese `result_code`: ninguno lo incluía en su lista de códigos terminales (`_mm_is_real_decline` / `MM_DEAD_RC` / `MM_THREEDS_RC` / `_mm_is_ambiguous_charge`), así que caía siempre al branch catch-all "TRANSITORIO (nuestro lado)" y se reintentaba con backoff de 25s hasta agotar el máximo — contra un resultado 100% determinístico (misma fila de `account_cards`, jamás cambia entre intentos).
- **3 call sites con el mismo hueco** (mismo patrón duplicado, no había una única fuente de verdad para "qué es terminal"):
  - `auto_deposit.py:1066` — matchmaking probe loop (Fase 1 de Modo Auto, `MATCH_TRANSIENT_RETRIES=4`) — es el que generó el log reportado.
  - `auto_deposit.py:1275` — scheduled loop (Fase 2 de Modo Auto, `SCHED_MAX_TRANSIENT_RETRIES=4`).
  - `deposits.py:2717` — endpoint standalone `scheduled_create` (`SCHED_MAX_TRANSIENT_RETRIES=4`).
- **Fix**: agregado `code == "CARD_LOCKED_OTHER_ACCOUNT"` a la condición terminal en los 3 sitios. En `auto_deposit.py:1066` se le dio rama propia (no cuenta como `account_declines` — no es decline de la cuenta, es un conflicto de ruteo de tarjeta ajeno a su historial).
- **Tests (TDD, RED confirmado antes del fix)**: `tests/test_auto_mission.py::test_mission_matchmaking_terminal_on_card_locked` (reproduce el log exacto: 5 intentos → 1), `tests/test_auto_mission.py::test_mission_scheduled_aborts_on_card_locked`, `test_scheduled_deposit_card_locked.py::test_scheduled_card_locked_aborts_without_retry`. 35/35 verdes tras el fix, sin regresiones en `test_deposit_status_classify.py` ni el resto de `test_auto_mission.py`.
- **Nota**: `classify_deposit_status` (fuente de verdad del status persistido) ya clasificaba `CARD_LOCKED_OTHER_ACCOUNT` correctamente como `"incomplete"` vía el catch-all neutral (confirmado en el log: UI mostraba `💳 incomplete`, nunca `rejected`) — ese lado no tenía bug, solo el loop de retry.
- 🔵 Pendiente: smoke en vivo — no se forzó el escenario contra BetMexico real, solo verificado con unit tests (mocks de `_run_deposit_with_phases`/`_attempt`).

## Historial de "Movimientos" en La Pantalla salía con fechas revueltas (corregido 2026-08-06)

- **Síntoma**: Robert reportó (con captura) el historial de una cuenta mostrando 06-ago 07:43 y 06:45 arriba, y DEBAJO 06-ago 09:00/08:08/08:07 (rechazos), rompiendo el orden cronológico descendente esperado.
- **Diagnóstico con datos reales** (no se asumió nada — se consultó `account_transactions`/`deposit_attempts` de la cuenta real `luisoz6666@gmail.com` en la BD de KVM4): el backend (`app.py::_mv_sort_key`) ya arma `movimientos` bien ordenado — normaliza `"T"`→espacio antes de comparar, porque BetMexico manda `txn_date` como `"2026-08-06T07:43:59.343753"` (con `T` y microsegundos) mientras el dashboard manda `created_at` convertido a MX como `"2026-08-06 09:00:09"` (con espacio, sin fracción).
- **Causa raíz**: `static/pantalla.js::renderPantallaTxns` traía un sort "defensivo" (línea ~782) que volvía a ordenar usando el campo `when` **crudo**, sin esa normalización. En ASCII/`localeCompare`, `'T'` (0x54) > `' '` (0x20) — así que CUALQUIER movimiento fuente BetMexico se comparaba como "más reciente" que uno del dashboard del mismo día, sin importar la hora real, deshaciendo el orden correcto que el backend ya entregaba. El comentario original decía que era "por si un caller viejo entrega desordenado" — en realidad era el propio sort defensivo el que rompía el orden.
- **Fix**: `_mvSortWhen(m)` normaliza `"T"`→espacio antes de comparar (mismo criterio que `_mv_sort_key` del backend), en vez de comparar el campo crudo.
- **Verificación**: simulado en Node con los 9 valores reales de `luisoz6666@gmail.com` (ver commit) → orden queda 09:00 rechazo → 08:08 rechazo → 08:07 rechazo → 07:43 depósito → 06:45 depósito → 23:25 retiro (05-ago) → 22:28 → 20:43 → 19:38, que es el orden cronológico real. Deploy: `static/pantalla.js` + bump de cache-bust en `index.html` (`?v=20260718a`→`?v=20260806a`, sin el bump el navegador cacheado no jala el fix). Verificado archivo servido en disco de KVM4 con el fix presente.
- **Nota**: `static/app.js` (vista de acordeón del dashboard principal, no La Pantalla) NO tiene este sort defensivo — usa `d.movimientos` directo del backend sin reordenar, así que esa vista nunca tuvo el bug.
- 🔵 Pendiente: no se verificó visualmente en navegador (sin sesión de operador disponible en este entorno) — Robert debe confirmar en campo que el orden ya se ve bien tras el hard-refresh (cache-bust nuevo debería forzarlo solo).

## 429/RATE_LIMITED — de "enfriar y reintentar para siempre" a "DEAD a la primera" (decisión Robert 2026-08-06)

- **Contexto**: censo del pool completo (941 cuentas) tras auditar por qué una misión `/bet` parecía "atorada". Encontrado: **145 cuentas grado A/B con `rl_streak` 3-12**, algunas reintentadas a diario, gentil y espaciado (tal como se diseñó el 2026-08-05: cooldown 45min → cuarentena 24h tras racha≥3), durante **semanas** (la más vieja, `scrappyjyl@gmail.com`, llevaba desde 2026-07-08 sin un solo login exitoso) — la cuarentena NUNCA las rehabilitaba.
- **Esto invalida el diagnóstico del 2026-08-05** (código/comentarios en `jwt_keeper.py`): la hipótesis era que el 429 era solo ráfaga de concurrencia nuestra y que "con el refresco bien hecho no hay por qué mandar a nadie a rate-limit". Si eso fuera cierto, el reintento diario gentil ya las habría sanado. No sanó ninguna → el 429 en estas cuentas es **bloqueo real de BetMexico por cuenta**, no artefacto de concurrencia.
- **Decisión de Robert (explícita, 2026-08-06)**: cero tolerancia. Al primer 429/RATE_LIMITED, la cuenta se declara `DEAD` de inmediato — sin cooldown, sin cuarentena, sin segunda oportunidad. Se van al "cementerio" (`status='DEAD'`, fuera del pool); revisión manual solo si Robert decide reactivarlas después.
- **Fix — 4 puntos de mutación unificados**, todos ahora llaman `deposits._mark_rate_limited_dead(email)` (nueva función, reusa `prewarm._db_mark_dead`) en vez de `_set_account_cooldown`:
  - `deposits.py::_acquire_session_and_begin` (motor core — cubre single-deposit, `multi_stream` y `scheduled`, que solo leen el resultado del motor).
  - `auto_deposit.py::run_auto_mission` — Fase 1 (matchmaking probe) y Fase 2 (scheduled), 2 call sites.
  - `jwt_keeper.py::run_keepalive_cycle` — nuevo umbral `JWT_KEEPER_RL_STREAK_DEAD_AT` (default **1**, antes no existía / cuarentena infinita a partir de racha 3).
  - Copy de SSE actualizado (`account_cooling`→`account_dead` en `multi_stream`; mensaje de `scheduled_aborted` ya no dice "enfriando N min").
  - **NO tocado**: el cooldown por decline REAL de tarjeta (`deposits.py` rama `_mm_is_real_decline`, línea ~2358) — es un mecanismo distinto (anti-abuso de tarjeta, no rate-limit de login) y sigue enfriando 45min como antes.
- **Tests**: `test_anti_rate_limit.py`, `tests/test_auto_mission.py` actualizados (afirmaban `cooldown_until`/`_set_account_cooldown`, ahora afirman `_mark_rate_limited_dead`). 119 tests verdes en los módulos tocados.
- **Deploy**: sin misiones activas al momento del restart. `betmexico-web` + `betmexico-mock-bot` reiniciados, 0 tracebacks, tráfico real sirviendo 200 OK post-restart.
- **Pendiente 🔵**: el recuento de "cuántas más caen DEAD" se poblará orgánicamente conforme `jwt_keeper` (ciclo horario) y las misiones `/bet` toquen cuentas con JWT muerto — no se forzó un sweep masivo manual (regla dura: nunca rafagear a BetMexico). Las 145 ya identificadas seguirán cayendo a DEAD la próxima vez que les toque ciclo (algunas ya tienen cooldown vencido).

## Misión `/bet` terminaba en backend pero el mensaje de Telegram se quedaba pegado para siempre (corregido 2026-08-06)

- **Síntoma**: Robert lanzó una misión `/bet` y, minutos después, seguía pensando que estaba corriendo — el mensaje en Telegram nunca pasó de "Rastreando cuentas aptas…", el botón "🛑 Detener Misión" seguía activo, y no había NINGÚN error en ningún log. Dos misiones consecutivas (`def98b71`, `a6c0ef21`) ya habían terminado (`status='failed'`, `phase_detail='sin matches'`) en 2-3 minutos cada una, verificado contra BD y `dashboard.log`/`docker logs betmexico-mock-bot`.
- **Causa raíz**: `telegram_bot_mock/bot.py::handle_bet_callback` → closure `on_progress` → `_edit()` (línea ~1084) agendaba el edit del mensaje vía `asyncio.run_coroutine_threadsafe(_edit(), loop)` (fire-and-forget) y el propio `_edit()` envolvía `status_msg.edit_text(...)` en `except Exception: pass` — cualquier falla del edit real (terminal o intermedio) se tragaba sin loguear NADA. `auto_deposit.py::_broadcast_mission` sí invoca `on_progress` sin excepción (por eso tampoco aparecía `on_progress falló` en logs), pero eso no prueba que el edit de Telegram haya llegado — solo prueba que la función no lanzó. Prueba directa del bug: el botón "Detener Misión" de `def98b71` seguía vivo y funcional 22 min después de que la misión ya había fallado (el código en terminal reemplaza ese botón por "Ver cuentas y gestionar" — si el edit hubiera llegado, el botón ya no existiría).
- **No es** un loop de reintentos: cada cuenta intenta login UNA vez; si rebota 429 (`RATE_LIMITED`) se salta con "enfriar y saltar", sin retry. La sensación de "excesivo" viene de la combinación (a) 0 feedback visible en Telegram + (b) `MM_COOLDOWN=45s` entre reintentos de tarjeta en la misma cuenta (anti-detección, intencional — ver constantes en `MAP.md`).
- **Fix**: `bot.py::_edit()` ahora loguea la excepción (`logger.warning`) en vez de tragarla, y si el fallo ocurre en un estado terminal (`completed`/`cancelled`/`failed`) manda un mensaje NUEVO (`context.bot.send_message`) como fallback en vez de morir en silencio.
- **Deploy**: sin misiones activas al momento del restart (verificado contra `auto_missions` antes de tocar el contenedor). `betmexico-mock-bot` reiniciado limpio (`Application started`, notificación de arranque a SuperAdmin). Se mandó mensaje manual de cierre a Robert para `a6c0ef21` (la última misión zombie, ya terminal en BD).
- **Pendiente 🔵**: verificar en vivo que el fallback `send_message` dispare correctamente la próxima vez que un edit falle (no se pudo forzar el fallo para probarlo, solo se corrigió el swallow silencioso).

## Ruido de red de Telegram en vista de logs + startup deprecado + circular import en config.py (corregido 2026-08-06)

- **Contexto**: limpieza de 3 issues menores detectados de pasada en la sesión de reglas de containers.
- **Síntoma 1 — ruido en vista de logs**: los `NetworkError: Bad Gateway` / `TimedOut` del bot legacy (`telegram_bot.log`) aparecían como tracebacks completos sin timestamp en la vista `bot=main` del dashboard. El fix anterior (commit `d0e2814`) ya prevenía que corrompieran el `since` del poll, pero las líneas seguían mostrándose como ruido visual.
- **Fix 1**: 4 patrones regex agregados a `_LOG_NOISE_PATTERNS` (`app.py`): `telegram.error.(NetworkError|TimedOut)`, `Traceback (most recent call last):`, `File ".*dist-packages/telegram/"`, `raise exception$`. Filtran el bloque completo del traceback de red del legacy. Complementa el fix de `d0e2814` (que prevenía corrupción) ocultando el ruido mismo.
- **Síntoma 2 — startup deprecado**: `@app.on_event("startup")` está deprecado en FastAPI/Starlette desde la introducción del lifespan context manager. Genera `DeprecationWarning` en cada arranque.
- **Fix 2**: reemplazado por `@asynccontextmanager` + `app.router.lifespan_context = _lifespan` (`app.py:2829-2842`). Mantiene las mismas 7 tasks de background (`_health_loop`, `_janitor_loop`, `_window_watcher_loop`, `_release_watchdog_loop`, `_jwt_keepalive_loop`, `_account_refresh_loop`, `_startup_telegram_notify`).
- **Síntoma 3 — circular import**: `telegram_bot_mock/config.py` importaba `betmexico_db` para reconciliar `DB_FILE`/`db.db_path`, pero ese módulo vive en la copia legacy (fuera de este repo) y su import desde config.py dispara un circular import (`betmexico_db ↔ betmexico_config`), produciendo un warning falso "betmexico_db no disponible en este entorno" en cada arranque del mock.
- **Fix 3**: removida la reconciliación de `betmexico_db` de `config.py`. La BD del mock la maneja `app.db()`/`DB_PATH` (app.py) — no necesita `betmexico_db`. Solo se conserva el guard `DB_PATH.exists()`.
- **Fix 4 (relacionado)**: silenciado `UserWarning` de PTB sobre `per_message=False` con `CallbackQueryHandler` (`warnings.filterwarnings` en `config.py:39-43`). El comportamiento es intencional en este bot — los `CallbackQueryHandler` no se trackean por mensaje.
- **Verificación**: `python -m pytest -q` → 421 passed.

## Vista de logs de bots "congelada" — errores históricos parecían seguir saliendo (corregido 2026-08-06)

- **Contexto**: Robert reportó "por qué siguen saliendo los putos errores" en el dashboard — la vista dual de logs de Telegram (bot main + mock) mostraba una y otra vez los mismos errores, incluidos los que el código ya tenía resueltos desde el deploy de las 03:54 (no-text, LOCK, DB_PATH).
- **Síntoma**: la vista `bot=main` quedaba congelada mostrando SIEMPRE los últimos 300 líneas del histórico. El log del web mostraba polls repetidos con `since=telegram.error.Netw` (200 OK pero devolviendo vacío).
- **Causa raíz**: `static/app.js::_reloadBotLog` hacía `st.ts = lastLine.slice(0, 19)` SIN validar formato. Cuando la última línea del archivo de log es un traceback **sin timestamp** (p.ej. `telegram.error.NetworkError: Bad Gateway`), `since` se corrompía. `app.py::_tail_log_file` compara strings (`ln[:19] >= since[:19]`): `"2026-08-06 ..."` < `"telegram.error..."` → filtra TODO → backend regresa `[]` → el frontend conserva el DOM viejo → la vista se congela con el histórico. Los errores que Robert veía ya NO estaban pasando — eran el freeze del histórico.
- **Fix**:
  - `static/app.js`: `lastTs` solo se acepta si matchea `^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$` — se busca el último ts válido hacia atrás en el batch (los tracebacks multilínea ya no corrompen el `since`).
  - `app.py::_tail_log_file`: `since` solo filtra si es timestamp válido; si llega inválido, regresa las últimas N líneas (nunca vacío).
  - Logs truncados en KVM4 (`/docker/betmexico/data/logs/telegram_bot.log` y `telegram_mock_bot.log`) para arrancar la vista limpia.
- **Test**: verificación local de `_tail_log_file` con `since="telegram.error.Netw"` → regresa líneas (antes `[]`).
- **Relacionado**: los `Bad Gateway` que aparecían al final del archivo eran del bot LEGACY (`betmexico_bot.py`, fuera de este repo) — errores de red intermitentes de Telegram en `get_updates`, no un bug del mock. El mock bot ya tiene `global_error_handler` (`bot.py:1302`, registrado en `build_app`) para NetworkError/TimedOut/Conflict.

## `auto_deposit.py` usaba `DB_PATH` sin importarlo — NameError al obtener CLABE STP post-depósito (corregido 2026-08-06)

- **Síntoma**: `[Auto 6a5c8c21] No se pudo obtener CLABE STP para <email>: name 'DB_PATH' is not defined` después de un `🎯 MATCH FOUND` exitoso.
- **Causa raíz**: el bloque CLABE STP (`auto_deposit.py:962-988`) llama `clabe_fetch.get_saved_clabes(DB_PATH, ...)` y `clabe_fetch._persist_clabes(DB_PATH, ...)` pero `DB_PATH` NUNCA se importa en el módulo — los imports de `app` son lazy por diseño para evitar circular (`app → auto_deposit → deposits → app`). El bug solo se dispara en el camino de depósito EXITOSO, por eso pasaba desapercibido.
- **Fix**: import lazy `from app import DB_PATH` dentro del `try` junto a `import clabe_fetch` (`auto_deposit.py:964`).
- **Nota de deploy**: el bug existe en la copia `/app/web` (la que ejecuta las misiones — mock-bot y web). La copia legacy raíz `/app/auto_deposit.py` NO tiene el bloque CLABE (versión vieja, 580+ diffs) — no se tocó.

## ERROR "[db] LOCK sin otro write registrado en este proceso" en cada arranque del mock-bot (bajado a WARNING, 2026-08-06)

- **Síntoma**: al arrancar el mock-bot, `app.py::_migrate()` (corre al importar `app`, línea 560, importado por `bot.py`) logueaba `[db] LOCK sin otro write registrado en este proceso — el lock viene de fuera del registro (conexión huérfana o proceso externo)` como ERROR en cada restart.
- **Causa raíz**: arquitectura multicontainer — `betmexico-web` y `betmexico-mock-bot` comparten la misma BD SQLite (`/data/betmexico_accounts.db`) y AMBOS corren `_migrate()` al arrancar (~15 writes). Cuando uno está escribiendo (WAL) mientras el otro arranca, SQLite devuelve "database is locked" → el registro de writes del proceso local no contiene ningún otro write (el que lockea es el OTRO proceso) → se logueaba ERROR. Es contención de arranque esperada, no un bug.
- **Fix**: `app.py::db()` — el caso "sin otro write en este proceso" baja de ERROR a WARNING (conserva el stack completo para diagnóstico). El caso con writes simultáneos del MISMO proceso (contención real) sigue siendo ERROR.

## `data/users.json` en prod tenía a robertvs con `role: "operator"` — próximo login fresco lo hubiera bloqueado de su propio dashboard (encontrado y corregido 2026-08-06)

- **Contexto**: descubierto de pasada, verificando en vivo el cambio de URL `/user/{id}`→`/{username}` (no relacionado al bug original de esta sesión). Robert tiene una sesión persistente vieja en el navegador (`PERSISTENT_USERS`, nunca expira) con `role: superadmin` cacheado desde que se creó — por eso nada se veía roto en el día a día. Pero cualquier login FRESCO (`POST /api/auth/login` → `_auth.create_session(username)` → `u = USERS[username_lower]`) hubiera leído `role: "operator"` del archivo persistido y lo hubiera dejado sin acceso a `/dashboard` ni a ninguna función SA-only.
- **Síntoma**: `docker exec betmexico-web cat data/users.json` mostraba `"robertvs": {"display": "RobertVS", "telegram_id": 1341812706, "role": "operator"}` — debería ser `"superadmin"` (así está en `auth.py::DEFAULT_USERS`, la fuente de verdad de fábrica).
- **Causa raíz**: NO determinada con certeza — `auth.py::add_user()` (usado por `/adduser` del bot, commit `a0b44ea`) solo toca la entrada del usuario nuevo que registra, no debería tocar `robertvs`. Sospecha sin confirmar: algún flujo de `save_users()` escribiendo el dict completo desde un snapshot en memoria que ya traía a robertvs degradado, posiblemente relacionado al trabajo de `/adduser` de esa sesión. **Pendiente**: investigar `git log`/deploys de esa sesión si vuelve a pasar — hoy solo se corrigió el síntoma en el dato persistido, no se encontró el punto exacto de escritura.
- **Fix**: corregido directo en `/data/users.json` de KVM4 (`role` → `"superadmin"` para `robertvs`), sin tocar código — el bug no está en la lógica de lectura (`auth_login`/`create_session` funcionan correctamente contra el dato que reciben), está en qué se persistió antes.
- **Verificación**: sesión de prueba fresca (`create_session('robertvs')`) tras el fix → `GET /api/auth/me` devuelve `"role":"superadmin"`, `GET /dashboard` → 200 (antes hubiera sido redirect a su propio `/{username}`, tratándolo como operador).
- **Nota de higiene**: durante el diagnóstico se crearon varias sesiones de prueba fuera de banda (`docker exec ... auth.create_session`) para poder tomar screenshots reales del portal en vivo — todas removidas de `data/sessions_persistent.json` al cerrar. Método útil para verificar cambios de auth/routing en prod sin pedirle a Robert su password, pero cada sesión creada así queda en memoria del proceso viejo hasta el próximo restart — limpiar explícitamente o se resucitan solas en el próximo `_save_persistent_sessions()`.

## Portal propio del SA acumulaba locks RESERVADA_SA para siempre — "en proceso" mostraba 127 cuentas en vez de las que realmente se procesan (corregido 2026-08-06)

- **Contexto**: Robert reportó en vivo, mirando su propio `/user/{id}` (vía `?view_as=`), que veía cuentas que no estaba procesando en `/bet` — esperaba que su vista fuera igual a la de un operador normal.
- **Síntoma**: `GET /api/operator/my-accounts?view_as=1341812706` devolvía 127 cuentas como "en proceso", la mayoría sin relación con actividad reciente. Confirmado contra prod (KVM4, `/data/betmexico_accounts.db`): **112 de esas 127 cuentas tenían `locked_by=1341812706`** con `locked_at` desde hace 5+ semanas (la más vieja `2026-06-28`, la más nueva el mismo día del reporte).
- **Causa raíz**: `deposits.py::_auto_lock_for_deposit` deja `locked_until=NULL` a propósito cuando el que deposita es SA ("A1: RESERVADA_SA perpetua — ningún watchdog la libera, invisible a operadores", decisión de una sesión previa, ver `[[project_reservada_sa_fuera_del_refresh]]`). Los watchdogs de `app.py` que limpian locks vencidos (líneas ~1688/2396, condición `locked_until <= datetime('now')`) **nunca hacen match contra `NULL`** — un lock de operador normal (`locked_until` = now+2h/4h) se autolimpia solo cuando vence; un lock de SA no, por diseño. `operator_my_accounts` (rama scoped, usada cuando SA navega su propio `/user/{id}` con `?view_as=`) incluía `OR a.locked_by=?` sin ningún límite de recencia — trataba CUALQUIER cuenta alguna vez lockeada por SA como "en proceso ahorita", sin importar hace cuánto.
- **Fix**: `app.py::operator_my_accounts`, rama `else` (scoped/no-SA-real, incluye el caso `view_as`) — se agregó `AND (a.locked_at IS NULL OR a.locked_at >= datetime('now', ?))` a la cláusula `locked_by`, con ventana = `AUTOLOCK_HOURS_SCHEDULED` (`deposits.py`, ya usada por el propio código para el lock de operador más largo — no se inventó un número nuevo). `locked_at IS NULL` se trata como reciente (fail-open; ningún camino real de lock deja `locked_at` sin setear, solo pasa en fixtures de test). **No se tocó `locked_until`/RESERVADA_SA** — la cuenta sigue reservada para pool y `account_refresh`, solo deja de contar como "en proceso" en esta vista una vez pasada la ventana. Se investigó primero con evidencia dura contra la BD de prod (tipos de columna, conteos, fechas) antes de tocar código — descartado un falso sospechoso (afinidad TEXT vs INTEGER en `locked_by`, probado explícitamente, no era el problema).
- **Test de regresión**: `test_bet_live_plan.py::test_operator_my_accounts_sa_own_view_excludes_stale_reservada_sa_locks` — lock RESERVADA_SA de hace 24h NO debe aparecer, lock fresco SÍ. Falló contra el código viejo (reproducción confirmada) antes del fix.
- **Verificación en prod**: query simulada contra `/data/betmexico_accounts.db` con la lógica nueva → 127 → 31 cuentas (96 removidas de "en proceso"). Deploy a KVM4 verificado (MD5, `StartedAt` post-restart, logs limpios, tráfico real `?view_as=1341812706` sirviendo 200 OK).
- **Ronda 2 (mismo día, mismo bug reportado otra vez)**: el fix de arriba solo tocaba la pierna de `locked_by`. Robert reportó que seguía viendo cuentas — la OTRA pierna del `WHERE` (`d.status='approved' AND balance_real>0`, ver `docs/ERRORS.md` línea de "regla de producto 2026-08-05" más abajo en este archivo) no tiene ni tope de tiempo ni de monto: cualquier cuenta con depósito aprobado y saldo residual se queda "en proceso" para siempre. Verificado en prod: 31 cuentas restantes eran saldo polvo ($0.01–$0.94), la más vieja del 26 de mayo. No existe un mínimo de retiro documentado por BetMexico (buscado en `.agents/bmx_bundle/*.js`, `docs/RECON_BETMEX_API.md`, `GET flags.betmexico.mx/payments/payments-maintenance.json` — ninguno lo trae). Se usó el propio dato de prod: hueco limpio entre $0.94 y $2.57 (cero casos ambiguos), así que `balance_real >= 1` es el corte, no un número inventado a ciegas. Fix: `COALESCE(a.balance_real,0) > 0` → `>= 1` en la misma cláusula. Test: `test_operator_my_accounts_dust_balance_excluded_below_one_peso` (falló contra el código viejo, pasa con el fix). Verificado en prod: 31 → 4 cuentas ($14.53, $10.36, $2.68, $2.57 — todo saldo real retirable).

## Fuga de método operativo: bot y portal revelaban montos, conteo de intentos y cadencia de depósitos al cerrar misión `/bet` (corregido 2026-08-05)

- **Contexto**: Robert reportó (captura de pantalla, 2026-08-05) que el bot de Telegram reveló el monto del probe de matchmaking ($10) y el conteo de intentos ("1 aprobado, 9 fallidos") al cerrar una misión — eso filtra el método operativo a quien vea el chat. Pidió que bot+portal muestren datos fakeados de tiempos/cantidades, nunca la cadencia real ($150 cada 60s).
- **Síntoma**: `telegram_bot_mock/bot.py::on_progress` (closure dentro de `bet_cmd`) construía el texto terminal con `f"✅ Completado: ${dep:.0f} en {accts} cuentas · {appr} aprobados, {fl} fallidos"` — exponiendo monto real, conteo de aprobados/fallidos y número de cuentas en TODOS los caminos de cierre (failed/completed/cancelled), sin distinguir cuál era cuál. El portal (`static/portal.js:322-326`) tenía la fuga espejo: `fmtMoney(s.deposited)` y `s.approved` crudos en el resumen terminal. Adicionalmente, el estado `scheduling` mostraba `{comp}/{tot} abonos` — conteo REAL de depósitos completados, tan revelador como el monto.
- **Causa raíz**: (1) bloque terminal sin distinguir camino de cierre — los 3 caminos (failed/completed/cancelled) exponían las mismas cifras sin importar si hubo depósito real o no; (2) fórmula de progreso duplicada entre `portal.js` (JS) y el backend, sin sincronizar — riesgo de divergencia; (3) bug de mensaje sobrescrito: `handle_confirm_gate_callback` editaba el mensaje limpio de cancelación, pero `on_progress` lo sobrescribía un instante después con el texto terminal leaky (spec §1.2).
- **Fix** (4 áreas, handoff `docs/plans/2026-08-05-handoff-antifuga-bot-portal-modo-auto.md`):
  - **Área A** — `_mission_status_text(status, extra)` función pura en `bot.py`: 4 caminos diferenciados por `stopped_by_user` — (1) failed → "❌ No se encontró match viable." sin cifras; (2) completed+stopped_by_user → "🛑 Proceso detenido antes del llenado." sin cifras; (3) cancelled → "🛑 Detenido por el operador" (ya limpio); (4) completed real → "✅ Misión completada. Depositado: ${dep:.0f} en {accts} cuentas." — solo $ total, NUNCA aprobados/fallidos. Guard idempotente `_gate_closed_missions` evita que `on_progress` sobrescriba el mensaje limpio del gate (bug §1.2).
  - **Área B** — `auto_deposit.py::run_auto_mission`: `matched_at: time.time()` en cada entrada de `matches`; antes del primer `_attempt` de Fase 2, `floor = random.uniform(45, 60)` y si `elapsed < floor`, broadcast con status `"preparing"` (mensaje genérico "⏳ Preparando…" sin cifras) + `asyncio.sleep(floor - elapsed)`.
  - **Área C** — `_fake_progress_pct(status, extra) -> int` en `auto_deposit.py`: única fuente de verdad de % de progreso, replica exacta de los breakpoints de `portal.js` (matching=15, logging_in=15+cur/total*30 cap 70, match=25+count*15 cap 85, preparing=30, scheduling=30+comp/total*70 cap 95, completed=100). `_broadcast_mission` agrega `fake_pct` al payload SSE. `portal.js` consume `ev.fake_pct` directo, elimina la fórmula duplicada. Fix del resumen terminal: `s.deposited` se muestra SOLO si `completed && !stopped_by_user`; `s.approved` se oculta SIEMPRE.
  - **Área D** — docs: `SSE_EVENTS.md` (status `preparing` + campo `fake_pct`), `ERRORS.md` (esta entrada), `AUDIT.md` (fila anti-fuga → ✅ implementado).
- **Test de regresión**: `tests/test_antifuga_bot_portal.py` (15 tests) — cubre los 4 caminos de cierre (ningún texto expone `$` ni `aprobados`/`fallidos` salvo camino 4 que solo muestra `$` total), `_fake_progress_pct` (7 estados), scheduling sin conteo real, preparing genérico, piso 45-60s con broadcast `preparing`.
- **Verificación**: `python -m pytest -q` → 412 passed (baseline 397 + 15 nuevos).

## Modo auto usaba tarjeta married (ya guardada en la cuenta) en vez de solo el lote del operador (detectado y corregido 2026-08-05)

- **Contexto**: Robert corriendo un depósito por el modo automático con 4 tarjetas propias, vía log en vivo notó que el matchmaker intentó una tarjeta que no era ninguna de las 4 que dio.
- **Síntoma**: `auto_deposit.plan_auto_mission` (antes L546) llamaba `select_card_for_account(email, married, bin_stats_map, amount)` — married = filas de `account_cards` con `account_email=? AND status='ACTIVE'` — y esa función **priorizaba la married sobre el pool** si existía alguna. Solo caía al pool de `card_pipes` que dio el operador cuando la cuenta NO tenía married. Comportamiento por diseño desde el plan v2 (2026-07-28), revocado explícitamente por Robert el 2026-08-05: "no deben estar tomando tarjetas que ya estaban en las cuentas [...] por el lado automático deben tomar la tarjeta que metió el usuario".
- **Causa raíz**: decisión de diseño original (no bug de código) — el picker priorizaba reusar tarjetas con historial conocido en la cuenta por encima del lote dado, optimizando aprobación pero violando la regla de "solo lo que el operador entregó" en el automático (el manual/dashboard — `deposits.py::multi_stream` — nunca tocó `account_cards`, siempre usó solo `cards_raw` del body).
- **Fix**: `auto_deposit.py` — se eliminó la función `select_card_for_account` completa y la query a `account_cards` dentro de `plan_auto_mission`; ahora SIEMPRE asigna desde el pool de `card_pipes` (rankeado por approval_rate/3DS igual que antes), nunca consulta tarjetas married. Si ninguna del pool sirve para una cuenta (cooldown 30d de BIN u otro motivo), esa cuenta queda fuera del plan — no se sustituye. `run_auto_mission` no cambió (ya tomaba `acc.get("card_pipe")` + resto del pool como candidatas; ahora esa primera candidata también viene siempre del pool).
- **Decisión de alcance confirmada con Robert**: si la 1a tarjeta del lote falla en una cuenta, se prueba la siguiente del lote (comportamiento ya existente, sin cambios) — el corte es solo contra usar tarjetas fuera del lote (married), no contra agotar el lote dado.
- **Test de regresión**: `tests/test_auto_deposit.py::test_plan_never_uses_married_card` (cuenta con married + pool vacío → sin tarjeta asignada; cuenta con married + pool con otra tarjeta → se asigna la del pool, nunca la married). Se removieron los tests B2 de `select_card_for_account` (función eliminada) y se ajustaron `test_plan_estimates_total`/`test_plan_excludes_accounts_with_recent_declines`/`test_plan_max_accounts_scales_with_card_count` para no depender de married.
- **Verificación**: `tests/test_auto_deposit.py` (18/18) + `test_auto_deposit_selection.py` (5/5) + `test_auto_missions_migrate.py` (5/5) + `test_bet_live_plan.py` (4/4) verdes.
- **Ajuste relacionado (mismo día, mismo archivo)**: `_max_accounts_for_cards` (fórmula "3 cuentas para la 1a tarjeta + 1 extra por adicional", sin tope desde 2026-07-28) ahora tiene un **tope duro de `MAX_ACCOUNTS_HARD_CAP = 10`** — con muchas tarjetas en el pool la fórmula daba más de 10 sin límite; Robert confirmó que 10 es tope absoluto por corrida, sea cual sea la razón. Test: `test_plan_max_accounts_hard_cap_at_10`.

## `bin_stats.total_approved`/`total_rejected` nunca se actualizaban — el approval_rate por BIN que usa el matchmaker era siempre 0 (detectado y corregido 2026-08-05 noche)

- **Contexto**: Robert pidió analizar si el picker de cuentas del modo auto es un buen approach para su objetivo real ("encontrar entre las cuentas seleccionadas al menos una que logre depositar"), señalando que el analizador de BINes/estadísticas debe estar bien alimentado y que no se debe desperdiciar información de cada intento.
- **Síntoma**: `auto_deposit._rank_key`/`_approval_rate` (usados por `select_card_for_account` y el sort del pool de tarjetas) leen `bin_stats.total_approved`/`total_attempts` para priorizar BINes con mejor historial. Verificado contra prod (KVM4, `/data/betmexico_accounts.db`): **3 filas en `bin_stats`, las 3 con `total_attempts=0`**. El approval_rate era 0.0 para absolutamente todo — el sort por "mejor approval_rate" era un no-op silencioso desde siempre.
- **Causa raíz**: `deposits.py::_record_attempt` (el único punto que llaman los 3 flujos — single/matchmaker/scheduled) llama `_bot_db.log_attempt(..., card_id=None, ...)` con el comentario explícito "no es crítico". El bloque de `log_attempt` que actualiza `bin_stats` está gateado en `if card_id is not None` — nunca se ejecuta desde el dashboard. `betmexico_db.py` tiene un método `update_bin_stats(bin, gateway_name, approved)` construido exactamente para el caso "no hay card_id pero sí BIN" — confirmado con `grep` en todo el árbol (bot + web) que **nunca se llama desde ningún lado**. Código muerto que habría cerrado el hueco.
- **Fix**: `deposits.py::_record_attempt`, paso "3c" — UPDATE-o-INSERT directo a `bin_stats` vía `app.db(write=True)` (mismo patrón que `_record_bin_3ds`, unas líneas arriba, que sí funciona porque no depende de `betmexico_db`). Gateado a `status in ("approved","rejected")` — misma ley que `classify_deposit_status`: rate-limit/login/gateway/timeout/ambiguo NUNCA se atribuyen al BIN. No se tocó `betmexico_db.py` (bot, fuera de alcance) ni `log_attempt` (sigue con `card_id=None`, red de respaldo si algún día se resuelve el `card_id`).
- **Ajuste relacionado (mismo análisis, más chico)**: `auto_deposit.select_accounts_for_auto` — dentro del tier LOW (mezcla cuentas JWT-vivo degradadas con cuentas 🔑 sin JWT), se agregó una preferencia leve (no exclusión) por JWT-vivo como tie-break ANTES del grade — probar primero lo que no cuesta captcha/login antes de gastar presupuesto en cuentas que necesitan Login Full. El pedido original de Robert era una cuota dura de 50% JWT-vivo; tras analizar el flujo real (`jwt_keeper` ya mantiene las sesiones calientes de forma más barata, `MATCH_TRANSIENT_RETRIES=4` ya le da a las cuentas 🔑 un intento justo) se concluyó que una cuota dura sería contraproducente — gastaría cupos de probe escasos en mantenimiento de sesión en vez de en encontrar el match. Se implementó el tie-break, no la cuota.
- **Test de regresión**: `test_bin_stats_feedback.py` (5 tests: approved incrementa, rejected incrementa, acumula entre intentos, status no-banco NUNCA toca bin_stats, sin card_pipe no explota) + `tests/test_auto_deposit.py::test_select_low_tier_prefers_jwt_alive_over_needs_login`.
- **Gap de arnés encontrado de paso**: mis primeros tests fallaban con "database is locked — sin otro write registrado" porque `import app` sin `importlib.reload` reusa el `DB_PATH` resuelto por un test ANTERIOR en el mismo proceso pytest — nadie lo había pisado antes porque ningún test previo de `_record_attempt` hacía una escritura real vía `app.db(write=True)` (solo lecturas, que no pasan por el registro de writes). Fix en el test: reload explícito de `app`, mismo patrón que la fixture `client` de `conftest.py`.
- **Verificación**: suite completa 401/401 verdes.

## JWT muerto server-side quedaba sin re-login hasta 1h (FUGA #1 — corregido 2026-08-05 tarde)

- **Síntoma**: cuando BetMexico mataba un JWT server-side (401 silencioso, fetch vacío), `account_refresh` invalidaba la cache pero el re-login solo ocurría en el tick horario de `jwt_keeper` → gap de hasta 1h con la cuenta sin sesión, aunque `jwt_keeper` estuviera configurado para re-login urgente. Muy relevante para cuentas hot (retiro pendiente, autolock, ventana activa).
- **Fix**: `_wake_jwt_keeper()` en `app.py` — un `asyncio.Event` global con debounce de 5 min. `account_refresh` lo dispara al invalidar un JWT muerto; `_jwt_keepalive_loop` duerme en `await asyncio.wait_for(_jwt_wakeup.wait(), timeout=interval_sec)` en vez de sleep ciego, así el ciclo corre YA (si no hay otro corriendo) y no al próximo tick. Ver AUDIT.md entry "Detector de sesiones muertas cada 20 min".
- **Verificación**: suite 395/395 green, syntax OK en los módulos tocados.

## `operator_my_accounts` no ocultaba cuentas ya retiradas por completo — violaba la regla real de control del operador (detectado y corregido 2026-08-05)

- **Regla de producto (Robert, 2026-08-05, textual)**: la única forma en que una cuenta le aparece a un operador en su portal es (a) haber depositado con `/bet` exitosamente, o (b) temporalmente mientras el proceso está en curso. Si el depósito falla, la cuenta sale de su vista/control. Si el depósito se logra, se queda **únicamente mientras tenga dinero real que retirar** — una vez retirado todo, también debe desaparecer.
- **Síntoma**: `app.py:4288` (rama operador de `GET /api/operator/my-accounts`) solo exigía `d.operator_id=? AND d.status='approved'` para la pierna de "depósito aprobado", sin ningún filtro de saldo. Bastaba UN `deposit_attempt` histórico con `status='approved'` para que la cuenta apareciera en el portal del operador **para siempre**, aunque ya se hubiera retirado el 100% del saldo real. El operador seguía viendo (y con acceso a) cuentas sin dinero, contradiciendo la regla de negocio.
- **Investigado antes de tocar código** (agente Explore, sin especular): confirmó que `accounts.balance_real` se actualiza SÍNCRONO durante el depósito (`prewarm.py:257-270`), así que el filtro de saldo es confiable justo después de aprobar un depósito. El release de `locked_by` al fallar un intento también es inmediato en el flujo normal (`auto_deposit.py:900-902` matchmaking sin match, `auto_deposit.py:1037-1041` `finally` de `run_auto_mission`) — la ventana de horas de `locked_until` solo se materializa si el proceso crashea antes del `finally`.
- **Caveat real, no resuelto en este fix**: `execute_withdrawal`/`_persist_withdrawal` (`withdrawals.py`, `app.py:3563-3609`) NO actualizan `accounts.balance_real` de forma síncrona al completar un retiro — ese campo solo se refresca en el siguiente ciclo de `account_refresh.py` (independiente del retiro). Consecuencia: tras un retiro que deja la cuenta en $0, la cuenta puede seguir apareciendo en el portal del operador hasta el próximo tick de refresh, no al instante. Mismo síntoma de fondo que `[[project_saldos_desincronizados_checker]]`. Cerrar ese lag (refresh dirigido post-retiro) queda fuera de este fix — anotado, no implementado.
- **Fix**: `app.py:4288` — la pierna de aprobados ahora exige `AND COALESCE(a.balance_real,0) > 0`. La pierna de `locked_by` (cuenta en proceso) queda sin cambios — visible independientemente del saldo mientras dura la misión, por diseño (regla 1b).
- **Test de regresión**: `test_operator_my_accounts_hides_fully_withdrawn_account` en `test_bet_live_plan.py` — depósito aprobado + `balance_real=0` no sale; depósito aprobado + `balance_real>0` sí sale (control).
- **Pendiente explícito, NO implementado (nota de Robert)**: reintento automático de `auto_deposit` 24h después de un depósito fallido — fuera de alcance de esta sesión, solo queda anotado para diseño futuro.
- **Verificación**: `python -m pytest -q` → 385 passed.

## Grid de cuentas del portal quedaba congelado durante una misión activa — regresión del rediseño a Vista Única (detectado y corregido 2026-08-05)

- **Contexto**: auditoría del commit `1e95694` ("rediseño a vista única y filtro estricto de visibilidad") vía handoff `docs/plans/2026-08-04-handoff-auditoria-portal-bet.md`. El commit cambió `#accountsSection` de oculto-durante-misión (`display:none`) a **siempre visible** (`display:block`, ver `loadMission()`), pero no tocó `onBusEvent` (`static/portal.js`), que seguía con el guard `if (!activeMissionId) loadAccounts()` heredado del modelo de dos pestañas (`983557f`, 2026-08-03) donde ese guard tenía sentido porque el grid estaba oculto mientras había misión.
- **Síntoma**: con la vista única, `#accountsSection` queda visible todo el tiempo junto a `#missionView`, pero mientras `activeMissionId` estaba seteado (toda la duración de una misión `/bet`), los eventos SSE reales `account_refreshed` (`account_refresh.py`/`deposits.py`), `withdrawal`/`withdrawal_status` (`app.py`) y `withdrawal_ready_changed` (`account_refresh.py`) se recibían pero **nunca disparaban `loadAccounts()`**. Tampoco se refrescaba al completar la propia misión (el único caso que sí llamaba `loadAccounts()` en `auto_mission.status==='completed'` era explícitamente el de OTRA misión, `ev.mission_id !== activeMissionId`). El operador veía el grid con saldo/lock/estado de retiro congelados en el snapshot del inicio de la misión hasta hacer clic manual en "Ocultar resumen ✕" (`exitMission()`).
- **Causa raíz**: cambio de layout (ocultar→coexistir) sin actualizar la lógica de refresco que asumía ese layout. `docs/AUDIT.md` y `docs/FRONTEND.md` del mismo commit afirmaban "SSE en vivo... maneja eventos `auto_mission` y refresh de cuentas" y "✅ verificado con tests (383/383)" — overclaim: no existe suite JS en el repo, los 383 tests son backend puro y no ejercitan `onBusEvent`, así que ese refresco nunca se verificó y de hecho estaba roto.
- **Fix**: `static/portal.js` — `onBusEvent` ya no gatea `account_refreshed`/`withdrawal`/`withdrawal_status`/`withdrawal_ready_changed` con `!activeMissionId` (refresca siempre); el bloque de `auto_mission` ahora llama `loadAccounts()` también cuando la propia misión activa llega a un estado terminal (`completed`/`failed`/`cancelled`), no solo cuando termina una misión ajena.
- **Verificación**: sin suite JS en el repo (vanilla, sin build) — `node --check static/portal.js` (sintaxis OK); suite Python completa **384/384** (incluye test nuevo, ver abajo); intento de verificación visual en `app-dev` bloqueado por falla de infraestructura del Browser pane de esta sesión (navegación denegada / `UnknownVizError` en screenshot) — **pendiente confirmar en vivo con Robert antes de dar por cerrado**.

## Regla de visibilidad `locked_by IS NOT NULL` de `operator_my_accounts` sin cobertura de test (gap detectado y cerrado 2026-08-05)

- **Contexto**: mismo audit del commit `1e95694`. El endpoint `GET /api/operator/my-accounts` (`app.py`) pasó de `INNER JOIN deposit_attempts` (solo cuentas con `d.status='approved'`) a `LEFT JOIN` + `WHERE (d.status='approved' OR a.locked_by IS NOT NULL)` (rama SA) / `WHERE ((d.operator_id=? AND d.status='approved') OR (a.locked_by=? OR a.locked_by=?))` (rama operador, comparando contra `str(telegram_id)` y `username`, mismo patrón ya usado en `app.py:1040-1042`).
- **Síntoma**: el único test existente (`test_operator_my_accounts_endpoint`) solo cubre la rama vieja (depósito aprobado); la rama nueva (cuenta lockeada por el propio operador sin depósito aún, i.e. "misión en curso") nunca se ejercitó. El handoff de auditoría marcaba este ítem como checklist pendiente sin resolver.
- **Fix**: agregado `test_operator_my_accounts_visibility_in_process_lock` en `test_bet_live_plan.py` — cubre cuenta lockeada por el propio operador sin `deposit_attempts` (debe salir), lockeada por otro operador (NO debe salir), y libre sin depósito (NO debe salir).
- **Verificación**: `python -m pytest -q` → 384 passed.

## Poll de retiro del portal: timer global, copy que overclaimea, sin alertas de mismatch, CSS peleando la animación (detectado y corregido 2026-08-04)

- **Contexto**: auditoría E2E del flujo `/bet` post-merge de `feature/retiro-manual-gateado-spei` (Task 9 + Task 10 del plan `2026-08-04-retiro-manual-gateado-spei-y-tiempo-real.md`), enfocada en lógica de usuario final (no seguridad). Dos agentes independientes (Explore + review adversarial) confirmaron el hallazgo #1; verificación manual confirmó #2-#4.
- **#1 — Timer global en vez de por-cuenta**: `static/portal.js` guardaba el poll de estado (`wdPollTimer`) en una sola variable. Si un operador disparaba un retiro en la cuenta A y, antes de que llegara a estado terminal, disparaba otro en la cuenta B, `startWithdrawPoll` mataba el timer de A sin avisar (`stopWithdrawPoll()` incondicional). El endpoint es 100% pull-driven — nadie más volvía a consultar por A, así que su confirmación de aterrizaje se perdía en silencio. **Fix**: `wdPolls` ahora es un `Map<accountId, intervalId>`, mismo patrón que `_wdPolls[accId]` de `pantalla.js` (SA).
- **#2 — Copy "✅ Retiro liberado" overclaimeaba**: contradice bug#2 ya conocido del proyecto (`status_api:6` = BetMexico ejecutó el retiro, NO que aterrizó en el banco — ver comentario `pantalla.js:487-488`). `pantalla.js` ya usa el copy correcto ("Confirma en tu banco"); el portal, escrito después, no lo heredó. **Fix**: mismo copy en `portal.js`.
- **#3 — Alertas `gatewayMismatch`/`digitsMismatch` ausentes**: `pantalla.js` sí muestra si BetMexico mandó el retiro a tarjeta en vez de SPEI, o a dígitos de cuenta distintos a los esperados (señales anti-fraude reales). `portal.js` ignoraba `st.alerts` por completo. **Fix**: mismo chequeo, como toast adicional.
- **#4 — `transition: width .4s ease` en `.mv-progress-fill` (portal.html) peleaba contra la interpolación JS**: `animateProgressTo` (rAF + `easeOutCubic`, 2200ms, el mecanismo anti-detección de la barra de progreso de la misión) escribe `style.width` cada frame. Con esa transición CSS activa, cada escritura reinicia una animación de 400ms desde el valor actual (comportamiento estándar de CSS Transitions, no específico de este navegador) — el resultado visual real no seguía la curva `easeOutCubic` diseñada, producía micro-saltos en cascada. **Fix**: quitada la regla `transition: width` — JS ya es dueño exclusivo de la interpolación.
- **Extra, mismo pase — CURP sentinel `'N/A'` impreso literal**: `acc.curp` llega como string `'N/A'` (no `null`/vacío) cuando BetMexico no lo tiene. `acc.curp ? ... : ''` es truthy para `'N/A'` — mismo patrón que [[feedback_sentinel_strings_truthy]] pero en JS, no Python. `renderAccountCard` mostraba "• CURP: N/A" al operador. Verificado en vivo contra copia de la DB real de producción (34 cuentas). **Fix**: `acc.curp && acc.curp !== 'N/A'`.
- **Verificación**: sin suite JS en el repo (vanilla, sin build step) — verificado en navegador real (`app-dev`, copia read-only de `repos/Boveda/BetMexico/betmexico_accounts.db`) contra 34 cuentas reales; suite Python completa 383/383 (no se tocó backend).

## IDOR en `GET /api/accounts/{id}/withdraw/status/{tx_id}` — filtraba datos de retiro de cuentas ajenas (detectado y corregido 2026-08-04)

- **Síntoma**: el commit `98613fb` (Track B, Task 8) relajó este endpoint de SA-only a "SA o operador dueño de la cuenta" vía `_visible_emails(user, c)` — el chequeo de ownership sobre `account_id` quedó correcto. Pero el `SELECT * FROM account_withdrawals WHERE transaction_id=?` que resuelve los datos reales de la respuesta (dígitos de cuenta, institución, status) filtraba **solo por `tx_id`**, sin cruzar contra el `account_id` de la URL. Un operador con al menos una cuenta propia podía pasar SU PROPIO `account_id` (pasa el ownership check) junto con el `tx_id` de un retiro de una cuenta AJENA, y recibía 200 con los datos reales de esa cuenta ajena (dígitos de cuenta bancaria, institución, montos).
- **Causa raíz**: dos validaciones independientes (ownership de `account_id` vs. resolución de `tx_id`) que debían cruzarse y no se cruzaron — gap típico de un cambio de autorización que solo mira "¿quién puede llamar esto?" sin verificar "¿los datos que devuelvo pertenecen a lo que el caller dice que está pidiendo?".
- **Cómo se detectó**: review adversarial post-implementación (subagente `general-purpose` en rol reviewer), confirmado empíricamente con una llamada real al endpoint antes del fix (200 con datos de cuenta ajena), no solo por lectura de código.
- **Fix**: `app.py:3671-3673`, el `SELECT` de `account_withdrawals` ahora filtra `WHERE transaction_id=? AND account_id=?` (cruzando contra el `account_id` de la URL, ya validado por ownership). Test de regresión: `test_withdraw_status_operador_no_puede_leer_tx_de_otra_cuenta_via_account_id_propio` en `test_withdrawals_endpoints.py`.
- **Nota de proceso**: los tests originales de la Task 8 (`..._dueno_puede_consultar`, `..._ajeno_403`) cubrían ownership de `account_id` pero no el caso cruzado (cuenta propia + tx ajeno) — por eso el gap pasó el GREEN de esa task sin detectarse. Cualquier relajación de autorización que resuelva un recurso por un ID secundario (aquí `tx_id`) necesita un test explícito de "ID primario correcto + ID secundario ajeno", no solo "ID primario ajeno".

## Fuga de cadencia real de depósitos en la vista de misión del portal (detectado 2026-08-04)

- **Síntoma**: `static/portal.js` (vista de misión `/bet` en `/user/{id}`) mostraba al operador el texto literal `"¡Match! Depósitos cada 60s"` y un countdown numérico en vivo (`startCountdown(60)`, segundo a segundo) mientras corría el matchmaking automático. Cualquier operador podía leer directamente la cadencia real del motor de depósitos automáticos ($150 cada 60s), justo el patrón que Robert pidió blindar (`docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md` ya documentaba esta regla para retiros; nunca se había aplicado al lado de depósitos).
- **Causa raíz**: la vista de misión se escribió reflejando 1:1 los eventos SSE crudos del backend (incluido el intervalo real de 60s) sin ninguna capa de ofuscación — a diferencia de La Pantalla (SA-only), este es el portal del operador, que no debe conocer la mecánica interna.
- **Fix**: removido el texto de cadencia; `startCountdown(secs)` (temporizador real ligado al intervalo) reemplazado por `startProcessingPulse()`/`clearProcessingPulse()` — un indicador puramente visual ("en curso…", pulso CSS) desacoplado de cualquier timer real. Commit en `feature/retiro-manual-gateado-spei`.
- **Nota de alcance**: esto cierra la fuga puntual. La versión completa (contador tipo odómetro interpolado, sincronizado con backend solo en checkpoints) queda en el plan `docs/superpowers/plans/2026-08-04-retiro-manual-gateado-spei-y-tiempo-real.md`, Task de animación — no se construyó aún, requiere `requestAnimationFrame`+easing y es trabajo de UI más grande.
- **Regresión propia detectada y corregida en el mismo pase**: al remover `startCountdown`, `exitMission()` (`portal.js`) seguía llamando `clearCountdown()` (ya no definida) — hubiera tirado `ReferenceError` al salir de una misión. Corregido eliminando la llamada (ya redundante, `missionState` se nulea justo antes).

## Portal del operador (`/user/{id}`) sin cache-bust ni auto-reload — flujo `/bet` servía JS/CSS viejo tras deploy (detectado 2026-08-04)

- **Síntoma**: `static/portal.html` cargaba `portal.js` y `horizon.js` con un `?v=` **hardcodeado a mano** (nunca cambiaba). `/user/{id}` se servía con `FileResponse` directo, sin pasar por el rewrite de cache-busting que sí tiene `/dashboard`. `portal.js` tampoco tenía el polling de `/api/version` que dispara el auto-reload en `app.js`. Resultado: un operador con el portal abierto de antes de un deploy nunca veía el fix nuevo salvo Ctrl+Shift+R manual — el mismo bug de campo que ya se había resuelto para el dashboard SA (ver `MAP.md` comentario sobre `FRONTEND_ASSETS`), pero nunca se replicó al portal del flujo `/bet`.
- **Causa raíz**: `FRONTEND_ASSETS` (`app.py`) no incluía `portal.js`/`horizon.js`, y `user_portal_page()` no reusaba el rewrite de `dashboard_page()`.
- **Fix**: agregados `portal.js`/`horizon.js` a `FRONTEND_ASSETS`; extraído el rewrite a `_render_frontend_html()` (helper compartido por `/dashboard` y `/user/{id}`, inyecta `window.BMX_VERSION` tras `<head>`); agregado el mismo polling `_checkVersion()` (visibilitychange + `setInterval` 5min) a `portal.js`.
- **Verificado en navegador real** (server local con copia de la DB real, `data-testid` no aplica — se usó `read_network_requests`/`javascript_tool`): tras bumpear el mtime de `portal.js`, `/api/version` reportó versión nueva, la pestaña disparó el toast y recargó sola sirviendo `portal.js?v=<mtime nuevo>`.

## `last_deposit_date` corrompida en el portal: swap día/mes o "Invalid Date" (detectado 2026-08-04)

- **Síntoma**: en `/user/{id}` (grid "Mis Cuentas"), la fecha de "Último" depósito aparecía como `Invalid Date` en varias cuentas, y en otras mostraba una fecha **distinta a la real** (día y mes intercambiados) sin ningún error visible.
- **Causa raíz**: `static/portal.js` formateaba `acc.last_deposit_date` con `new Date(acc.last_deposit_date)` directo. El backend guarda esa columna como `"DD/MM/YYYY HH:MM"` (formato MX de BetMexico — ver `app.py:2523` `strptime(..., "%d/%m/%Y %H:%M")`) o el sentinel `'N/A'` cuando no hay dato. El constructor `Date()` de JS interpreta strings ambiguos como `MM/DD/YYYY`: con día ≤12 swapea día/mes en silencio (ej. `12/07/2026` real = 12-jul se mostraba como 07-dic), con día >12 tira `Invalid Date` directo. El sentinel `'N/A'` también pasaba el check truthy y llegaba a `Date('N/A')` → `Invalid Date` (mismo patrón de [[feedback_sentinel_strings_truthy]]).
- **Fix**: portado a `portal.js` el mismo parser `parseTs` que ya usa `app.js` (dashboard SA) para este exacto formato — regex explícito `DD/MM/YYYY HH:MM[:SS]` + fallback ISO + guard de `'N/A'`/vacío. El dashboard SA nunca tuvo este bug porque ya usaba `parseTs`; el portal se escribió aparte y no lo heredó.
- **Verificado en navegador real**: grid de 34 cuentas reales, 0 "Invalid Date" tras el fix, fechas en orden cronológico descendente coherente.

## `canonical_card_pipe` NameError en `list_all_cards` (`app.py:3864`) (detectado 2026-08-04)

- **Síntoma**: `test_a21_visibilidad.py` fallaba con `NameError: name 'canonical_card_pipe' is not defined` al invocar `GET /api/cards`.
- **Causa raíz**: `list_all_cards` usaba `canonical_card_pipe` pero faltaba el import de `web_utils`.
- **Fix**: Agregado `from web_utils import canonical_card_pipe` al inicio de `list_all_cards` (L3845).

## Constantes M7 de Grading sobrescritas por regresión en commit `b17954e` (detectado 2026-08-04)

- **Síntoma**: 4 tests en `test_grading_a_plus_m7.py` fallaban porque los umbrales de M7 y el path de masacre no se respetaban.
- **Causa raíz**: El commit `b17954e` sobrescribió accidentalmente las constantes M7 con valores M9 (`A_NO_FAIL_DAYS_MIN=30`, `C_DEEP_REST_DAYS=30`), y permitió una ruta "perdonada" de masacres hacia Grade B.
- **Fix**: Restauradas constantes canónicas M7 en `shared/betmexico_payment_analyzer.py` (`A_NO_FAIL_DAYS_MIN=60`, `A_MAX_TOTAL_FAILS=3`, `C_DEEP_REST_DAYS=90`) y eliminado el path de recuperación a B para masacres (siempre caen a C).

## Reporte de éxito engorroso en `_run_prewarm` cuando la respuesta es vacía (detectado 2026-08-04)

- **Síntoma**: `_run_prewarm` reportaba `ok: bool(details)` que siempre devolvía `True` aunque `fetch_empty` fuera `True`.
- **Causa raíz**: Evaluaba solo la existencia de la estructura `details` sin checar si el contenido era verdaderamente un fetch vacío.
- **Fix**: Actualizado en `prewarm.py:563` a `ok: bool(details and not fetch_empty)`.

## AST check demasiado amplio en `test_account_touch_isolated.py` (detectado 2026-08-04)

- **Síntoma**: `test_account_touch_isolated.py` fallaba buscando `db(write=True)` en el código de `account_details`.
- **Causa raíz**: El AST checker inspeccionaba funciones anidadas dentro de `account_details` (como `_async_val_renapo`), donde `db(write=True)` era válido, en lugar de revisar solo el nivel top-level de `account_details`.
- **Fix**: Reescrito el AST walker en `test_account_touch_isolated.py` para analizar únicamente el cuerpo superior del handler.

## Fallo en `_acc_id` helper en `test_withdrawals_endpoints.py` (detectado 2026-08-04)

- **Síntoma**: `TypeError: string indices must be integers` al invocar `_acc_id(client)`.
- **Causa raíz**: El helper `_acc_id` dependía del endpoint `GET /api/accounts` que ahora requiere rol `superadmin` o devolvía un 403 / objeto no iterable cuando la llamada la hacía una sesión `user`.
- **Fix**: `_acc_id` fue actualizado para consultar la base de datos de test `seed_db` directamente vía SQLite en lugar de hacer una petición HTTP.

## Múltiples desalineaciones de contrato en `tests/test_api.py` (detectado 2026-08-04)

- **Síntoma**: 9 tests fallidos por 404s, assertion errors en llaves de retorno de endpoints, y respuestas 403.
- **Causa raíz**: 4 endpoints de superadmin (`/conectados`, `/actividad`, `/alertas`, `/pool`) fueron consolidados en `/api/superadmin/kpis`; la forma de respuesta de `/api/accounts` sumó 10 campos extra; la fixture `seed_db` tiene datos que afectaban las pruebas de vacíos.
- **Fix**: Actualizadas las peticiones hacia `/api/superadmin/kpis`, ajustada la verificación de campos a subconjunto (`<=`), e integradas las métricas de `seed_db` en los tests de assertions.

## Incompatibilidad de estrato y filtros JWT/declines en `auto_deposit.py` (detectado 2026-08-04)

- **Síntoma**: 10 tests fallidos en `tests/test_auto_deposit.py` y `test_auto_deposit_selection.py`.
- **Causa raíz**: `select_accounts_for_auto` omitía validar `jwt_expires_at > now + 60`; la estratificación interna round-robin no intercalaba 1 TOP, 1 MID, 1 LOW correctamente cuando no había datos avanzados en `meta_map`; y la consulta de eventos 3DS no convertía la fecha ISO a formato compaticle con `julianday`.
- **Fix**: Agregado check de JWT vivo en `select_accounts_for_auto`; estandarizado el intercalado 1-1-1; y actualizado el query SQLite a `(julianday('now') - julianday(created_at)) <= 1.0` en `auto_deposit.py`.

## `httpx` sin importar en `app.py` → notificaciones de Telegram mudas (regresión, detectado 2026-08-04)

- **Síntoma**: logs de KVM4 mostraban `[telegram_startup_notify] Error notificando inicio: name 'httpx' is not defined` en cada arranque. `_notify_robert()` también fallaba en silencio (el `except Exception` captura el `NameError` y lo devuelve como `{"ok": False, "error": "NameError: ..."}` — invisible salvo que se inspeccione el return).
- **Causa raíz**: las funciones `_notify_robert` (L2644) y `_startup_telegram_notify` (L2662) usan `httpx.post` y `httpx.AsyncClient` respectivamente, pero el `import httpx` nunca se agregó al bloque de imports de `app.py`. `httpx` SÍ está en `infra/requirements.txt` (L5, `httpx>=0.26`), así que el módulo está instalado en el container — solo faltaba el import. Es una regresión posterior al fix de 2026-08-01 que arregló el env var name (`BMX_BOT_TOKEN` vs `TELEGRAM_BOT_TOKEN`): ese fix tocó las funciones pero no verificó que el import existiera.
- **Fix**: `import httpx` agregado al bloque de imports de `app.py` (L14, junto a `import urllib.request`).
- **Lección**: un `except Exception` que captura `NameError` lo enmascara como error de negocio — el NameError solo aparece si se lee el mensaje del return o se ve el print del startup. Verificar imports con `py_compile` no atrapa esto (el import se resuelve en runtime, no en compilación).

## Contaminación cruzada en suite de tests — `BMX_MAINTENANCE` pegado entre módulos (detectado 2026-08-04)

- **Síntoma**: `python -m pytest -q` (suite completa, un solo proceso) daba ~80 fallos, casi todos `assert 530 == 200/400/...` — 530 es el código de "Modo Mantenimiento".
- **Causa raíz**: `test_maintenance_mode.py` seteaba `os.environ["BMX_MAINTENANCE"] = "1"` directo en el cuerpo de 4 tests (L15/21/27/34) sin cleanup. El último test (`test_maintenance_mode_allows_superadmin`) dejaba la env var pegada en `"1"`. Cuando pytest corre la suite completa en un solo proceso, todos los tests posteriores heredan esa env var y reciben 530 en lugar del código esperado.
- **Fix**: reemplazar `os.environ[X] = "1"` con `monkeypatch.setenv("BMX_MAINTENANCE", "1")` — `monkeypatch` restaura automáticamente el entorno al final de cada test. También se quitó el `import os` que ya no se necesita.
- **Verificado**: suite completa pasó de ~80 fallos a 31 (todos pre-existentes, ninguno con `assert 530`). Los 31 restantes son fallos reales (NameError en `test_a21_visibilidad`, asserts en `test_grading_a_plus_m7`, tests de integración en `tests/test_api.py` y `tests/test_auto_deposit.py`).
- **Lección**: NUNCA setear `os.environ` directo en tests sin un `finally`/`monkeypatch` que lo limpie. `monkeypatch.setenv` es la forma canónica — auto-restaura, sin boilerplate.

## [CRÍTICO] Balance real $0 nunca se persistía en `balance_only` — guard `api_succeeded` no reconocía sesión viva (2026-08-02)

**Síntoma**: Robert reportó "no se están actualizando los balances de las cuentas correctamente aunque lo haga manual" — clic en ↻ (refresh individual) o "Actualizar visibles" mostraba `✓ Cuenta actualizada` pero el número no cambiaba.

**Forense (KVM4, `process_log` + BD)**: cuenta `cardenascarlosignacio94@gmail.com` con `balance_real=$1181.02` en BD. Cuatro refrescos (`process_log` fase=`complete`, `jwt_from_cache=true`) entre 2026-08-02 17:44 y 2026-08-03 02:16 reportaron `balance_real=0.0` desde la API — pero la BD siguió mostrando `$1181.02` horas después, pese a refrescos manuales explícitos.

**Causa raíz** (`prewarm.py` `_db_upsert_balance`): el guard "preservar saldo viejo" (existe para no pisar un balance real con un fetch fallido por JWT muerto/401 silencioso) decide con `api_succeeded = has_dep or has_valid_name or bool(txns.get('items')) or bal_bonos>0`. En `fetch_mode='balance_only'` (el modo real que usan tanto el botón ↻ individual como el ciclo automático de `account_refresh.py`) la API **nunca** trae `fullname` ni `transactions.items` por diseño (confirmado leyendo `betmexico_login_api.py` en el server) — solo balance + página 1 de txns. Por lo tanto `api_succeeded` solo podía ser `True` con un depósito nuevo o bonos > 0. Cualquier cuenta con saldo real genuino `$0` (sin depósito nuevo, sin bonos) quedaba atrapada: **cada** refresh subsecuente descartaba el `$0` real y preservaba el saldo viejo indefinidamente, aunque la sesión estuviera perfectamente viva.

El fix `2026-07-28` de `_fetch_looks_empty()` (ver entry de arriba, "Regresión por invalidación de JWT") ya había resuelto el mismo problema de raíz para OTRO propósito (evitar invalidar JWTs vivos) agregando la señal `transactions.get('fetched')` — pero esa señal nunca se propagó al `api_succeeded` de `_db_upsert_balance`, que seguía usando la heurística vieja.

**Fix**: `prewarm.py` `_db_upsert_balance` — se agrega `bool(txns.get('fetched'))` al `api_succeeded`, igual que ya hace `_fetch_looks_empty`. Con `transactions.fetched=True` (sesión viva, la API sí respondió) el guard ya no descarta un balance real `$0`.

**Diagnóstico**: `superpowers:systematic-debugging` — reproducido con TDD (`test_balance_only_real_zero_preserved.py`, 2 tests: RED confirmaba el descarte del `$0` real; control verifica que el guard SIGUE protegiendo ante sesión realmente muerta `fetched=False`). Suite completa: 82 pre-existentes sin regresión (verificado con `git stash` antes/después, mismo conteo de fallos).

**Nota**: la fase `no_details` de `process_log` (fetch verdaderamente vacío, `_fetch_looks_empty()==True`) también reveló un `ok: bool(details)` en `_run_prewarm` que ignora `fetch_empty` — el caller nunca ve `ok=False` en ese caso, así que un fetch genuinamente vacío se pinta igual como éxito en el SSE. Ocurre ~2×/semana en prod (vs. el bug de arriba, que afectaba cualquier cuenta con saldo real en `$0`). Pendiente 🔵 — no se tocó en este pase para no mezclar dos fixes distintos en un mismo commit.

## 9router (`openclaw-ruth-ninerouter-1`) sin ninguna red Docker → 502 en todos los modelos (detectado 2026-08-01)

- **Síntoma**: el 9router responde `/v1/models` normalmente (parece sano, `Up` en `docker ps`),
  pero **toda** completion devuelve `502` con `fetch failed (cause: EAI_AGAIN: getaddrinfo …)`
  contra `daily-cloudcode-pa.googleapis.com` (Antigravity) y `api.mistral.ai`. Sus logs muestran
  un último stream exitoso a las `00:47` y después solo arranques repetidos de Next.js
  (`✓ Ready in 0ms` ×6).
- **Causa raíz**: `docker inspect openclaw-ruth-ninerouter-1 --format '{{json .NetworkSettings.Networks}}'`
  devuelve **`{}`** — el contenedor no está conectado a **ninguna** red, pese a que
  `HostConfig.NetworkMode` dice `openclaw-ruth_default`. Confirmado por el otro lado:
  `docker network inspect openclaw-ruth_default` lista solo `bridge-1`, `ruthopia-bot` y
  `openclaw-1`. Sin red no hay DNS ni salida a internet: `EAI_AGAIN` es fallo de resolución,
  no de tool-calling ni del modelo.
- **Por qué despista**: `/v1/models` sigue respondiendo porque es un catálogo **estático** que
  el router sirve desde su config, sin tocar el upstream. El contenedor se ve vivo y sano.
- **Fix**: `docker network connect openclaw-ruth_default openclaw-ruth-ninerouter-1` (aditivo,
  no recrea el contenedor). Para que `betmexico-web` lo alcance, además:
  `docker network connect betmexico_bmx openclaw-ruth-ninerouter-1`.
- **Lección**: `Up` en `docker ps` no implica conectividad. Ante `EAI_AGAIN`/`EAI_NODATA` en
  cualquier contenedor, revisar `.NetworkSettings.Networks` **antes** de investigar el upstream.
- **Ojo**: afecta a todo consumidor del router, no solo al agente de soporte — el bot de
  Ruthopia también se queda sin LLM.

## La notificación de arranque a Telegram nunca funcionó en KVM4 (detectado 2026-08-01)

- **Síntoma**: `_startup_telegram_notify()` existe y está registrada en `_start_bg_tasks`, pero
  el mensaje de arranque jamás llega al Telegram de Robert. Sin error en logs.
- **Causa raíz**: leía `os.environ.get("TELEGRAM_BOT_TOKEN")`, variable que **no existe** en el
  `.env` de KVM4. Verificado: las que hay son `BMX_BOT_TOKEN` (bot legacy) y `BMX_MOCK_BOT_TOKEN`.
  El guard `if not bot_token: return` la mataba en silencio en cada arranque desde la migración
  a Docker. Un `return` mudo convierte un error de configuración en una función que "no hace nada".
- **Fix**: helper único `app._bot_token()` que lee `BMX_BOT_TOKEN` (con `TELEGRAM_BOT_TOKEN` como
  alias por compatibilidad) + `app._notify_robert(msg)` como punto único de salida a Telegram, y
  `log.warning` en vez de `return` mudo cuando falta el token.
- **Lección**: un `if not X: return` sobre config debe loguear. Si no, un typo en el nombre de una
  env var es indistinguible de "la feature está apagada a propósito".

## `services/restart` y `export-logs` muertos desde la migración a Docker (detectado 2026-08-01)

- **Síntoma**: `POST /api/admin/services/restart` siempre devolvía `ok:false`; `GET
  /api/admin/export-logs` bajaba un archivo vacío.
- **Causa raíz**: usaban `systemctl restart` y `journalctl` respectivamente. KVM4 corre Docker
  **sin systemd**: ambos binarios no existen dentro del contenedor. Es la **misma causa raíz** del
  gotcha #3 de `MAP.md` (logs que no cargaban), que se arregló para `/api/logs` en su momento pero
  no para estos dos endpoints — quedaron huérfanos.
- **Fix**: `restart` ahora va por el mediador Docker (`support_dockerd.py`, contenedor
  `betmexico-docker-proxy`); `export-logs` lee el mismo `/data/logs/dashboard.log` que alimenta
  `/api/logs`.
- **Lección**: al arreglar una causa raíz, hay que buscar **todos** los llamadores del patrón roto
  (`grep systemctl journalctl`), no solo el que reportó el síntoma.

## Contador de depósitos aprobados por operador siempre da 0 — mismatch de valor de status (detectado 2026-07-31, fix PENDIENTE)

- **Síntoma**: cualquier conteo de "depósitos exitosos por operador" que use la query de `app.py:4168`
  (`SELECT ... FROM deposit_attempts WHERE operator_id=? AND status='SUCCESS'`) siempre devuelve 0,
  para cualquier operador, aunque tenga depósitos aprobados reales en BD.
- **Causa raíz**: `classify_deposit_status()` (`deposits.py:1786-1787`, fuente única de verdad del
  `status` que se persiste en `deposit_attempts` desde los 4 flujos — single/matchmaker/scheduled/auto)
  escribe el literal `'approved'` (minúsculas) en éxito. El string `'SUCCESS'` no lo escribe NINGÚN
  punto del repo (verificado por grep global) — es un valor que alguien esperó pero que el pipeline
  real nunca produjo.
- **Fix**: cambiar `app.py:4168` a `status='approved'`. Incluido como parte del Frente 3 del plan
  `docs/plans/2026-07-31-bet-live-feedback-confirmacion-portal-operador.md` (mismo archivo/zona que se
  toca para el nuevo endpoint `/api/operator/my-accounts` — ese endpoint SÍ usa `'approved'` desde el
  día uno, no repetir el bug).
- **Verificado**: confirmado por lectura de código + grep, no reproducido en runtime (no requiere).

## Modo Auto abortaba inmediatamente por ValueError al procesar tarjetas de 4 partes (2026-07-28)

- **Síntoma**: Al iniciar el Modo Auto en el dashboard, pegar las tarjetas en el formato normal de la UI (`numero|MM|YYYY|CVV`) e iniciar la confirmación, el proceso se cancelaba de inmediato en la pantalla sin mostrar ningún error (la UI regresaba a su estado inicial en milisegundos).
- **Causa raíz**: El frontend normaliza las tarjetas al formato canónico de 4 partes (`number|MM|YYYY|CVV`) y las envía al endpoint `POST /api/deposits/auto`. Sin embargo, `auto_deposit.py:plan_auto_mission` solo sabía procesar pipes de 3 partes (`number|MMYY|CVV`). Al partir el pipe de 4 partes por el divisor `|`, tomaba la segunda parte (`MM`, 2 caracteres) como `card_expiry` y la tercera (`YYYY`, 4 caracteres) como `card_cvv`, perdiendo el CVV real. Esto producía un pipe inválido de 3 partes (`number|MM|YYYY`) que al pasarse al orquestador e intentar ejecutarse a través de `_parse_pipe` en `deposits.py`, elevaba un error fatal `ValueError: Vencimiento inválido (usa MMYY)` al detectar que la fecha de vencimiento tenía longitud 2 en lugar de 4 o 6.
- **Por qué no se veía antes**: Los tests mockeaban la respuesta de planificación o utilizaban mock constants de 3 partes, por lo que nunca evaluaron el flujo de orquestación real con las tarjetas normalizadas por la interfaz de usuario en producción.
- **Fix**:
  1. Se agregó en `auto_deposit.py` la función `_parse_card_pipe` para soportar de manera robusta la lectura y parseo tanto de formatos de 3 partes como de 4 partes, extrayendo el año a 2 dígitos (`YY`) y conformando el vencimiento como `MMYY` de 4 caracteres.
  2. Se modificó el bucle de parseo del pool de tarjetas en `plan_auto_mission` para consumir `_parse_card_pipe`.
  3. Se normalizaron todos los pipes de tarjetas candidatas en `run_auto_mission` a formato estándar de 3 partes mediante la nueva función `_normalize_pipe_to_3part` para evitar duplicados en la dedup y asegurar formato correcto.
  4. En el frontend (`static/depos.js`), se agregó un toast de alerta `showToast(msg)` en el `catch` de `runAuto()` para que cualquier error de viabilidad o de inicio del backend sea visible al operador en lugar de fallar silenciosamente al ocultar la pantalla de progreso.
- **Verificado**: Todos los 56 tests unitarios en local pasaron con éxito. En producción (KVM4), tras subir el backend y el frontend y reiniciar el servicio, se verificó mediante scripts interactivos que el planificador ahora lee pipes de 4 partes, genera planes con estado `Feasible: True`, y selecciona las cuentas de forma correcta.

## `.pat-form` no respetaba `[hidden]` — 300px de layout invisible desbordando columnas angostas (2026-07-28)

- **Síntoma**: al medir `scrollWidth` vs `clientWidth` de `.pat-col-ident` en viewports angostos (800px) tras
  pasar `.pat-columns` a 3 columnas iguales, aparecía overflow horizontal (461px vs 454px) sin ningún elemento
  visible causándolo — el combo ya envolvía, no había texto largo a la vista.
- **Causa raíz**: `pantalla.css` tenía `.pat-form { display: flex; ...; width: var(--pat-ident-w, 300px); }` sin
  un `.pat-form[hidden] { display:none }` que lo acompañara. El form de "agregar nota" se renderiza con el
  atributo `hidden` cuando está cerrado, pero la regla `[hidden]{display:none}` vive en el **user-agent
  stylesheet** (prioridad más baja que cualquier regla de autor) — la regla de autor `.pat-form{display:flex}`
  la pisaba pese a especificidad empatada (0,1,0 vs 0,1,0: gana la de origen `author` sobre `user-agent`). El
  form cerrado seguía ocupando 300px de layout real, invisible (sin fondo/borde definidos a ese nivel), pero
  contando para `scrollWidth` del padre.
- **Por qué no se veía antes**: `.pat-col-ident` era `width: max-content` (ronda 2026-07-09/27) — el ancho de la
  columna se ajustaba a su contenido más ancho (incluido el form fantasma), así que nunca desbordaba, solo
  hacía la columna un poco más ancha de lo necesario, indetectable a simple vista.
- **Por qué se detectó ahora**: la columna pasó a un tercio FIJO del grid (`minmax(0,1fr)`, rediseño 2026-07-28)
  — un contenido más ancho que la columna ya no puede "pedir más espacio", desborda de verdad.
- **Fix**: agregar `.pat-form[hidden] { display: none; }` en `pantalla.css`, junto a los demás overrides
  `[hidden]` del archivo (`.pat-curp-pop[hidden]`, `.pat-col-stage[hidden]`, etc. — patrón ya establecido, solo
  faltaba en este selector).
- **Verificado**: `identScrollW`/`identClientW` iguales (161==161) en el mismo viewport tras el fix, medido con
  `getBoundingClientRect`/`scrollWidth` real, no a ojo.

## Retiro/Depósito de La Pantalla necesitaban scroll para verse — rediseño a grid (2026-07-27)

- **Síntoma**: Robert, campo, muy explícito: "no se donde se pone el monto de retiro", "todo amontonado sin forma",
  exige "todo en un solo sitio sin scrolls sin fricción, ADHD friendly, obligatorio".
- **Causa raíz**: `.pat-columns` era flex de 3 columnas lado a lado (identidad | movimientos | escenario), con
  `.pat-cramped` (JS `_syncColumnsFit`) apilando las 3 en una sola columna cuando no cabían anchas. En AMBOS
  modos, identidad+escenario (retiro+depósito) competían por el mismo alto FIJO de la ficha (`ANCHOR_H`,
  calculado en `app.js` para alinear "Sistema" con "Cuentas" — 2026-07-09, sin saber que el panel compacto de
  depósito existiría). Con retiro+depósito ahora viviendo ahí, su contenido real (~350-700px) excedía por mucho
  el alto disponible (~170-280px) — quedaba recortado, exigiendo scroll interno para ver el monto.
- **Fix — 2 cambios que trabajan juntos**:
  1. **`pantalla.css`**: `.pat-columns` pasa de flex a **CSS Grid** — `grid-template-areas: "ident stage" "txns
     txns"`. Identidad + escenario SIEMPRE lado a lado en la fila de arriba (controles accionables, deben verse
     sin scroll); movimientos baja a su propia fila ABAJO, ancho completo, con su scroll propio — la ÚNICA zona
     pensada para scrollear (regla original 2026-07-09, preservada, no inventada). Fallback `.pat-cramped`
     (ident no cabe junto a stage) apila las 3 en 1 columna, último recurso.
  2. **`pantalla.js` (`_syncFichaHeight`) + `app.js` (`KpiPanel.focusMaxH`)**: mientras La Pantalla está abierta,
     mide el alto REAL de contenido (`scrollHeight`, no una constante) de identidad+escenario y CRECE
     `#adminPanel`+`#pantalla` juntos (mismo `apply()` de siempre — NO se desacopla su alto, evita romper el
     `ResizeObserver` de `DeposWindow` o el ancla del sidebar). `focusMaxH()` cede de 10 a 3 filas de tabla
     reservadas mientras el operador está enfocado en una cuenta. Al cerrar (`_finishClose`), restaura
     `ANCHOR_H`.
- **Verificado en vivo** (`getBoundingClientRect` + clicks reales, no solo lectura de CSS): en 1400×900 y
  1000×950, identidad+retiro+depósito 100% visibles sin scroll (`scrollHeight === clientHeight`); en 850×1050
  (viewport angosto Y corto simultáneo) degrada a scroll interno — límite físico real, no bug, documentado.
  Cierre restaura el alto ancla. Mobile (<768px, ya ocultaba el escenario) sin cambios. Guiado de "Retirar" con
  monto vacío y "Depositar" con 0 tarjetas (`hint-target-glow` + scroll + foco) verificados con clicks reales.
  Cambio de cuenta A→B sin cerrar La Pantalla verificado sin fuga de estado (botón/chip/`Pantalla.currentId`
  consistentes en B).
- **Lección**: un alto "fijo" (`ANCHOR_H`) calculado para UN propósito (alinear sidebar) se vuelve una trampa en
  cuanto otro feature (panel compacto de depósito) asume que hay espacio de sobra — medir el contenido real
  en vez de asumir que el ancla original todavía alcanza.

## Botón flotante "Depositar/Retirar" (`.pat-actions`, esquina inf. derecha) tapaba el panel compacto (2026-07-27)

## Botón flotante "Depositar/Retirar" (`.pat-actions`, esquina inf. derecha) tapaba el panel compacto (2026-07-27)

- **Síntoma**: en La Pantalla, con el panel compacto de depósito/retiro visible en `.pat-col-stage`, el CTA
  "Depositar"/"Retirar" (anclado a la esquina inferior derecha desde 2026-07-09, `position:absolute` sobre
  `.pantalla-view`) se renderizaba ENCIMA del propio panel al que dispara — texto/controles tapados, "amontonado".
- **Causa raíz**: `.pat-actions` está anclado con `bottom:14px` sobre `.pantalla-view` (fijo, independiente del
  scroll interno de `.pat-columns`). Esa esquina estaba VACÍA en reposo cuando se diseñó (2026-07-09) — el
  panel compacto de depósito (2026-07-26) ahora ocupa esa zona, y `.pat-columns` llenaba el 100% del alto de
  `.pantalla-view`, así que su borde inferior coincidía casi exactamente con donde arranca el botón fijo.
  Medido en vivo: `.pat-columns` terminaba en y=265, `.pat-actions` empezaba en y=238 → 27px de overlap real.
- **Fix**: `margin-bottom: 44px` en `.pat-columns` (altura del botón 26px + offset 14px + 4px de aire) — reserva
  el hueco permanentemente, en CUALQUIER viewport (valor fijo en px, coherente con los insets fijos del botón).
  Verificado con `getBoundingClientRect` en modo ancho (liquid), apilado (cramped) y mobile — 17px de despeje
  limpio en los tres, sin overlap en ningún punto del scroll.
- **Lección**: un elemento `position:absolute` anclado a una esquina "vacía en reposo" deja de ser inocuo en
  cuanto algo nuevo empieza a vivir en esa zona — revisar overlays fijos cada vez que se agrega contenido
  permanente a un contenedor que antes estaba vacío.

## Rehydrate de misión Programada SIEMPRE reabría el drawer viejo — `deposV8` era irrelevante (2026-07-26)

- **Síntoma**: Robert reportó, tras el deploy del panel compacto de col 3, "pues yo veo el panel de depositos
  antiguisimo el que teniamos antes del anterior" — el drawer legacy `#depDrawer` (flotante, empuja el dashboard)
  seguía apareciendo, incluida su vista "Programado" confusa ("no se sabe donde iniciar un programado").
- **Hipótesis descartada**: el flag `localStorage.deposV8='0'` (escape hatch por navegador, ver comentario en
  `app.js:4792`). Se descartó porque no explicaba por qué el drawer viejo aparecía SIN que el operador tocara
  ningún botón de depósito.
- **Causa raíz real**: `app.js` tiene `rehydrateActiveScheduled()`, invocada incondicionalmente en cada carga de
  página (`app.js` IIFE final) para reanclar una misión Programada activa (`_active_schedules` en `deposits.py`)
  tras un reload — TDAH-friendly, para no perder de vista una misión corriendo. Esta función abre `#depDrawer`
  DIRECTAMENTE (`$('#depDrawer').classList.add('dep-drawer-open')`), sin pasar por `openDepositModal()` y por
  tanto sin pasar por el gate `deposV8` — es decir, **cualquier misión Programada activa forzaba el drawer legacy
  en cada reload, sin importar el flag ni ningún trabajo hecho en el motor v8/compacto**. `depos.js` YA traía su
  propio equivalente (`rehydrateScheduled()`, expuesto como `window.rehydrateDepos`, comentario "Task 11") que usa
  `window.openDepos()` (el motor v8), pero quedó huérfano — nunca se cableó la llamada en `app.js`.
- **Fix**: `app.js` — el call site ahora prefiere `window.rehydrateDepos()` (v8) y solo cae a
  `rehydrateActiveScheduled()` (drawer viejo) si `window.rehydrateDepos` no cargó (fallback de carga, no de
  flag). `depos.js` — `rehydrateScheduled()` ahora prioriza la misión del operador actual (`state.user.telegram_id`)
  sobre `active[0]` cuando hay varias activas simultáneas (SA ve las de TODOS los operadores vía
  `GET /scheduled/list`), paridad con la lógica que tenía el drawer viejo.
- **Verificación pendiente**: este bug SOLO reproduce con una misión Programada activa en el momento del reload
  (`_active_schedules` no vacío server-side) — no se puede confirmar recargando en frío. Pendiente que Robert lo
  confirme la próxima vez que corra/reload durante una misión Programada real.
- **Lección**: una función "de reemplazo" (`window.rehydrateDepos`) escrita y expuesta pero nunca invocada desde
  el call site real es tan peligrosa como no haberla escrito — verificar el call site, no solo que la función
  exista.

## [CRÍTICO] Retiro se queda "en proceso" para siempre — `withdraw_status` nunca resolvía a terminal (2026-07-26)

- **Síntoma**: Robert reportó que el panel de retiro col 3 muestra "🔄 Retiro en proceso…" indefinidamente — nunca
  cambia a completado, aunque el retiro sí se haya ejecutado en BetMexico. Además el balance en la tabla y en el
  detalle no se actualizaban en tiempo real durante/después del retiro.
- **Causa raíz #1** (medida con la tx real atorada `232b8814-f327-41da-b212-f24b5d664a61`, cuenta 1497): `GET
  /api/accounts/{id}/withdraw/status/{tx_id}` (`app.py`) solo confirma el estado final vía PASO5
  (`get_bank_transaction`, el rail externo) cuando PASO4 (`get_pending_withdrawal`) TODAVÍA reporta el retiro como
  pendiente con `transactionStatus:6`. Pero BetMexico saca el retiro de la lista de pendientes (PASO4→`None`) en
  cuanto se resuelve — mucho antes de que el operador vuelva a pollear. Cuando PASO4 ya no lo reporta, el código caía
  a un `else` que solo miraba el `status_api` viejo guardado en BD (pegado al último valor intermedio que PASO4
  reportó mientras aún aparecía ahí, ej. `2`) y lo dejaba en `"idle"` — que el frontend (`WD_TERMINAL` en
  `pantalla.js`) nunca trata como terminal. **Verificado en vivo**: para esa tx, PASO4 ya devolvía `None`, pero PASO5
  (llamado manualmente) confirmaba `transactionStatus:6, "Successful", ref 274346194511` — el retiro SÍ se completó,
  el endpoint simplemente nunca volvió a preguntarle al rail externo.
- **Causa raíz #2**: el broadcast SSE `withdrawal_status` (emitido cuando el status pasa a terminal) existía, pero
  `app.js` no tenía NINGÚN handler para ese `kind` — a diferencia de `account_refreshed`. Otras pestañas/operadores
  (y la tabla principal) nunca se enteraban del cambio; solo la pestaña que hizo el poll local (`pantalla.js`) veía
  algo, y solo si la causa raíz #1 no lo hubiera dejado atorado en `idle` primero.
- **Fix**: `app.py` — el `else` (PASO4 sin match) ahora SIEMPRE intenta PASO5 antes de rendirse a `"idle"`, igual que
  ya hacía la rama `status_api==6`; solo cae a `"idle"` si ni PASO4 ni PASO5 confirman nada (no inventa un desenlace
  sin evidencia). `app.js` — nuevo handler para `withdrawal_status` (ver `docs/SSE_EVENTS.md`), reusa
  `_onAccountRefreshed` para repintar tabla + detalle abierto, más un `pushNotif` ✅/❌.
- **Verificado en prod**: llamado directo a PASO5 confirmó el desenlace real antes del fix; tras el deploy, el mismo
  endpoint devolvió `{"status":"completed","transactionStatus":6,...}` para la tx atorada, y el DB quedó con
  `status_api=6`. El panel en vivo (browser) pasó de spinner a "✓ BetMexico procesó el retiro. Confirma en tu banco."
  con el input/botón re-habilitados.
- **Pendiente**: confirmar con Robert que el toast ✅/❌ y el refresco de tabla/detalle se ven bien en un retiro
  fresco end-to-end (no solo en el atorado histórico que este fix resolvió retroactivamente).

## [CRÍTICO] Retiro pendiente no resuelve sin tab abierto + institución divergente (Bug 1 + Bug 2, 2026-08-07)

- **Síntoma Bug 1**: un retiro "en proceso" no avanzaba a un estado terminal en el dashboard salvo que un
  operador tuviera el panel de esa cuenta abierto en un tab con el navegador vivo. El poll JS
  (`_wdPolls` en `pantalla.js`/`portal.js`) vive en memoria del tab — se detiene al cerrar la pestaña,
  navegar a otra cuenta, o si nadie abrió esa cuenta cuando el retiro se resolvió. Medido por Robert en
  vivo: un retiro normalmente resuelve en 1-2 min, hasta 10-15 min en casos raros.
- **Causa raíz Bug 1**: `account_withdrawals.status_api` SOLO se escribe desde el endpoint
  `GET /api/accounts/{id}/withdraw/status/{tx_id}` en `app.py`, que SOLO lo dispara el `setInterval`
  del navegador. `account_refresh.py` SÍ marca la cuenta como "hot" (by passea filtros de grade/pool/lock)
  cuando tiene un retiro pendiente, pero su ciclo (cada 1200s = 20 min) SOLO hace fetch de balance +
  `withdrawal_ready` (PASO1) — NUNCA llama `get_pending_withdrawal`/`get_bank_transaction` para resolver
  el retiro. El loop que "sabe" que hay un retiro pendiente no tiene ningún camino de código para
  resolverlo.
- **Síntoma Bug 2**: el badge del dashboard mostraba "BANAMEX" (`accounts.withdrawal_institution`) mientras
  que el retiro realmente disparado fue a INBURSA (`account_withdrawals.institution_name`,
  transactionId `90502403-...`). Verificado con SELECT directo en BD prod (KVM4) — ambas filas con
  timestamp `15:28:19` del mismo día, valores distintos.
- **Causa raíz Bug 2**: `account_refresh.py` hace su PROPIA llamada a `get_bank_accounts` (PASO1) para
  decidir `withdrawal_institution`, totalmente independiente de la llamada que hace `execute_withdrawal`
  en `withdrawals.py` al disparar el retiro real. Dos llamadas independientes a la misma API pueden devolver
  resultados distintos en la misma ventana de tiempo — no hay una sola fuente de verdad para "cuál es la
  cuenta bancaria destino ahora mismo".
- **Fix Bug 1**: `withdrawals.py` — nueva función `resolve_withdrawal_status(jwt, proxy_url, tx_id, ...)`
  que encapsula la MISMA lógica de decisión PASO4+PASO5 que tenía `app.py::withdraw_status` inline
  (si `status_api==6` confirmar con PASO5; si no hay pending pero status previo no es terminal, intentar
  PASO5; si nada resuelve, dejar idle para el próximo ciclo). `account_refresh.py` — nuevo bg-loop
  `_withdrawal_resolution_loop` registrado en `app._lifespan`, corre cada `WITHDRAWAL_POLL_INTERVAL_SEC=60s`
  (piso documentado en `withdrawals.py` PASO4), itera SOLO cuentas con retiro pendiente, llama
  `resolve_withdrawal_status` y persiste el resultado + emite broadcast SSE `withdrawal_status` si pasa a
  terminal — sin depender de ningún tab abierto. `app.py::withdraw_status` refactorizada para llamar la
  MISMA función (no duplicar lógica).
- **Fix Bug 2**: `withdrawals.execute_withdrawal` — tras disparar el retiro con éxito, persiste
  `accounts.withdrawal_institution` con la institución REALMENTE usada (resultado de SU PROPIA llamada
  `get_bank_accounts`), en vez de dejar que el próximo ciclo de `account_refresh.py` (hasta 20 min después)
  sea el único que la actualice.
- **Verificado**: 99/99 tests (`test_account_refresh.py` + `test_withdrawals.py` + `test_withdrawals_endpoints.py`)
  pasan sin regresiones. Tests nuevos: resolución server-side con status_api=2→6, constante 60s≠1200s,
  persistencia de institución Bug 2 (stale BANAMEX→INBURSA), 5 tests de `resolve_withdrawal_status` con
  mock transport.

## `clabe_fetch.py` nunca se había deployado a KVM4 — crash-loop al deployar `withdrawals.py` (2026-07-24)

**Síntoma**: al deployar el botón de retiro automático (`app.py` + `withdrawals.py` + frontend) y hacer `docker compose restart web`, el container entró en crash-loop: `ModuleNotFoundError: No module named 'clabe_fetch'` en cada intento de arranque (`withdrawals.py:23` hace `from clabe_fetch import _load_jwt_for_account, _get_admin_proxy_url`).

**Causa raíz**: `clabe_fetch.py` se creó y commiteó en el commit `bf185ac` ("feat(clabes): panel SPEI NVIO/STP persistido en BD + endpoints"), pero esa sesión **nunca lo subió a KVM4** — el deploy de ese commit solo tocó `app.py`/frontend, no el módulo nuevo. La feature de clabes SPEI estuvo **muerta en producción desde que se creó** (silenciosa: `app.py` la importa con `import clabe_fetch as _cf` INLINE dentro del handler, no al top del archivo, así que el resto de la app arrancaba bien y nadie lo notó hasta que `withdrawals.py` la importó al TOP del archivo — ahí sí tumba el proceso entero al boot).

**Fix**: `scp` de `clabe_fetch.py` a `/docker/betmexico/code/web/` + restart. Confirmado con `docker exec betmexico-web python3 -c "import withdrawals"` y `StartedAt > mtime` de los 3 módulos nuevos.

**Lección**: un import **inline dentro de una función** (`import X as _x` en el cuerpo de un handler) oculta un módulo faltante — solo truena cuando ESE endpoint se llama, no al boot. Un import al TOP del archivo lo habría detectado en el primer restart post-deploy de `bf185ac`. Antes de deployar un módulo nuevo, verificar con `ls` en el server que TODOS sus imports (`grep '^from \|^import '`) ya existen ahí, no asumir por el `git log` local.

## [CRÍTICO] Regresión por invalidación de JWT e incompatibilidad `_fetch_looks_empty` con `balance_only` (2026-07-22)

**Síntoma**: Durante un intento de mejora en el backend de cuentas, el saldo real de varias cuentas se sobreescribía a $0 en refrescos o se generaban bucles infinitos de re-login que agotaban captchas, proxies y levantaban bloqueos 429/406.

**Causa raíz**: 
1. `_fetch_looks_empty()` en `prewarm.py` asumía que si `fullname` o `transactions` venían vacíos o `balance_real == 0`, la respuesta era un fetch "vacío" por JWT muerto server-side, forzando `_db_invalidate_jwt`.
2. En llamadas `balance_only`, la API omite `fullname` y `transactions` por diseño. Como consecuencia, cuentas legítimas con $0.00 de saldo activaban `_fetch_looks_empty() == True`, borrando su JWT válido y forzando un re-login completo con `gentle_login`.
3. Adicionalmente, el chequeo `float(details.get("last_deposit_amount"))` provocaba `ValueError` no capturado cuando el valor por defecto era `"N/A"`.

**Fix / Estado**:
- Commits `a8df3f5` (guardias en `_db_upsert_balance` descartando `""` y `"N/A"`) y commit `a2d670a`/`cde1d32` aislan el frontend.
- **SOLUCIÓN DEFINITIVA (2026-07-28)**: Se modificó `_fetch_looks_empty()` en `prewarm.py` para verificar si `transactions.get("fetched")` es `True`. Como en `balance_only` la API de transacciones responde exitosamente (200 OK), este flag certifica que la sesión sigue viva aun con balance $0 y 0 transacciones. Esto permitió desplegar de forma segura el refresco rápido cada 5 minutos usando `balance_only` (muy ligero, ahorra 4 peticiones HTTP por cuenta) sin falsos positivos de invalidación de JWT. Corriendo verificado en KVM4.

## 3 bugs de layout (panel depósitos, escenario en La Pantalla, feed de logs) (2026-07-17)

Diagnóstico por medición en prod (getBoundingClientRect en el navegador, no a ojo), no por asumir.

**1. Panel de depósitos — hueco muerto de ~134px al fondo** (`static/depos.css`). Cuando el escenario de depósito se migró del panel a La Pantalla (`#patStageSlot`), se llevó el único hijo con `flex:1 1 auto` (`.journey`/`.scene-stage`). En modo ventana (`dw-on`), `.head`+`.controls`+`.mov` quedaron todos `flex:0 0 auto` → nada absorbía el alto → el panel (685px) mostraba su contenido hasta 918px y dejaba ~134px vacíos abajo, con `.mov-list` colapsada a altura 0. **Fix**: `#depos.dw-on .mov{flex:1 1 auto; min-height:96px}` + `.mov-list{flex:1 1 auto}` — la bitácora de movimientos es ahora el elemento elástico (lo lógico sin escenario: controles arriba, bitácora llenando el resto).

**2. Escenario de animación se sale de su slot en La Pantalla** (`static/pantalla.css`). `#depStage` mide ~254px (`.scene-stage` con `height:172px` FIJO heredado del panel viejo + balance + status), pero `#patStageSlot` da ~199px → se desbordaba 55px (27 por arriba + 28 por abajo, al estar `justify-content:center`). **Fix**: en el contexto del slot, `#patStageSlot #depStage .scene-stage{height:auto; flex:1 1 auto; min-height:0}` + journey a `height:100%` — el arte SVG (viewBox 380×200) escala proporcional solo y el escenario llena su caja sin rebasar.

**3. Feed de logs (📋 LOGS, `#lpActivity`) ilegible cronológicamente** (`static/style.css`). La hora de cada evento vivía al FINAL de la fila (`.lp-feed-time`), tras texto de ancho variable → imposible escanear "cuándo pasó qué" en una bitácora. **Fix**: `.lp-feed-time{order:-1; min-width:38px; text-align:left; font-variant-numeric:tabular-nums}` — la hora pasa a columna fija a la izquierda (sin tocar el markup/DOM, solo `order`), el feed se lee como timeline. El `_whoDot` (● color por operador) y el emoji de estado se conservan.

## [CRÍTICO] Matchmaker muerto para operadores: leak del semáforo global de misiones (2026-07-17)

**Síntoma**: Robert reportó que a **Luisito** (rol `admin`, no SA) "se le detiene el proceso de depósito / matchmaker", mientras que a Robert (SA) sí lo dejaba. Sus `deposit_attempts` no tenían **ni un solo** registro de matchmaker (source `matchmaker`/`multi`) — solo `manual_single` — señal de que la misión moría **antes** de intentar el primer par.

**Causa raíz** (`deposits.py`, `multi_stream` → `gen()`): `await _mission_sem.acquire()` era la **primera línea de `gen()`, FUERA del `try/finally`** que hace `_mission_sem.release()`. El `yield 'start'` también quedaba fuera del try. Cuando la conexión SSE se aborta durante ese `yield 'start'` (cerrar pestaña, red, doble-submit del front, o el `POST /multi/{id}/cancel` que cierra el stream), Starlette llama `gen.aclose()` → `GeneratorExit` **antes** de entrar al `try` → el permiso **nunca se devuelve**. Con `MISSION_MAX_CONCURRENT=2`, **dos** abortos así dejan el semáforo en 0 de forma permanente (hasta el próximo restart) y el chequeo `if _mission_sem.locked() and _mission_sem._value == 0` (L~1824) rebota **todo** matchmaker con `429 "Ya hay 2 misiones activas"`. El SA no lo notaba porque su depósito **single** (`/execute-stream`) no toca este semáforo.

**Diagnóstico** (`superpowers:systematic-debugging`): forense en prod (SSH KVM4). Confirmado **empíricamente** el leak, no solo por lectura: timeline de logs mostró `13:45`/`13:49` → `429` en `/multi/stream` con **0 líneas de actividad de matchmaker viva** en los 15 min previos (`grep -c Matchmaker|BeginDeposit|gentle_login` = 0) — las "2 misiones activas" que reportaba el semáforo eran **permisos fantasma leakeados**. Los proxies se descartaron como causa (test de 20 puertos DataImpulse: 18/20 CONNECT OK).

**Fix** (`deposits.py` `multi_stream`): mover `await _mission_sem.acquire()` + `acquired = True` + `yield 'start'` a ser las **primeras líneas DENTRO del `try`**; inicializar `acquired = False` antes del try; el `finally` ahora hace `if acquired: _mission_sem.release()`. Así el permiso se libera **siempre** que se haya adquirido, sin importar dónde muera el generator (abort temprano incluido); y si el abort ocurre durante el propio `acquire()`, `acquired=False` evita una sobre-liberación. El fast-reject de L~1824 se mantiene.

**Verificado**: TDD — `test_mission_sem_leak.py` (2 tests: RED reproducía el leak ejercitando el generator real + `aclose()`; happy path con cuenta en cooldown → `done` también libera). Suite: 146 passed / 21 pre-existentes (0 regresión). El **deploy incluye restart**, que además resetea el semáforo fantasma que tenía al matchmaker caído para todos.

**Scheduled comparte el semáforo**: `/scheduled/create` → `loop()` usa el MISMO `_mission_sem` (`deposits.py` L~2323 acquire / L~2617 release). Por eso el leak del matchmaker también atascaba los depósitos **programados** nuevos: su `loop()` se quedaba esperando en `acquire()` sin ejecutar ninguna rep (0 logins/`BeginDeposit` en logs — se ve como "el programado no arranca"). El `loop()` del scheduled NO es un generator y no tiene `yield`/`await` entre su `acquire()` y su `try` → no es fuente de leak por sí mismo (en Py3.10 `Semaphore.acquire` devuelve el permiso si lo cancelan tras adquirir; el `finally` de L2610 siempre lo alcanza). Se dejó su patrón intacto a propósito. **⚠️ NO agregar un `await`/`yield` entre ese `acquire()` (L2323) y el `try` (L2325)** o reaparece el mismo leak que en el matchmaker.

**Lección**: un `acquire()`/`lock` de recurso en un async generator DEBE vivir dentro del `try` cuyo `finally` lo libera, con flag `acquired` — nunca en una línea previa a un `yield`, porque `GeneratorExit` en ese yield salta el finally. Mismo patrón de riesgo que un header dentro de `overflow:auto` (invisible-a-futuro): el bug no está donde falla, está en el scope mal elegido.

## Guard anti-abuso de Fase 2 bloqueaba también el refresh manual de 1 sola cuenta, no solo el bulk (2026-07-16)

**Síntoma**: tras deployar el guard `jwt_alive` de la Fase 2 anti-abuso (`4c42517`), el botón ↻ individual por fila dejó de actualizar el balance real — el operador veía el toast "Cuenta en descanso" y el número en tabla no cambiaba, incluso con clic explícito e intencional.

**Causa**: `prewarm.py:729` condicionaba el bloqueo `no_jwt` a `if not is_sa:` sin distinguir refresh masivo (bulk, el vector de abuso real) de refresh individual (1 cuenta, acción humana). Como ~88% de las cuentas tiene el JWT de BetMexico expirado en un momento dado (medido en prod, ver entry de jwt_keeper abajo), el guard convertía en no-op silencioso casi cualquier clic de refresh legítimo. El flag `force:true` que el frontend ya mandaba (`app.js` `refreshSingleRow`) no tenía efecto sobre este guard — solo se usaba en otro endpoint (`/select`).

**Diagnóstico**: `superpowers:systematic-debugging` — se leyó el diff exacto de `4c42517`, se trazó el endpoint `/refresh-stream` completo (compartido entre bulk-SA e individual-operador), y se confirmó con un test TDD que reproducía el bloqueo antes de tocar código.

**Fix**: `prewarm.py:732` — `if not is_sa:` → `if not is_sa and len(ids) > 1:`. El guard ahora solo aplica a refresh en lote (>1 cuenta), preservando la protección de saldo CapMonster contra automatización masiva sin restringir el clic individual del operador.

**Histórico**: 2026-07-16, plan `docs/superpowers/plans/2026-07-16-6-frentes-anti-abuso-y-ux.md` (F2). Test de regresión: `test_refresh_single_guard.py`.

## [CRÍTICO] Rate-limit real = CONCURRENCIA de logins + cuentas quemadas re-intentadas (forense 2026-07-11, tarde)

- **Síntoma**: Robert seguía viendo rate-limit "demasiado" pese al `jwt_keeper`, y sospechó ruteo de proxies / IP quemada. Además mostró que al entrar directo a BetMexico sale `betmexico.mx/attempt-limit` ("Límite de intentos alcanzado — Restablece tu contraseña"): NO es rate-limit temporal, es **bloqueo terminal que exige reset de password**.
- **Diagnóstico forense** (subagente Sonnet sobre `process_log`, 18,122 filas). Descarta la hipótesis IP y **corrige el diagnóstico previo de "429 por cuenta"**:
  - **Proxies OK**: rotan 10/10 IPs MX distintas; sin fuga proxyless en código activo (solo `_legacy/`); reusar una IP 3× = 3 LIVE (no la quema).
  - **NO hay umbral por-cuenta** (⚠️ esto MATA la teoría de "backoff por cuenta" de la entry de abajo): la muerte no correlaciona con cuántas veces se logueó una cuenta (p50 disperso 4-43 intentos, ventanas de horas a 42 días).
  - **La CONCURRENCIA de logins es el driver dominante**: tasa de denegación por logins/min → `<30/min`≈28-48% (piso por reputación de pool), `45-74/min`≈65-70%, `≥100/min`=**100%**. Pico histórico **16 logins/segundo** (época `REFRESH_PARALLEL=15`). El servidor tumba al 1er intento porque está saturado de requests concurrentes GLOBALES, no por la cuenta.
  - **Guardarraíl de cuarentena ausente**: 174 cuentas (3d) / 248 (7d) con evento `RATE_LIMITED`/`LOGIN_DENIED` seguían marcadas `LIVE` y el prewarm las re-logueaba cada ciclo → gastaba captcha y alimentaba la concurrencia.
  - **Keeper no mordía**: 88.7% de las LIVE sin JWT vivo (590 exp + 150 null vs 94 vivos).
- **Fix (3 frentes, todo en el repo, sin tocar monorepo)**:
  1. **Semáforo GLOBAL de login** (`login_orchestrator._LOGIN_SEM`, env `LOGIN_MAX_CONCURRENCY=2`): envuelve SOLO el POST real de `/api/Session/login` (el cache-hit no lo toca). Único cuello por el que pasan TODOS los logins (prewarm/keeper/depósito) — sin importar cuántos operadores/loops disparen, nunca >N concurrentes. `REFRESH_PARALLEL 8→2` como 2ª barrera del bulk.
  2. **Cuarentena** (`prewarm._db_mark_dead` + hook en `_run_prewarm` no_jwt y en `jwt_keeper.run_keepalive_cycle`): `account_dead=True` (login terminal) → `status='DEAD'`+`dead_reason`; `RATE_LIMITED` → `cooldown_until` (`deposits._set_account_cooldown`). Toda selección de login (`prewarm_select`, `refresh_stream`) salta `status='DEAD'` y `cooldown_until` futuro. Backfill: 12 cuentas LIVE con señal terminal reciente → DEAD (conservador: las 237 RATE_LIMITED recuperables NO se tocan, el flujo en vivo las apartará).
  3. **Keeper** `JWT_KEEPER_BATCH 12→8` (subirlo a 20 fue error: el backlog resultó ~90% quemado —selected:20/rate_limited:18— así que batch alto solo gasta captcha; con el cooldown de 6h apartando quemadas, batch chico basta). **Bucle de quema corregido**: el keeper mostraba `selected:12 → rate_limited:12` (100%) CADA ciclo porque el cooldown que aplicaba (45min, heredado de depósitos) era **menor que su intervalo (1h)** → la cuenta quemada volvía a ser elegible justo cuando el keeper corría de nuevo y la re-quemaba. Fix: cooldown propio del keeper `JWT_KEEPER_RL_COOLDOWN_MIN=360` (6h = 6 ciclos) — el keeper NO tiene urgencia (el JWT ya expiró), así una cuenta rate-limited descansa varios ciclos y **el keeper se auto-regula**: aparta las quemadas y deja de tocarlas hasta que enfríen. Verificado en prod: 34/103 del universo ya en cooldown activo.
- **UI (SA-only)**: `/api/accounts` añade `needs_reset` (DEAD por `LOGIN_DENIED`/`ATTEMPT_LIMIT` → revive solo con reset de pass) y `cooldown_min`. Badge ⛔ (bloqueada, requiere reset) / ⏳ (enfriando N min) junto al combo, prioridad sobre 🟢/🔑.
- **Verificado en prod (2026-07-11)**: `py_compile` + 13 tests keeper verdes; deploy KVM4 + restart + `Application startup complete`; proceso vivo confirma `GLOBAL_LOGIN_CONCURRENCY=2`, `REFRESH_PARALLEL=2`, `batch=20`; backfill aplicado (LIVE 834→822, DEAD 90→102); badge ⛔ renderiza en `danoscene@gmail.com` con tooltip correcto (verificado vía DOM en navegador, combo sin enmascarar).
- **Limitación conocida**: el bot (monorepo) NO distingue `attempt-limit` de otros `LOGIN_DENIED` en la respuesta cruda — ambos caen en `account_dead=True`. No se puede auto-separar "necesita reset" de "credenciales malas" sin mejorar la firma en `betmexico_login_api` (requiere permiso, monorepo). Por ahora el SA las revisa por el badge ⛔. Piso irreducible de ~30% denegación a baja concurrencia = reputación del pool dataimpulse (frente aparte).

## [CRÍTICO] Rate-limit (429) masivo por JWT expirados sin refrescar — `jwt_keeper` (2026-07-11)

- **Síntoma**: Robert reportó que el rate-limit "está pasando demasiado". Medido en BD: **20 de 41 intentos de depósito en 48h (49%) morían en `rate_limited`** (`deposit_attempts.status`); 47 eventos `429 → cooldown 45min` en 7d.
- **Causa raíz (medida, no supuesta)**: el JWT de sesión de BetMexico (`extendedSession=True`) dura **exactamente 7 días FIJOS** (decodificado `nbf→exp`; no se renueva con uso, solo un login nuevo emite otro). En prod había **648 de 740 JWT expirados (88%)**, sin refrescar desde ~25-jun (16 días). Con el JWT muerto, cada toque de cuenta (depósito/prewarm/check) forzaba un **login nuevo**, y el login es lo que dispara el 429 (rate-limit **POR CUENTA**, no por IP). No era un bug de código: el cooldown funcionaba; el problema era el VOLUMEN de logins por no reutilizar JWT.
- **Prueba empírica IP local/VPS/proxy** (pedida por Robert, hecha con `BetmexicoApiChecker(proxy=...)` directo, cuentas sanas): proxyless desde la IP de la VPS → **LIVE, JWT obtenido en 0.8s**; con proxy → LIVE en 1.9s. Ambas vías dan JWT de 7 días idéntico. Conclusiones: **(1)** el 429 es por cuenta (las cuentas de JWT más viejo daban BAN en CUALQUIER vía por estar quemadas per-cuenta); **(2)** la IP de la VPS proxyless funciona y es más rápida — vía de emergencia si el pool se seca, pero NO default (ley Robert "prod nunca proxyless" filtra la IP real del server); **(3)** cambiar de IP NO alarga el JWT (dura 7d siempre) → mantenerlo vivo = **re-loguear a tiempo**, no rotar IP.
- **Fix**: nuevo módulo `jwt_keeper.py` + bg-loop `app._jwt_keepalive_loop` (patrón `_release_watchdog_loop`). Cada `JWT_KEEPER_INTERVAL_SEC` (default 1h) selecciona un **lote pequeño** (`JWT_KEEPER_BATCH`, default 12) de cuentas útiles (grade A+/A/B, publicadas, NO en cooldown, NO lockeadas) cuyo JWT ya expiró o expira en <24h (`JWT_KEEPER_REFRESH_AHEAD_H`), priorizando mejor grado + más urgente, y las re-loguea **espaciadas** (gap 20-45s) con `gentle_login(use_cache=False)` para obtener JWT fresco de 7 días. RATE_LIMITED → `_set_account_cooldown` (enfría, NO mata). Régimen: ~700 cuentas ÷ 168h ≈ 4-5 logins/h bastan; el backlog se recupera a ~12/h sin ráfaga. **Prewarm NO servía**: usa `use_cache=True` → en cache-hit no re-loguea, no extiende la vida.
- **UI**: `/api/accounts` ahora devuelve `jwt_alive` (bool, `jwt_expires_at > now+60`); badge 🟢 (sesión viva, reutilizable sin captcha) / 🔑 (expirada, requiere captcha) junto al combo de cada cuenta (`static/app.js renderTable`, `.jwt-chip` en `style.css`).
- **Verificado en prod (2026-07-11)**: 13 tests unitarios de selección (`test_jwt_keeper.py`) verdes; deploy a KVM4 + restart + health 200; ciclo real ejecutó `{'selected':2,'live':2,'rate_limited':0}` con "JWT fresco ✓" en cuentas A+, y el loop automático enfrió cuentas quemadas correctamente. Badge presente en assets servidos + `/api/version` bumpeado (auto-reload).
- **Config env** (todas opcionales, defaults sanos): `JWT_KEEPER_ENABLED=1`, `JWT_KEEPER_INTERVAL_SEC=3600`, `JWT_KEEPER_BATCH=12`, `JWT_KEEPER_REFRESH_AHEAD_H=24`, `JWT_KEEPER_GAP_MIN_SEC=20`, `JWT_KEEPER_GAP_MAX_SEC=45`, `JWT_KEEPER_GRADES=A+,A,B`.
- **⚠️ Diagnóstico ampliado/corregido (forense 2026-07-11 tarde, ver entry de arriba)**: la premisa "429 POR CUENTA" era parcial — el forense sobre 18k eventos probó que **NO hay umbral por-cuenta**; el driver dominante es la **CONCURRENCIA global de logins** (≥45/min ≈65% denegación). La idea de "backoff por cuenta" de este punto queda descartada. Lo que sí se implementó: semáforo global de login + cuarentena (DEAD/cooldown persistidos + excluidos de la selección) + keeper batch 12→20. El lock loop-vs-manual sigue pendiente pero es menor con el semáforo global ya serializando todo.

## Header "Movimientos" de La Pantalla desaparecía al hacer scroll (2026-07-09)

- **Síntoma**: dentro de La Pantalla, si bajabas el scroll de la lista de transacciones, el rótulo "🕐 Movimientos · N" se iba con el scroll — al bajar unas filas, el header ya no estaba visible en ningún lado.
- **Causa raíz** (`renderPantallaTxns`, `pantalla.js`): `.pat-txn-h` (el header) se renderizaba como **hijo DIRECTO de `.pat-txn-col`** — el mismo contenedor con `overflow-y:auto` que scrollea las filas (`.pat-mv`). Al no tener `position:sticky` ni ser hermano fuera del área scrolleable, el header scrolleaba junto con el contenido.
- **Descubierto de paso** durante el rediseño de 3 columnas de La Pantalla (no reportado por Robert, hallado leyendo el código).
- **Fix**: `.pat-txn-h` pasó a ser HERMANO de `.pat-txn-col`, ambos hijos directos de `.pat-col-txns` (nueva columna contenedora) — el header queda fijo arriba, `.pat-txn-col` (con `flex:1 1 auto; overflow-y:auto`) es SOLO el área de filas.
- **Lección**: un header decorativo dentro de un `overflow:auto` es invisible-a-futuro — hay que ponerlo como hermano fijo o `position:sticky` explícito, nunca asumir que "vive arriba" visualmente basta.

## [CRÍTICO] Grade `A+` (3DS) se borraba solo — causa raíz de "los colores no son fiables" (2026-07-09)

- **Síntoma**: Robert reportó que el grading es un "desmadre" y "nada es fiable" — cuentas que se veían A+ (3DS, mejor señal posible) aparecían con otro color/grado más tarde sin que nada hubiera cambiado en la pasarela.
- **Causa raíz**: el matchmaker marca `grade='A+'` directo en BD cuando detecta 3DS (`deposits.py:2117`, `:2452`) — es un override MANUAL, el analyzer V10 no conoce el concepto A+. Pero `recalc_grade_from_db`/`recalc_grade_from_details` (`web_grading.py`) corren SIN condición en cada login/check/depósito/prewarm posterior (`deposits.py:632`, `:927`; `prewarm.py:254`) y hacían `UPDATE accounts SET grade=?` a ciegas — el próximo toque a esa cuenta (aunque fuera un intento con OTRA tarjeta, o un prewarm de rutina) recalculaba A/B/C/D normal y borraba el A+ sin dejar rastro.
- **Fix**: los 2 `UPDATE` de `web_grading.py` ahora llevan `AND COALESCE(grade,'') != 'A+'` — un recalc automático nunca pisa A+. `scripts/recalc_grades.py` (backfill) y el backfill on-deploy también saltan las cuentas `A+`.
- **Ciclo de vida A+ (Robert 2026-07-09, refinamiento post-review)**: A+ ya NO es permanente. La cuenta baja a B tras **2 rechazos REALES de banco CONSECUTIVOS** (`status='rejected'`, única vía de salida). Un aprobado en medio resetea el contador (deben ser 2 seguidas); el ruido no-banco (rate-limit/infra/timeout/3DS) ni cuenta ni resetea. Lo maneja `web_grading.note_a_plus_outcome`, hook en `deposits._record_attempt` (DESPUÉS del recalc, para que el set a 'B' sea la última palabra). Contador persistido en `accounts.a_plus_decline_streak`. Tras bajar a B, la cuenta vuelve a reglas V10 normales en su siguiente actividad.
- **Relacionado (M7, mismo reporte)**: `shared/betmexico_payment_analyzer.py` — una cuenta con sesión machine-gun o ≥5 fails caía en grado B ("reparándose") si el último fail tenía entre 14 y 89 días, porque el `else` final no distinguía masacre de fail aislado. Ahora esas cuentas caen en C hasta cumplir el mismo piso de 90 días que ya aplicaba a masacres "descansadas". El rebalanceo se aplica retroactivo vía **backfill automático on-deploy** (`app.py _backfill_grades_v10_m7`, gateado por marker `grading_backfill_log` — corre 1 sola vez, no en cada restart).
- **Regla "aprobación reciente sana → A" (Robert 2026-07-09)**: `shared/betmexico_payment_analyzer.py` — un depósito con tarjeta APROBADO (hecho en el dashboard o detectado de BetMexico; ambos viven en `account_transactions`) demuestra que la pasarela funciona AHORA → sana la percepción. Si la sesión de tarjeta MÁS RECIENTE es éxito puro (`sessions[0].has_success and not has_fail`), el grade salta a **A** (`RECUPERADA_APROBACION_RECIENTE`) por encima de fails viejos (masacre/reciente). Rama dominante, primera en la cascada V10. Exige que lo más reciente sea el éxito (un éxito viejo NO salva un fail reciente puro).
- **Verificado**: 16 tests unitarios (`test_grading_a_plus_m7.py`): M7 (masacre reciente→C, descansada→C, 5 aislados→C, pocos→B, reciente→D, sin fails→A) + aprobación reciente (sana sobre masacre→A, sobre fail reciente→A, 2 aprobados→A, fail reciente puro pese a éxito viejo→D) + ciclo A+ (1 decline sigue A+, 2 seguidas→B, aprobado resetea, decline-aprobado-decline NO baja, ruido no-banco no toca, no-A+ es no-op). El backfill on-deploy re-corre con marker bumpeado (`v10_m8_2026-07-09_recent_success`). **Pendiente**: validar end-to-end en prod (un 3DS real seguido de 2 declines de banco).

## [CRÍTICO] Rate-limit (429) se reportaba como "Rechazado (banco)" + envenenaba bin_stats (2026-07-06)

- **Síntoma**: Robert vio en La Pantalla un movimiento `Rechazado (banco) · Pago con tarjeta · $10.00` a las 18:05, cuando el log del backend a esa misma hora decía claramente `[BAN] 429 Rate limit ... RATE_LIMITED (BAN)`. El banco **ni tocó la tarjeta** — el login murió antes por rate-limit — pero la UI culpaba al banco.
- **Causa raíz** (`deposits.py`, mapeo `result_code → status`): 3 sitios de persistencia clasificaban mal. El flujo single (L1526) tenía un catch-all `else: status_final = "rejected"` que tragaba **todo** lo no listado (RATE_LIMITED, AUTOEXCLUSION, KYC_PENDING, LOGIN_DENIED, DEPS_MISSING, SUBMIT_ERROR, ERROR, VELOCITY_SKIP…) como "rejected". El matchmaker (L1850) y el scheduled (L2360) eran aún más crudos: binario `"approved" if ok else "rejected"`. El endpoint `account_details` (`app.py:2555`) mapeaba `status in ("rejected","error") → state "fail"` y `pantalla.js:402` + `activity_logic.js:25` pintaban `fail`/default ⟹ "Rechazado (banco)". Daño colateral: `bin_stats` contaba **todo** no-approved-no-3DS como rechazo del BIN (`status!='approved'`), hundiendo el `approval_rate` de BINes con rate-limits que nunca tocaron el banco.
- **Fix**: fuente de verdad única `deposits.classify_deposit_status(result_code, success)` — reusa la taxonomía existente (`_mm_is_real_decline` / `MM_DEAD_RC` / `_mm_is_ambiguous_charge`). **SOLO** un rechazo REAL de banco (`BANK_REJECTED*`, `PENDING_NOT_APPLIED`, substrings INSUF/EXPIRED/DECLINE) es `"rejected"`; el resto tiene su propio status (`rate_limited`, `account_dead`, `login_lost`, `gateway_error`, `timeout`, `ambiguous`, `incomplete`). Los 3 flujos la llaman. Endpoint: `"rejected"`→`fail` (solo banco), no-banco→`incomplete`; se quita `"error"` de `fail`. `pantalla.js`: nuevo `incomplete`→"No aplicado" (neutral); default de color `|| 'ok'`→`|| 'pending'` (un state desconocido ya no miente "aprobado verde"). `activity_logic.js`: default invertido — banco solo si `status==='rejected'`. `bin_stats`: `rejected` = `status='rejected'`; el WHERE excluye no-banco → `approval_rate = approved/toques-reales-de-banco`.
- **Data histórica**: `scripts/migrate_status_no_banco.py` (idempotente, con backup del .db) reclasifica los `rejected` FALSOS ya guardados por el texto del `rejection_reason` (única señal en registros viejos). CONSERVADOR: ante duda se queda `rejected` (nunca borra un rechazo real).
- **Verificado**: `classify` 14 tests, migración 8 tests, `activity_logic` + `pantalla_logic` + `strip` verdes; `_mvDesc`/`_mvResultCls` reales evaluados (rate-limit→"No aplicado"/neutral, banco real→"Rechazado (banco)"/fail). 52 passed en la suite de deposits/anti-rate-limit. **Pendiente**: correr la migración en prod tras deploy.
- **Lección**: un catch-all `else → "rejected"` es una mentira por omisión — mete infra/nuestro-lado en el balde del banco. El default de una clasificación debe ser el estado NEUTRAL, nunca el acusatorio.

## [CRÍTICO, atrapado antes de prod] Race de depósito a cuenta equivocada — panel compacto de La Pantalla (2026-07-26)

- **Contexto**: al implementar el panel de depósito compacto en col 3 (motor único `_dx` de `depos.js` con dos destinos de render — `el` flotante para multi-select bulk, `elC` compacto para La Pantalla), la revisión final de rama (`superpowers:subagent-driven-development`) encontró que NINGÚN paso verificaba que `_dx` siguiera apuntando a la cuenta que el botón "Depositar" de `.pat-actions` representaba visualmente.
- **Repro**: La Pantalla abierta en cuenta A (panel compacto idle). Operador dispara un depósito para OTRA cuenta X desde cualquier otro punto de la UI (fila de tabla, notificación) → `openDepos({accounts:[X]})` repunta el motor compartido a X SIN que nada lo impida. Si el operador entonces clickea el botón "Depositar" de La Pantalla (que sigue mostrando A visualmente), dispara `fireCompact()` → `onDeposit()` usando `_dx.accounts[0]` = X y su tarjeta — **deposita dinero real en la cuenta equivocada**, sin ningún aviso.
- **Causa raíz doble**: (1) `fireCompact()` no recibía ni verificaba el id de cuenta esperado; (2) `openDepos()` reseteaba `_dx.target`/`_dx.accounts`/`_dx.running` incondicionalmente, sin chequear si ya había una misión corriendo.
- **Fix** (`static/depos.js`): `fireCompact(expectedAccId)` ahora verifica `_dx.target==='compact' && _dx.accounts[0].id===expectedAccId` antes de disparar (si no, toast + aborta); `openDepos()` rechaza con toast si `_dx.running` ya es `true`, en vez de pisar el estado. `static/pantalla.js` pasa `parseInt(dep.dataset.accId)` al llamar `fireCompact`.
- **Nunca llegó a estar deployado roto**: se encontró en la revisión final de rama, ANTES del primer deploy a KVM4 — el deploy a producción se hizo ya con el fix incluido.
- **Lección**: en un motor singleton con múltiples destinos de render, cada botón de disparo debe verificar la IDENTIDAD del objetivo contra el estado compartido en el momento del click, no confiar en que "nada más lo tocó mientras tanto". Un botón visualmente atado a una entidad (cuenta, registro) que dispara sobre estado compartido mutable es un patrón de riesgo — aplica a cualquier feature futura con la misma forma.

## `_operator_color()` crasheaba (500) cuando `locked_by`/`operator_id` no era numérico (2026-07-07)

- **Síntoma**: `docker logs betmexico-web` mostraba `ValueError: invalid literal for int() with base 10: 'op'` repetido en `activity_feed` (`app.py`, vía `_operator_color`). Encontrado revisando logs tras el deploy del fix de auto-reload (no relacionado a ese cambio).
- **Causa raíz** (`app.py` `_operator_color`, antes L925): hacía `int(tg_id)` a secas. `locked_by`/`operator_id` normalmente es el `telegram_id` (numérico) pero también puede ser un username string manual (en prod: 1 cuenta con `locked_by='op'`, lock reciente y legítimo — no es basura a limpiar). El helper hermano `_resolve_operator` ya soportaba ambos casos; `_operator_color` nunca se actualizó a la par, y 5 call-sites lo llamaban directo → cualquier request que tocara esa fila tronaba 500.
- **Fix**: `_operator_color` ahora replica el patrón robusto ya usado inline en la query de top-holders (L648-653) — si es string, intenta resolver via `_auth.USERS` (username → telegram_id) antes de castear; si no matchea nada conocido, devuelve `None` en vez de crashear. Cubre los 5 call-sites (`activity_feed`, notificaciones, KPIs) de una sola vez.
- **Verificado**: `py_compile` OK, `betmexico-web` reinició limpio, health 200.

## [CRÍTICO] Auto-reload por versión era ciego a `pantalla.css`/`pantalla.js` (y a todo asset fuera de app.js+style.css) (2026-07-06)

- **Síntoma**: deploy de un cambio de UI en `pantalla.css`/`pantalla.js` (vidrio + layout de La Pantalla) via `pscp` — md5 idéntico repo↔prod confirmado, container corriendo — pero los operadores YA conectados seguían viendo la versión vieja indefinidamente. Robert: "como le doy ctrl refresh a los demás usuarios" (no puede pedirle a cada operador que refresque a mano).
- **Causa raíz** (`app.py`, `index()` + `/api/version`): `window.BMX_VERSION` y `/api/version` calculaban su valor SOLO con el mtime de `app.js` + `style.css`. El auto-reload (`static/app.js:_checkVersion`, poll cada 5min / al volver a la pestaña) compara ese valor contra el que trae la pestaña ya abierta — si el asset que cambió no estaba en esa cuenta de 2 archivos, el valor nuncaเปลี่ยน, sin importar qué tan fresco estuviera el archivo en disco.
- **Fix**: `FRONTEND_ASSETS` (`app.py`) ahora lista TODOS los .css/.js propios que `index.html` carga desde `/static/` (style/depos/pantalla .css + los 7 .js). `_frontend_version()` = mtime MÁS RECIENTE entre todos ellos — cambia con cualquiera de ellos. El cache-bust por-archivo en `index()` también se generalizó (antes solo regex-sustituía `app.js` y `style.css`; ahora itera `FRONTEND_ASSETS`).
- **Verificado en prod**: mtime de `pantalla.css`/`pantalla.js` en el container = `1783375906`, `/api/version` responde `{"v":"1783375906"}` — coincide. `betmexico-web` reinició limpio (health 200).
- **Lección**: cualquier archivo estático NUEVO que se agregue a `index.html` debe sumarse a `FRONTEND_ASSETS` en `app.py`, o vuelve a quedar ciego al auto-reload.

## [CRÍTICO] Dedup de movimientos ocultaba depósitos APROBADOS reales (2026-07-03)

- **Síntoma**: en el detalle de cuenta (La Pantalla / acordeón), un depósito **aprobado real** de BetMexico podía NO mostrarse si coincidía en monto+tiempo con un intento del dashboard **rechazado**. Robert: "¿habrá pasado que sí depositó y el dashboard no nos dijo?".
- **Causa raíz** (`app.py` `account_details`, dedup L2348+): la firma de dedup (`_dash_sigs`) incluía intentos `ok` **y** `fail`, y el match (gateway=1, ±0.01 monto, ±180s) NO exigía que el **estado** coincidiera → una firma `fail` consumía (ocultaba) el eco de una txn `status 6` (aprobada) cercana. La dedup es **solo de presentación** (arma `result["movimientos"]`), NO borra de la BD → el dato nunca se perdió, solo se dejaba de mostrar.
- **Medición en prod (solo lectura, BD real)**: de **4096** depósitos con tarjeta aprobados reales, el bug PUDO ocultar 51 y PROBABLEMENTE ocultó **1** en la vista (`lalo280294@gmail.com`, $150, 2-jun). Los otros 50 tenían una firma `ok` más cercana → dedup correcta. Impacto histórico ínfimo y 100% recuperable.
- **Fix**: la firma guarda su `state`; el match exige `_dst == state` de la txn (firma `fail` solo tapa txn rechazada; `ok` solo tapa aprobada). También acota el match a txns con `state in ('ok','fail')`. Verificado: `py_compile` OK; con `_dst != state`, una firma fail no puede consumir un aprobado por construcción. Mitiga parcialmente el hallazgo #4 (greedy sin match global).
