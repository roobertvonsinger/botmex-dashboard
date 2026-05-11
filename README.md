# botmex-dashboard — Bitácora operativa BetMexico

> 🌐 **Producción**: **https://botmexico.com.mx** (HTTPS auto via Traefik + Let's Encrypt en KVM4)
> 🤖 **Bot Telegram**: `@betmx_bot` (polling activo)
> 💾 **BD**: `/docker/betmexico/data/betmexico_accounts.db` (~902 cuentas)

## Propósito

El dashboard **NO es decoración**. Es una herramienta operativa que:

1. **TRACKEA** cada intento de depósito (con tarjeta usada, monto, estado, operador, latencia)
2. **CONTROLA** — el operador decide qué hacer, el dashboard ejecuta y reporta
3. **MONITOREA** servicios externos (CapMonster, proxies MX, WebScraping.ai) en tiempo real
4. **GUARDA DATOS** — todo lo útil persiste; nada relevante se pierde

> Test mental: si dentro de 1 semana querés saber qué pasó con la cuenta X — qué tarjetas se probaron, cuándo, cuánto, con qué resultado, qué operador — ¿podés? Si NO → falta funcionalidad.

## 📚 Documentación

| Tipo | Archivo |
|---|---|
| **Arranque rápido** | [`docs/README.md`](docs/README.md) — índice de toda la docs |
| **Arquitectura** | [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) + [`docs/diagrams/`](docs/diagrams/) (Mermaid) |
| **Endpoints** | [`docs/ENDPOINTS.md`](docs/ENDPOINTS.md) — tabla maestra (~55 endpoints reales) |
| **Frontend** | [`docs/FRONTEND.md`](docs/FRONTEND.md) — secciones, modales, handlers |
| **Eventos SSE** | [`docs/SSE_EVENTS.md`](docs/SSE_EVENTS.md) — 16+ tipos de broadcast |
| **Errores comunes** | [`docs/ERRORS.md`](docs/ERRORS.md) — síntoma + causa + fix |
| **Audit (spec vs actual)** | [`docs/AUDIT.md`](docs/AUDIT.md) — gap analysis |
| **Deploy** | [`docs/protocols/deploy-protocol.md`](docs/protocols/deploy-protocol.md) + [`deploy-checklist.md`](docs/protocols/deploy-checklist.md) |
| **Mantenimiento** | [`docs/protocols/maintenance.md`](docs/protocols/maintenance.md) |
| **Soporte / Troubleshooting** | [`docs/protocols/support.md`](docs/protocols/support.md) |
| **Mapa mental (Obsidian)** | [`docs/obsidian/MOC.md`](docs/obsidian/MOC.md) + [`botmex-dashboard.canvas`](docs/obsidian/botmex-dashboard.canvas) |

## 🛠 Stack

- **Backend**: FastAPI + uvicorn + SQLite (`/data/betmexico_accounts.db`, hot-mount)
- **Frontend**: vanilla HTML/CSS/JS — sin frameworks, sin build step
- **Imagen Docker**: `mcr.microsoft.com/playwright/python:v1.49.0-jammy` + tzdata + deps Python
- **Orquestación**: Docker Compose en `/docker/betmexico/` (KVM4)
- **Reverse proxy**: Traefik (container vecino) con cert Let's Encrypt auto-renew

## ⚡ Quickstart local

```bash
pip install -r requirements.txt
cp .env.example .env
# editar .env: BETMEX_DB=<path/a/betmexico_accounts.db>, CAPMONSTER_KEY=..., WSAI_API_KEY=..., BMX_MASTER=<bypass-password>
python app.py
```

Abre http://127.0.0.1:8080

## 🚀 Deploy

```bash
# Cambio frontend (hot-mount, sin restart):
pscp -batch -pw "***" static/* root@100.77.154.31:/docker/betmexico/code/web/static/

# Cambio backend (hot-mount + restart):
pscp -batch -pw "***" *.py root@100.77.154.31:/docker/betmexico/code/web/
plink -batch -pw "***" root@100.77.154.31 "cd /docker/betmexico && docker compose restart web"
```

**Antes de cualquier deploy → leer [`docs/protocols/deploy-checklist.md`](docs/protocols/deploy-checklist.md)**.

## 🤖 Skill obligatoria

`.claude/skills/botmex-bitacora/SKILL.md` debe invocarse SIEMPRE antes de cambiar código del dashboard. Bloquea commits que NO actualicen `docs/`.

## 🗺 Replicar metodología a otros repos

Ver [`templates/repo-docs-template/`](templates/repo-docs-template/) — estructura clonable.

## ⚠️ Avisos críticos

1. **Token Telegram único**: si el VPS viejo (`187.77.207.90`) revive, NO arrancar bot allí (conflicto polling).
2. **BD canónica vive en KVM4**: `/docker/betmexico/data/betmexico_accounts.db`. La del VPS viejo es obsoleta.
3. **Código del bot Telegram aún en monorepo** (`Proyectos/BetMexico/Telegram/`). Migración a su propio repo pendiente.
4. **NUNCA copiar del monorepo viejo al deploy directo** — siempre pasar por el repo canónico primero. Ver `feedback_no_alucinar.md` en memoria.

## 📜 Histórico de sesiones

Ver [`AVANCES_SESION.md`](AVANCES_SESION.md).
