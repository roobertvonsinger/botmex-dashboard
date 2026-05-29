# Errores comunes + quick fixes

> Bitácora viva. Agregar entry cada vez que un error nuevo aparezca.

## Backend

### `[deps] bot init failed: No module named 'X'` al arrancar

**Síntoma**: container `betmexico-web` no arranca. Endpoints como `/api/deposits/multi/stream` devuelven **503 Service Unavailable**.

**Causa**: `app.py` importa módulos del bot Telegram (`betmexico_db`, `betmexico_login_service`, `web_routes_deposits`, etc.) que no están presentes en `/docker/betmexico/code/`.

**Diagnóstico**:
```
docker logs betmexico-web 2>&1 | grep "bot init failed"
```

**Fix**:
1. Identificar el módulo faltante en el traceback.
2. Buscar en `repos/botmex-dashboard/` (repo canónico). Si está allí: `pscp` a KVM4.
3. Si NO está en el repo: copiarlo del **bot Telegram** (`Proyectos/BetMexico/Telegram/`) AL REPO PRIMERO (no directo al deploy), commit, push, luego pscp.
4. Restart: `docker compose restart web`.

**Histórico**: pasó 2026-05-11. Faltaban `web_routes_*.py`, `web_utils.py`, `web_watchdog.py`, `web_auth.py`, `tzdata` package.

---

### Spike de 406 FAILURE_IN_CAPTCHA en login (depósitos + actualización de cuentas)

**Síntoma**: muchos logins fallan con `[API] Status: 406` / `RETRY_CAPTCHA`. Tasa real por intento subió 0% (05-23) → 24% (05-26) → 48% (05-27). Pasa en updates y depósitos.

**Causa raíz (medida, NO supuesta)**: BetMexico endureció su antifraude ~25-may (frontend build `bmx-prod-v26.5.25` agregó reCAPTCHA **v3**). El 406 es rechazo por **reputación de IP / score**, disfrazado de fallo de captcha. NO fue cambio nuestro (`betmexico_login_api.py` intacto desde 11-may). El commit `6908af3` (rotación agresiva de 5 IPs) lo empeoró: martillar **quema IPs**.

**Descartado con datos** (NO reintentar): migrar a v3 (0% aun con navegador real Playwright); token v2 declarado `captchaVersion:"v3"` (0%); misma-IP solve+submit (10%, peor); reportar a CapMonster (riesgo de ban, los 406 no son tokens malos).

**Fix**: quedarse en v2; **dejar de martillar** y portar la estrategia gentil del bot (`betmexico_check.py`: jitter + throttle por `captcha_fail_streak` + backoff 403/429); resolver v2 proxyless + submit por sticky residencial MX fresco; reintentos gentiles (p≈50%/intento fresco → 4 intentos ≈ 94%). **Plan completo: `docs/plans/login-orchestration-rework.md`.**

---

### Movimientos del modal: las horas "nuestras" salían +6h (corregido 2026-05-28)

**Síntoma**: en el modal de detalle (sección MOVIMIENTOS), las transacciones propias (ícono rayo, `source=dashboard`) aparecían 6 horas adelante vs la página real de BetMexico. Ej: depósito mostrado a las 08:09 cuando la página lo muestra a 02:09. Las de BetMexico (`source=betmex`, globo) salían bien → "algunas bien, otras no".

**Causa raíz (verificada con BD prod, NO supuesta)**: `deposit_attempts.created_at` se guarda en **UTC naïve** (`'2026-05-28 08:09:43'`, confirmado: ≈ `date -u` del host, no la hora CST del container). `account_transactions.txn_date` de BetMexico ya viene en **hora MX naïve** (confirmado: SPEI en BD coinciden con la franja de la página). El frontend (`parseTs` en `app.js`) trata **todo** timestamp naïve como hora local MX → las UTC salían +6h. Además el sort por `when` mezclaba UTC y MX → orden inconsistente entre fuentes.

**Fix**: `app.py` (endpoint de detalle, armado de `movimientos`) convierte SOLO `created_at` de UTC→MX con `zoneinfo America/Mexico_City` (fallback `-6h`; MX no tiene DST desde 2022) antes de mandarlo en `when`. `txn_date` queda intacto (ya MX). Helper `_utc_to_mx()`. Bonus: el sort vuelve a ser correcto (ambas fuentes en MX).

---

### El matchmaker marca cuentas BUENAS como DEAD cuando falla el login (corregido 2026-05-28)

**Síntoma**: cuentas válidas quedan `status='DEAD'` con `dead_reason='LOGIN_FAILED'` y ya no se reintentan.

**Causa raíz**: `deposits.py` (matchmaker `multi_stream`) metía `LOGIN_FAILED` en la misma rama que `AUTOEXCLUSION`/`KYC_PENDING` y persistía `status='DEAD'` en BD.  
Pero `LOGIN_FAILED` = 406/captcha/proxy = fallo de **nuestra infraestructura**, nunca de la cuenta.  
Agravante: `LOGIN_FAILED` es el ÚNICO código que el matchmaker puede producir (`AUTOEXCLUSION`, `KYC_PENDING`, `3DS_UNDETECTED`, `SHADOW_BAN?` nacen en `web_routes_deposits.py` y nunca llegan a `multi_stream`). O sea esa rama mataba cuentas buenas el 100% de las veces que se activaba. Con la tasa de 406 alta (may 2026), a escala masacraba.

**Daño documentado**: 5 cuentas marcadas DEAD innecesariamente (11–15 may 2026):
- `fcojavii2662@gmail.com`
- `azul_171175@live.com`
- `memo.teo10@gmail.com`
- `danoscene@gmail.com`
- `silcas22@gmail.com`

**Diagnóstico**:
```bash
sqlite3 /data/betmexico_accounts.db \
  "SELECT email, dead_reason, dead_at FROM accounts WHERE status='DEAD' AND dead_reason='LOGIN_FAILED'"
```

