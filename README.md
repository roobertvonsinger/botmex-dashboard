# botmex-dashboard

Dashboard web v2 de BetMexico. Frontend nuevo (Obsidian Refined) sobre la BD existente que ya gestiona el bot Telegram.

> 🚨 **DEPLOY EN PROD**: ver [`DEPLOY.md`](DEPLOY.md). VPS actual = **KVM4** (Docker Compose en `/docker/betmexico/`). VPS viejo `187.77.207.90` murió 2026-05-11 — migración forzada.

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env
# editar .env si la BD vive en otro path
python app.py
```

Abre http://127.0.0.1:5001

## Scope (Sprint 1)

- Desktop-only viewport (≥1280px). Mobile/tablet responsive deferred until Sprint 2 panel work decides final layout. The shell is fixed at `100vh` with sidebar at `216px` on purpose to maximize information density.

## Stack

- **Backend:** FastAPI + uvicorn + SQLite (read-only contra `betmexico_accounts.db`)
- **Frontend:** vanilla HTML/CSS/JS — sin frameworks, sin build step
- **Diseño:** Obsidian Refined (handoff de Claude Design, tokens OKLCH)

## Roadmap

- [x] Sprint 1 — MVP tabla básica (vista usuario)
- [x] Sprint 2 — L invertida SuperAdmin (Conectados, Actividad LIVE, Alertas, Pool)
- [x] Sprint 3 — Sistema de uso + locks + notificaciones SSE + sidebar status
- [x] Sprint 4 — Depósitos read-only (deposit_attempts, view + endpoints)
- [ ] Sprint 5 — Pre-warm + deploy VPS + integración bot TG
