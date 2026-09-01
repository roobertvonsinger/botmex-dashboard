# 05 — Validación de Tarjetas & Liveness

**Ubicación:** `card_checker.py`, `bin_intelligence.py`, `shared/betmexico_payment_analyzer.py`.
**Canvas Raíz:** [[00 — BotMex System Map.canvas]]

### Ficha Técnica
- **Qué inicia el flujo:** Comando `/check` o cosecha desde Ruthopia Bridge (`vault_cards.db`).
- **Decisión central:** Análisis de BIN, algoritmos de pasarela y pre-verificación sin quemar crédito.
- **Qué modifica:** Marca de tarjetas en base de datos: Válida, Quemada, Locked o Requiere 3DS.
- **Qué comunica:** Reporte al operador si la tarjeta está lista para ser inyectada al pipeline `/bet`.
- **A qué flujo abre:** [[04 — Flujo Auto-deposit]].
