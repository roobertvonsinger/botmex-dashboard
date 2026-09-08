# BET_POLICY — refactor de `/bet` a nodos + operador inteligente

> Estado vivo del refactor del flujo `/bet` (`auto_deposit.py`). Plan completo:
> `C:\Users\rober\.claude\plans\como-podriamos-hacer-un-dynamic-cupcake.md`.

## Objetivo

Descomponer `run_auto_mission` (~1000 líneas, 4 fases entrelazadas) y `plan_auto_mission`
(~330 líneas de SQL crudo) en un **pipeline de nodos** puros y testeables:

- Lógica de retry/rotación → módulo determinista aislado (`bet_retry_policy.py`).
- Las ~32 constantes/umbrales dispersos → un objeto de política versionado (`bet_policy.py`).
- Un **advisor LLM** (`bet_advisor.py`) consultado en cada punto de selección de cuentas
  (plan inicial + recálculos dinámicos a mitad de misión), con fallback determinista.
  El LLM NUNCA entra al hot path por-depósito.

**Regla dura:** los nodos son puros o read-only. Solo el shell (`run_auto_mission` /
`plan_auto_mission`) escribe en BD, duerme, lockea y llama al pool de captcha. Los efectos
secundarios quedan exactamente donde están hoy.

**Gate innegociable:** `python tools/verify_bet_suite.py` (13 invariantes canónicas) +
`pytest tests/test_auto_mission.py tests/test_bet_retry_characterization.py` al 100% en cada fase.

## Fases

| Fase | Qué | Estado |
|---|---|---|
| 0 | Red de caracterización (golden-master) del `run_auto_mission` actual | ✅ `tests/test_bet_retry_characterization.py` (12 tests) |
| 1a | `bet_retry_policy.decide_next_action` + `bet_policy.BetPolicyConfig` (módulos puros, sin cablear) | ✅ `tests/test_bet_retry_policy.py` (46) · `tests/test_bet_policy.py` (5) |
| 1 | Cableado en el inner loop de FASE 1 (`_*_view` → `decide_next_action` → `_apply_action`) | ✅ caracterización 12/12 sin editar · `verify_bet_suite` 13/13 · `test_auto_mission` 29/29 |
| 1b | Extender `retry_policy` a FASE 2 (scheduled) — `decide_next_action(phase="SCHEDULED")` + `_apply_sched_action` | ✅ caracterización 20/20 (12 viejas sin editar + 8 FASE 2) · `test_bet_retry_policy` 70 · `verify_bet_suite` 13/13 |
| 2 | `bet_policy.load_policy()` + override `/data/bet_policy.json` + `_SANE_BOUNDS` + `digest()` + CLI `apply()` + `POLICY` cableado en shell + migración `auto_missions.policy_digest` | ✅ `test_bet_policy` 14/14 · caracterización 28/28 sin editar · `verify_bet_suite` 13/13 |
| 3 | `bet_advisor` (LLM plan-time + recálculo dinámico), default OFF (`BET_ADVISOR_ENABLED`) | 🔵 pendiente |
| 4 | `bet_tuner` (ajuste offline de parámetros con diff aprobable) | 🔵 ronda siguiente |

## Fase 1a — módulos puros (hecho, sin cambio de conducta)

`bet_policy.py` — `BetPolicyConfig` (frozen dataclass) + `DEFAULT`. Los ~10 escalares
que el inner loop de FASE 1 usa hoy como constantes de módulo, con **defaults =
valores exactos actuales**. Campos `_LOCKED_FIELDS` (`account_max_declines_per_run`,
`card_max_declines`, `card_max_attempts`, `circuit_breaker_consecutive_429`) protegen
las invariantes 4/5/7/10. `load_policy()` + override de disco = FASE 2.

`bet_retry_policy.py` — `decide_next_action(outcome, account, card, mission, config)
-> Action`. Función **pura** (sin BD/sleep/lock/log). Replica el orden de ramas del
inner `while True` de `auto_deposit.py` L1838-2141:
`ok → BALANCE_LIMIT_EXCEEDED → 3DS → dead/429 (+circuit breaker) → decline/ambiguo
→ CARD_LOCKED_OTHER_ACCOUNT → transitorio`. Reusa la taxonomía de `deposits`
(`MM_DEAD_RC`/`MM_THREEDS_RC`/`_mm_is_real_decline`/`_mm_is_ambiguous_charge`).
`Action` (frozen) lleva `kind` + flags de efecto + deltas de contadores que el
shell aplica (la policy nunca muta sus inputs).

## Fase 1 — cableado en el inner loop de FASE 1 (hecho, sin cambio de conducta)

`run_auto_mission` gana 5 helpers anidados (`auto_deposit.py`, justo antes del
`while not _cancelled()` de matchmaking):

- `_outcome_view` / `_account_view` / `_card_view` / `_mission_view` — construyen las
  vistas inmutables **antes de cualquier mutación** (`account.remaining_candidates` =
  candidatas de `target` tras el `pop(0)` del pipe en curso; `mission.transient_count`
  = el contador `transient` del par pre-incremento).