**Fix aplicado** (`deposits.py` L1550-1558, 2026-05-28):
- `LOGIN_FAILED` ya NO toca BD ni `dead_reason`.  
- Emite evento SSE `type:'login_retry'` con `{email, code, tail, attempt}`.  
- Marca `acc["login_retry"]=True` y `acc["fail_count"]=MM_MAX_FAILS` en memoria (solo sale del run actual — no persiste).  
- `3DS_UNDETECTED` / `SHADOW_BAN?` salieron de la rama DEAD → caen en el `else` genérico (strike a tarjeta + cuenta, no DEAD).  
- Solo `AUTOEXCLUSION` y `KYC_PENDING` siguen marcando `status='DEAD'` persistente.

**Regla de Robert (2026-05-28, no negociable)**:  
Una cuenta solo muere por (1) 401 credenciales/lock definitivo, (2) KYC_PENDING, (3) AUTOEXCLUSION.  
Todo lo demás — incluido cualquier LOGIN_FAILED (406/captcha/proxy/BAN-429/timeout) — se convierte en REINTENTOS, jamás DEAD.

**Recovery SQL ejecutado en prod KVM4** (backup previo en `/docker/betmexico/data/backups/`):
```sql
UPDATE accounts
SET status='LIVE', dead_reason=NULL, dead_at=NULL
WHERE status='DEAD' AND dead_reason='LOGIN_FAILED';
-- Filas afectadas: 5
```

**Histórico**: detectado 2026-05-28. Raíz introducida en el diseño inicial del matchmaker. Ver también `docs/plans/login-orchestration-rework.md` §4.

---

### Las tarjetas no se persisten en `account_cards` después de un depósito aprobado

**Síntoma**: depósito BANK_APPROVED en `deposit_attempts` pero `account_cards` para esa cuenta = 0 rows. El panel detalles muestra "Sin tarjetas guardadas".

**Causa raíz**: el módulo `betmexico_db.py` usa **ruta relativa** (`DB_FILE = Path("betmexico_accounts.db")`) → resuelve a `/app/betmexico_accounts.db` (BD fantasma) dentro del container, mientras la BD real está en `/data/betmexico_accounts.db`.

**Diagnóstico**:
```
docker exec betmexico-web find / -name 'betmexico_accounts.db' 2>/dev/null
```
Si ves 2 archivos → la fantasma está creándose y desviando escrituras.

**Fix** (aplicado 2026-05-11):
- `Proyectos/BetMexico/Telegram/betmexico_db.py:26` debe ser:
  ```python
  import os as _os
  DB_FILE = Path(_os.environ.get("BETMEX_DB", "betmexico_accounts.db"))
  ```
- `.env` debe tener `BETMEX_DB=/data/betmexico_accounts.db`.
- Borrar la fantasma: `docker exec betmexico-web rm -f /app/betmexico_accounts.db` (verificar antes que esté vacía o tenga solo datos huérfanos).

---

### Tarjetas no se guardan en `account_cards` tras APPROVED por single moderno / multi / scheduled (2026-05-25)

**Síntoma**: el operador deposita exitosamente con una tarjeta nueva. La próxima vez que abre la cuenta, la tarjeta NO aparece en "💳 Tarjetas guardadas" y tiene que volverla a pegar manualmente. Solo persiste en `deposit_attempts.card_pipe`, no en `account_cards`.

**Causa raíz**: tres endpoints distintos comparten el wrapper `_run_deposit_with_phases` ([deposits.py:490](../deposits.py)):
- `POST /api/deposits/execute-stream` (single moderno)
- `POST /api/deposits/multi/stream` (matchmaker)
- `POST /api/deposits/scheduled/create` (programado)

Ese wrapper **NO** llama a `db.register_card_to_account`. Solo el legacy `_run_deposit` del bot (usado por `/api/deposits/execute` legacy, no consumido por el UI moderno) lo hace. El persister centralizado `_record_attempt` ([deposits.py:391](../deposits.py)) escribía en `deposit_attempts` con `card_pipe` pero ignoraba `account_cards`. El AUDIT viejo marcaba esa fila como ✅ pero era falso para los 3 endpoints modernos.

**Fix aplicado** (2026-05-25):
- Bloque dedicado en `_record_attempt` ([deposits.py:441-477](../deposits.py)):
  - Si `status == "approved"` y hay `card_pipe`: parsea pipe → `(cc_num, cc_exp, cc_cvv)`, busca password de la cuenta vía `app.db()`, resuelve nombre del operador desde `web_auth.WEB_USERS_RAW`, llama `db.register_card_to_account` (idempotente por UNIQUE card_number).
  - 3DS_REQUIRED NO guarda (la tarjeta no se acreditó). Regla operativa Robert: solo APPROVED real cuenta como tarjeta marriage.
  - Cubre los 3 endpoints en un solo punto.

**Diagnóstico**:
```bash
docker exec betmexico-web sqlite3 /data/betmexico_accounts.db \
  "SELECT a.email, a.cards_count, COUNT(da.id) as approved_attempts FROM accounts a
   LEFT JOIN deposit_attempts da ON da.account_email=a.email AND da.status='approved'
   GROUP BY a.email HAVING approved_attempts > 0 AND a.cards_count = 0"
```
Si hay rows → cuentas que tenían approved attempts pero 0 cards (regresión histórica). Para retro-poblar: correr un script que recorra `deposit_attempts` con status=approved y haga register_card_to_account por cada row.

---

### `_sse_queues` siempre vacío durante broadcasts del scheduled — clients=0 fantasma (2026-05-26)

**Síntoma**: el frontend SE conecta al SSE (`/api/events`), el browser reporta la conexión activa, pero NUNCA recibe los eventos `scheduled_*` del schedule que disparó. El watchdog 30s del frontend dispara la alerta "⚠️ Sin señal del backend".

