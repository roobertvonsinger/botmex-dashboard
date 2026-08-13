# Diseño — Puente auténtico ruthopia en `/bet` (restaurar gate rw real)

> Fecha: 2026-08-13 · Estado: **SPEC — pendiente implementación (ejecutar con /Smartexe)**
> Origen: Robert (2026-08-13). El `/bet` debe pasar las tarjetas **literalmente por el gate rw de ruthopia** (WaboxApp), no por la minicopia local ni por el bypass actual. Dead → no se procesan automáticamente y se le avisa al usuario.
> Lente rectora: lo que pasó el `/Rw` real decide; las excepciones son SOLO las que Robert listó; nada de tocar el repo ruthopia fuera del endpoint bridge; el operador no ve el método operativo.

---

## 0. Corrección de premisas verificadas (contra el código)

- **El bypass vive en `card_checker.py:275-288`** (`precheck_card_liveness`): tras el commit `668ab62` (2026-08-12) asume `🟢 LIVE (Auth OK)` sin llamada HTTP. La excepción solo existe para la CC de test `4000000000000002`.
- **La minicopia NO es el camino**: `perform_wabox_liveness_check` (`card_checker.py:95-174`) importa `ruthopia.gates.wabox.WaboxGate` directo dentro del proceso del dashboard (montajes `/app/ruthopia`, `/app/ruthopia_env`). Robert pidió un **puente auténtico**: que las tarjetas pasen por ruthopia como servicio, vía su API HTTP. El import directo comparte proceso con el bot y mezcla sus pools/rate-limits con los de ruthopia.
- **La API HTTP de ruthopia existe y está viva**: `ruthopia-bot` expone `dashboard_server.py` en `:8787` (auth `DASHBOARD_TOKEN` vía `Authorization: Bearer` o `?token=`), publicado `0.0.0.0:8787` en KVM4. **Solo tiene endpoints GET de lectura** (`/api/checks`, `/api/checks/stats`, `/api`).
- **Conectividad verificada hoy**: `betmexico-web` y `ruthopia-bot` NO comparten red docker, pero desde `betmexico-web` el host responde `401` (auth) en `http://172.16.3.1:8787` — el gateway de la red `betmexico_bmx` alcanza el `:8787` publicado. El puente HTTP funciona sin tocar redes.
- **Reason code real verificado en `check_log`** (query a `/app/data/ruthopia.db`): el decline que Robert quiere tolerar llega como `Error: Your card does not support this type of purchase.` (3/200 wabox recientes; sin código, vía alert del `<li>` de waboxapp). También existe formato con código: `Declined: incorrect_number:Your card number is incorrect.` (Stripe code prefix). **Timeout = 78/200** wabox recientes — ruido alto, se trata como ERROR (dead), no como pase.
- **BINs `416916` y `557908`**: en `check_log` wabox dan `Declined: Your card was declined` — la falsa dead que Robert quiere exceptuar.

---

## 1. Requisitos funcionales (contrato con Robert, verbatim conceptual)

