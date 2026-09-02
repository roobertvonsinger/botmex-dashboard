# MAP — botmex-dashboard
### Guía de navegación para agentes IA · lectura obligatoria al iniciar sesión

> Secciones `[AUTO]` se regeneran en cada commit. No editar — se sobreescriben.
> Para navegar funciones específicas dentro de un módulo: leer `MAP_DEEP.md`.
> Regenerar manualmente: `python scripts/gen_map.py`

---

## Si necesitas... `[MANUAL]`

| Si necesitas... | Ve a | Nota |
|-----------------|------|------|
| Modificar flujo de depósito (lógica core) | `deposits.py` | Motor principal |
| Modificar endpoints HTTP de depósito | `deposits.py` (router) | execute-stream / multi / scheduled |
| Modificar matchmaker / programado | `deposits.py` (`multi_stream` / `scheduled_create`) | |
| Modificar prewarm | `prewarm.py` (router) | |
| Agregar endpoint nuevo | `app.py` (`@app.X` inline) o `deposits.py`/`prewarm.py` (router) | Routers vivos: prewarm + deposits |
| Cambiar pool de proxies / failover | `proxy_pool.py` | `call_with_proxy_failover` es la API recomendada |
| Cambiar lógica de grading | `web_grading.py` + `shared/betmexico_payment_analyzer.py` | Algoritmo V10 |
| Cambiar autenticación / sesiones | `auth.py` + `web_auth.py` | |
| Ver logs en vivo (endpoint) | `app.py` (`@app.get /api/logs`, inline) | Lee `/data/logs/dashboard.log` |
| Cambiar esquema BD | `app.py` → `_migrate()` | Migraciones aditivas solamente |
| Agregar evento SSE | `app.py` → `_broadcast()` + `docs/SSE_EVENTS.md` | |
| Cambiar caps duros de depósito | `deposits.py` L28–L35 | DEP_MAX_PER_TXN, DEP_MAX_24H, AUTOLOCK_HOURS_* |
| Analizar si una tarjeta/pasarela está quemada | `shared/betmexico_payment_analyzer.py` | Algoritmo V10 |
| Cambiar el comportamiento del agente de soporte | `docs/AGENTE_SOPORTE.md` | Es el system prompt literal — se edita sin tocar Python |
| Agregar/quitar una herramienta del agente | `support_tools.py` | Escritura → agregar a `_EXECUTORS` (un test verifica que no falte) |
| Cambiar el modelo del agente | env `SUPPORT_MODEL_CHAIN="a,b,c"` | Cadena con fallback; default en `support_llm.DEFAULT_CHAIN` |
| Reiniciar contenedores desde el código | `support_dockerd.py` | Lista blanca; el socket NO se monta en `betmexico-web` |
| Ver estado funcional de features | `docs/AUDIT.md` | ✅❌⚠️🔵❓ |
| Ver errores conocidos + fix | `docs/ERRORS.md` | |
| Deploy a KVM4 | `DEPLOY.md` + `docs/protocols/deploy-protocol.md` | |
| Endpoints completos con params | `docs/ENDPOINTS.md` | |
| Mapa de funciones dentro de un módulo | `MAP_DEEP.md` | Solo cuando vas a navegar código interno |

---

## Flujos principales `[MANUAL]`

### Depósito único
```
deposits.py router (/execute-stream) → _run_deposit_with_phases → gentle_login (login único)
  → proxy_pool.py (call_with_proxy_failover)
  → CapMonster API (reCAPTCHA v2)
  → BetMexico API: BeginDeposit → makePayment → verify
  → web_grading.py (recalc_grade_from_db)
  → app.py _broadcast() → SSE → frontend
```

### Misión batch (matchmaker)
```
deposits.py (/multi/stream → multi_stream) → _run_deposit_with_phases (cuenta×tarjeta)
  max 5 cuentas × 5 tarjetas · gap aleatorio 3-8s
  APROBADA → vincular tarjeta↔cuenta
  Rechazo específico (TARJETA_INVALIDA/INSUF/EXPIRED) → marcar tarjeta, siguiente
  Gateway 5xx ×2 → PAUSE TOTAL
```