**Causa raíz**: `app.py` se cargaba **DOS VECES** en `sys.modules` con nombres distintos:
- `__main__` — instancia creada cuando uvicorn arranca con `python web/app.py` (entry point del Dockerfile).
- `app` — instancia creada cuando `deposits.py`, `prewarm.py`, etc. hacen `from app import _broadcast`. Python no encuentra `app` en sys.modules y reimporta el archivo.

Aunque ambas instancias apuntan al mismo `/app/web/app.py`, son módulos Python distintos con namespaces independientes. Cada uno tiene su propio `_sse_queues` (list separada).

**Consecuencia**: El endpoint `/api/events` está registrado en la app FastAPI de `__main__`, así que los clientes SSE se agregan a `__main__._sse_queues`. Pero `_broadcast` invocado desde `deposits.scheduled_create.loop()` empuja a `app._sse_queues` (otra lista, siempre vacía). Los eventos se "broadcastean" pero ningún cliente está suscrito a esa queue.

Verificación runtime:
```python
import app as a1
import web.app as a2  # o cualquier path que encuentre el mismo file
assert a1 is a2  # FALSE — son módulos distintos
assert a1._sse_queues is a2._sse_queues  # FALSE — listas distintas
```

**Fix aplicado** (2026-05-26, [app.py:18](../app.py)): alias en sys.modules apenas arrancamos como __main__:
```python
if __name__ == "__main__":
    sys.modules.setdefault("app", sys.modules[__name__])
```

Cuando `deposits.py` luego hace `from app import _broadcast`, Python encuentra `app` ya en sys.modules y reutiliza la instancia de `__main__`. Una sola lista `_sse_queues`, todos los broadcasts encuentran clientes.

**Diagnóstico que confirmó el bug**: instrumenté `_broadcast` y `_sse_generator` con `id(q)` (identidad de la queue) y `all_ids = [id(x) for x in _sse_queues]`. Pre-fix los logs mostraban:
- Conexión: `q_id=134005432697216 all_ids=[134005432697216]`
- Broadcast (mismo proceso, segundos después): `clients=0 q_ids=[]`

El cliente seguía conectado al server (no había log de desconexión), pero el `_broadcast` veía otra lista vacía. Post-fix los `q_ids` del broadcast coinciden con el `q_id` del client conectado.

---

### Modal Programado se queda "Preparando intento 1 de 10…" por 30s+ sin actualizar (2026-05-25)

**Síntoma**: el operador lanza una misión Programada de N depósitos. El panel premium muestra `0/N` con el texto "Preparando intento 1 de N…" y NO cambia durante medio minuto o más. El depósito sí está corriendo en backend (los `deposit_attempts` se persisten), pero el feed live del modal no responde.

**Causa raíz (dos componentes)**:

1. **Pool warm-up invisible**: `scheduled_create.loop()` espera `await pool.start_factory()` y `pool.prefetch(1)` antes de iterar — 5-15s sin ningún `phase_cb` emitido. El frontend no tiene señal de vida durante esa ventana → operador ve "Preparando…" estático y asume backend muerto.

2. **Race condition de `sched_id`**: si el captcha pool ya estaba warm, el primer `phase_cb("login_start", ...)` puede dispararse en <100ms — antes de que la respuesta HTTP de `/scheduled/create` haya retornado al frontend y `_schedShow(sched_id, ...)` haya seteado `_schedActive`. La guarda en `_schedOnPhase` (`if (!_schedActive ...) return`) descartaba silenciosamente el evento. Los siguientes eventos SÍ entraban, pero el operador veía el primer iter sin transición visual.

**Fix aplicado** (2026-05-25):

Backend ([deposits.py:1610-1625](../deposits.py)):
- Heartbeat `kind:scheduled_started` broadcasted **inmediatamente** dentro de `loop()`, ANTES de `pool.start_factory()`. Confirma backend vivo en <50ms.

Frontend ([static/app.js:3545-3625](../static/app.js)):
- **Buffer**: si `scheduled_phase/scheduled/scheduled_aborted/scheduled_cancelled` llega con `_schedActive=null`, se acumula en `_schedPendingEvents` y se reproduce desde `_schedShow` cuando el state está listo.
- **Hint rotator** (`_schedHintTimer`): durante el pool warm-up el texto cicla cada 3.5s: `⚡ Calentando captcha pool` → `🔑 Solicitando token CapMonster` → `🚀 Levantando worker` → `⏳ Esperando primer login`. Se cancela al recibir el primer `scheduled_phase` real.
- **Watchdog 30s** (`_schedWatchdogTimer`): si no llega ningún `scheduled_phase` en 30s desde `_schedShow`, alerta al operador: `⚠️ Sin señal del backend (>30s). La misión sigue corriendo, pero el feed live no responde.` Permite distinguir "pool lento" de "SSE muerto" en producción.

**Diagnóstico runtime**:
```js
// En consola del navegador durante un Programado:
console.log('_schedActive:', _schedActive, 'pending:', _schedPendingEvents.length);
```
- Si `_schedActive=null` y misión activa → race fix no corrió (revisar versión deploy).
- Si pending > 0 al final → buffer ayudó, eventos huérfanos.

---

### Cuentas muestran balance/depósito/check desactualizados después del prewarm

**Síntoma**: pulsar "Actualizar visibles" consume Capsolver pero el dashboard sigue mostrando balance viejo, sin fecha de último depósito y `last_checked_at` que no avanza.

**Causa (3 bugs combinados)**:

1. **`_db_upsert_balance` incompleto** (bug en versión desplegada): sólo actualizaba `balance_real` y `balance_total` (que podía llegar NULL si la API no lo calcula). Nunca escribía `balance_bonos`, `last_deposit_amount`, ni `last_deposit_date`.

2. **Capsolver gastado en vano**: `pool.prefetch(1)` resolvía un captcha ANTES de chequear si el JWT seguía en cache. Si el JWT era válido, el captcha prefetchado se descartaba.

3. **`ok=True` falso cuando `details=None`**: si el fetch fallaba (timeout 18s, API sin datos, JWT rechazado), `_run_prewarm` igual retornaba `{"ok": True}` → frontend leía el row viejo como "actualizado". `last_checked_at` nunca se escribía → anti-spam (30min) no detectaba el intento → retry inmediato.

