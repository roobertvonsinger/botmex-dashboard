# 03 — Auth, Roles y Visibilidad

**Ubicación:** `auth.py`, `web_auth.py`.
**Canvas Raíz:** [[00 — BotMex System Map.canvas]]

### Ficha Técnica
- **Qué inicia el flujo:** Peticiones HTTP a endpoints protegidos del dashboard.
- **Decisión central:** ¿El operador es dueño de las cuentas solicitadas o es Superadmin?
- **Qué modifica:** Asignación de sesión segura en cookies/headers y filtrado estricto por `telegram_id`.
- **Qué comunica:** HTTP 403 Forbidden o redirección al formulario de login.
- **A qué flujo abre:** [[02 — Dashboard y Portal]].
