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
| Modificar endpoints HTTP de depósito | `web_routes_deposits.py` | FastAPI router |
| Modificar flujo de misiones (batch/scheduled) | `web_routes_missions.py` | 803L, leer reglas al inicio del archivo |
| Modificar prewarm | `prewarm.py` + `web_routes_prewarm.py` | |
| Agregar endpoint nuevo | `web_routes_X.py` + registrar en `app.py` | Grep `include_router` en app.py |
| Cambiar pool de proxies / failover | `proxy_pool.py` | `call_with_proxy_failover` es la API recomendada |
| Cambiar lógica de grading | `web_grading.py` + `shared/betmexico_payment_analyzer.py` | Algoritmo V10 |
| Cambiar autenticación / sesiones | `auth.py` + `web_auth.py` | |
| Ver logs en vivo (endpoint) | `web_routes_logs.py` | Lee `/data/logs/dashboard.log` |
| Modificar watchdog de balance | `web_watchdog.py` | Loop background |
| Cambiar esquema BD | `app.py` → `_migrate()` | Migraciones aditivas solamente |
| Agregar evento SSE | `app.py` → `_broadcast()` + `docs/SSE_EVENTS.md` | |
| Cambiar caps duros de depósito | `deposits.py` L28–L35 | DEP_MAX_PER_TXN, DEP_MAX_24H, AUTOLOCK_HOURS_* |
| Analizar si una tarjeta/pasarela está quemada | `shared/betmexico_payment_analyzer.py` | Algoritmo V10 |
| Ver estado funcional de features | `docs/AUDIT.md` | ✅❌⚠️🔵❓ |
| Ver errores conocidos + fix | `docs/ERRORS.md` | |
| Deploy a KVM4 | `DEPLOY.md` + `docs/protocols/deploy-protocol.md` | |
| Endpoints completos con params | `docs/ENDPOINTS.md` | |
| Mapa de funciones dentro de un módulo | `MAP_DEEP.md` | Solo cuando vas a navegar código interno |

---

## Flujos principales `[MANUAL]`

### Depósito único
```
web_routes_deposits.py → deposits.py (_run_deposit)
  → betmexico_login_api (JWT/login)  [dep del bot, runtime import]
  → proxy_pool.py (call_with_proxy_failover)
  → CapMonster API (reCAPTCHA v3)
  → BetMexico API: BeginDeposit → makePayment → verify
  → web_grading.py (recalc_grade_from_db)
  → app.py _broadcast() → SSE → frontend
```

### Misión batch (matchmaker)
```
web_routes_missions.py → deposits.py _run_deposit (cuenta×tarjeta)
  max 5 cuentas × 5 tarjetas · gap aleatorio 3-8s
  APROBADA → vincular tarjeta↔cuenta
  Rechazo específico (TARJETA_INVALIDA/INSUF/EXPIRED) → marcar tarjeta, siguiente
  Gateway 5xx ×2 → PAUSE TOTAL
```

### Misión programada (scheduled)
```
web_routes_missions.py → loop 60s → deposits.py _run_deposit
  APROBADO → completed
  Rechazo → STOP (no reintentar, requiere override manual)
  Captcha pool prefetchea tokens; TOKEN_MAX_AGE=55s
```