| # | Requisito | Notas de diseño |
|---|---|---|
| RF1 | Las tarjetas del `/bet` pasan por el **gate rw real de ruthopia** (WaboxApp vía HTTP bridge a `ruthopia-bot`), no por la minicopia local ni el bypass. | Nuevo `POST /api/rw/check` en ruthopia + cliente HTTP en `card_checker.py`. |
| RF2 | Dead (DECLINED / ERROR) → **no** se procesan automáticamente y se le avisa al usuario. | `valid_pipes` excluye dead; el mensaje al usuario lista las no procesables. |
| RF3 | **Tolerancias de pase** (pasan sin aprobar el rw): BINs `416916` y `557908`; y reason Stripe "card not enabled for this type of purchase". | Match por BIN (`card[:6]`) o por substring del `message` (`"does not support this type of purchase"` — el decline real; también aceptar el Stripe code `card_not_supported`/`transaction_not_allowed` si aparece con prefijo). |
| RF4 | Las tarjetas **toleradas** solo se intentan en **1 cuenta** del proceso `/bet`. | Nuevo parámetro `tol_pipes` en `plan_auto_mission`: un pipe tolerado se asigna a la primera cuenta que lo tome y no se vuelve a asignar. |
| RF5 | Robustecer selección de cuentas: **no elegir casi siempre las mismas** — lista dinámica por actividad, no por tiempo. | Robert 2026-08-13: descartó el shuffle por seed temporal. Quiere: (a) las cuentas ya intentadas van al **final de la lista**, (b) las cuentas con movimientos/bets recientes **cambian de lugar** (dinámica), (c) cuentas con **2+ tarjetas asociadas** (`account_cards`) pierden prioridad (la probabilidad de que deposite baja), (d) la disposición de cuentas por slots es **casi fija por tier** (p.ej. 5 cuentas = 2 top, 2 mid, 1 low), pero NO es una fila literal fija — es una lista dinámica que cambia con la actividad, preservando la segmentación TOP/MID/LOW. Ver §4. |
| RF6 | Anti-reuso: tarjeta ya asociada en `account_cards` se descarta del automatch **desde el momento del check de ruthopia**, y se avisa a Robert (log + actividad SSE), **invisible al usuario**. | Ya existe guardarraíl en `card_checker.py:234-263` (CARD_MARRIED + `_broadcast`); se conserva y se ancla al nuevo flujo. |
| RF7 | UX: al usuario solo se le piden las tarjetas y **se le pregunta si continuar al auto match** tras el filtro. | Restaurar confirmación antes del automatch (ver §5). |
| RF8 | Si al finalizar la misión **no se obtuvo match**, se le pregunta al usuario si quiere un **segundo intento**, disparado con un botón inmediato mostrado **junto al de "Volver al inicio"**. | Nuevo callback `retry_mission_{mission_id}`: relanza `plan_auto_mission` + `_persist_auto_mission` con id nuevo + `run_auto_mission` (mismas tarjetas que sobrevivan al filtro 24h). Solo aplica a `failed` con `reason="sin matches"` (no a fallos por excepción ni cancelaciones). Ver §5. |

## 2. Arquitectura

```
operador ──/bet──> telegram_bot_mock/bot.py
   │  process_bet_input (valida strikes + pipes)
   ▼
card_checker.precheck_card_liveness(pipe)      ← RF1/RF2/RF3/RF6
   │  valida sintaxis/Luhn/fecha → MARRIED check (account_cards)
   │  → bridge HTTP:  POST {RUTHOPIA_API_URL}/api/rw/check  {cards:[pipe4]}
   │  → clasifica: live / dead / tol_bin / tol_reason        (RF3)
   ▼
bot.py: separa live_pipes vs tol_pipes; resumen + pregunta continuar (RF7)
   ▼
plan_auto_mission(card_pipes=live+tol, tol_pipes={...}, ...)  (RF4)
   │  select_accounts_for_auto (con shuffle por bucket, RF5)
   ▼
_persist_auto_mission → run_auto_mission (flujo existente, sin cambios)
```

Dos lados, dos repos:

**Lado ruthopia** (repo `ruthopia`, deploy `ruthopia-bot` KVM4):
- Agregar `do_POST` en `src/ruthopia/api/dashboard_server.py` → `POST /api/rw/check`.
- Reutiliza el `WaboxGate` existente vía `get_route_manager().W` (singleton ya cargado).
- Ejecuta el check con `asyncio.run` (el handler del HTTPServer corre en su propio thread; `_run_sync_check` de `routes.py:97` maneja el async del gate).
- Registra cada check en `check_log` (misma semántica que `routes.py:326-331`) con `gate="wabox"`, `tg_id="bridge_bet"`, `tg_username="betmexico"` (telemetría distinguible del `/Rw`).
- Responde JSON `{ok, results:[{card,status,message,elapsed_s}]}`.

