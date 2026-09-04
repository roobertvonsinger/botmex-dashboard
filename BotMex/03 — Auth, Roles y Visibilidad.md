# 03 — Auth, Roles y Visibilidad (RBAC)

> **Ubicación:** `auth.py`, `web_auth.py`.
> **Canvas Detallado:** [[03 — Auth, Roles y Visibilidad.canvas]]
> **Modelo Mental:** [[09 — Arquitectura de Grafo de Agentes (Cocina)]] (Estación de Control de Acceso y Puerta de Seguridad).

---

## 🔐 Ficha Técnica y Matriz de Control

### 1. Manejo de Sesión Segura
- Basado en cookies firmadas criptográficamente (`web_auth.py`).
- Cada petición protegida pasa por el middleware `@require_session`.
- Si la cookie es inválida o ha expirado, redirige de inmediato a `/login` con código HTTP 302/401.

### 2. Matriz de Roles (RBAC)
- **Superadmin (`is_superadmin == 1`):**
  - Visibilidad total sobre todas las cuentas del sistema (`accounts`).
  - Control de misiones globales y visor de logs unificado.
  - Permiso para degradar vista con `?view_as={id}` sin alterar su rol real.
- **Operador:**
  - Visibilidad acotada a las cuentas vinculadas a su `telegram_id`.
  - Prohibido el acceso a cuentas ajenas o a endpoints administrativos (`/api/admin/*`).

### 3. Guardrail Inmutable 403 Forbidden
- Toda consulta SQL o mutación valida estrictamente:
  `WHERE id = ? AND (operator_id = ? OR ? = 1)`
- Cualquier intento de forzar un ID ajeno emite un HTTP 403 Forbidden y genera un registro de auditoría en `/data/logs/dashboard.log`.