### Misión programada (scheduled)
```
deposits.py (/scheduled/create → loop) → _run_deposit_with_phases
  APROBADO → completed
  Rechazo → STOP (no reintentar, requiere override manual)
  Captcha pool prefetchea tokens; TOKEN_MAX_AGE=55s
```

### Prewarm
```
prewarm.py (router)
  Cap: 30 pre-warms/operador/10min · skip si JWT vigente y last_check < 5min
  Timeout 25s/task · logs en process_log (process_type='prewarm')
```

---

## Gotchas críticos — no repetir `[MANUAL]`

| # | Síntoma | Causa raíz | Fix |
|---|---------|------------|-----|
| 1 | SSE no llega al frontend aunque backend emite | Doble-import de `app.py` = dos instancias de `_sse_queues` | `app.py` L18–32: `sys.modules.setdefault("app", sys.modules[__name__])` |
| 2 | 406 FAILURE_IN_CAPTCHA masivo (build v26.5.25+) | Reputación de IP de proxies + antifraude BetMexico. **NO es mismatch de versión** — v3 probado con Playwright real = 0%. v2 sigue siendo el token correcto. | Fix real: login v2 gentil (anti-ráfaga, jitter, backoff) + **NO matar cuentas por 406** (`LOGIN_FAILED` → `login_retry`, jamás DEAD). Ver `docs/ERRORS.md` §"matchmaker mata cuentas buenas". |
| 3 | Logs no cargan en dashboard tras restart | Antes: journalctl (VPS). KVM4 es Docker sin systemd | `app.py` L40–62: RotatingFileHandler a `/data/logs/dashboard.log` |
| 4 | Token captcha expirado en scheduled | TOKEN_MAX_AGE=55s · sleep(60) = token viejo al despertar | Captcha pool prefetchea; ver `deposits.py` sección "captcha pool" |
| 5 | `create_task(gather())` crashea Py3.11+ | Bug asyncio en multi-depósito | Fix en `deposits.py` (`multi_stream`) |
| 6 | BANK_REJECTED ≠ error de captcha | BANK_REJECTED = banco rechazó la tarjeta, no el captcha | No reintentar en BANK_REJECTED |
| 7 | LitPort falla 0% | Reputación IP baja para BetMexico | Excluido via `_EXCLUDED_PROXY_HOSTS` en `proxy_pool.py` |
| 8 | `402 Payment Required` masivo en login (sin `[API] Status:` previo) | **Proxy sin saldo** (IPRoyal). El 402 es del CONNECT al proxy (`X-Response-Origin: proxy-server`), NO de BetMexico ni proxyless. | IPRoyal en `_EXCLUDED_PROXY_HOSTS`. Recargar saldo y quitarlo. Ver `docs/ERRORS.md` §"402 Payment Required". |
| 9 | Un contenedor se ve `Up` y hasta responde HTTP, pero toda llamada saliente falla con `EAI_AGAIN: getaddrinfo` | **Sin red Docker**: `.NetworkSettings.Networks` == `{}`. Sin red no hay DNS ni egress; los endpoints que sirven datos estáticos siguen respondiendo y disimulan el problema. Le pasó al 9router (13 h caído sirviendo `/v1/models` normal). | `docker inspect <c> --format '{{json .NetworkSettings.Networks}}'` **antes** de culpar al upstream → `docker network connect <red> <c>` (aditivo, no recrea). Ver `docs/ERRORS.md` §"9router sin ninguna red Docker". |

---

## Módulos `[AUTO métricas / MANUAL propósito]`

> Edita la columna **Propósito** directamente — el script la preserva al regenerar.

