# Propuesta de Cambio — 429 Cooldown vs DEAD

**Canvas Asociado:** [[Cambios/Propuesta — 429 cooldown.canvas]]
**Estado:** Propuesta lista para implementación.

### Contexto
Cuando BetMexico o la pasarela responden con código HTTP `429 (Too Many Requests)`, la lógica actual en `auto_deposit.py` marca la cuenta de inmediato como `DEAD`.

### Dolor Operativo
Las cuentas marcadas `DEAD` se descartan y nunca más se usan. Un pico de tráfico de 10 minutos puede matar 5-10 cuentas perfectamente sanas que solo necesitaban descansar unas horas.

### Solución Diseñada
1. En `classify_deposit_status()`, cuando el código sea 429:
   - Cambiar estatus a `'rate_limited'`.
   - Establecer marca temporal `cooldown_until = datetime.utcnow() + timedelta(hours=24)`.
2. En `select_accounts_for_auto()`:
   - Excluir solo si `status == 'rate_limited' AND cooldown_until > datetime.utcnow()`.
   - Si ya expiró el cooldown, la cuenta vuelve automáticamente a la selección sin intervención humana.
