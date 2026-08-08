# Misión: mapear en vivo el ruteo SPEI-vs-tarjeta en retiros

> **Pendiente, programada para hoy 2026-08-08 en la tarde (después de 15:00).**
> Robert la pidió explícitamente en sesión (no como cron): si la siguiente sesión
> lo ve trabajando BetMexico/retiros/depósitos después de esa hora, **insistir**
> en armar esta sesión de pruebas — no asumir que ya se hizo sin confirmarlo.

## Objetivo

Robert reporta, como dato de campo (no hipótesis — ya lo ha visto pasar con
varias cuentas): después de varios retiros SPEI exitosos seguidos en la misma
cuenta, en algún punto — al subir el monto, o sin que él identifique el
disparador exacto — el retiro **cambia a reembolso a tarjeta** en vez de
SPEI, y eso "caga" la operación (dinero atorado esperando reembolso bancario
en vez de aterrizar limpio por SPEI).

Objetivo de la misión: **capturar ese cambio EN VIVO, con datos duros**, no
inferirlo. Responder con evidencia:
1. ¿Existe un umbral de MONTO que dispara el cambio a reembolso?
2. ¿Es un tema de CONTEO de retiros consecutivos (ej. tras N retiros seguidos,
   el N+1 cambia)?
3. ¿Es tiempo/sincronización (la cuenta de retiro tarda en "consolidarse" del
   lado de BetMexico)?
4. ¿Hay combinación de factores (monto + conteo + tiempo)?

## Lo que YA sabemos (no re-investigar, partir de aquí)

- Nuestro código (`withdrawals.py::begin_withdrawal`) llama **exclusivamente**
  `POST /api/stp/BeginWithdrawal` — nunca elegimos tarjeta nosotros. Si pasa,
  es 100% decisión interna de BetMexico, no de nuestro request.
- **Hueco de instrumentación confirmado y explotable** (`withdrawals.py:471-477`):
  mientras el retiro está `Pending` (PASO4, `GET /api/User/PendingWithdrawal`),
  la respuesta cruda SÍ trae `gatewayType` (1=tarjeta, 2=SPEI) e
  `isCashWithdrawal` — **verificado en vivo hoy** contra un retiro real
  (`f530c740-...`, cuenta `a323440@uach.mx`, id 1632): `{'gatewayType': 2,
  'isCashWithdrawal': False, 'transactionStatus': 2, ...}`. Pero el código
  actual **descarta esos dos campos por completo** durante el estado pendiente
  — solo persiste `gateway` hasta que `transactionStatus==6`, vía PASO5
  (`get_bank_transaction`, `Transactions/ByUser`). Si BetMexico cambia de
  rail A MEDIO CAMINO (antes de status 6), hoy es invisible.
- No existe ningún log histórico de `institution_name`/`gatewayType` a través
  del tiempo — solo el valor final. Por eso el mapeo tiene que hacerse en
  vivo, no se puede reconstruir con lo que ya hay en BD.
- El candado `CARD_LOCKED_OTHER_ACCOUNT` (tarjeta ligada a otro email) es
  100% nuestro, no de BetMexico — no es el mecanismo detrás de este bug.
- Enum de status (retiros), de `docs/RECON_BETMEX_API.md:109-117`:
  `-1/0/1/2 = pendiente (distintos sub-estados)`, `6 = Successful`,
  `-4 = Failed`.

## Prerrequisito: instrumentación mínima ANTES de la sesión de pruebas

Sin esto, la sesión de pruebas no sirve de nada — hay que poder VER
`gatewayType`/`isCashWithdrawal` cambiar en tiempo real, no solo al final:

1. Modificar `withdrawals.py::resolve_withdrawal_status` (o crear un poller
   aparte, más simple y desechable, para no arriesgar el flujo de producción)
   para que en CADA poll de PASO4 (no solo cuando `status==6`) loguee/persista
   `gatewayType` e `isCashWithdrawal` del dict `pending` crudo, con timestamp.
   Sugerido: tabla nueva `account_withdrawal_polls` (append-only) con columnas
   `tx_id, polled_at, transactionStatus, gatewayType, isCashWithdrawal,
   amount`. NO tocar el comportamiento actual del guardarraíl (`alerts`), solo
   agregar captura paralela.
