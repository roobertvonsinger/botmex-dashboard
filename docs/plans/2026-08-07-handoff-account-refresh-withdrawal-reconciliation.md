# Handoff — reconciliación server-side de retiros pendientes + fuente única de institución

## Contexto de producto

`botmex-dashboard` es el panel operativo del bot BetMexico (repo independiente, Forgejo
`Robertvs/botmex-dashboard`). Los operadores retiran saldo de cuentas BetMexico vía SPEI/STP.
Todo el flujo de retiro vive en `withdrawals.py` (5 pasos, documentados en su docstring) y se
expone vía `app.py`. Hay un bg-loop separado, `account_refresh.py`, que corre cada
`ACCOUNT_REFRESH_INTERVAL_SEC` (default 1200s) y refresca balance de cuentas con JWT vigente.

NO tocar: `deposits.py` (flujo de depósito con tarjeta), `auto_deposit.py`, `login_orchestrator.py`,
nada del bot de Telegram. Este handoff es EXCLUSIVAMENTE sobre `account_refresh.py` +
`withdrawals.py` + tests asociados.

## Bug 1 (el principal) — status de retiro pendiente nunca se resuelve solo

**Síntoma confirmado por Robert en vivo (2026-08-07)**: una cuenta con retiro "en proceso" no
avanza a un estado terminal en el dashboard salvo que un operador tenga el panel de esa cuenta
abierto en un tab con el navegador vivo.

**Causa raíz (confirmada leyendo código, con líneas)**:

- `account_withdrawals.status_api` (columna que decide si el retiro sigue pendiente o ya
  terminó) SOLO se escribe desde el endpoint `GET /api/accounts/{account_id}/withdraw/status/{tx_id}`
  en `app.py` (función `withdraw_status`, aprox. líneas 3782–3926). Esa función es la ÚNICA que
  llama a `get_pending_withdrawal` (PASO4) y `get_bank_transaction` (PASO5) de `withdrawals.py` —
  las únicas dos llamadas que pueden mover `status_api` a un valor terminal (6 = ejecutado, <0 =
  fallido).
- Ese endpoint SOLO lo dispara un `setInterval` en JavaScript del lado del navegador:
  `_wdPolls` en `static/pantalla.js` (función `_fetchWithdrawStatus`, aprox. línea 610) y el
  mismo patrón en `static/portal.js` (aprox. línea 689). Ese poll vive en memoria del tab del
  navegador — se detiene si se cierra la pestaña, se navega a otra cuenta, o si nadie abrió esa
  cuenta cuando el retiro se resolvió.
- `account_refresh.py` SÍ corre server-side sin depender de ningún tab abierto (bg-loop en
  `run_refresh_cycle`), y SÍ marca la cuenta como prioritaria ("hot", bypassea todos los filtros
  de grade/pool/lock) cuando tiene un retiro pendiente vía `is_hot_account`
  (`has_pending_withdrawal`, aprox. línea 166 en `account_refresh.py`). PERO el cuerpo del ciclo
  (aprox. líneas 320–379) solo hace: (a) fetch de balance/movimientos "balance_only", (b) un
  check de `withdrawal_ready` vía `get_bank_accounts` (esto es PASO1, para saber si HAY una cuenta
  de retiro aprobada para un FUTURO retiro — no tiene nada que ver con resolver el retiro YA
  disparado). Nunca llama `get_pending_withdrawal`/`get_bank_transaction`. El loop que "sabe" que
  hay un retiro pendiente no tiene ningún camino de código para resolverlo.

## Bug 2 (relacionado, mismo archivo) — dos fuentes independientes para "institución de retiro"

**Síntoma confirmado por Robert en vivo (2026-08-07, cuenta `a323440@uach.mx`, id 1632)**: el
badge del dashboard mostraba "BANAMEX" (columna `accounts.withdrawal_institution`) mientras que
el retiro que REALMENTE se disparó en el mismo segundo fue a INBURSA (columna
`account_withdrawals.institution_name`, transactionId `90502403-3e1c-4f9f-9d66-19f3fbae304d`).
Verificado con SELECT directo en BD prod (KVM4) — ambas filas con timestamp `15:28:19` del mismo
día, valores distintos.

