# DEPLOY — Protocolo declarado

> **VPS actual de producción**: **KVM4** (Tailscale `100.77.154.31` / pública `2.24.211.109`)
> **VPS anterior**: ~~`187.77.207.90`~~ caído desde 2026-05-11 — migración forzada
> **Forma de deploy**: Docker Compose en `/docker/betmexico/`

---

## ⚠️ AVISOS CRÍTICOS

1. **Token Telegram único** — si el VPS viejo (`187.77.207.90`) vuelve a estar online, **NO arrancar el bot allí** o habrá conflicto de polling (Telegram solo entrega updates a UN consumer).
2. **BD canónica vive en KVM4** — `/docker/betmexico/data/betmexico_accounts.db`. Si VPS viejo revive, su BD queda obsoleta. Plan: respaldar y descartar.
3. **NO editar código en el monorepo (`Proyectos/BetMexico/Telegram/` o `Web/`)** — está marcado para migración a su propio repo. Si tocas ambos, creas bifurcaciones que destruyen trabajo.

---

## Arquitectura en KVM4

```
/docker/betmexico/
├── Dockerfile           # imagen base Playwright + deps consolidadas
├── docker-compose.yml   # 2 services: bot + web
├── .env                 # secretos (chmod 600, NO en git)
├── data/
│   └── betmexico_accounts.db   # BD compartida (montada en /data dentro container)
└── code/                # código fuente (montado en /app dentro container)
    ├── betmexico_bot.py         # entry point bot Telegram
    ├── betmexico_*.py           # módulos compartidos
    ├── patch_capmonster.py
    ├── requirements.txt
    └── web/                     # dashboard FastAPI (este repo)
        ├── app.py
        ├── auth.py
        ├── deposits.py
        ├── prewarm.py
        ├── requirements.txt
        └── static/
```

### Servicios

| Container | Imagen | Comando | Puerto host | Función |
|---|---|---|---|---|
| `betmexico-bot` | `betmexico:latest` | `python betmexico_bot.py` | — | Bot Telegram (polling) |
| `betmexico-web` | `betmexico:latest` | `python web/app.py` | `8080` | Dashboard FastAPI |

Ambos comparten:
- Volumen `./data:/data` (BD SQLite)
- Volumen `./code:/app` (código en caliente, sin rebuild)
- `.env` (mismo file de secrets)
- Red Docker `bmx` (bridge)

### Acceso

- **Dashboard (público)**: **`https://botmexico.com.mx`**, `https://www.botmexico.com.mx` y **`https://botmexico.net`** (alias operativo desde 2026-07-12, ver `docs/ERRORS.md` §"botmexico.com.mx inaccesible") — TLS automático vía Traefik + Let's Encrypt, cert con SAN combinado
- **Dashboard (Tailscale, debug)**: containers NO exponen 8080 al host. Para debug interno: `docker exec betmexico-web curl http://localhost:8080/api/health` o `docker network inspect betmexico_bmx` y curl al IP interno.
- **Bot Telegram**: `@betmx_bot` (token en `.env`)

### Reverse proxy (Traefik en KVM4)

Traefik corre como service vecino en `/docker/traefik/` (network `host`, entrypoints `:80`/`:443`, certresolver `letsencrypt` con HTTP-01 challenge). Auto-redirect HTTP→HTTPS configurado globalmente.

Labels en `docker-compose.yml` del servicio `web`:
```yaml
labels:
  - 'traefik.enable=true'
  - 'traefik.http.routers.betmexico.rule=Host(`botmexico.com.mx`) || Host(`www.botmexico.com.mx`) || Host(`botmexico.net`)'
  - 'traefik.http.routers.betmexico.entrypoints=websecure'
  - 'traefik.http.routers.betmexico.tls.certresolver=letsencrypt'
  - 'traefik.http.services.betmexico.loadbalancer.server.port=8080'
```

Para agregar un nuevo dominio: ampliar la regla `Host(...)` y propagar DNS A → `2.24.211.109`. Traefik emite cert en background.

---

## Flujo de deploy

### 1. Cambios en código del dashboard (este repo)

```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"
HOST="root@100.77.154.31"

# Subir archivo(s) modificado(s) — dashboard vive en code/web/
scp -P 22 -o StrictHostKeyChecking=no -i "$KEY" \
  prewarm.py "$HOST:/docker/betmexico/code/web/prewarm.py"

scp -P 22 -o StrictHostKeyChecking=no -i "$KEY" \
  static/app.js "$HOST:/docker/betmexico/code/web/static/app.js"

scp -P 22 -o StrictHostKeyChecking=no -i "$KEY" \
  static/style.css "$HOST:/docker/betmexico/code/web/static/style.css"

# Restart (no rebuild — código montado como volumen)
ssh -o StrictHostKeyChecking=no -i "$KEY" $HOST \
  "docker compose -f /docker/betmexico/docker-compose.yml restart web"
```