- `_apply_action(action, target, account_id, email, pipe, k, code, r) -> str` —
  helper **del shell**: réplica verbatim de los efectos y su ORDEN de las 6 ramas de
  retry/rotación de hoy (SKIP_ACCOUNT, THREEDS_CERT, ACCOUNT_DEAD, CARD_DECLINE,
  RETIRE_CARD_LOCKED, GIVE_UP_PAIR). Los mutadores de estado (`_unlock`, `done`,
  `cooldown_until`, `_retire_card`, DB writes, `_broadcast_mission`) leen estado vivo
  igual que el monolito. Devuelve `'retry'` (RETRY_SAME → el shell hace `_sleep_step`
  + `continue`) o `'break'`.

El `if ok:` de match encontrado sigue **inline** (es finalización de match, no retry —
nodo `card_marriage_writer`, se descompone en ronda futura).

## Fase 1b — cableado en el loop de FASE 2 scheduled (hecho, sin cambio de conducta)

`decide_next_action` gana una rama corta arriba de todo: `if m.phase == "SCHEDULED":
return _decide_scheduled(o, m, cfg)`. FASE 2 no rota tarjeta ni cuenta, así que
`_decide_scheduled` sólo distingue 3 casos:

- **`PROGRESS`** — `o.ok`: rep acreditada. `wait_s = sched_rep_gap_s` (60) si quedan
  reps, si no 0. El shell hace `completed++/deposited+=curr_amt/approved++`, la
  captura de JWT SP-2 y el `_m_update`/broadcast (igual que el `if ok:` inline de
  FASE 1).
- **`ABORT_ACCOUNT` + `sched_abort_terminal=True`** — `_sched_is_terminal(o)`:
  rate-limit / dead-family / 3DS / decline real / cargo ambiguo / `CARD_LOCKED`.
  `_apply_sched_action` replica L2399-2426: `_mark_rate_limited_dead` **o**
  `UPDATE accounts DEAD` **o** nada, luego `failed++` + `_m_update(abortada)` +
  `_broadcast_mission(aborted=code)`.
- **`RETRY_SAME` / `ABORT_ACCOUNT` + `sched_abort_terminal=False`** — transitorio:
  `RETRY_SAME` con `wait_s = sched_retry_backoff_s` (25) hasta
  `sched_max_transient_retries` (4), luego `ABORT_ACCOUNT` sin broadcast
  (`_m_update(f"sin éxito tras {retries} reintentos")`).

`reset_session` (marcadores `"sesión rechazada"`/`"401"`/`"redirectlogin"` con
`session_jwt` vivo) lo marca la policy y lo aplica el **shell** ANTES de
`_apply_sched_action` (orden verbatim de L2482): pone `session_jwt=None` y
recrea el pool si hacía falta. El fallback **$190→$150 se queda en el shell**,
resuelto antes de llamar a `decide_next_action`.

`MissionRetryState` gana `reps_completed` / `reps_target` / `session_jwt_present`
(defaults preservan FASE 1). `bet_policy` gana `sched_max_transient_retries=4`,
`sched_retry_backoff_s=25`, `sched_rep_gap_s=60` (= `deposits.SCHED_*` +
`asyncio.sleep(60)`).

Quirks del comportamiento actual **preservados** (documentados en la caracterización):
doble-unlock `[1,2,1,2,3,3]` en el 3-strikes; circuit breaker de 429 que setea
`cancelled` local pero NO corta el outer `while not _cancelled()`.

## Fase 2 — centralización de config (hecho, sin cambio de conducta)

`bet_policy.py` gana:

- **`load_policy() -> BetPolicyConfig`** — funde un override de disco sobre `DEFAULT`.
  Ruta: `$BET_POLICY_FILE` o `/data/bet_policy.json`. Formato:
  `{"version": 2, "policy": {<campo>: <valor>, ...}}`. **Nunca lanza**: sin archivo,
  JSON malo, `version` distinta de `POLICY_VERSION` (=2), o `policy` vacío tras
  filtrar → `DEFAULT` horneado. Un campo fuera de `_SANE_BOUNDS`, `_LOCKED`, o
  desconocido se descarta **sin tumbar** el resto del merge.
- **`_SANE_BOUNDS`** — `(lo, hi)` inclusivo por campo TUNEABLE. Todo campo no
  `_LOCKED` tiene una entrada (lo verifica `test_bet_policy.py`).
- **`digest(cfg=None) -> str`** — `sha1[:12]` estable del dataclass (JSON
  `sort_keys`). Mismo `cfg` → mismo digest. Va a `auto_missions.policy_digest`.
- **CLI `apply(<proposal.json>)`** (`python -m bet_policy apply ...`) — valida el
  diff contra `_SANE_BOUNDS` + `_LOCKED_FIELDS`, imprime cada rechazo, y si algo
  queda aplicable lo escribe a `_policy_path()` en el formato que lee `load_policy()`.
  RC 0 = escribió · 1 = nada aplicable · 2 = no pude leer el proposal.

