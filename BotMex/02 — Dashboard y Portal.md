# 02 — Dashboard y Portal Web (FastAPI)

> **Ubicación:** `app.py`, `templates/`, `static/` (Puerto `:8001` local / `:8080` Docker KVM4).
> **Canvas Detallado:** [[02 — Dashboard y Portal.canvas]]
> **Modelo Mental:** [[09 — Arquitectura de Grafo de Agentes (Cocina)]] (Estación de Visualización, Monitoreo y Control de Mando).

---

## 🖥️ Ficha Técnica y Estructura del Portal

### 1. Gate de Sesión y Ruteo Raíz (`/`)
- Si no hay cookie de sesión activa → Redirige a `/login`.
- Si el usuario tiene rol **Superadmin** → Redirige a `/dashboard`.
- Si el usuario tiene rol **Operador** → Redirige a `/user/{telegram_id}`.

### 2. Panel Superadmin (`/dashboard`)
- Vista global con KPIs del sistema (total fondeado, retiros pendientes, cuentas activas por tier).
- **Consola de Logs:** Lee directamente `/data/logs/dashboard.log` con selector de categorías, filtros por texto y enlaces clickeables a cuentas.
- **Soporte `?view_as={telegram_id}`:** Permite al Superadmin auditar exactamente lo que ve un operador específico degradando su contexto visual sin alterar permisos en base de datos.

### 3. Portal de Operador (`/user/{telegram_id}`)
- **Grid "Mis Cuentas":** Muestra exclusivamente las cuentas del operador. Oculta automáticamente aquellas con balance 100% retirado para evitar ruido visual.
- **Chip 1-Click CLABE:** Permite copiar la CLABE STP y CURP en un solo clic para transferencias bancarias.
- **Vista de Misión SSE:** Renderiza barra de progreso reactiva, tarjetas evaluadas y countdown anti-huella alimentado por `/api/stream`.
- **Botones Operativos:** Retiro manual y Liberar cuenta sin requerir contraseñas adicionales.