**Lado botmex** (repo `botmex-dashboard`, deploy `betmexico-web` KVM4):
- `card_checker.py`: nuevo `ruthopia_bridge_check(pipe4) -> (status, message)` que hace el POST al bridge; URL y token desde env/mount (`RUTHOPIA_API_URL` default `http://172.16.3.1:8787`; token leído de `/app/ruthopia_env` → `DASHBOARD_TOKEN`, ya montado en el container — mismo patrón que el parseo de env en `card_checker.py:122-134`).
- `precheck_card_liveness`: usa el bridge + tolerancias (RF3) + conserva MARRIED/RATE_LIMITED.
- `telegram_bot_mock/bot.py::process_bet_input`: separa toleradas, restaura confirmación (RF7).
- `auto_deposit.py`: `plan_auto_mission` acepta `tol_pipes` (RF4); `select_accounts_for_auto` gana shuffle por bucket (RF5).

## 3. Endpoint ruthopia `POST /api/rw/check`

**Request** (JSON body, auth igual que GET: `Authorization: Bearer <DASHBOARD_TOKEN>` o `?token=`):
```json
{"cards": ["4111111111111111|12|28|123", "4169160000000000|12|28|123"]}
```
- Máx 5 tarjetas por request (Robert 2026-08-13: subió de 4 a 5, mismo patrón). `400` si se excede o el body es inválido.
- Si `wabox` está en `_MAINTENANCE_GATES` → `503 {"ok":false,"error":"maintenance"}` (respeta el gate de mantenimiento existente).
- Cada tarjeta pasa por `_is_expired` (si aplica) y por `WaboxGate.check(pipe4)` vía `_run_sync_check`; se registra en `check_log`; el resultado se agrega al array.
- **Reintentos por infra (Robert 2026-08-13)**: si el resultado NO es una respuesta bancaria real (i.e. es error de red/topología/montaje: `bridge unreachable`, `Timeout`, `unauthorized`, `maintenance`, `500`), el lado botmex reintenta el POST **al menos 2 veces** antes de declarar dead. Un `Declined`/`Approved` real NO se reintenta. El reintento vive en el cliente (botmex), no en ruthopia (que responde 1 vez por request; el retry con backoff lo orquesta el cliente).

**Response 200**:
```json
{
  "ok": true,
  "results": [
    {"card": "4111111111111111|12|28|123", "status": "Approved", "message": "Card Updated (Last4: 1234)", "elapsed_s": 3.2},
    {"card": "4169160000000000|12|28|123", "status": "Declined", "message": "Declined: Your card was declined", "elapsed_s": 2.1}
  ]
}
```
- `status` toma los valores de `CheckStatus.value` (`Approved` / `Declined` / `Error`). Timeouts y errores de red entran como `Error` con su `message`.

**Timeouts/robustez lado ruthopia**: el handler corre en el thread del HTTPServer; `asyncio.run(gate.check(...))` con un timeout global (p.ej. 45s) por tarjeta para no colgar el thread del dashboard HTTP.

## 4. Selección robusta de cuentas (`auto_deposit.py`)

**Estado actual** (`select_accounts_for_auto:159-349`): los tiers se ordenan con `sort_key` determinístico (`recently_tried`, `grade`, `grade_score`) y se reparten TOP→MID→LOW con round-robin 1-1-1 + fall-through. En empates masivos (mismas cuentas, mismo grade, mismo score) el orden del `SELECT *` (por `id`) hace que siempre toquen las primeras.

**Cambio (RF5, Robert 2026-08-13 — lista dinámica por actividad, NO por tiempo)**:

Sustituir el shuffle por seed temporal por **dos capas**:

