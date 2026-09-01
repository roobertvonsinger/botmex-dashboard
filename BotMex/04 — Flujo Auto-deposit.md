# 04 — Flujo Auto-deposit

**Ubicación:** `auto_deposit.py`, `deposits.py`.
**Canvas Detallado:** [[04 — Flujo Auto-deposit.canvas]]

### Ficha Técnica
- **Qué inicia el flujo:** `/bet` confirmado desde Telegram o Web con lote de tarjetas (`pipes`).
- **Decisión central:**
  1. **Matchmaking Tier 40/40/20 (A/B/C):** Selección balanceada de cuentas sanas.
  2. **Exclusiones & Anti-Mezcla:** Cuentas `DEAD`, `cooldown_until` (429), `locked_by` ajeno. Si saldo $\ge \$100$ fondeado <24h, PROHIBIDA tarjeta distinta (evita baneo pasarela). Misma tarjeta casada SÍ puede recargar (hasta cap 24h de $1,499).
  3. **Tie-Break JWT:** Preferir cuentas con JWT vivo antes del grade dentro de Tier LOW.
  4. **Tope duro:** Máx 10 cuentas por corrida.
  5. **Anti-huella:** Piso de espera de 45-60s en `status: preparing`.
  6. **Clasificación:** `APPROVED` (casar tarjeta), `REJECTED` (jubilar tarjeta), `LOCKED` (jubilar ya), `TRANSITORIO` (hasta 4 reintentos).
- **Qué modifica:** Columna `balance`, `is_married`, `deposit_status` en SQLite.
- **Qué comunica:** Broadcast SSE continuo (`_broadcast_mission`) al bot y al portal.
