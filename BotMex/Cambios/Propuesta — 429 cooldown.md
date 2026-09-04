# Propuesta — 429 Cooldown vs DEAD (IMPLEMENTADO)

> **Canvas Asociado:** [[Cambios/Propuesta — 429 cooldown.canvas]]
> **Estado:** **IMPLEMENTADO Y ACTIVO EN PRODUCCIÓN** (`deposits.py`, `auto_deposit.py`).

---

### Contexto y Resolución
Anteriormente, cuando BetMexico o la pasarela respondían con HTTP `429 (Too Many Requests)` o 406 de captcha, la cuenta se marcaba erróneamente como `DEAD`.

### Implementación Actual
1. **Clasificación:** En `classify_deposit_status()`, ante 429 o 406 transitorio se clasifica como `'rate_limited'`.
2. **Cooldown 24h:** Se aplica `cooldown_until = datetime.utcnow() + timedelta(hours=24)`.
3. **Auto-Despertado:** En `select_accounts_for_auto()`, al expirar las 24h la cuenta vuelve al pool automáticamente sin requerir intervención manual ni rescates.
