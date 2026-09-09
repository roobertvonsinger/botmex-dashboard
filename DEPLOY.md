# DEPLOY — Protocolo declarado (Post-Migración Karen KVM4)

> **DOCUMENTO CANÓNICO ACTUALIZADO**: Consulta [`docs/protocols/deploy-protocol.md`](docs/protocols/deploy-protocol.md).
> **VPS actual de producción**: **Karen VPS** (`2.25.98.162` / alias `karen` en `~/.ssh/config` / Tailscale `100.87.56.127`)
> **VPS anteriores**: 
> - ~~`100.77.154.31`~~ / ~~`2.24.211.109`~~ (KVM4 vieja suspendida el 04-Sep-2026)
> - ~~`187.77.207.90`~~ / ~~`76.13.113.195`~~ (legacy)
> **Forma de deploy**: **Git-Only** a `/opt/kvm4/apps/betmexico/code` (bind-mount a `/app` en containers).

---

## ⚠️ AVISOS CRÍTICOS

1. **Deploy EXCLUSIVO vía Git**: Prohibido hacer subidas sueltas por SCP/SFTP que dejen el checkout en estado "frankenstein". Todo deploy se hace con commit + push a `origin/main` y `git reset --hard origin/main` en el servidor.
2. **BD canónica vive en Karen VPS**: `/opt/kvm4/apps/betmexico/data/betmexico_accounts.db`.
3. **SSH Key**: `C:\Users\rober\Dropbox\TESTING DEV\SSH KEYS\kvm4_hostinger` (o `~/.ssh/kvm4_hostinger`).

---

## Arquitectura en Karen VPS

```
/opt/kvm4/apps/betmexico/
├── Dockerfile           # imagen base
├── docker-compose.yml   # services: web, bot, telegram-mock, balance-poller
├── .env                 # secretos (chmod 600, NO en git)
├── data/
│   └── betmexico_accounts.db   # BD compartida (montada en /data dentro container)
└── code/                # repo git (montado en /app dentro container)
    ├── app.py           # entrypoint dashboard FastAPI
    ├── betmexico_bot.py # entrypoint bot Telegram
    ├── static/          # frontend assets
    └── ...
```

### Servicios

| Container | Imagen | Comando | Puerto host | Función |
|---|---|---|---|---|
| `betmexico-web` | `betmexico:latest` | `python app.py` | `8001:8080` | Dashboard FastAPI |
| `betmexico-bot` | `betmexico:latest` | `python betmexico_bot.py` | — | Bot Telegram (polling) |
| `betmexico-mock-bot` | `betmexico:latest` | `python telegram_bot_mock/bot.py` | — | Mock Telegram |
| `betmexico-balance-poller` | `betmexico:latest` | `python scripts/session_balance_poller.py` | — | Poller de saldos |

---

## Flujo Canónico de Deploy (Git-Only)

```bash
# 1. Local (repos/botmex-dashboard)
git add <archivos>
git commit -m "..."
git push origin main

# 2. En Karen VPS: pull limpio y restart
ssh karen "cd /opt/kvm4/apps/betmexico/code && git fetch origin -q && git reset --hard origin/main && docker restart betmexico-web"

# 3. Verificación
ssh karen "docker exec betmexico-web curl -s http://localhost:8080/api/health/ping"
ssh karen "docker logs --tail 30 betmexico-web"
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