<!-- GEN:start:modulos -->
| Módulo | L# | Logger | Propósito |
|--------|----|---------|-----------| 
| `account_refresh.py` | 592 | `betmexico.dashboard.account_refresh` | Refresca balance/movimientos de cuentas con JWT VIGENTE (sin login, sin captcha) — bg-loop cada 5min (`ACCOUNT_REFRESH_INTERVAL_SEC=300`). Cuentas "hot" (balance>$50, autolock activo, retiro pendiente) se priorizan y bypassean grade/pool/lock |
| `app.py` | 5528 | `betmexico.dashboard.account_refresh` | App Flask principal: config, BD SQLite, rutas base, bus SSE, KPIs/admin, watchdog init |
| `auth.py` | 287 | `—` | Core de autenticación: sesiones, hashing de passwords, decorador `require_session` |
| `auto_deposit.py` | 2191 | `betmexico.dashboard.auto_deposit` | _[completar]_ |
| `autoexclusion.py` | 177 | `betmexico.dashboard.autoexclusion` | _[completar]_ |
| `betmexico_config.py` | 183 | `betmexico` | _[completar]_ |
| `betmexico_db.py` | 2960 | `—` | _[completar]_ |
| `betmexico_deposit.py` | 958 | `—` | _[completar]_ |
| `betmexico_login_api.py` | 1138 | `httpx` | _[completar]_ |
| `betmexico_login_service.py` | 144 | `betmexico.login_service` | _[completar]_ |
| `betmexico_payment_analyzer.py` | 492 | `—` | _[completar]_ |
| `betmexico_utils.py` | 1159 | `—` | _[completar]_ |
| `bin_intelligence.py` | 701 | `betmexico.dashboard.bin_intelligence` | _[completar]_ |
| `card_checker.py` | 598 | `betmexico.dashboard.card_checker` | _[completar]_ |
| `clabe_fetch.py` | 188 | `betmexico.dashboard.clabe_fetch` | _[completar]_ |
| `conftest.py` | 218 | `—` | Fixtures pytest (BD en memoria, cliente test, sesión de prueba) |
| `curp_utils.py` | 267 | `—` | _[completar]_ |
| `deposits.py` | 3154 | `betmexico.dashboard.deposits` | Motor de depósitos: `_run_deposit`, captcha pool, retry-con-failover, caps duros |
| `jwt_keeper.py` | 389 | `betmexico.dashboard.jwt_keeper` | Mantiene JWT de sesión vivos (7d): re-loguea espaciado las cuentas por expirar para bajar el 429. Bg-loop horario `app._jwt_keepalive_loop`. Config `JWT_KEEPER_*` |
| `login_orchestrator.py` | 207 | `betmexico.dashboard.login_orch` | _[completar]_ |
| `prewarm.py` | 918 | `betmexico.dashboard.prewarm` | Pre-carga JWT + balance para cuentas — acelera depósitos. Deps del bot en runtime |
| `proxy_pool.py` | 389 | `dashboard.proxy_pool` | Pool de proxies: rotación, `call_with_proxy_failover`, exclusión de hosts quemados |
| `renapo_validator.py` | 154 | `betmexico.renapo_validator` | _[completar]_ |
| `saneador_daemon.py` | 275 | `saneador` | _[completar]_ |
| `scripts/backfill_account_cards.py` | 123 | `—` | _[completar]_ |
| `scripts/gen_map.py` | 484 | `—` | Regenerador de MAP.md + MAP_DEEP.md — AST + git log. Corre en pre-commit hook |
| `scripts/migrate_status_no_banco.py` | 80 | `—` | _[completar]_ |
| `scripts/recalc_grades.py` | 136 | `—` | Utilería dev: recalcular grades de todas las cuentas desde BD |
| `scripts/update_429.py` | 11 | `—` | _[completar]_ |
| `scripts/update_proxy001_list.py` | 35 | `—` | _[completar]_ |
| `scripts/verify_all_accounts_active.py` | 140 | `verify_all_accounts` | _[completar]_ |
| `shared/betmexico_payment_analyzer.py` | 592 | `—` | Algoritmo V10: clasifica pasarela/tarjeta A=sana/B=recuperando/C=lenta/D=quemada |
| `web_auth.py` | 159 | `betmexico.web.auth` | Endpoints HTTP de auth: login, logout, me, cambio de password |
| `web_grading.py` | 197 | `betmexico.web.grading` | Recalcula `grade` y `grade_score` de una cuenta desde BD (usa analyzer V10) |
| `web_utils.py` | 265 | `betmexico.web.utils` | Helpers compartidos: _friendly_error, _normalize_ccexp, _build_proxy_url |
| `withdrawals.py` | 999 | `betmexico.dashboard.withdrawals` | Retiro automático vía API BetMexico (5 pasos). `execute_withdrawal` orquesta PASO0-3. `_refresh_account_after_withdrawal` refresca saldo post-retiro reusando JWT |
<!-- GEN:end:modulos -->