**Causa raíz**: `account_refresh.py` (líneas ~340–378, dentro del bloque `withdrawal_ready`) hace
su PROPIA llamada a `get_bank_accounts` (PASO1) para decidir `withdrawal_institution`, totalmente
independiente de la llamada a `get_bank_accounts` que hace `execute_withdrawal` en
`withdrawals.py` al disparar el retiro real. Dos llamadas independientes a la misma API pueden
(y en este caso lo hicieron) devolver resultados distintos en la misma ventana de tiempo — no hay
una sola fuente de verdad para "cuál es la cuenta bancaria destino ahora mismo".

## Dato de campo (Robert, en vivo 2026-08-07) — cadencia real de resolución

Un retiro normalmente resuelve (pasa de pendiente a terminal) en **1-2 minutos**. En casos raros
puede tardar **10-15 minutos**. Esto es MEDIDO por Robert operando en vivo, no una estimación.

**Implicación dura para el fix**: el ciclo genérico de `account_refresh.py` corre cada
`ACCOUNT_REFRESH_INTERVAL_SEC` (default 1200s = 20 min) — eso es 10-20x más lento que el caso
normal. Si el fix de Bug 1 solo se engancha al ciclo genérico, el operador seguiría viendo
"en proceso" hasta 20 minutos después de que el retiro YA resolvió, que es casi el mismo problema
con otro número. **La resolución de retiros pendientes necesita su propia cadencia, corta**, NO
la cadencia de refresh de balance de 20 min. `get_pending_withdrawal` (PASO4, `withdrawals.py`)
ya documenta en su propio docstring "el polling es 60s mínimo — no taladrar (rate-limit)" — usar
ESE piso (60s) como intervalo del nuevo mecanismo, no el de 1200s.

## Fix pedido

### Parte A — cerrar Bug 1

**Requisito de cadencia (no negociable, ver dato de campo arriba)**: la resolución de retiros
pendientes debe correr en un ciclo propio de ~60s (el piso documentado en PASO4), independiente
del ciclo genérico de `account_refresh.py` de 20 min. Puede ser un `asyncio` sub-loop dentro del
mismo módulo que solo itera cuentas con retiro pendiente activo (`_PENDING_WD_EXISTS_SQL`) — ese
universo es chico (solo cuentas con retiro en curso ahora mismo), así que 60s no es taladrar la
API en general, es taladrar SOLO lo que realmente está pendiente. Declarar el intervalo como
constante nombrada (ej. `WITHDRAWAL_POLL_INTERVAL_SEC = 60`), no un número mágico inline.

En `account_refresh.py`, dentro de `run_refresh_cycle` (el bloque que ya existe para cuentas
`hot` con `has_pending_withdrawal=True`, ver el bloque `withdrawal_ready` actual ~líneas 340-379)
o en el nuevo sub-loop de 60s (lo que OpenCode decida más limpio — declarar la decisión en el
reporte final):

1. Antes (o en vez) de solo chequear `withdrawal_ready`, si la cuenta tiene un retiro pendiente
   real (existe fila en `account_withdrawals` con `status_api IS NULL OR (status_api >= 0 AND
   status_api != 6)` — ESTA es la misma condición SQL que ya usa `_PENDING_WD_EXISTS_SQL`,
   reusarla, no reescribirla), llamar `get_pending_withdrawal(jwt, proxy_url)` (PASO4) igual que
   hace `app.py::withdraw_status`.
2. Replicar la MISMA lógica de decisión que ya existe en `app.py::withdraw_status`
   (líneas 3822–3926: si `status_api==6` confirmar con `get_bank_transaction` PASO5 antes de
   marcar terminal; si no hay `pending` pero `status_api` previo indica terminal, no tocar; si
   nada resuelve, dejar en pending para el próximo ciclo) — NO inventar una lógica nueva, es
   copiar/extraer la que ya está probada ahí a una función compartida que ambos (el endpoint HTTP
   y el bg-loop) puedan llamar. Evaluar extraer esa lógica de `app.py::withdraw_status` a una
   función reusable en `withdrawals.py` (p.ej. `resolve_withdrawal_status(jwt, proxy_url, tx_id,
   expected_digits, prev_status_api)` que devuelva el mismo dict `out` que hoy construye
   `withdraw_status`) para que `app.py` y `account_refresh.py` llamen la MISMA función en vez de
   duplicar la lógica.
