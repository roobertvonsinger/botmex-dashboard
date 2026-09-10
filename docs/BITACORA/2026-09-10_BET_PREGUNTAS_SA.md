# Bitácora — `/bet`: preguntas SA-only (con/sin liveness · ignorar casamiento) — 10-sep-2026

## Pedido de Robert
En el flujo `/bet` (bot Telegram, contenedor `betmexico-mock-bot`):
1. **Siempre**, una vez que el SA ingresa las tarjetas, preguntarle **solo a él** si correr
   el `/bet` **con check** o **sin check** de liveness (gate RW de Ruthopia). "Sin check"
   deshabilita el liveness **solo para esa corrida**.
2. **Cuando se detecta una tarjeta que ya está en otra cuenta (casada en BD)**, preguntarle
   también — además de "intentar en su cuenta casada", una opción para **ignorar el
   casamiento**: tratar la tarjeta como no enlazada y mandarla al pool junto con las demás.
3. Los **demás operadores no ven ninguna pregunta**: corren siempre con check, pasan por el
   filtrado sí o sí, y la tarjeta casada se intenta en su cuenta ligada en modo silencioso.

## Qué se implementó

### Q1 — con / sin check de liveness (SA-only, siempre)
- `card_checker.precheck_card_liveness(card_pipe, operator_id=None, skip_rw_liveness=False)`.
  Con `skip_rw_liveness=True` se omite **solo** el gate RW (pasaporte DB + bridge HTTP +
  tolerancias). Sintaxis/Luhn/fecha, **detección de tarjeta ya-en-BD**, `RATE_LIMITED` y la
  alerta de rechazos 24h siguen corriendo. La tarjeta entra como `⚪ SIN CHECK`.
- `telegram_bot_mock/bot.py`: gate Q1 en `process_bet_input` cuando
  `operator_id == SUPERADMIN_ID and not is_fast_mode` y no se ha respondido en la corrida
  (`context.user_data["_bet_rw_answered"]`). Botones `bet_rw_on` / `bet_rw_off`.
  El callback re-invoca `process_bet_input(skip_rw=...)`.
- Aplica también al atajo `/bet <tarjetas>` en un solo mensaje (para el SA se detiene una
  vez a preguntar; luego arranca). **`/betf` queda intacto** — directo, sin escalas, sin
  liveness ni prompt de casada (`is_fast_mode` sigue siendo el único skip total).

### Q2 — tarjeta ya-en-BD (SA-only, condicional)
- El prompt de casada (`💍`) ahora es **SA-only**. Botón nuevo:
  `🔀 Ignorar Casamiento — pool sin su cuenta` → callback `btn_bet_launch_ignore_marr`.
- `auto_deposit.plan_auto_mission(..., ignore_marriage_pans=None)`:
  - Los PANs en el set salen del `_priority_emails` fast-track y del binding `married_pairs`.
  - REGLA 2 de asignación **se invierte** para esos PANs: la tarjeta va a cualquier cuenta
    elegible **MENOS su cuenta dueña**.
  - El set viaja en el `plan` (`plan["ignore_marriage_pans"]`).
- `run_auto_mission`: lee `plan["ignore_marriage_pans"]`, los saca de `married_card_owners`
  y guarda su dueña en `_owner_block`. Helper `_pipe_ok_for()` centraliza el chequeo
  (casadas 1:1 + veto de dueña) en los dos filtros de candidatas + el recálculo dinámico
  (`plan_auto_mission(ignore_marriage_pans=...)`) + `_pull_fresh_live_account(blocked_owner_pans=...)`.
- **Default vacío/None = cero cambio de conducta** (invariante canónica 9 intacta).

### No-SA (todos los demás): sin cambios de UX
- Liveness siempre ON (no se pregunta).
- Tarjeta casada → tiro directo a su cuenta dueña en silencio + el resto del pool corre normal.
- Los prompts interactivos de casada y de alto-rechazo pasan a ser **SA-only**; para no-SA
  se resuelven con default silencioso (alto-rechazo → se incluye).

## Tests
- `tests/test_card_checker.py`: `skip_rw` no toca el bridge / sí marca casada.
- `tests/test_bet_canonical_suite.py`: `09b` (ignorar casamiento → cae en extraño, veta dueña),
  `09c` (set vacío = noop). `verify_bet_suite.py` verde.
- `tests/test_telegram_bot_mock.py`: SA recibe Q1, no-SA no; `bet_rw_off` re-invoca precheck
  con `skip_rw=True`; tope de 5 tarjetas (SA sin tope / no-SA rechazado).
- Suites `test_auto_mission` / `test_bet_retry_characterization` / `test_auto_deposit*` verdes.

## Fuera de alcance (cambios compatibles hacia atrás)
- Portal web "Modo Auto" y endpoint `/api/bot/bet` (app.py) — no tocados; los params nuevos
  tienen default off.

## Nota — regresión ajena observada
`tests/test_bot_bet.py::test_bot_bet_no_passwords_in_response` falla en `origin/main`
(`app.py:5427 TypeError`) tras `78d2233` (sesión paralela, "grade D deja de ser descarte").
No es de este cambio — pertenece a `/api/bot/bet`. Flagueado para su dueño.

## Deploy
`git reset --hard origin/main` en KVM4 + `docker restart betmexico-mock-bot betmexico-web`.