**Fix aplicado** (`prewarm.py`, 2026-05-13):
- `_db_upsert_balance`: calcula `balance_total = bal_real + bal_bonos`, escribe `balance_bonos`, escribe `last_deposit_*` cuando la API los trae válidos.
- `_run_prewarm`: chequea `_db_get_jwt_cache` ANTES de `make_pool/prefetch`. JWT vigente → fetch directo, 0 Capsolver. JWT de cache rechazado por BetMexico → invalida el cache (`jwt_token=NULL`) para forzar login real la próxima vez.
- `_run_prewarm`: retorna `ok=False` cuando `details is None`. Siempre escribe `last_checked_at` (incluso en timeout) para activar el anti-spam.

**Diagnóstico rápido**:
```bash
docker exec betmexico-web sqlite3 /data/betmexico_accounts.db \
  "SELECT phase, COUNT(*) FROM process_log WHERE process_type='prewarm' GROUP BY phase"
```

---

### `tzdata` falta / `apt-get install tzdata` bloquea el build

**Síntoma**: `ZoneInfoNotFoundError: 'No time zone found with key America/Mexico_City'` al cargar `betmexico_login_api.py`. O `docker build` se queda colgado en `Configuring tzdata` esperando input.

**Causa**: imagen base `mcr.microsoft.com/playwright/python` **NO incluye** `tzdata` ni el módulo Python `playwright` por defecto.

**Fix**: el Dockerfile DEBE tener:
```dockerfile
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Mexico_City
RUN ln -fs /usr/share/zoneinfo/America/Mexico_City /etc/localtime && \
    apt-get update && apt-get install -y --no-install-recommends tzdata && \
    dpkg-reconfigure -f noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    ... \
    'tzdata' \
    'playwright>=1.49.0'
```

`DEBIAN_FRONTEND=noninteractive` es **obligatorio** o el build se cuelga.

---

### Container restart se queda en "Deactivating" mucho tiempo

**Síntoma**: `docker compose restart web` tarda más de 30s, status muestra "Restarting".

**Causa**: conexiones SSE abiertas (`/api/events`) bloquean el shutdown ordenado de uvicorn.

**Fix**:
```bash
docker compose kill -s SIGKILL web
docker compose up -d web
```

---

### `/api/deposits/multi/stream` 200 OK pero matchmaker no avanza

**Síntoma**: el endpoint responde, pero el frontend nunca recibe eventos en el `EventSource`.

**Causa**: pool de captcha falla en obtener tokens (CapMonster sin saldo o key inválida).

**Diagnóstico**:
```bash
curl -X POST https://api.capmonster.cloud/getBalance -H 'Content-Type: application/json' \
  -d '{"clientKey":"<KEY>"}'
```

**Fix**:
- Si balance < $5 → recargar
- Si error `ERROR_KEY_DOES_NOT_EXIST` → actualizar `.env` con nueva key

---

### Login a BetMexico devuelve 403 RATE_LIMITED después de varios intentos

**Síntoma**: log dice `[BAN] 403 Rate limit: <email>`. Login deja de funcionar para esa cuenta temporalmente.

**Causa**: BetMexico rate-limita IPs/cuentas que hacen muchos logins seguidos.

**Fix**:
- Esperar 10-30 minutos
- Rotar proxy: `POST /api/admin/refresh-proxy` (SA)
- Verificar que `betmexico_login_api` usa el proxy MX (sufijo `_country-mx` en proxy URL)

---

### Cuentas autoexcluidas se colaban como LIVE y fallaban con críptico `BEGIN_ERROR` (corregido 2026-05-29)

**Síntoma**: depósito (programado/single/matchmaker) sobre una cuenta autoexcluida fallaba en `gateway_begin` con `BEGIN_ERROR` en ~0–2s, sin avisar al operador qué pasó. La cuenta seguía apareciendo LIVE (como "basura" en la lista) y se reintentaba.

**Causa raíz (verificada con login fresco real, NO supuesta)**: la API de login de BetMexico (`/api/Session/login`) devuelve `isSuccess=True` + JWT **incluso para cuentas autoexcluidas** → `gentle_login` las clasifica `LIVE`. La restricción solo se manifiesta al depositar: `begin_deposit` (paymentsapi) devuelve `401 {"redirectLogin":true}`. El campo de autoexclusión SÍ viene en el perfil (`GET https://betmexico.mx/api/Users/{userId}` → `data.autoexclusion = {exclusionMonth, resumeExclusionDate}`), pero el extractor del bot (`fetch_account_details_parallel`) lo ignora.

**Fix aplicado** (commit `99d1523`, todo en el repo dashboard — el monorepo NO se tocó, solo se leyó):
- `autoexclusion.py` (nuevo): `check_autoexclusion(jwt, proxy)` consulta `/api/Users/{userId}` con el JWT que el dashboard ya tiene tras `gentle_login` y devuelve la info si `resumeExclusionDate` es futura. `mark_account_autoexcluded()` → `status='DEAD'`, `dead_reason='AUTOEXCLUSION hasta DD/MM/YYYY (N meses)'`.
- **Update** (`prewarm._run_prewarm`): gate tras login → autoexcluida pasa a DEAD y sale de la vista (`list_accounts` filtra `status='LIVE'`).
- **Depósito** (`deposits._run_deposit_with_phases`): gate tras login, ANTES de `begin_deposit` → `AUTOEXCLUSION` + DEAD + mensaje con fecha. Cubre los 3 flujos (comparten el wrapper). Fallback: un `401 redirectLogin` en `begin_deposit` re-verifica autoexclusión. Body crudo de `begin_deposit` ahora se loguea (antes se perdía).
- Frontend: misión abortada y feed muestran el `reason` explícito, no el code pelón.