> **Nota**: usar Tailscale IP `100.77.154.31` con la key `kvm4_hostinger`.
> `pscp`/`plink` se cuelgan en bash (prompt interactivo sin TTY). Usar `scp`/`ssh` nativo.

### 2. Cambios en bot Telegram (monorepo, `Proyectos/BetMexico/Telegram/`)

> **NOTA**: el bot vive en el monorepo por ahora. Cuando migre a su propio repo, se actualizará este flujo.

```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"
HOST="root@100.77.154.31"

# Subir archivo(s) — bot vive en code/ raíz
scp -P 22 -o StrictHostKeyChecking=no -i "$KEY" \
  betmexico_X.py "$HOST:/docker/betmexico/code/betmexico_X.py"

# Restart container bot
ssh -o StrictHostKeyChecking=no -i "$KEY" $HOST \
  "docker compose -f /docker/betmexico/docker-compose.yml restart bot"
```

### 3. Cambios en dependencias (requirements / Dockerfile)

```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"
HOST="root@100.77.154.31"

ssh -o StrictHostKeyChecking=no -i "$KEY" $HOST \
  "cd /docker/betmexico && docker compose build && docker compose up -d"
```

### 4. Update de API keys (.env)

```bash
KEY="C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger"
HOST="root@100.77.154.31"

ssh -o StrictHostKeyChecking=no -i "$KEY" $HOST \
  "sed -i 's/OLD_KEY/NEW_KEY/g' /docker/betmexico/.env && \
   docker compose -f /docker/betmexico/docker-compose.yml restart"
```

---

## Logs y troubleshooting

```bash
# Logs en vivo
docker logs -f betmexico-bot
docker logs -f betmexico-web

# Logs últimas N líneas
docker logs --tail 50 betmexico-web

# Estado
docker compose ps

# Healthcheck dashboard
curl http://localhost:8080/api/health

# Verificar balance CapMonster
curl -X POST https://api.capmonster.cloud/getBalance \
  -H 'Content-Type: application/json' \
  -d '{"clientKey":"<KEY_DEL_ENV>"}'
```

---

## Backups

- **BD**: `/docker/betmexico/data/betmexico_accounts.db` — copiar con `cp` periódicamente a `/docker/betmexico/data/backups/` o vía pscp a local.
- **.env**: guardado en gestor de passwords del dev — NO en git.

---

## Restore desde cero (DR)

```bash
# 1. Clonar/subir esta estructura a /docker/betmexico/
# 2. Restaurar BD a data/
# 3. Crear .env (chmod 600)
# 4. Build + up
cd /docker/betmexico
docker compose build
docker compose up -d
docker compose ps
```

---

## Variables de entorno (`.env`)

| Variable | Valor / fuente | Notas |
|---|---|---|
| `BMX_BOT_TOKEN` | token Telegram | desde @BotFather |
| `BMX_CAPMONSTER_KEY` | `1f249a94...` | CapMonsterCloud API |
| `CAPMONSTER_KEY` | mismo que arriba | alias usado por el dashboard |
| `BMX_RECAPTCHA_SITEKEY` | sitekey público BetMexico | hardcoded |
| `BMX_CAPSOLVER_KEY` | `CAP-...` | CapSolver (legacy, no activo) |
| `BETMEX_DB` | `/data/betmexico_accounts.db` | path dentro del container |
| `BMX_WEB_PORT` | `8080` | puerto interno del web |
| `BMX_MASTER` | `Cachau2022` | bypass auth web |
| `WSAI_API_KEY` | `e338d7e4...` | WebScraping.ai (monitor sidebar) |
| `KIMI_API_KEY` | `sk-...` | Moonshot Kimi K2.5 (opcional) |

---

## Histórico

| Fecha | Cambio |
|---|---|
| 2026-07-12 | **`botmexico.net` agregado como alias** (Traefik + cert SAN) tras DNS de `botmexico.com.mx` reseteado a placeholder Webador en Openprovider — ver `docs/ERRORS.md` |
| 2026-05-11 | **Dominio `botmexico.com.mx` activado** con HTTPS + Let's Encrypt vía Traefik |
| 2026-05-11 | **Migración KVM4** — dockerizado, salimos de VPS Hostinger `187.77.207.90` (caído) |
| 2026-04-11 | Último deploy en VPS viejo (sesión 80) |
