# 06 — Sesiones, JWT y Refresh

**Ubicación:** `jwt_keeper.py`, `account_refresh.py`, `prewarm.py`.
**Canvas Raíz:** [[00 — BotMex System Map.canvas]]

### Ficha Técnica
- **Qué inicia el flujo:** Loop en background cada 5 min (`ACCOUNT_REFRESH_INTERVAL_SEC=300`) o trigger `/prewarm`.
- **Decisión central:** Identificar cuentas con JWT vigente para renovarlo sin solicitar nuevo captcha. Priorizar cuentas "hot" (saldo >$50 o retiro activo).
- **Qué modifica:** Columna `jwt_token`, `last_refresh` y saldo real en `betmexico_accounts.db`.
- **Qué comunica:** Evento de cuenta actualizada y lista para match sin costo de login.
