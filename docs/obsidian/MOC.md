# MOC — botmex-dashboard

> Map of Content para Obsidian. Punto de entrada al mapa mental del sistema.
> Abrir desde el vault `TESTING DEV/` en Obsidian.

## 🚦 Estado de la operación

- **Producción**: [[botmexico.com.mx]] en KVM4 Docker
- **Bot Telegram**: `@betmx_bot` (polling)
- **BD**: `/docker/betmexico/data/betmexico_accounts.db` (~902 cuentas)

## 🗺️ Flujos principales

- [[Flujo deposit single]] — 1 cuenta, 1 tarjeta
- [[Flujo matchmaker]] — N×M pairing greedy con SSE
- [[Flujo scheduled]] — N reps cada 1 min, aborta-on-fail
- [[Flujo prewarm]] — pre-cargar JWT + balance
- [[Flujo SSE bus]] — eventos en tiempo real backend ↔ frontend
- [[Flujo CURP]] — calc/validar contra gob.mx

## 🧱 Capas del stack

- [[Backend layer]] — FastAPI, routers, endpoints
- [[Frontend layer]] — vanilla JS, secciones, modales
- [[BD schema]] — accounts, account_cards, deposit_attempts, payment_tests, etc.
- [[Infra layer]] — KVM4, Docker, Traefik, Let's Encrypt

## ⚙️ Operaciones

- [[Deploy protocol]] → `docs/protocols/deploy-protocol.md`
- [[Deploy checklist]] → `docs/protocols/deploy-checklist.md`
- [[Maintenance]] → `docs/protocols/maintenance.md`
- [[Support troubleshooting]] → `docs/protocols/support.md`

## 🔍 Referencias

- [[ENDPOINTS]] — tabla maestra
- [[SSE_EVENTS]] — eventos broadcast
- [[ERRORS]] — errores comunes
- [[AUDIT]] — gap-analysis spec vs actual

## 🧠 Mapas mentales

- [[botmex-dashboard.canvas]] — canvas visual del sistema
- [[bitacora-principles.md]] — principios de la bitácora

## 🔗 Cross-repo

- [[RITA orchestration]] → `repos/rita-dashboard/`
- [[Ruthopia bot]] → `repos/ruthopia/`
- [[Forgejo]] — gestor de repos privados en KVM4
