# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `.` o `/botmex`. Cierra con `/cerrar-bmx` o `/cerrar`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

---

## ▶ ARRANQUE INMEDIATO (2026-09-08) — Refactor `/bet` a nodos + operador inteligente

**Rama activa:** `feat/bet-nodes-refactor` (pusheada, HEAD `8879660`).
**Plan completo:** `C:\Users\rober\.claude\plans\como-podriamos-hacer-un-dynamic-cupcake.md`
**Estado vivo del refactor:** `docs/BET_POLICY.md`

### Qué es
Descomponer `auto_deposit.py::run_auto_mission` (~1000 líneas) en un pipeline de nodos puros +
extraer la lógica de retry a `bet_retry_policy.py` + centralizar las ~32 constantes en
`bet_policy.BetPolicyConfig` + un advisor LLM (`bet_advisor.py`, 9router) para la pre-selección
de cuentas. El LLM NUNCA en el hot path por-depósito.

### Hecho
- **Fase 0** (`efab82b`): `tests/test_bet_retry_characterization.py` — 12 golden-master.
- **Fase 1a** (`28cb65d`): `bet_policy.BetPolicyConfig`+`DEFAULT` (10 escalares, defaults =
  constantes vivas, `_LOCKED_FIELDS` protege inv. 4/5/7/10) + `bet_retry_policy.decide_next_action`
  (función PURA, réplica del orden de ramas de FASE 1). 51 tests nuevos. `verify_bet_suite` "9"→"13".
- **Fase 1** (`8879660`): cableado en el inner loop de FASE 1 matchmaking —
  `_outcome_view/_account_view/_card_view/_mission_view` (pre-mutación) → `decide_next_action`
  → `_apply_action` (helper del shell, efectos verbatim). Las 6 ramas `if code...` (~200 L) →
  12 L. El `if ok:` de match sigue inline. **Cero cambio de conducta** (caracterización 12/12
  SIN editar). Gate: `verify_bet_suite` 13/13 · `test_auto_mission` 29/29 · scheduler/selection/
  endpoints verdes · 120 en la corrida agregada.

### PRIMERA ACCIÓN próxima sesión → Fase 1b
Extender `decide_next_action` a **FASE 2 (scheduled)** con `mission.phase="SCHEDULED"`.
1. Caracterización extendida: nuevos tests golden-master de la FASE 2 en
   `test_bet_retry_characterization.py` (hoy solo 3: nine-reps, decline-aborta, cancel).
   Ramas de FASE 2 (`auto_deposit.py` ~L2322-2402): `ok`→progress (completed++, `sleep(60)`) /
   terminal-para-esta-cuenta (rate/dead/3DS/decline/ambiguo/CARD_LOCKED/PENDING_NOT_APPLIED →
   `failed++`, `break`) / transitorio (`retries` x4, `sleep(SCHED_RETRY_BACKOFF_SEC=25)`,
   reset de `session_jwt` si "sesión rechazada"/"401"/"redirectlogin"). El fallback $190→$150
   **se queda en el shell**. Sin rotación de tarjeta en scheduled.
2. `decide_next_action` gana rama `if m.phase == "SCHEDULED"` → kinds `PROGRESS` / `ABORT_ACCOUNT`
   + reusa `RETRY_SAME`. Config: `sched_max_transient_retries=4`, `sched_retry_backoff_s=25`
   (= `dep.SCHED_MAX_TRANSIENT_RETRIES` / `dep.SCHED_RETRY_BACKOFF_SEC`) en `bet_policy`.
3. `_apply_sched_action` (2º helper del shell) para FASE 2 — el shell de FASE 2 no tiene
   `target`/`accounts_state`, usa el dict `m` y `retries`.
4. Gate: caracterización (vieja + nueva) SIN editar la vieja + `verify_bet_suite` 13/13 +
   `test_auto_mission` + `test_auto_deposit_scheduler`. Commit + push.

Orden de fases: 0 ✅ → 1a ✅ → 1 ✅ → **1b** → 2 (`load_policy()`+disco) → 3 (advisor OFF).
`bet_tuner` (Fase 4) = ronda siguiente.

---

## 🐛 Bugs abiertos flagueados esta sesión (chips de spawn_task)

1. **Circuit breaker de 429 no corta el outer loop** (`auto_deposit.py` ~L2018–2030): setea
   `cancelled` local, pero `while not _cancelled()` lee status en BD → sigue procesando TODAS
   las cuentas del plan en 429. `test_char_rate_limit_circuit_breaker_current_behavior` lo
   documenta. Fix: escribir status terminal a BD en el breaker, o `while not _cancelled() and
   not cancelled`.
2. **8 tests `test_auto_deposit.py::test_plan_*` rotos en `main`**: fixture `seed_db`/`_add_account`
   no siembra `jwt_token`/`jwt_expires_at` vigentes y `plan_auto_mission` ahora exige JWT vivo.
   Modelo a copiar: `tests/test_bet_canonical_suite.py` (siembra `jwt_expires_at DEFAULT 2147483647`).

---

## 🧭 Estado de repos / infra

- **Rama `main`:** 4 commits **sin pushear** a `origin/main` (`29bf812`, `1453167`, `51992d0`,
  `7211c2e`) — NO son de esta sesión (posiblemente sesión paralela / cambio de cuenta Antigravity).
  Verificar si están listos y pushear, o entender por qué se pararon. No los toqué.
- **Remoto canónico:** `github.com/roobertvonsinger/botmex-dashboard` (ya no Forgejo).
- **KVM4-Karen (`2.25.98.162`):** API `/bet` viva (`:8001` → 302). No se deployó nada esta sesión.
- **9router:** `http://2.25.98.162:20128/v1` VIVO (requiere API key). Es el gateway para el
  advisor de Fase 3. Cliente reutilizable: `git show feat/support-agent:support_llm.py`.

## 📌 Pendientes previos (estado sin verificar esta sesión — cruzar con git log antes de re-ejecutar)
- DNS Cutover Hostinger: `botmex` A → `2.25.98.162` en zona `2puty.tech`.
- AUTO-1 (Gateway de Retiros por Telegram) sobre `SPEC_AUTOMATIZACIONES_ALTO_IMPACTO.md`.

## 🛡️ Suite Canónica /bet (innegociable)
Todo cambio en auto-depósito/matchmaking: `python tools/verify_bet_suite.py` → 13/13 antes de commit.