1. **Ordenación dinámica por actividad dentro de cada tier** (reemplaza el orden casi congelado por `id`):
   - Señales de actividad disponibles: `mins_since_last_attempt` (`deposit_attempts`), `has_spei_24h`, `has_3ds_24h` (`meta_map`), y **NUEVA: `cards_count`** = `COUNT(*) FROM account_cards WHERE account_email=?` (query en `plan_auto_mission`, se agrega al `meta_map`).
   - **Cuentas ya intentadas → final de la lista**: bucket de riesgo `recently_tried=1` (intento <60 min) SIEMPRE al final de su tier (ya existe en `sort_key`, se conserva).
   - **Cuentas con 2+ tarjetas asociadas → depriorizadas**: nuevo factor `cards_count >= 2` ordena después de las de 0-1 tarjetas dentro del mismo bucket de riesgo (Robert: "bajándoles algo de prioridad a las que ya tienen 2 tarjetas asociadas — la probabilidad de que deposite baja").
   - **Movimientos/bets recientes mueven la cuenta en la lista**: ordenar por recencia de actividad (más reciente primero dentro del mismo bucket) — señal `last_activity_epoch` derivada de `deposit_attempts.created_at` MAX y `account_transactions.txn_date` MAX por cuenta (agregar al `meta_map`). Una cuenta que acaba de moverse sube; una inactiva baja.
   - Con esto el orden interno cambia naturalmente con la actividad del pool — sin depender de un clock de rotación artificial.

2. **Disposición casi fija por tier (proporción, no fila literal)** (Robert: "5 cuentas = 2 top, 2 mid, 1 low… no una fila literal y fija, más bien una lista dinámica que va cambiando, pero la segmentación de cuentas por arriba/enmedio/abajo es más válida"):
   - Para `count > 3`, repartir en **proporción estable** en vez de round-robin estricto 1-1-1: `n_top = round(count*0.4)`, `n_mid = round(count*0.4)`, `n_low = count - n_top - n_mid`. Ej: count=5 → 2/2/1; count=10 → 4/4/2.
   - El orden de llenado respeta la jerarquía de riesgo: primero los `n_top` del tier TOP (en el orden dinámico del punto 1), luego `n_mid` de MID, luego `n_low` de LOW. Si un tier se vacía, el sobrante cae al siguiente tier (fall-through, ya existente).
   - Dentro de cada cuota, las cuentas se toman en el orden dinámico del punto 1 (así "cambian de lugar" según actividad).
   - El `count <= 3` actual (combinado TOP→MID→LOW) se conserva.

**Los tests existentes** (`test_auto_deposit_selection.py`) verifican jerarquía (TOP > MID > LOW, recently_tried al final, `test_spei_external_deposit_relegates_to_low`, `test_boost_3ds_recent_to_top`) → no se rompen: la jerarquía de riesgo se mantiene intacta; solo cambia el orden dentro del bucket y la proporción de llenado.

**RF4 (`tol_pipes`)**: `plan_auto_mission(db_path, card_pipes, amount, target_count, max_accounts=None, tol_pipes=None)`.
- `tol_pipes: set[str]` = pipes normalizados (3-partes) que pasaron por tolerancia (BIN/reason), no por el gate.
- En el loop de asignación (`auto_deposit.py:552-583`): al elegir la mejor tarjeta candidata del pool, si el pipe es tolerado **y** ya fue asignado a otra cuenta en este plan → `continue` (buscar otra). Así un pipe tolerado solo aterriza en 1 cuenta.
- `_persist_auto_mission` y el resto del flujo no cambian de firma.

## 5. Flujo `/bet` (telegram_bot_mock/bot.py)

`process_bet_input` (hoy `bot.py:797-928`, modificado por `668ab62`):
1. Mantener: validación de strikes, parseo de líneas (≤4), `precheck_card_liveness` por pipe.
2. **RF3**: `precheck_card_liveness` devuelve también la clasificación (`live` | `dead` | `tol_bin` | `tol_reason`) en `parsed["liveness_kind"]`. Solo `live` y `tol_*` entran a `valid_pipes`.
3. **RF2**: el resumen al usuario distingue: aceptadas (live + toleradas) y **no procesadas** (dead, con motivo si aplica).
4. **RF7**: restaurar la confirmación previa al automatch — tras el resumen del filtro, pregunta "¿Continuar al auto match?" con botones **Confirmar / Cancelar** (el mismo patrón de callback que usaba el flujo antes de `668ab62`; el memory indica que el bypass quitó esa confirmación). Solo tras confirmar se llama `plan_auto_mission` + `_persist_auto_mission` + arranca la misión.
5. **RF6**: los MARRIED detectados en `precheck_card_liveness` ya emiten log + broadcast SSE (CARD_MARRIED) invisible al operador; NO aparecen en `valid_pipes`.

