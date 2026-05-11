# infra/ — Docker stack para BetMexico (KVM4)

Esta carpeta tiene los archivos canónicos de infraestructura que se usan en producción.

## Archivos

| Archivo | Propósito |
|---|---|
| `Dockerfile` | Imagen base (playwright/python + tzdata + todas las deps) |
| `docker-compose.yml` | 2 services: `betmexico-bot` (Telegram) + `betmexico-web` (FastAPI :8080) |
| `.env.example` | Plantilla de variables (rellenar `.env` en KVM4, NO commitear el real) |

## Deploy desde cero en otro host

```bash
# 1. Crear estructura
mkdir -p /docker/betmexico/{code/web,data}
cd /docker/betmexico

# 2. Copiar este Dockerfile y compose
scp infra/Dockerfile root@HOST:/docker/betmexico/
scp infra/docker-compose.yml root@HOST:/docker/betmexico/

# 3. Subir código:
#    - Dashboard: app.py auth.py deposits.py prewarm.py + static/  →  /docker/betmexico/code/web/
#    - Bot Telegram (desde Proyectos/BetMexico/Telegram/):  betmexico_*.py  →  /docker/betmexico/code/

# 4. Subir BD existente:
scp betmexico_accounts.db root@HOST:/docker/betmexico/data/

# 5. Crear .env desde plantilla y rellenar valores:
scp infra/.env.example root@HOST:/docker/betmexico/.env
# editar /docker/betmexico/.env con keys reales
chmod 600 /docker/betmexico/.env

# 6. Build + up
cd /docker/betmexico
docker compose build
docker compose up -d

# 7. Verificar
docker compose ps
curl http://localhost:8080/api/health
docker logs --tail 20 betmexico-bot
```

## Ver `../DEPLOY.md` para el protocolo completo de deploy continuo.
