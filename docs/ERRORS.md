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