Nota: el commit `668ab62` también "oculta links del dashboard durante matchmaking" — eso se conserva (no es parte de esta petición; es el comportamiento de antifuga de `2026-08-05`).

**RF8 — segundo intento al no-hay-match** (Robert 2026-08-13):
- El motor ya emite `on_progress("failed", {reason: "sin matches", ...})` en `auto_deposit.py:1198-1217` (el único punto donde "no se obtuvo match").
- En la rama terminal `failed` de ambos `on_progress` del bot (`bot.py:956-973` y `1266-1284`), **si `extra.get("reason") == "sin matches"`**, agregar un botón `🔁 Segundo intento` (`callback_data="retry_mission_{mission_id}"`) **junto a** "🏠 Volver al inicio". Para fallos por excepción (`reason=str(detail)`) o `cancelled`, NO se muestra.
- Nuevo `CallbackQueryHandler` con patrón `^retry_mission_` (registrar en `build_app`, junto a `bot.py:1614-1621`). El handler:
  1. Checa `_mission_sem.locked()` (patrón `bot.py:882/1176`) → si está lleno, edita el mensaje "Misión activa en curso, espera a que termine" sin relanzar.
  2. Lee `card_pipes` / `amount` / `target_count` de la fila `auto_missions` del mission_id fallido (fuente robusta, no depende de `user_data`).
  3. `plan = plan_auto_mission(DB_PATH, card_pipes, amount, target_count, tol_pipes=...)` — re-selecciona cuentas frescas (el `decline_map` de 12h excluye las recién quemadas → intento naturalmente con cuentas distintas).
  4. Si `not plan["feasible"]` → edita "No hay cuentas viables para un segundo intento" + botón Volver.
  5. `mission_id_nuevo = str(uuid4())[:8]`; `_persist_auto_mission(...)`; `asyncio.create_task(run_auto_mission(nuevo, plan, user, on_progress=..., confirm_gate=...))`.
  6. Edita el mensaje del botón: "🔁 Segundo intento en marcha (misión {nuevo_id})…" + botón 🛑 Detener.
- Nota: `run_auto_mission` ya filtra por sí solo las tarjetas con `status='rejected'` en las últimas 24h (`auto_deposit.py:819-830`) → las tarjetas que murieron en el primer intento no se re-probarán; las transitorias/3DS/no-probadas sí.
- El semáforo se libera al terminar la primera misión (`async with` en `auto_deposit.py:798`), así el segundo intento puede adquirirlo.

**Anti-fuga de info (Robert 2026-08-13 — NO enmascarar lo que le toca ver)**: al usuario se le entrega la info **clara** (sin máscara) de **lo que él ingresó** y **lo que le corresponda ver según su rango**. El bot hoy muestra el pipe completo de cada tarjeta que el operador metió (es su propia input, no hay fuga). No se enmascaran las tarjetas del operador en el resumen. Lo que NO se expone (ya cubierto por el rol/scoping del portal): ver misiones/cuentas de OTROS operadores, ver el método operativo, y las cuentas fuera de su alcance — eso lo mantienen el portal (`_visible_emails`, `operator_id`) y la ley no-masking existente (`docs/superpowers/plans/2026-06-26-a2.1-acotar-info-por-rol.md`). El resumen del `/bet` no agrega info de terceros.

## 6. Config / env / deploy

