# Propuesta — Nueva Regla Married Card (IMPLEMENTADO)

> **Canvas Asociado:** [[Cambios/Propuesta — Nueva regla married card.canvas]]
> **Estado:** **IMPLEMENTADO Y ACTIVO EN PRODUCCIÓN** (`deposits.py`, regla de oro #9).

---

### Invariante Inmutable 1:1
- **1 Tarjeta = 1 Cuenta BetMexico de por vida.**
- Al detectarse un depósito aprobado (`APPROVED`), `is_married = 1` y se asocia `married_card_id`.
- La tarjeta queda excluida del matchmaking general.
- **Recarga Permitida:** La misma tarjeta SÍ puede volver a fondear su misma cuenta casada hasta el tope de 24 horas ($1,499 MXN).
