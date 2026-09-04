# 08 — BD, Eventos e Infraestructura (Cimientos del Sistema)

> **Ubicación:** `betmexico_db.py`, `proxy_pool.py`, `app.py`, Docker KVM4 (`betmexico-web`).
> **Canvas Detallado:** [[08 — BD, Eventos e Infraestructura.canvas]]
> **Modelo Mental:** [[09 — Arquitectura de Grafo de Agentes (Cocina)]] (Los Cimientos, Servicios Básicos y Red Eléctrica de la Cocina).

---

## 🌐 Ficha Técnica y Topología de Infraestructura

### 1. Base de Datos SQLite en Modo WAL
- **Archivo:** `betmexico_accounts.db`
- **Concurrencia:** Activado `PRAGMA journal_mode=WAL;` y `busy_timeout=30000;` (30 segundos). Permite lecturas simultáneas ilimitadas sin bloquear escrituras de depósitos o daemons.
- **Tablas Maestras:** `accounts`, `missions`, `cards`, `deposits`, `withdrawals`, `bin_stats`.

### 2. Piscina de Proxies Residenciales (`proxy_pool.py`)
- Rotación automática de IPs residenciales para peticiones HTTP hacia BetMexico.
- **Failover Inmediato:** `call_with_proxy_failover` conmuta a otro proxy en <1s ante timeouts o respuestas anómalas.
- **Regla Anti-Quema de Saldo:** Exclusión estricta de proveedores con HTTP 402 (`IPRoyal sin saldo`) o baja reputación (`LitPort`).
- **Restricción Dura:** Proxies residenciales se usan **exclusivamente para JSON** (prohibido descargar estáticos, JS o imágenes).

### 3. Bus de Eventos SSE en Memoria (`_sse_queues`)
- Distribución de eventos en tiempo real hacia navegadores y callbacks de Telegram vía `/api/stream`.
- **Protección Singleton:** Línea `sys.modules.setdefault("app", sys.modules[__name__])` para evitar la duplicación de colas por doble-import de FastAPI.

### 4. Entorno de Despliegue (Docker en KVM4)
- Corre en contenedor Docker `betmexico-web` con volumen persistente en `/data`.
- Logs rotativos en `/data/logs/dashboard.log` (evita depender de `systemd` dentro del contenedor).