**Regla de Robert (2026-05-29)**: autoexclusión = una de las 3 razones de muerte → DEAD es correcto y persistente.

**Diagnóstico**:
```bash
docker exec betmexico-web sqlite3 ... # (no hay sqlite3 en el container; usar python3)
docker exec betmexico-web python3 -c "import sqlite3;c=sqlite3.connect('/data/betmexico_accounts.db');print(c.execute(\"SELECT email,status,dead_reason FROM accounts WHERE dead_reason LIKE 'AUTOEXCLUSION%'\").fetchall())"
```

---

### Programado quemaba captcha toda la misión aunque reusara la sesión (corregido 2026-05-29)

**Síntoma**: una misión Programada (1 tarjeta, N reps, reuso de JWT) seguía resolviendo tokens CapMonster cada ~55s durante todos los minutos del run, aunque solo la iter 0 hace login.

**Causa raíz**: `scheduled_create.loop()` arranca `pool.start_factory()`, cuyo `_factory_loop` mantiene el pool lleno a `max_pool` indefinidamente: cada token expira a los `TOKEN_MAX_AGE=55s` y el factory lo regenera. Las iters 1..N reusan `session_jwt` (0 captcha), pero el factory seguía produciendo. Una misión de 9 reps (~9 min) resolvía ~9 tokens innecesarios.

**Fix** (`deposits.py`, commit `99d1523`): tras capturar la sesión en iter 0 (`session_jwt`), `await pool.stop()` (idempotente) y `pool=None`. El factory sólo vive durante el login inicial (donde sí se necesita para reintentos de `gentle_login`); después se apaga. 1 token por misión en vez de ~N.

---

### Movimientos/balance no se actualizaban tras un intento de depósito (corregido 2026-05-29)

**Síntoma**: tras depositar (aprobado o rechazado), el panel de detalle seguía mostrando movimientos/saldo viejos hasta picar "Actualizar visibles" manual.

**Causa raíz**: las transacciones solo se capturaban en el LOGIN (que ocurre ANTES del depósito) → el intento recién hecho nunca se reflejaba. En programado, las iters con reuso de sesión (`persist_login_data=False`) ni refrescaban.

**Fix** (`deposits.py`, commit `99d1523`): helper `_refresh_account_after_deposit()` corre al final de `_run_deposit_with_phases` (los 3 flujos): reusa el JWT del login (sin captcha) para `fetch_account_details_parallel(fetch_mode="full")` y persiste balance+txns+grade vía los persisters de `prewarm`. Emite SSE `account_refreshed`; el frontend repinta la fila y, si el detalle de esa cuenta está abierto, recarga los movimientos sin cerrar el panel. Costo: +2–5s por intento (sin captcha).

---

### El programado abortaba la misión entera ante fallos TRANSITORIOS (corregido 2026-05-29)

**Síntoma**: misiones programadas de N reps morían en la iter 1-2 con `✗ Misión abortada — BEGIN_ERROR` (504 Gateway Timeout) o `— LOGIN_FAILED` (406 FAILURE_IN_CAPTCHA), sin reintentar. Robert: *"¿por qué chingados se detiene si falla el login? eso ya lo habíamos ajustado"*.

**Causa raíz**: el loop del scheduled hacía `if not ok: scheduled_aborted; break` ante **cualquier** falla. El ajuste previo (commit `78b4628`) fue solo para el MATCHMAKER (no marcar DEAD por `LOGIN_FAILED`); el programado seguía abortando. Un `504` del gateway de pagos o un `406` de captcha — ambos **infraestructura NUESTRA, no la cuenta** — mataban la misión completa.

**Fix** (`deposits.py` + `static/app.js`, commit `951c449`):
- **`begin_deposit` con retry** (`_run_deposit_with_phases`, los 3 flujos): es PRE-COBRO (paso 1, antes de `submit_card`) → reintentarlo NO duplica cargos. Ante `50x`/`timeout`/`connection` reintenta `BEGIN_MAX_ATTEMPTS=3` con backoff 6s. `_is_transient_gateway_error()` excluye 401/redirectLogin (eso es sesión/autoexclusión).
- **Loop del programado reescrito (`for`→`while`)**: cuenta reps **EXITOSAS**. Ante fallo TRANSITORIO (todo lo que NO está en `SCHED_TERMINAL_RC`) reintenta la **misma rep** hasta `SCHED_MAX_TRANSIENT_RETRIES=4` con backoff `25s` (enfría IP en 406), **sin abortar**. Si la sesión reusada muere (401) reactiva el pool para re-login. Solo detienen razones REALES: `BANK_REJECTED`, `BANK_REJECTED_AFTER_APPROVE`, `3DS_REQUIRED`, `AUTOEXCLUSION`, `KYC_PENDING`, `LOGIN_DENIED`, `PENDING_NOT_APPLIED`, `DEPS_MISSING`.
- **Frontend**: evento `scheduled_retry` → panel muestra `🔁 Reintentando intento N (x/4)` + rastro en timeline + label en feed. No se queda pegado.

**Regla de Robert (2026-05-29)**: errores de NUESTRA infraestructura (captcha/proxy/gateway/login 406) = REINTENTOS, jamás detener. Igual principio que `gentle_login` y el matchmaker. Solo el estado REAL de BetMexico (tarjeta rechazada, autoexclusión, KYC, credenciales) detiene.

---

## Frontend

### El feed de actividad muestra 2 entradas por 1 mismo depósito fallido

**Causa**: scheduled aborted dispara 2 broadcasts (`kind:scheduled` + `kind:scheduled_aborted`).

**Workaround**: ignorar visualmente — es 1 solo intento real (confirmar con `docker logs | grep TARGET <email>` cuenta apariciones reales).

**Fix pendiente**: consolidar en 1 evento o agrupar en UI por `sched_id + iter`.

---

### El modal de depósito programado se cierra automáticamente

**Causa**: `setTimeout(() => closeDepositModal(), 1500)` en `executeScheduled()` (app.js:3148 - LEGACY).

