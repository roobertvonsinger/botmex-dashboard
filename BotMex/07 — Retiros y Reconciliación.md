# 07 — Retiros y Reconciliación

**Ubicación:** `withdrawals.py`, `clabe_fetch.py`, `renapo_validator.py`.
**Canvas Raíz:** [[00 — BotMex System Map.canvas]]

### Ficha Técnica
- **Qué inicia el flujo:** Cuenta con balance acreditable > $0 y sin bloqueo de seguridad.
- **Decisión central:** Validación de CLABE STP y CURP titular para dispersión instantánea.
- **Qué modifica:** Estatus de cuenta `withdrawing` → `withdrawn` y decremento de saldo operativo.
- **Qué comunica:** Emisión de ficha SPEI 1-click copy directamente al bot de Telegram y dashboard.