**Cableado (`auto_deposit.py`):** `POLICY = bet_policy.load_policy()` al inicio de
`run_auto_mission` **y** `plan_auto_mission` (snapshot congelado por-misión — un
diff aprobado se recoge en la SIGUIENTE misión, nunca a mitad de una viva). El
shell y `_apply_action`/`_apply_sched_action` leen `POLICY.*`; los 2 call-sites de
`decide_next_action` reciben `POLICY` (antes `bet_policy.DEFAULT`). Las constantes
de módulo (`PROBE_AMOUNT`, `MM_CROSS_ACCOUNT_GAP`, `MM_CARD_MAX_DECLINES`,
`MM_MAX_ACCOUNT_DECLINES_PER_RUN`, `MAX_ACCOUNTS_HARD_CAP`,
`MATCH_TRANSIENT_RETRIES`) quedan como **alias `= bet_policy.DEFAULT.x`** para
importadores externos y la red de caracterización. `random.uniform(45,60)` →
`random.uniform(POLICY.sched_first_dep_floor_min_s, ...max_s)`. `deposits.py` NO se
tocó — su path scheduled legacy conserva sus propias constantes (no es matchmaking
`/bet`, no lo afina el tuner).

**Nuevos campos** en `BetPolicyConfig` (`POLICY_VERSION` 1→2):
`sched_first_dep_floor_min_s=45.0`, `sched_first_dep_floor_max_s=60.0`.

**Migración:** `auto_missions.policy_digest TEXT` (aditiva, `app.py::_migrate`).
`plan_auto_mission` devuelve `plan["policy_digest"]`; `_persist_auto_mission` lo
mete en el INSERT. En prod aún no existe `/data/bet_policy.json` → `load_policy()`
== `DEFAULT` == conducta idéntica a Fase 1b.

**Cero cambio de conducta:** `test_bet_retry_characterization.py` 28/28 **sin
editarse**; `verify_bet_suite` 13/13; `test_auto_mission`/`test_auto_deposit_scheduler`
verdes. (Pre-existentes rojos NO tocados: 8× `test_auto_deposit.py::test_plan_*`
por JWT en fixture; `test_confirm_gate_in_auto_deposit` por contaminación cross-módulo
— pasa en aislamiento.)

## Fase 0 — caracterización (hecho)

`tests/test_bet_retry_characterization.py` fija la **secuencia exacta** de efectos
observables del `run_auto_mission` actual por rama de `result_code` (orden de intentos,
orden de sleeps, transiciones de `status`, orden de unlock, cuentas dead). Debe pasar
SIN EDITARSE tras el refactor de FASE 1/1b — si un test se rompe, la conducta cambió.

Hallazgos documentados en los tests (comportamiento actual, no se toca en el refactor):

- **Doble unlock por cuenta** en el 3-strikes de decline/3DS: la rama de decline
  desbloquea pero nunca limpia `target["locked"]`, así que el purge de `_retire_card`
  (al 3er strike) vuelve a desbloquear. Idempotente en prod. Secuencia: `[1,2,1,2,3,3]`.
- **Piso anti-fuga de FASE 2**: siempre `random.uniform(45,60)` s antes de la 1a rep.
- **Circuit breaker de 429 no corta el outer loop** (posible bug — spawn_task de la
  sesión 2026-09-08): setea `cancelled` local, pero el outer `while not _cancelled()`
  lee status en BD → sigue procesando todas las cuentas del plan. Ver `docs/ERRORS.md`
  cuando se arregle.

## `bet_policy.json` — override de disco (Fase 2)

- **Ubicación:** `/data/bet_policy.json` en KVM4 (volumen montado, persiste entre
  restarts). Local/test: `$BET_POLICY_FILE`.
- **Se genera SOLO vía `python -m bet_policy apply <proposal.json>`** — nunca a mano.
  El archivo se commitea al aprobar → historial + rollback por git (patrón del plan).
- **No existe todavía en prod.** Sin él, `/bet` corre con `DEFAULT` (idéntico a hoy).
- **Formato:**
  ```json
  { "version": 2, "policy": { "mm_cooldown_s": 55 }, "digest": "3c54f1359770" }
  ```
- **Campos `_LOCKED` (rechazados por `apply()` y `load_policy()`):**
  `account_max_declines_per_run`, `card_max_declines`, `card_max_attempts`,
  `circuit_breaker_consecutive_429` — protegen invariantes 4/5/7/10.

## Tests pre-existentes rotos (no bloquean el refactor)

`tests/test_auto_deposit.py::test_plan_*` (8 tests) fallan en `main` desde antes: el
fixture `seed_db`/`_add_account` no siembra `jwt_token`/`jwt_expires_at` vigentes y
`plan_auto_mission` ahora exige JWT vivo. Spawn_task de la sesión 2026-09-08.
