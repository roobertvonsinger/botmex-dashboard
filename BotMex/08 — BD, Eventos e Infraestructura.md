# 08 — BD, Eventos e Infraestructura

**Ubicación:** `betmexico_db.py`, `proxy_pool.py`, KVM4-old (`100.77.154.31`), KVM4-karen (`2.25.98.162`).
**Canvas Raíz:** [[00 — BotMex System Map.canvas]]

### Ficha Técnica
- **Qué inicia el flujo:** Toda llamada HTTP saliente y toda transacción de persistencia.
- **Decisión central:**
  - **SQLite:** WAL mode, timeout 30s, cero lockeos largos.
  - **Proxy Pool:** Rotación con failover (`call_with_proxy_failover`); exclusión estricta de LitPort e IPRoyal sin saldo (402).
- **Qué modifica:** Tablas maestras `accounts`, `missions`, `cards`, `deposits`, `withdrawals`.
- **Qué comunica:** Canal de streaming SSE (`/api/stream`) y túneles HTTP/S limpios.