3. Persistir el cambio en `account_withdrawals` (mismos UPDATEs que ya hace `app.py`:
   `status_api`, `gateway`, `last_modified_utc`).
4. Emitir el mismo broadcast SSE `kind: "withdrawal_status"` que ya emite `app.py` (líneas
   ~3928-3940) cuando el estado pasa a terminal, para que cualquier tab abierto lo vea sin su
   propio poll.

### Parte B — cerrar Bug 2

En el mismo ciclo, para cuentas `hot`, usar UNA sola llamada a `get_bank_accounts` por cuenta por
ciclo (no dos llamadas independientes a la misma API para cosas distintas). Concretamente: el
bloque `withdrawal_ready` de `account_refresh.py` y `execute_withdrawal` de `withdrawals.py` no
comparten llamada porque corren en momentos distintos (uno es periódico, el otro es on-demand al
disparar el retiro) — esto es aceptable, PERO cuando `execute_withdrawal` SÍ dispara un retiro,
debe también actualizar `accounts.withdrawal_institution`/`withdrawal_ready` con el resultado de
SU PROPIA llamada a `get_bank_accounts` (que ya hace), en vez de dejar que la próxima ejecución
de `account_refresh.py` (hasta 20 min después) sea la única que la actualice. Buscar dónde
`execute_withdrawal` ya tiene el resultado de `get_bank_accounts` (PASO1, `withdrawals.py`
~líneas 85-128) y, tras disparar el retiro con éxito, persistir `withdrawal_institution` con la
institución REALMENTE usada (reusar `account_refresh._db_set_withdrawal_ready` si es importable
sin ciclo, o su misma query UPDATE).

## Fuera de alcance

- NO tocar `deposits.py`, `auto_deposit.py`, el flujo de depósito con tarjeta.
- NO diseñar todavía la automatización de "retiro auto" para operadores (hay un spec de Robert en
  `docs/plans/2026-08-07-retiro-auto-spec.md`, pero es trabajo aparte, posterior a este fix).
- NO cambiar el intervalo de `account_refresh.py` (`ACCOUNT_REFRESH_INTERVAL_SEC`) ni los
  criterios de `is_hot_account` — ya cubren `has_pending_withdrawal` correctamente, el problema
  es lo que el ciclo HACE con esa cuenta, no cómo la selecciona.
- NO agregar dependencias nuevas.

## Verificación esperada antes de reportar terminado

1. `python -m pytest test_account_refresh.py test_withdrawals.py test_withdrawals_endpoints.py -q`
   — deben pasar TODOS (agregar los nuevos tests ahí, no en archivos nuevos).
2. Nuevo test en `test_account_refresh.py`: cuenta con fila en `account_withdrawals` con
   `status_api=2` (pendiente) marcada `hot` por `has_pending_withdrawal` → el mecanismo de
   resolución debe llamar `get_pending_withdrawal`/`get_bank_transaction` (mockeados) y el UPDATE
   de `status_api` debe reflejarse en BD sin que nada del lado HTTP/cliente intervenga. Test
   separado que confirme el intervalo del nuevo ciclo/sub-loop es ~60s (constante nombrada, NO
   1200s) — assert sobre la constante, no sobre tiempo real transcurrido.
3. Nuevo test: `execute_withdrawal` exitoso debe dejar `accounts.withdrawal_institution` igual a
   la institución de la cuenta bancaria REALMENTE usada en esa transacción (no la de un chequeo
   viejo).
4. `git diff --stat` acotado a: `account_refresh.py`, `withdrawals.py`, `app.py` (solo si se
   extrae la función compartida), `test_account_refresh.py`, `test_withdrawals.py`. Cualquier otro
   archivo modificado es fuera de alcance — revertir.
5. Reportar en el resultado final: qué función se extrajo/comparte (si aplica), qué tests se
   agregaron, y el diff completo de los archivos tocados.
