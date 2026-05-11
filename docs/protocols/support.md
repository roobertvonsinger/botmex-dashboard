# Support — Troubleshooting

> Estructurado por síntoma. Ir directo al que aplica. Si no aparece, agregarlo después de resolverlo.

## Síntomas y fixes

### El dashboard no carga (https://botmexico.com.mx)

```bash
# 1. ¿DNS bien?
nslookup botmexico.com.mx 8.8.8.8  # → 2.24.211.109

# 2. ¿Traefik responde?
curl -I https://botmexico.com.mx  # → 200, 301 o 404 (no timeout)

# 3. ¿Container web vivo?
plink -batch -pw "Kashau2022##" root@100.77.154.31 "docker compose -f /docker/betmexico/docker-compose.yml ps"

# 4. ¿Healthcheck?
curl https://botmexico.com.mx/api/health
```

Si DNS bien + Traefik OK + container vivo + health 200 → problema es de cliente (cache, red).

### `/api/deposits/multi/stream` devuelve 503

Ver `docs/ERRORS.md` → "`[deps] bot init failed`".

### Tarjeta aprobada NO aparece en panel detalles

Ver `docs/ERRORS.md` → "Las tarjetas no se persisten".

### Matchmaker dispara pero no avanza

Ver `docs/ERRORS.md` → "matchmaker 200 OK pero no avanza" (CapMonster sin saldo).

### `403 Rate limit` al hacer login a BetMexico

Ver `docs/ERRORS.md` → "Login BetMexico devuelve 403".

### Programado se ejecuta 2 veces al fallar

NO se ejecuta 2 veces. Son 2 broadcasts del MISMO fallo. Ver `docs/SSE_EVENTS.md` sección "Patrón de duplicado".

### Cert SSL vencido / inválido

```bash
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "docker logs --tail 50 traefik-traefik-1 2>&1 | grep -iE 'acme|certif|letsencrypt'"
```

Forzar renovación: `docker restart traefik-traefik-1`.

### Container restart muy lento ("Deactivating" eterno)

Ver `docs/ERRORS.md` → "Container restart se queda en Deactivating".

### Build Docker bloqueado / lento

Ver `docs/ERRORS.md` → "Builds Docker paralelos pelean por buildkit".

## Diagnóstico general

### Estado de containers

```bash
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "docker compose -f /docker/betmexico/docker-compose.yml ps && echo --- && docker stats --no-stream"
```

### Estado de BD

```bash
plink -batch -pw "Kashau2022##" root@100.77.154.31 "docker exec betmexico-web python -c '
import sqlite3, os
c = sqlite3.connect(\"/data/betmexico_accounts.db\")
print(\"path size:\", os.path.getsize(\"/data/betmexico_accounts.db\"))
print(\"accounts:\", c.execute(\"SELECT COUNT(*) FROM accounts\").fetchone())
print(\"cards:\", c.execute(\"SELECT COUNT(*) FROM account_cards\").fetchone())
print(\"deposit_attempts:\", c.execute(\"SELECT COUNT(*) FROM deposit_attempts\").fetchone())
print(\"latest attempt:\", c.execute(\"SELECT account_email, amount, status, created_at FROM deposit_attempts ORDER BY id DESC LIMIT 1\").fetchone())
'"
```

### Estado servicios externos

```bash
# CapMonster
curl -s -X POST https://api.capmonster.cloud/getBalance \
  -H 'Content-Type: application/json' \
  -d '{"clientKey":"<key_de_env>"}' | jq .

# WSai
curl -s "https://api.webscraping.ai/account?api_key=<key>" | jq .

# Telegram bot vivo
curl -s "https://api.telegram.org/bot<token>/getMe" | jq .
```

## Plantilla de incidente

Cuando algo se rompe en prod, anotar:

```markdown
### Incidente YYYY-MM-DD HH:MM

**Síntoma observado**: …

**Logs relevantes**:
```
(pegar)
```

**Comandos ejecutados**: …

**Causa raíz**: …

**Fix aplicado**: …

**Doc actualizado**: lista archivos en `docs/` actualizados.

**Cómo prevenir en el futuro**: …
```

Guardar en `docs/incidents/<fecha>.md` (crear carpeta si no existe).

## Si Robert escala a otro modelo/agente

Si Claude no puede resolver, escalar:
- A **RITA** (orquestadora en `repos/rita-dashboard/`) — pasarle handoff con: estado, logs, qué se probó.
- Handoff debe incluir: comandos exactos para reproducir el síntoma + comandos exactos que se probaron + output de cada uno.
