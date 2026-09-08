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
| 1b | Extender `retry_policy` a FASE 2 (scheduled) | 🔵 pendiente |
| 2 | `bet_policy.BetPolicyConfig` + `load_policy()` + override en `/data/bet_policy.json` | 🔵 pendiente |
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

Quirks del comportamiento actual **preservados** (documentados en la caracterización):
doble-unlock `[1,2,1,2,3,3]` en el 3-strikes; circuit breaker de 429 que setea
`cancelled` local pero NO corta el outer `while not _cancelled()`.

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

## Tests pre-existentes rotos (no bloquean el refactor)

`tests/test_auto_deposit.py::test_plan_*` (8 tests) fallan en `main` desde antes: el
fixture `seed_db`/`_add_account` no siembra `jwt_token`/`jwt_expires_at` vigentes y
`plan_auto_mission` ahora exige JWT vivo. Spawn_task de la sesión 2026-09-08.