### Prewarm
```
web_routes_prewarm.py → prewarm.py
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
| 5 | `create_task(gather())` crashea Py3.11+ | Bug asyncio en multi-depósito | Fix en `web_routes_deposits.py` |
| 6 | BANK_REJECTED ≠ error de captcha | BANK_REJECTED = banco rechazó la tarjeta, no el captcha | No reintentar en BANK_REJECTED |
| 7 | LitPort falla 0% | Reputación IP baja para BetMexico | Excluido via `_EXCLUDED_PROXY_HOSTS` en `proxy_pool.py` |

---

## Módulos `[AUTO métricas / MANUAL propósito]`

> Edita la columna **Propósito** directamente — el script la preserva al regenerar.

<!-- GEN:start:modulos -->
| Módulo | L# | Logger | Propósito |
|--------|----|---------|-----------| 
| `app.py` | 2423 | `betmexico.dashboard.sse` | App Flask principal: config, BD SQLite, rutas base, bus SSE, KPIs/admin, watchdog init |
| `auth.py` | 164 | `—` | Core de autenticación: sesiones, hashing de passwords, decorador `require_session` |
| `autoexclusion.py` | 177 | `betmexico.dashboard.autoexclusion` | _[completar]_ |
| `conftest.py` | 79 | `—` | Fixtures pytest (BD en memoria, cliente test, sesión de prueba) |
| `deposits.py` | 2180 | `betmexico.dashboard.deposits` | Motor de depósitos: `_run_deposit`, captcha pool, retry-con-failover, caps duros |
| `login_orchestrator.py` | 300 | `betmexico.dashboard.login_orch` | _[completar]_ |
| `prewarm.py` | 692 | `betmexico.dashboard.prewarm` | Pre-carga JWT + balance para cuentas — acelera depósitos. Deps del bot en runtime |
| `proxy_pool.py` | 295 | `dashboard.proxy_pool` | Pool de proxies: rotación, `call_with_proxy_failover`, exclusión de hosts quemados |
| `scripts/gen_map.py` | 486 | `—` | Regenerador de MAP.md + MAP_DEEP.md — AST + git log. Corre en pre-commit hook |
| `scripts/recalc_grades.py` | 131 | `—` | Utilería dev: recalcular grades de todas las cuentas desde BD |
| `shared/betmexico_payment_analyzer.py` | 578 | `—` | Algoritmo V10: clasifica pasarela/tarjeta A=sana/B=recuperando/C=lenta/D=quemada |
| `web_auth.py` | 138 | `betmexico.web.auth` | Endpoints HTTP de auth: login, logout, me, cambio de password |
| `web_grading.py` | 113 | `betmexico.web.grading` | Recalcula `grade` y `grade_score` de una cuenta desde BD (usa analyzer V10) |
| `web_routes_cards.py` | 136 | `betmexico.web.cards` | Endpoints CRUD de tarjetas — listar, agregar, eliminar |
| `web_routes_deposits.py` | 391 | `betmexico.web.deposit` | Endpoints HTTP del flujo de depósito: single, multi, scheduled start/stop |
| `web_routes_logs.py` | 98 | `betmexico.web.logs` | Endpoint `/api/logs`: lee `/data/logs/dashboard.log` y stream SSE en vivo |
| `web_routes_missions.py` | 803 | `betmexico.web.missions` | Endpoints de misiones batch y scheduled: crear, cancelar, estado, historial |
| `web_routes_notifications.py` | 111 | `betmexico.web.notif` | Endpoints de notificaciones push / alertas al operador |
| `web_routes_prewarm.py` | 260 | `betmexico.web.prewarm` | Endpoints HTTP de prewarm: start, cancel, status |
| `web_utils.py` | 243 | `betmexico.web.utils` | Helpers compartidos: _friendly_error, _normalize_ccexp, _build_proxy_url |
| `web_watchdog.py` | 276 | `betmexico.web.watchdog` | Loop background: refresca balance de cuentas LIVE cada N min, genera notificaciones |
<!-- GEN:end:modulos -->

---

## Constantes operacionales `[AUTO]`

<!-- GEN:start:constantes -->
| Constante | Valor | Módulo |
|-----------|-------|--------|
| `SESSION_TTL` | `86_400` | `auth.py` |
| `PERSISTENT_USERS` | `{"robertvs"}` | `auth.py` |
| `PERSISTENT_TTL` | `60 * 60 * 24 * 365 * 10` | `auth.py` |
| `DEP_MAX_PER_TXN` | `499.0` | `deposits.py` |
| `DEP_MAX_24H` | `1499.0` | `deposits.py` |
| `AUTOLOCK_HOURS_SINGLE` | `2` | `deposits.py` |
| `AUTOLOCK_HOURS_MULTI` | `2` | `deposits.py` |
| `AUTOLOCK_HOURS_SCHEDULED` | `4` | `deposits.py` |
| `BEGIN_MAX_ATTEMPTS` | `3` | `deposits.py` |
| `BEGIN_RETRY_BACKOFF_SEC` | `6` | `deposits.py` |
| `SCHED_MAX_TRANSIENT_RETRIES` | `4` | `deposits.py` |
| `SCHED_RETRY_BACKOFF_SEC` | `25` | `deposits.py` |
| `CARD_VELOCITY_MEMORY_MIN` | `30` | `deposits.py` |
| `CARD_VELOCITY_FREE_PAIR` | `2` | `deposits.py` |
| `CARD_VELOCITY_COOLDOWN_SEC` | `60` | `deposits.py` |
| `MM_COOLDOWN` | `5` | `deposits.py` |
| `MM_MAX_FAILS` | `2` | `deposits.py` |
| `MM_MAX_LOGIN_RETRIES` | `3` | `deposits.py` |
| `MM_MAX_BANK_REJECTS` | `2` | `deposits.py` |
| `CAP_PER_OPERATOR_10MIN` | `9999` | `prewarm.py` |
| `ACCOUNT_FRESH_MINUTES` | `30` | `prewarm.py` |
| `ACCOUNT_DAILY_LIMIT` | `3` | `prewarm.py` |
| `REFRESH_PARALLEL` | `8` | `prewarm.py` |
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
| `WEB_USERS` | `{k.lower(): v for k, v in WEB_USERS_RAW.items()}` | `web_auth.py` |
| `BETMEXICO_PAYMENTS_API` | `"https://paymentsapi.betmexico.mx"` | `web_routes_deposits.py` |
| `PROCESSORPAY_MAKE_PAYMENT_URL` | `"https://processorpay.com/sanval/api/IframeGames/makePayment"` | `web_routes_deposits.py` |
| `CAPMONSTER_ENDPOINT` | `"https://api.capmonster.cloud"` | `web_routes_prewarm.py` |
| `CAPMONSTER_ENDPOINT` | `"https://api.capmonster.cloud"` | `web_watchdog.py` |
<!-- GEN:end:constantes -->

---

## Variables de entorno `[AUTO]`

<!-- GEN:start:env -->
| Variable | Default | Definida en |
|----------|---------|-------------|
| `BMX_CAPMONSTER_KEY` | `"a9040840fdb3828ecc6090a6010afcad"` | `web_routes_missions.py` |
| `BMX_NO_PROXY` | `"0"` | `web_routes_deposits.py` |
| `BMX_WATCHDOG_INTERVAL_MIN` | `"90"` | `web_watchdog.py` |
<!-- GEN:end:env -->

---

## Cambios recientes `[AUTO]`

<!-- GEN:start:recientes -->
| Hash | Mensaje |
|------|---------|
| `0faf6c3` | docs(errors): causa del 406 = IPRoyal con IP fija (city) -> rotativo nacional (2026-05-29) |
| `2d469a8` | fix(proxy+multi): IPRoyal rotativo (no IP fija quemada) + reintentos de login en matchmaker |
| `7b8a195` | feat(proxy-health): mostrar salud del POOL EN USO (alive/total), no un proxy suelto |
| `eb4c3ba` | fix(proxy-health): chequear el pool ACTIVO, no LitPort excluido (falsa alarma 'caido') |
| `24ff785` | docs(errors): programado reintenta transitorios en vez de abortar (sesion 2026-05-29) |
| `951c449` | fix(programado): reintentar fallos transitorios en vez de abortar la mision |
| `e6c5220` | docs(errors): autoexclusion -> DEAD, captcha en programado, refresh post-deposito (sesion 2026-05-29) |
| `99d1523` | feat(autoexclusion): detectar autoexcluidas -> DEAD + mensaje explicito; refrescar movimientos post-deposito; cortar captcha en programado |
| `ff9044a` | fix(movimientos): horas propias salían +6h (UTC sin convertir a MX) |
| `78b4628` | feat(login): orquestación gentil (gentle_login) + fix matchmaker mata-cuentas |
| `3c31ca5` | docs(map): Bóveda BetMexico marcada pendiente + guía de qué guardar |
| `3ae9271` | docs(map): agregar Bóveda como sección en MAP.md |
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