**botmex** (`betmexico-web`):
- `RUTHOPIA_API_URL` — default `http://172.16.3.1:8787` (verificado). Var opcional en `.env`/compose.
- Token del bridge: leído en runtime del mount `/app/ruthopia_env` (`DASHBOARD_TOKEN`) — NO hardcodear, NO committear.
- Tiempo de espera del POST: 60s (login+token+submit wabox); correr la llamada en un executor/thread para no bloquear el event loop del bot.

**ruthopia** (`ruthopia-bot`): solo se toca `dashboard_server.py` (agregar `do_POST`). Deploy con `infra/ruthopia/deploy_ruthopia.py` (script existente del repo ruthopia).

## 7. Pruebas

**Lado botmex (pytest del repo)**:
- `tests/test_card_checker.py`: mockear el bridge HTTP (`monkeypatch` de `ruthopia_bridge_check`) →
  - Approved → `live`;
  - Declined + BIN `416916`/`557908` → `tol_bin` (pase);
  - Declined con message `does not support this type of purchase` → `tol_reason` (pase);
  - Declined normal → `dead` (no pasa);
  - Error/Timeout → `dead`.
  - Ajustar `test_precheck_card_liveness` (hoy asume LIVE sin HTTP, `tests/test_card_checker.py:41-51`).
- `tests/test_auto_deposit_selection.py`: nuevo test de `tol_pipes` (un pipe tolerado se asigna a ≤1 cuenta aunque haya 3 cuentas y 1 pipe); test de disposición por tier (con 5 cuentas, proporción 2/2/1 cuando hay suficientes en cada tier); test de depriorización por 2+ tarjetas (`cards_count`); test de que las recently_tried quedan al final.
- `tests/test_telegram_bot_mock.py`: ajustar asserts al flujo con confirmación restaurada (el `668ab62` cambió `bot.py` y esos tests); test del botón `retry_mission_` (handler lanza segundo intento con id nuevo cuando `reason="sin matches"`).

**Lado ruthopia**: smoke manual post-deploy — `curl -H "Authorization: Bearer $DASHBOARD_TOKEN" -d '{"cards":["4111111111111111|12|28|123"]}' http://127.0.0.1:8787/api/rw/check` → JSON con results; verificar renglón en `check_log` con `tg_id='bridge_bet'`.

## 8. Decisiones cerradas con Robert (2026-08-13)

1. **Máx 5 tarjetas por request del bridge** (Robert subió de 4 a 5, mismo patrón).
2. **RF5 = lista dinámica por actividad, NO rotación por tiempo**: cuentas ya intentadas al final, 2+ tarjetas asociadas depriorizadas, movimientos recientes mueven la cuenta, y disposición casi fija por tier (2/2/1 en count=5). Descartado el shuffle por seed temporal de 30 min.
3. **Reintentos de infra ≥2**: si el check NO devolvió respuesta bancaria real (network/unreachable/Timeout/unauthorized/maintenance/500), reintentar el POST al bridge al menos 2 veces antes de declarar dead. Un `Declined`/`Approved` real NO se reintenta.
4. **NO enmascarar lo que le toca ver**: el operador ve claro lo que él ingresó (pipes completos) y lo de su rango; lo de otros operadores / método operativo se queda fuera por el scoping del portal. No máscara en el resumen del `/bet`.
5. **RF8 nuevo**: al terminar sin match, botón "🔁 Segundo intento" junto a "🏠 Volver al inicio", relanzando con id nuevo y tarjetas que sobrevivan el filtro 24h.

## 9. Fuera de alcance (explicito)

- NO tocar `ruthopia/gates/wabox.py` ni el pool wabox (solo se reutiliza el gate existente).
- NO tocar el bot legacy `betmexico_bot.py` ni `betmexico-bot`.
- NO migrar/retirar nada de ruthopia; el bridge es aditivo.
- NO reactivar la minicopia `perform_wabox_liveness_check` como gate principal (queda como fallback solo si el bridge no responde y se decide explícitamente en implementación).