---

## Constantes operacionales `[AUTO]`

<!-- GEN:start:constantes -->
| Constante | Valor | Módulo |
|-----------|-------|--------|
| `WITHDRAWAL_POLL_INTERVAL_SEC` | `60` | `account_refresh.py` |
| `ROBERT_CHAT_ID` | `1341812706` | `app.py` |
| `SESSION_TTL` | `86_400` | `auth.py` |
| `PERSISTENT_USERS` | `{"robertvs"}` | `auth.py` |
| `PERSISTENT_TTL` | `60 * 60 * 24 * 365 * 10` | `auth.py` |
| `THREEDS_RECENT_H` | `24` | `auto_deposit.py` |
| `MIN_WITHDRAWAL_AMOUNT` | `100.0` | `auto_deposit.py` |
| `PROBE_AMOUNT` | `10.0` | `auto_deposit.py` |
| `MATCH_TRANSIENT_RETRIES` | `4` | `auto_deposit.py` |
| `MM_CROSS_ACCOUNT_GAP` | `5` | `auto_deposit.py` |
| `MM_MAX_ACCOUNT_DECLINES_PER_RUN` | `2` | `auto_deposit.py` |
| `MM_CARD_MAX_DECLINES` | `3` | `auto_deposit.py` |
| `MM_ACCOUNT_MAX_DECLINES_1H` | `2` | `auto_deposit.py` |
| `MAX_TEXT_COMBOS` | `100` | `betmexico_config.py` |
| `HUMAN_COOLDOWN` | `60` | `betmexico_config.py` |
| `MAX_COMBOS` | `5000` | `betmexico_config.py` |
| `FLUSH_EVERY` | `20` | `betmexico_config.py` |
| `HITS_PER_BLOCK` | `100` | `betmexico_config.py` |
| `SMART_FILTER_COOLDOWN_MIN` | `20` | `betmexico_config.py` |
| `SMART_FILTER_STALE_CHECKS` | `3` | `betmexico_config.py` |
| `SMART_FILTER_ACTIVITY_HOURS` | `12` | `betmexico_config.py` |
| `SMART_FILTER_BALANCE_THRESHOLD` | `10.0` | `betmexico_config.py` |
| `FILTER_RECENT_MINUTES` | `10` | `betmexico_config.py` |
| `FILTER_RECENT_WAIT_MINUTES` | `10` | `betmexico_config.py` |
| `FILTER_DAILY_LIMIT` | `3` | `betmexico_config.py` |
| `FILTER_DAILY_WAIT_HOURS` | `3` | `betmexico_config.py` |
| `LOGO` | `"┏ ◍ B🤖T ━┓
  chk

"` | `betmexico_config.py` |
| `BETMEXICO_PAYMENTS_URL` | `"https://paymentsapi.betmexico.mx"` | `betmexico_deposit.py` |
| `PROCESSORPAY_URL` | `"https://processorpay.com/sanval/api/IframeGames/makePayment"` | `betmexico_deposit.py` |
| `TXN_STATUS_SUCCESS` | `6` | `betmexico_payment_analyzer.py` |
| `TXN_STATUS_PENDING` | `0` | `betmexico_payment_analyzer.py` |
| `TXN_STATUS_FAILED` | `-4` | `betmexico_payment_analyzer.py` |
| `TXN_TYPE_DEPOSIT` | `1` | `betmexico_payment_analyzer.py` |
| `GATEWAY_CARD` | `1` | `betmexico_payment_analyzer.py` |
| `TXN_TYPE_MAP` | `{0: "⬇️", 1: "⬆️"}` | `betmexico_utils.py` |
| `WABOX_STRIPE_PK` | `"pk_live_WQNz0qa1BmBu47grZwTpj8BR"` | `card_checker.py` |
| `UTOPIA_CACHE_TTL_SEC` | `1800` | `card_checker.py` |
| `BETMEXICO_PAYMENTS_API` | `"https://paymentsapi.betmexico.mx"` | `clabe_fetch.py` |
| `BEGIN_DEPOSIT_PATH` | `"/api/stp/BeginDeposit"` | `clabe_fetch.py` |
| `DEP_MAX_PER_TXN` | `499.0` | `deposits.py` |
| `DEP_MAX_24H` | `1499.0` | `deposits.py` |
| `AUTOLOCK_HOURS_SINGLE` | `2` | `deposits.py` |
| `AUTOLOCK_HOURS_MULTI` | `2` | `deposits.py` |
| `AUTOLOCK_HOURS_SCHEDULED` | `4` | `deposits.py` |
| `BEGIN_MAX_ATTEMPTS` | `3` | `deposits.py` |
| `BEGIN_RETRY_BACKOFF_SEC` | `6` | `deposits.py` |
| `RATE_LIMIT_COOLDOWN_MIN` | `45` | `deposits.py` |
| `SCHED_MAX_TRANSIENT_RETRIES` | `4` | `deposits.py` |
| `SCHED_RETRY_BACKOFF_SEC` | `25` | `deposits.py` |
| `CARD_VELOCITY_MEMORY_MIN` | `30` | `deposits.py` |
| `CARD_VELOCITY_FREE_PAIR` | `2` | `deposits.py` |
| `CARD_VELOCITY_COOLDOWN_SEC` | `60` | `deposits.py` |
| `MM_COOLDOWN` | `45` | `deposits.py` |
| `MM_CARD_COOLDOWN` | `5` | `deposits.py` |
| `MM_MAX_ACCOUNT_FAILS` | `2` | `deposits.py` |
| `MM_MAX_CARD_FAILS` | `1` | `deposits.py` |
| `MM_MAX_ACCOUNTS_PER_CARD` | `1` | `deposits.py` |
| `MM_MAX_PAIR_TRANSIENT` | `4` | `deposits.py` |
| `MM_MAX_LOGIN_RETRIES` | `2` | `deposits.py` |
| `CAP_PER_OPERATOR_10MIN` | `9999` | `prewarm.py` |
| `ACCOUNT_FRESH_MINUTES` | `30` | `prewarm.py` |
| `ACCOUNT_DAILY_LIMIT` | `3` | `prewarm.py` |
| `REFRESH_PARALLEL` | `2` | `prewarm.py` |
| `CAPMONSTER_MIN_BALANCE` | `5.0` | `prewarm.py` |
| `BALANCE_FRESH_SEC` | `5 * 60` | `prewarm.py` |
| `TASK_TIMEOUT_SEC` | `25` | `prewarm.py` |
| `INITIAL_MAP` | `"""\` | `scripts/gen_map.py` |
| `INITIAL_MAP_DEEP` | `"""\` | `scripts/gen_map.py` |
| `TXN_STATUS_SUCCESS` | `6` | `shared/betmexico_payment_analyzer.py` |
| `TXN_STATUS_PENDING` | `0` | `shared/betmexico_payment_analyzer.py` |
| `TXN_STATUS_FAILED` | `-4` | `shared/betmexico_payment_analyzer.py` |
| `TXN_TYPE_DEPOSIT` | `1` | `shared/betmexico_payment_analyzer.py` |
| `GATEWAY_CARD` | `1` | `shared/betmexico_payment_analyzer.py` |
| `A_NO_FAIL_DAYS_MIN` | `60` | `shared/betmexico_payment_analyzer.py` |
| `A_MAX_TOTAL_FAILS` | `3` | `shared/betmexico_payment_analyzer.py` |
| `A_MAX_BIGFAIL_SESS` | `0` | `shared/betmexico_payment_analyzer.py` |
| `D_RECENT_FAIL_DAYS` | `14` | `shared/betmexico_payment_analyzer.py` |
| `D_MASSACRE_COUNT` | `3` | `shared/betmexico_payment_analyzer.py` |
| `C_DEEP_REST_DAYS` | `90` | `shared/betmexico_payment_analyzer.py` |
| `SCORE_FLOOR` | `{"A": 80, "B": 60, "C": 40, "D": 0}` | `shared/betmexico_payment_analyzer.py` |
| `SCORE_CEIL` | `{"A": 100, "B": 79, "C": 59, "D": 39}` | `shared/betmexico_payment_analyzer.py` |
| `PAYMENTS_API` | `"https://paymentsapi.betmexico.mx"` | `withdrawals.py` |
| `TRANSACTIONS_BY_USER_PAGE_SIZE` | `50` | `withdrawals.py` |
| `DEFAULT_BATCH_AMOUNT` | `200.0` | `withdrawals.py` |
| `BATCH_WITHDRAWAL_COOLDOWN_SEC` | `30.0` | `withdrawals.py` |
<!-- GEN:end:constantes -->

---

## Variables de entorno `[AUTO]`

<!-- GEN:start:env -->
| Variable | Default | Definida en |
|----------|---------|-------------|
| `BETMEX_DB` | `os.getenv("DB_PATH", "/data/betmexico_accounts.db" if (os.name != "nt" and Path("/data/betmexico_accounts.db"` | `betmexico_db.py` |
| `BMX_BOT_TOKEN` | `"8516175452:AAGz_PCh9Oq3D9l5DZtCzgdU5ObAJH-b1Gs"` | `betmexico_config.py` |
| `BMX_CAPMONSTER_KEY` | `""` | `betmexico_login_api.py` |
| `BMX_CAPSOLVER_KEY` | `""` | `betmexico_login_api.py` |
| `BMX_RECAPTCHA_SITEKEY` | `"6Lcz348mAAAAACAn9C2YDf2GT7Rd2UVqhGdWeVc4"` | `betmexico_login_api.py` |
| `BMX_WEB_URL` | `"https://botmexico.com.mx"` | `betmexico_utils.py` |
| `CAPTCHA_HUB_URL` | `"http://captcha-hub:8889"` | `betmexico_login_api.py` |
<!-- GEN:end:env -->

---

## Cambios recientes `[AUTO]`

<!-- GEN:start:recientes -->
| Hash | Mensaje |
|------|---------|
| `592945d` | feat: regla de oro 1:1 de tarjetas casadas, cooldown 45s por cuenta y saneamiento cuentas 429 DEAD |
| `71e866c` | fix(auto_deposit): rotacion continua de flota LIVE, piso 2 procesos reales y umbral retiro 100 pesos |
| `45587c2` | fix(auto_deposit): desbloquear cuentas con withdrawal_ready=1 si saldo <  y ajustar ventana 1h en tests |
| `e778a69` | feat(auto_deposit): scheduler continuo, afinidad bin corona y suite canonica bet |
| `16afd94` | chore(reorg): mover 35 tests a tests/, purgar DBs fantasma y alinear canvas |
| `92ed3a1` | skills: suite oficial obsidian instalada en botmex-dashboard |
| `7a9bb1e` | docs(session): sync NEXT-SESSION with latest deposit unlock and UI transparency fixes |
| `9cbb7af` | fix(deposits): unlock non-approved cards, bypass SA velocity check and surface real error details in UI |
| `73888f2` | docs(vault): reubicar mapas Canvas en la raíz del vault BotMex |
| `60c797e` | docs(canvas): agregar arquitectura visual soberana BotMex (Canvas N0, N1, Cambios e HTML interactivo) |
| `c443558` | docs(meta): actualizacion de NEXT-SESSION, .gitignore y mapa logico de flujos |
| `0ffc28d` | fix(deposits): regla canónica anti-mezcla de tarjetas sobre saldo fresco (<24h / >=100) |
<!-- GEN:end:recientes -->

---

## Logs `[MANUAL]`

| Log | Path (container) | Rotación |
|-----|-----------------|----------|
| Dashboard principal | `/data/logs/dashboard.log` | 10 MB × 3 |
| Tail en vivo | `GET /api/logs/stream` (SSE) | — |
| Logger raíz | `betmexico.dashboard` | `app.py` L47 |

---

## Directorios críticos `[MANUAL]`

| Path (container) | Propósito |
|-----------------|-----------|
| `/data/betmexico_accounts.db` | BD SQLite principal (compartida con bot TG) |
| `/data/logs/` | Log files persistentes (volumen Docker) |
| `static/` | Frontend: index.html, app.js, style.css |
| `docs/` | Documentación operativa completa |
| `infra/` | Dockerfile + docker-compose.yml |
| `shared/` | Módulos compartidos con bot Telegram |

---

## Docs de referencia `[MANUAL]`

| Doc | Qué tiene |
|-----|-----------|
| `docs/ARCHITECTURE.md` | Esquema BD, flujos, decisiones de diseño |
| `docs/ENDPOINTS.md` | Endpoints completos con params y ejemplos |
| `docs/AUDIT.md` | Estado por función (✅ ❌ ⚠️ 🔵 ❓) |
| `docs/ERRORS.md` | Errores conocidos: síntoma / causa / fix |
| `docs/BIN_THRESHOLDS.md` | Thresholds por BIN (límites $/24h, # txns, 3DS vs rechazo) — inteligencia de tarjetas |
| `docs/SSE_EVENTS.md` | Catálogo de eventos SSE (kind, payload) |
| `DEPLOY.md` | Deploy a KVM4 |
| `MAP_DEEP.md` | Mapa de funciones por módulo (rangos de líneas) |

---

## Bóveda — código canónico protegido `[MANUAL]`

> Si algo se rompe en el repo activo, aquí está la versión protegida para restaurar.
> **No modificar la Bóveda** — es de solo lectura. Copiar al repo y modificar ahí.

**Path absoluto (Dropbox local):** `C:\Users\rober\Dropbox\TESTING DEV\repos\Boveda\`
**Path relativo desde repos/:** `../Boveda/` (o `Boveda/` si estás parado en `repos/`)

| Archivo en Bóveda | Descripción |
|-------------------|-------------|
| `Boveda/Ruthopia/RGates/telcel_cipher_v1.0.py` | Cipher canónico Telcel v1.0 (Ruthopia/RGates) |
| `Boveda/Ruthopia/RGates/wabox_bypass_v1.0.py` | Bypass WABox v1.0 (Ruthopia/RGates) |
| `Boveda/BetMexico/` | ⚠️ **PENDIENTE** — carpeta no creada aún. Ver nota abajo. |

**BetMexico Dashboard — qué guardar en Bóveda (pendiente de hacer):**
Cuando se trabaje el backend en la sesión correspondiente, crear:
```
Boveda/BetMexico/deposits/          deposits_vX.Y.py      (motor _run_deposit + captcha pool)
Boveda/BetMexico/analyzer/          betmexico_payment_analyzer_vX.Y.py  (Algoritmo V10)
Boveda/BetMexico/proxy/             proxy_pool_vX.Y.py    (call_with_proxy_failover)
```
Criterio: guardar cuando un módulo alcanza un estado estable y probado que no queremos perder.

**Estructura general:** `Boveda/<proyecto>/<módulo>/<archivo_vX.Y.py>` — versionado explícito en nombre.

---

## Notas de sesión `[MANUAL]`

<!-- Apuntes rápidos de sesión activa — borrar entre sesiones -->
