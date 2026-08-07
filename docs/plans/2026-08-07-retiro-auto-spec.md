# Retiro automático (spec de Robert, dictada en vivo 2026-08-07)

> Capturado tal cual lo dijo Robert mientras retiraba en vivo de `a323440@uach.mx`, para no
> perderlo entre threads de la misma sesión. NO implementado todavía — depende del fix de
> [2026-08-07-handoff-account-refresh-withdrawal-reconciliation.md](2026-08-07-handoff-account-refresh-withdrawal-reconciliation.md)
> (sin reconciliación server-side confiable de `status_api`, no hay forma honesta de saber
> "cuándo se liberó el retiro anterior" ni "cuándo se recibió el SPEI" sin que alguien esté
> mirando el tab).

## Flujo

1. **Primer retiro**: monto $100. Debe dispararse **al menos 15 minutos después** de haber
   recibido el SPEI (el depósito que fondeó la cuenta).
2. **Confirmación visual obligatoria** (Telegram + portal) de dos cosas antes/al disparar el
   primer retiro:
   - El SPEI fue recibido.
   - La cuenta bancaria de BetMexico se actualizó correctamente — mostrar banco + cuenta
     (enmascarada) tal como la reporta BetMexico, solo como referencia para el operador.
3. **Detección de reembolso a tarjeta** (falla dura, no reintentable): si el primer retiro
   resulta en un reembolso a la tarjeta en vez de un pago real por SPEI, el auto-retiro se
   **detiene** y se le pide al operador que solicite otro SPEI. Candidato técnico para esta
   detección: el campo `gateway` de PASO5 (`get_bank_transaction`, `withdrawals.py`) — ya existe
   `alerts.gatewayMismatch` en `/api/accounts/{id}/withdraw/status/{tx_id}`
   ([app.py:3842](../../app.py)) que distingue gateway=SPEI vs gateway=tarjeta. Falta confirmar
   con Robert si ese flag es exactamente la señal o si hay otra distinción.
4. **Si el primer retiro sale bien**: los siguientes retiros son de **$200 cada uno**.
   - Mínimo **2 minutos** entre que se libera un retiro y se dispara el siguiente.
   - **Uno a la vez** — nunca dos retiros en paralelo sobre la misma cuenta.
   - Repetir hasta agotar el saldo retirable.
5. **Cola/residuo final**: si al final queda menos de $200 pero más de $100, retirar exactamente
   ese remanente. Regla general: **no dejar residuos** — el ajuste de montos no puede ser un
   plano rígido "$200 y luego $100"; necesita una condición que reparta el remanente sin dejar
   piquitos sueltos (ej. si quedan $250, ¿se retiran $200+$50 dejando $50 varado, o se ajustan a
   $125+$125? — **pendiente de confirmar con Robert la regla exacta de repartición**).

## Pendiente de confirmar antes de diseñar la implementación

- ¿El piso de retiro es SIEMPRE $100 (nunca menos), y el techo por transacción SIEMPRE $200?
- Regla exacta de repartición del remanente cuando no cae limpio en múltiplos de $200 desde $100.
- Mecanismo exacto de detección de "reembolso a tarjeta" (confirmar si es `gatewayMismatch` o
  algo más específico).
- ¿Este flujo aplica a TODAS las cuentas con auto-depósito, o es específico de ciertas
  instituciones bancarias / grades?

## Secuencia real medida (Robert, retiro en vivo 2026-08-07, cuenta `a323440@uach.mx`)

7 retiros, $1,557.18 total, ~19m43s. Todos los gaps ≥2 min (cumple la regla dictada):

| # | Monto | Gap vs anterior | Balance resultante |
|---|-------|------------------|---------------------|
| 1 | $100.00 | — | $1,357.18 |
| 2 | $200.00 | 3m47s | $1,157.18 |
| 3 | $200.00 | 2m14s | $957.18 |
| 4 | $200.00 | 2m37s | $757.18 |
| 5 | $200.00 | 3m43s | $557.18 |
| 6 | $257.18 | 4m30s | $300.00 |
| 7 | $300.00 | 2m52s | $0.00 |

Los últimos dos (#6 ajustado a $257.18 para dejar $300 "redondo", #7 se llevó los $300 completos
en una sola transacción en vez de partir 200+100) NO siguieron el patrón simple $200→remanente —
Robert lo hizo así en el momento, sin que quede claro todavía si es una regla repetible o una
decisión ad hoc. **Preguntas abiertas sin responder**: ¿por qué $257.18 en el #6? ¿el tope de
$200/transacción es duro o solo aplica mientras se esperan más SPEIs (el último retiro, al no
haber más fondeo pendiente, se lleva todo de una vez)?

## Fase 2 (posterior al fix de reconciliación) — medir el riesgo de "reembolso a tarjeta"

Robert (2026-08-07): elevar el monto de retiro, o retirar todo de una vez, corre un riesgo alto
de que BetMexico lo regrese como reembolso a tarjeta **incluso después de que el SPEI ya fue
recibido**. No se sabe todavía si la causa es (a) el monto, (b) el tiempo entre retiros, o (c) un
bug de BetMexico — la instrucción explícita es MEDIR, no asumir una regla.

- **Señal de verdad-terreno YA existe**: `get_bank_transaction` (PASO5, `withdrawals.py`) ya
  calcula `gateway_mismatch=True` cuando `gateway==1` (tarjeta) en vez de `gateway==2` (SPEI
  real) — ver `withdrawals.py` docstring de `get_bank_transaction` y el uso en
  `app.py::withdraw_status` (`alerts.gatewayMismatch`).
- **Por qué depende del fix de Bug 1**: hoy esa señal solo se calcula cuando alguien tiene el tab
  abierto — un dataset construido así estaría sesgado hacia los casos vigilados a mano, no hacia
  TODOS los reembolsos reales. Sin resolución server-side incondicional, no hay forma honesta de
  medir la correlación real monto/tiempo → reembolso.
- **Tras el fix**: instrumentar cada fila de `account_withdrawals` con las variables candidatas
  (monto, segundos desde el retiro anterior liberado, segundos desde que se recibió el SPEI que
  fondeó la cuenta) + el resultado (`gateway_mismatch` sí/no) para que el patrón salga de los
  datos acumulados, no de una regla inventada. Diseño de qué columnas/vista exactas: siguiente
  sesión, con `superpowers:brainstorming` (es trabajo creativo nuevo, no un bugfix).

## Siguiente paso

Usar `superpowers:brainstorming` antes de diseñar esto como feature (es trabajo creativo nuevo,
no un bugfix) — y solo después de que el fix de reconciliación de retiros esté deployado y
verificado en vivo (si no, "confirmar que el SPEI fue recibido" seguiría dependiendo de que
alguien tenga el tab abierto, y la Fase 2 de medición quedaría con datos sesgados).
