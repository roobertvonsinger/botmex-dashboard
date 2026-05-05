# botmex-dashboard

Dashboard web v2 de BetMexico. Frontend nuevo (Obsidian Refined) sobre la BD existente que ya gestiona el bot Telegram.

## Quickstart

```bash
pip install -r requirements.txt
cp .env.example .env
# editar .env si la BD vive en otro path
python app.py
```

Abre http://127.0.0.1:5001

## Stack

- **Backend:** FastAPI + uvicorn + SQLite (read-only contra `betmexico_accounts.db`)
- **Frontend:** vanilla HTML/CSS/JS — sin frameworks, sin build step
- **Diseño:** Obsidian Refined (handoff de Claude Design, tokens OKLCH)

## Roadmap

- [x] Sprint 1 — MVP tabla básica (vista usuario)
- [ ] Sprint 2 — L invertida SuperAdmin (Conectados, Actividad LIVE, Alertas, Pool)
- [ ] Sprint 3 — Sistema de uso + locks + notificaciones SSE
- [ ] Sprint 4 — Depósitos (envuelve módulo blindado)
- [ ] Sprint 5 — Pre-warm + deploy VPS + integración bot TG
