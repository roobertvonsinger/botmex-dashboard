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
| 1 | `bet_retry_policy.decide_next_action` para FASE 1 (matchmaking) | 🔵 pendiente |
| 1b | Extender `retry_policy` a FASE 2 (scheduled) | 🔵 pendiente |
| 2 | `bet_policy.BetPolicyConfig` + `load_policy()` + override en `/data/bet_policy.json` | 🔵 pendiente |
| 3 | `bet_advisor` (LLM plan-time + recálculo dinámico), default OFF (`BET_ADVISOR_ENABLED`) | 🔵 pendiente |
| 4 | `bet_tuner` (ajuste offline de parámetros con diff aprobable) | 🔵 ronda siguiente |

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