2. Alternativa más rápida si no da tiempo a lo anterior: script standalone
   (`scripts/poll_pending_withdrawal.py`, desechable) que se corre a mano
   durante la sesión, hace poll cada 5-10s (más agresivo que los 60s de
   producción — ES SOLO PARA ESTA SESIÓN DE PRUEBAS, no dejarlo corriendo
   después) contra la cuenta activa, e imprime/guarda cada cambio de
   `gatewayType`/`transactionStatus` con hora exacta.

## Cuentas candidatas para las pruebas (confirmar con Robert cuál usar)

- `a323440@uach.mx` (id BD 1632) — la que se usó hoy, ya con retiro history
  documentado (institución INBURSA, ya pasó por 5 retiros SPEI exitosos hoy:
  $100, $200, $200, $400... revisar historial actualizado antes de retomar).
- Cualquier otra cuenta que Robert señale como "segura para repetir" — el
  criterio es que él la controle y esté dispuesto a mover montos reales de
  prueba varias veces seguidas ahí.

## Metodología propuesta (ajustar con Robert al arrancar la sesión)

1. **Baseline**: snapshot de la cuenta elegida (balance, `withdrawal_ready`,
   `withdrawal_institution`, últimos retiros en `account_withdrawals`).
2. **Modo manual con navegador** (como propuso Robert): él opera la UI real
   de BetMexico/el dashboard a mano — depósitos y retiros — mientras Claude
   corre el poller en paralelo (vía SSH/docker exec a KVM4, usando el JWT
   cacheado de la cuenta, SIN forzar logins nuevos que puedan tirar su sesión
   activa) y captura cada cambio de estado con timestamp.
3. **Variables a variar entre corridas**, una a la vez si es posible (para
   aislar la causa):
   - Monto del retiro (empezar bajo, subir gradualmente hasta reproducir el
     cambio a tarjeta, si aparece).
   - Número de retiros consecutivos sin pausa.
   - Tiempo entre depósito SPEI previo y el retiro (inmediato vs con espera).
   - Método del depósito previo (tarjeta vs SPEI vs ninguno reciente).
4. **Capturar en cada corrida**: `gatewayType`/`isCashWithdrawal` en cada
   poll (no solo al final), `transactionStatus`, timestamps exactos,
   monto, y el estado de `BankAccounts` (institución/CLABE aprobada) antes y
   después.
5. **Objetivo de cierre**: al menos UNA reproducción capturada en vivo del
   cambio a reembolso de tarjeta con el trace completo (para confirmar la
   hipótesis real, no solo la sospecha de Robert), o — si no se reproduce —
   documentar honestamente cuántos intentos/condiciones se cubrieron sin
   éxito, sin forzar una conclusión sin evidencia.

## Límites de seguridad (igual que en esta sesión, no relajar)

- Claude/subagentes: **solo lectura y polling**. Todo depósito/retiro real lo
  dispara Robert manualmalmente. Ningún POST a `BeginWithdrawal`/
  `BeginDeposit`/`card/beginwithdrawal` iniciado por el agente.
- No tocar el monorepo BetMexico legacy fuera de este repo.
- Si se implementa la tabla `account_withdrawal_polls` u otra instrumentación
  permanente: root-cause, TDD, tests en verde, commit+push+deploy directo
  (rutina ya autorizada) — es solo visibilidad, no cambia ruteo de dinero.
- Si el mapeo revela que SÍ hay un umbral/patrón controlable, **no
  implementar ningún cambio de ruteo real sin reportarlo primero** — eso
  sigue requiriendo decisión explícita de Robert antes de deploy.

## Entregable esperado

Reporte corto (formato ya establecido: qué se hizo, qué se encontró, qué
significa, siguiente paso) con:
- Trace(s) capturado(s) del cambio de rail, si se reprodujo.
- Condiciones bajo las cuales SÍ/NO se reprodujo.
- Si aplica: propuesta concreta de safeguard (ej. alerta en vivo si
  `gatewayType` cambia a 1 mientras el retiro está pendiente, para que el
  operador pueda reaccionar antes de que se complete el reembolso).