**Fix aplicado 2026-05-11**: quitado el auto-close. El modal queda abierto, el usuario lo cierra cuando quiere. Mensaje en `#depResult` indica "Sigue el progreso en el feed de Actividad".

---

### Tarjetas no aparecen en el panel detalles aunque hay depósitos exitosos

Ver "Las tarjetas no se persisten" arriba (mismo bug raíz).

---

### Cuentas no quedan reservadas al depositar (otros operadores las siguen viendo)

**Síntoma**: dos operadores trabajan la misma cuenta sin saberlo → conflict en BetMexico (sesiones simultáneas → bans).

**Causa**: el flujo de depósito (single/multi/scheduled) no aplicaba `locked_by` automáticamente. El lock era solo manual vía botón "Lock" del cmdBar.

**Fix aplicado 2026-05-11**:
- `deposits._auto_lock_for_deposit(account_id, operator_id, user, hours)` ejecuta UPDATE en `accounts.locked_by/locked_at/locked_until` al inicio de cada deposit
- Llamado desde `/api/deposits/execute` (2h), `/api/deposits/multi/stream` (2h por cuenta), `/api/deposits/scheduled/create` (4h)
- Rechaza con 409 si está lockeada por otro operador (SA puede override)
- Filtro en `/api/accounts`: non-SA solo ve cuentas con `locked_by IS NULL` o `locked_by = <my_tg_id>`
- Broadcast SSE `kind:lock` con `auto:true` para distinguir lock manual vs automático

**Histórico**: commit `<TBD>` 2026-05-11.

---

### Feed de Actividad muestra 2 entradas idénticas por cada depósito

**Síntoma**: el feed muestra 2 rows con mismo email/monto/timestamp/estado.

**Causa**: 2 funciones escribían a `deposit_attempts` en paralelo:
1. `web_routes_deposits._persist_final` → `db.log_attempt` (info completa)
2. `deposits._record_attempt` → INSERT directo (sólo con `card_pipe`)

Cada deposit creaba 2 rows → 2 events SSE → 2 filas en el feed.

**Fix aplicado 2026-05-11**:
- `_record_attempt` ya NO escribe — solo broadcastea SSE (1 sola vez)
- `_persist_final` ahora recibe y guarda `card_pipe` en la columna
- BD: limpiados duplicados existentes con query agrupada por `(email, amount, status, minute)`

**Histórico**: introducido con la migración inicial (2 paths heredados). Resuelto en commit `4ce207b`.

---

## Matchmaker live-progress (Task 4)

### `velocity_skip` deja rows en spinner permanente

**Síntoma**: en el panel matchmaker (multi), tras un `VELOCITY_SKIP` la tarjeta y la cuenta involucradas quedan con spinner girando hasta que un evento futuro las toque.

**Causa**: `handleMmEvent` no tenía `case 'velocity_skip'`. El `trying` previo ya dejó `card.status='busy'` y `acc.status='busy'`, y nadie las regresaba a `idle`.

**Fix** (2026-05-15, commit post-`f4c68e8`): agregado handler en `static/app.js` que pone ambos en `idle`, limpia `busyEmail/busyTail` + `currentPhase`, y agrega línea al feed con el `wait_sec`.

---

### Sub-indicador de fase desaparece cuando otro par dispara `_mmRender`

**Síntoma**: en matchmaker con 2+ pares concurrentes, el texto en `.mm-pair-phase` ("🔑 Login…", "💳 Tarjeta…") aparece y desaparece intermitentemente.

**Causa**: `_mmRender` hace `innerHTML = cardsHtml` — destruye el DOM y lo re-crea desde el modelo (`_mm.cards` / `_mm.accounts`). El texto inyectado por `_mmSetPairPhase` solo vivía en el DOM, no en el modelo, así que cualquier evento que dispare `_mmRender` (otro par, otro `trying`, etc.) lo borraba.

**Fix** (2026-05-15): `_mmSetPairPhase` ahora persiste el texto como `card.currentPhase` y `acc.currentPhase`. `_mmRender` inyecta este valor en el HTML inicial de filas `busy`. Eventos terminales (`match`, `rejected`, `account_dead`, `velocity_skip`, `done`) limpian `currentPhase = ''` para no mostrar texto stale en una segunda ronda.

---

### SSE drain loop sin heartbeat — proxies cierran conexión en captchas largos

**Síntoma**: en captchas que tardan 30s+, el cliente recibe `net::ERR_INCOMPLETE_CHUNKED_ENCODING` o el stream queda colgado. nginx/traefik cierran por timeout sin tráfico.

**Causa**: en `deposits.py` `multi_stream`, el drain loop del `gather_task` hacía `except asyncio.TimeoutError: pass` — 0 bytes enviados por SSE mientras los attempts corrían en paralelo.

**Fix** (2026-05-15): el `except asyncio.TimeoutError` ahora emite `yield ": ping\n\n"` (SSE comment heartbeat — no es un event, no afecta al cliente JS, pero mantiene la conexión activa contra proxies).

---

### `CancelledError` perdido en finally del execute-stream → activity feed loses entries

**Síntoma**: en escenarios de client-disconnect (browser cerrado mid-depósito), el feed de actividad pierde la entrada aunque el depósito haya completado en backend.

**Causa**: en `deposits.py` `/execute-stream`, el bloque de rescate de result hacía:
```python
try:
    result = deposit_task.result() or {}
except Exception:
    result = {}
```
`asyncio.CancelledError` es `BaseException`, no `Exception` (Python 3.8+). El except no lo atrapa, el resto del finally no corre, `_record_attempt` nunca se llama.

**Fix** (2026-05-15, v20260515f): cambiar a `except BaseException:` solo en ese rescate. El resto del código sigue con `except Exception` (intencional para no tragar CancelledError donde sí debe propagar).

---

### `gateway_check_done` rojo aunque depósito aprobado

**Síntoma**: el step `check` del stepper queda rojo mientras el banner final dice "Aprobado". Visualmente contradictorio.

