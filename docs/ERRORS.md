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
