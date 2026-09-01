# 02 — Dashboard y Portal Web

**Ubicación:** `app.py` (FastAPI), `templates/`, `static/` (Puerto `:8001` local / `:8080` VPS).
**Canvas Raíz:** [[00 — BotMex System Map.canvas]]

### Ficha Técnica
- **Qué inicia el flujo:** Visita del navegador a `/` (login), `/dashboard` (Superadmin) o `/user/{tg_id}` (Operador).
- **Decisión central:** Control de rol (`is_superadmin`) y soporte para `?view_as={id}` para auditar sin tocar permisos.
- **Qué modifica:** Acciones manuales de retiro, liberación de cuentas y triggers de depósitos.
- **Qué comunica:** Stream SSE instantáneo (`_sse_queues`) con progreso de depósitos y consola de logs en vivo.
- **A qué flujo abre:** [[03 — Auth, Roles y Visibilidad]] y [[07 — Retiros y Reconciliación]].