**Causa**: `check_transaction` puede devolver `txn_status=0` (procesando) en depósitos ya aprobados. La condición frontend `txn_status === 1 || === 2` marcaba fail. La aprobación real viene de `result_code == "BANK_APPROVED"` en `gateway_submit_done`.

**Fix** (2026-05-15, v20260515f): `_handleExecStreamEvent` ahora solo marca fail si `d.check_error` está presente; `txn_status` es informativo. Adicionalmente, en el evento `type='done'` con `success: true`, se fuerza el step `check` a ok como reconcile final.

---

### Multi `done` event nunca emitido si el generator explota

**Síntoma**: en multi (matchmaker), si el generator lanza excepción, el finally limpia el pool pero el cliente nunca recibe `done`. Las pair rows (cards/accounts) quedan stuck con spinner hasta recargar la página.

**Causa**: el `yield {'type':'done'}` estaba FUERA del `try/finally` en `multi_stream`. Cualquier excepción dentro del try saltaba directo al finally sin pasar por el yield.

**Fix** (2026-05-15, v20260515f):
1. Backend: mover el `yield done` DENTRO del try. Agregar `except Exception` que emite `{'type':'fatal','run_id','error'}` antes del finally.
2. Frontend (`app.js`): agregar flag `_mmGotDone` en el SSE consumer. Si el stream cierra sin `done|fatal|cancelled`, limpiar busy → idle preventivo en cards/accounts y mostrar toast "Conexión interrumpida — selección reseteada".

---

### Botón ↻ de fila salta debajo del saldo cuando el monto tiene 4+ dígitos

**Síntoma**: en la tabla principal, cuando una cuenta tiene saldo `$1,234.56` o más, el botón ↻ (refresh individual) se mueve a la línea siguiente, ensanchando la fila y rompiendo la alineación con el resto de filas.

**Causa**: `#accTable td.num` tenía `width: 92px`. El monto en mono `$X,XXX.XX` + botón (22px + 6px margen) excede 92px → flex wrap natural del navegador empuja el botón abajo.

**Fix** (2026-05-21, `static/style.css:1075`):
```css
#accTable th.num, #accTable td.num { width: 128px; min-width: 128px; white-space: nowrap; }
```
- Sube el ancho a 128px (cabe `$99,999.99` + botón ↻).
- `white-space: nowrap` es la red de seguridad: aunque el contenido crezca, el botón nunca salta de línea (el cell se desborda en horizontal en su lugar, lo cual es muy preferible al wrap vertical).

**Histórico**: detectado 2026-05-21 por Robert tras ver saldos altos en la operación diaria.

---

### JWT cache rancio NUNCA se invalida — captcha desperdiciado en cada refresh

**Síntoma**: una cuenta con JWT cacheado que BetMexico ya rechazó silenciosamente sigue intentando login con ese mismo JWT cada refresh. La API devuelve `details` vacío, el balance no se actualiza, pero `last_checked_at` sí — el operador no nota nada salvo que el balance está stale.

**Causa**: en `prewarm.py:_run_prewarm` la variable `jwt_from_cache` se inicializa en `False` y nunca se asigna `True`. El bloque `if jwt_from_cache: _db_invalidate_jwt(email)` era código muerto desde el commit inicial.

