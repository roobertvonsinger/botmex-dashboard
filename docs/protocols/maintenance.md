# Mantenimiento

> Tareas recurrentes para mantener el dashboard sano.

## Diaria

### Healthcheck rápido (manual o cron)

```bash
curl -sf https://botmexico.com.mx/api/health | jq .
# esperado: {"ok": true, "db": "/data/betmexico_accounts.db", "accounts": <int>}
```

Si falla → ver `support.md`.

### Saldos de servicios (visible en sidebar del dashboard)

| Servicio | Threshold alerta | Acción si bajo |
|---|---|---|
| CapMonsterCloud | < $5 | recargar via panel propio del servicio |
| WebScraping.ai | < 1,000 calls | recargar / generar nueva key |
| LitPort (proxy MX) | latencia > 2s o errores | rotar proxy con `POST /api/admin/refresh-proxy` |

## Semanal

### Backup BD

```bash
plink -batch -pw "Kashau2022##" root@100.77.154.31 \
  "mkdir -p /docker/betmexico/data/backups && \
   cp /docker/betmexico/data/betmexico_accounts.db \
      /docker/betmexico/data/backups/bmx_$(date +%Y%m%d_%H%M).db && \
   ls -la /docker/betmexico/data/backups/ | tail -5"
```

Mantener al menos 4 semanas de backups. Borrar más viejos:
```bash
find /docker/betmexico/data/backups/ -name 'bmx_*.db' -mtime +28 -delete
```

🔵 **Pendiente**: automatizar con cron en KVM4.

### Revisar `deposit_attempts` huérfanos

Intentos sin `card_pipe` (pre-fix 2026-05-11) o sin `gateway_response_raw`:

```bash
docker exec betmexico-web python -c "
import sqlite3
c = sqlite3.connect('/data/betmexico_accounts.db')
print('Sin card_pipe:', c.execute('SELECT COUNT(*) FROM deposit_attempts WHERE card_pipe IS NULL').fetchone())
print('Sin gateway_response_raw:', c.execute('SELECT COUNT(*) FROM deposit_attempts WHERE gateway_response_raw IS NULL').fetchone())
"
```

## Mensual

### Rotar API keys

| Key | Cadencia recomendada |
|---|---|
| `BMX_CAPMONSTER_KEY` | rotar si hay sospecha de leak |
| `WSAI_API_KEY` | rotar si scraping intensivo |
| `BMX_BOT_TOKEN` | NO rotar a menos que sea comprometido |

Flujo: ver `deploy-protocol.md` sección F (cambio de `.env`).

### Cuentas DEAD vs LIVE

```bash
docker exec betmexico-web python -c "
import sqlite3
c = sqlite3.connect('/data/betmexico_accounts.db')
for r in c.execute('SELECT status, COUNT(*) FROM accounts GROUP BY status'):
    print(r)
"
```

Si hay > 20% DEAD, investigar (¿BAN masivo? ¿Proxy quemado?).

### `account_cards` con `total_rejected` alto

```bash
docker exec betmexico-web python -c "
import sqlite3
c = sqlite3.connect('/data/betmexico_accounts.db')
for r in c.execute('SELECT card_number, account_email, total_deposits, total_approved, total_rejected FROM account_cards WHERE total_rejected > 5 ORDER BY total_rejected DESC LIMIT 10'):
    print(r)
"
```

Decidir si marcarlas como `status='BURNED'`.

## Trimestral

### Actualizar imagen base Playwright

Checar si hay nueva versión estable:
```bash
curl -s 'https://mcr.microsoft.com/v2/playwright/python/tags/list' | jq .tags
```

Si hay LTS más nueva, actualizar `infra/Dockerfile`:
```dockerfile
FROM mcr.microsoft.com/playwright/python:v1.X.0-jammy
```

Y rebuild (ver `deploy-protocol.md` sección E).

### Audit de routers legacy

Revisar `AUDIT.md` sección "Routers legacy NO montados". Decidir activar/borrar.

### Optimizar BD (vacuum + WAL checkpoint)

```bash
docker exec betmexico-web python -c "
import sqlite3
c = sqlite3.connect('/data/betmexico_accounts.db')
c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
c.execute('VACUUM')
c.commit()
print('OK')
"
```

## Reactivas (cuando aplique)

### CapMonster $5 → recargar

Notificación bell `capmonster_low`. Recargar en su dashboard. Sin acción en el código.

### Proxy MX down → rotar

```bash
curl -X POST https://botmexico.com.mx/api/admin/refresh-proxy \
  -H "Cookie: bmx_auth=<token-SA>"
```

### BD WAL > 100MB → checkpoint

```bash
ls -lh /docker/betmexico/data/betmexico_accounts.db*
# Si betmexico_accounts.db-wal > 100MB:
docker exec betmexico-web python -c "
import sqlite3
c = sqlite3.connect('/data/betmexico_accounts.db')
c.execute('PRAGMA wal_checkpoint(TRUNCATE)')
"
```

## Logs

Los logs viven en docker (no persistente entre restarts del daemon).
Exportar antes de restart de daemon:
```bash
docker logs --since 24h betmexico-web > web-$(date +%Y%m%d).log
docker logs --since 24h betmexico-bot > bot-$(date +%Y%m%d).log
```

🔵 **Pendiente**: pipe logs a archivo persistente (driver `json-file` con `max-size` ya está implícito; explorar `journal-d`).