**Fix** (2026-05-21, [prewarm.py:398](prewarm.py#L398)): quitar el guard `if jwt_from_cache`. Ahora cuando `details` viene vacío, el JWT cacheado se invalida incondicionalmente y el próximo refresh hace login real.

**Histórico**: detectado por code review 2026-05-21 (Batch 1 holistic).

---

### `/api/prewarm/refresh-stream` no cancela tasks si el cliente desconecta

**Síntoma**: el operador cierra el browser mid-refresh masivo → hasta 15 tasks `_run_prewarm` siguen corriendo en background, gastando captchas de CapMonster cuyo resultado nadie lee.

**Causa**: el async generator no llamaba `await request.is_disconnected()` durante el loop principal.

**Fix** (2026-05-21, [prewarm.py:655](prewarm.py#L655)): chequeo al inicio de cada iteración del `while done_count < len(accs)`. Si disconnected → cancelar todas las tasks pending → break.

---

### `_record_attempt` NO se llamaba si el cliente desconectaba mid-deposit (single)

**Síntoma**: depósito iniciado vía `/api/deposits/execute`, el operador cierra la pestaña o falla la red mid-deposit. Si BetMexico ya aprobó el cargo, la tarjeta se "quema" sin que la BD tenga row en `deposit_attempts` → invisibilidad total.

**Causa**: el handler tenía `except Exception as e:` alrededor de `_run_deposit`. `asyncio.CancelledError` deriva de `BaseException` (Py 3.8+), no de `Exception`, así que no entraba al except y el `_record_attempt` que vivía dentro de él nunca corría.

**Fix** (2026-05-21, [deposits.py:616](deposits.py#L616)):
- `except BaseException as e:` captura ambos.
- `_record_attempt` movido al `finally` (siempre corre).
- Re-raise post-finally: `Exception` → `HTTPException(500, ...)` (preserva contrato con frontend), `CancelledError` → propagación bare.
- Mismo patrón aplicado a iteración de scheduled ([deposits.py:1324](deposits.py#L1324)).

---

### Matchmaker tight-loop sobre tarjetas velocity-blocked

**Síntoma**: en el feed se ven decenas de `velocity_skip` consecutivos para la misma tarjeta en segundos. El matchmaker no quema (el velocity check funciona) pero satura el SSE y consume ciclos.

**Causa**: el `VELOCITY_SKIP` retornaba inmediato. El cooldown del matchmaker (`MM_COOLDOWN=5s`) es menor que el `wait_sec` del velocity (60s), así que la misma combinación card+account se volvía a intentar 12 veces en el minuto.

**Fix** (2026-05-21, [deposits.py:1001](deposits.py#L1001)): `await asyncio.sleep(min(vel["wait_sec"] or 60, 30))` antes de retornar. Cap a 30s para no bloquear otros pares en el batch.

---

### `pool.start_factory()` failure dejaba cuentas lockeadas + state inconsistente

**Síntoma raro**: si CapMonster está caído al lanzar un multi/scheduled, las cuentas del batch quedaban auto-lockeadas 2-4h sin posibilidad de release manual (excepto SA override).

**Causa**: en `multi_stream.gen()` y `scheduled_create.loop()`, las llamadas `pool = make_pool(...)` y `await pool.start_factory()` estaban FUERA del `try:` que tenía el `finally` con `pool.stop()` + `_active_mm_runs.pop()` + `_active_schedules.pop()`. Si start_factory raise → finally nunca corre → state inconsistente.

**Fix** (2026-05-21, [deposits.py:1033](deposits.py#L1033) y [deposits.py:1287](deposits.py#L1287)): pool init movido DENTRO del try. Init `pool = None, prefetch = None` antes. Finally guardea con `if ... is not None:`.

---

## Deploy / Infra

### Builds Docker paralelos pelean por buildkit

**Síntoma**: `docker build` se queda colgado o falla con errores raros.

**Causa**: 2+ procesos `docker build` corriendo al mismo tiempo.

**Diagnóstico**: `ps aux | grep "docker build" | grep -v grep`

**Fix**:
```bash
pkill -9 -f 'docker build'
docker builder prune -f
docker build -t betmexico:latest .   # uno solo, sin background
```

---

### El smoke test pasa `/api/health` pero el dashboard está roto

**Causa**: probar solo `/health` es insuficiente. Si `app.py` importa módulos opcionales (`web_routes_deposits`) con `try/except`, el endpoint básico puede levantar mientras routers críticos fallan.

**Fix**: smoke test funcional. Después de cada deploy probar:
```bash
docker exec betmexico-web curl -sf http://localhost:8080/api/health | grep ok
docker exec betmexico-web curl -X POST http://localhost:8080/api/deposits/multi/stream
# Espero 401 (auth required) → router cargado. 503 = router NO cargado.
```

---

### Cert SSL Let's Encrypt no se emite

**Síntoma**: `https://botmexico.com.mx` da error de certificado.

**Causa**: DNS no propagó o el desafío HTTP-01 falla (puerto 80 bloqueado).

**Diagnóstico**:
```bash
nslookup botmexico.com.mx 8.8.8.8   # debe apuntar a 2.24.211.109
curl -I http://botmexico.com.mx     # debe redirigir 301 a HTTPS
docker logs traefik-traefik-1 2>&1 | grep -i 'letsencrypt\|acme' | tail -20
```

**Fix**: si DNS está bien y el cert no se emite, restart Traefik: `docker restart traefik-traefik-1`.

---

### Feed de Actividad muestra telegram_id numérico en columna "Quién"

**Síntoma**: la columna Quién muestra `1341812706` en vez de `RobertVS` (o el display name correspondiente) — pero solo para depósitos/locks que llegaron por SSE en vivo. Si se recargaba la página, los nombres aparecían bien.

**Causa raíz**: los broadcasts SSE en `deposits.py` enviaban `"who": operator_id` (entero crudo del telegram_id). El endpoint REST `/api/activity` sí pasaba el valor por `_resolve_operator()`, pero los eventos vivos no — el frontend los recibía sin resolver y los pintaba tal cual.

**Diagnóstico**: comparar payload SSE en consola del browser (`F12 → Network → /api/events`) contra el JSON de `/api/activity`. Si el SSE trae `"who": 1341812706` y el REST trae `"who": "RobertVS"`, es este bug.

**Fix** (aplicado 2026-05-26): agregar helper `_resolve_who(val)` en `app.py:707` que devuelve `{"who": ..., "who_color": ...}` ya resueltos. En `deposits.py`, late-import el helper y reemplazar cada `"who": operator_id` por `**_resolve_who(operator_id)` en los 8 broadcasts (lock auto, deposit, multi, scheduled_started, scheduled_phase, scheduled, scheduled_aborted ×2, scheduled_cancelled).

**Histórico**: el bug entró cuando los broadcasts se agregaron con el shape `who: operator_id` directo (no pasaba por `_resolve_operator`). El feed REST estaba bien desde el principio, lo que enmascaró el problema hasta que se notó la inconsistencia visual entre página recién cargada vs eventos en vivo.

---

### Tabla "Intentos del dashboard" trunca la tarjeta (`...|0628|` sin CVV)

**Síntoma**: en el modal de detalles de cuenta, la sección "🎯 INTENTOS DEL DASHBOARD" muestra la columna Tarjeta cortada (`4913660004872817|0628|` sin el `|685` final), y la columna Cuándo se rompe a 3 líneas (`26-`, `may,`, `11:22`).

**Causa raíz**: `.d-txn-scroll` tenía solo `overflow-y: auto`. Cuando el grid del modal (col 2, row 2) quedaba angosto, la tabla se comprimía y como las celdas no tenían `white-space: nowrap`, el texto se rompía en celdas estrechas — y los pipe de tarjeta (sin espacios) directamente se desbordaban y quedaban cortados sin scroll horizontal disponible.

**Fix** (aplicado 2026-05-26): en `static/style.css`:
- `.d-txn-scroll` → agregar `overflow-x: auto` (scroll horizontal si la suma de columnas excede el ancho).
- `.d-txn-table td.dim.mono, td.combo, td.combo b, td.num` → `white-space: nowrap` (timestamp/tarjeta/monto no se rompen).

**Histórico**: las celdas crecían cuando había espacio, pero al apretarse, los pipes se mutilaban silenciosamente. Lo notó Robert visualmente.

---

## Plantilla para nuevos errores

Agregar al cierre:
```
### <título conciso del síntoma>

**Síntoma**: …

**Causa**: …

**Diagnóstico**: comandos / queries

**Fix**: pasos exactos

**Histórico**: cuándo pasó, qué se aprendió
```
