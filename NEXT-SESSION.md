# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `.` o `/botmex`. Cierra con `/cerrar-bmx` o `/cerrar`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

---

## ▶ ARRANQUE INMEDIATO (2026-09-08) — Refactor `/bet` a nodos + operador inteligente

**Rama activa:** `feat/bet-nodes-refactor` (pusheada, 1 commit `efab82b` sobre `main`).
**Plan completo:** `C:\Users\rober\.claude\plans\como-podriamos-hacer-un-dynamic-cupcake.md`
**Estado vivo del refactor:** `docs/BET_POLICY.md`

### Qué es
Descomponer `auto_deposit.py::run_auto_mission` (~1000 líneas) en un pipeline de nodos puros +
extraer la lógica de retry a `bet_retry_policy.py` + centralizar las ~32 constantes en
`bet_policy.BetPolicyConfig` + un advisor LLM (`bet_advisor.py`, 9router) para la pre-selección
de cuentas (plan inicial + recálculo dinámico a mitad de misión). El LLM NUNCA en el hot path
por-depósito. Robert quiere: "operador inteligente que en tiempo real recalcule la selección
de cuentas"; retries y mecánica siguen deterministas.

### Hecho — Fase 0 (commit `efab82b`)
`tests/test_bet_retry_characterization.py` — 12 tests golden-master que fijan la secuencia
exacta de efectos del `run_auto_mission` actual. Contrato de no-regresión para Fase 1.
Verde: `verify_bet_suite` 13/13 · `test_auto_mission` 29/29 · caracterización 12/12.

### PRIMERA ACCIÓN próxima sesión → Fase 1
1. `git checkout feat/bet-nodes-refactor` (ya existe local + remoto).
2. Test primero: `tests/test_bet_retry_policy.py` — unit puro de `decide_next_action` por rama
   (~30 casos). Ver la interfaz completa (`Action`, `OutcomeView`, `AccountRetryState`,
   `CardRetryState`, `MissionRetryState`) en el plan §"Componentes e interfaces".
3. Crear `bet_retry_policy.py` (tipos + función pura; importa solo helpers módulo-nivel de
   `deposits`: `_mm_is_real_decline`, `_mm_is_ambiguous_charge`, `MM_DEAD_RC`, `MM_THREEDS_RC`).
4. Crear `bet_policy.py` con `BetPolicyConfig` + `DEFAULT` **solo** (sin load de disco aún).
   Defaults = valores EXACTOS actuales (leerlos del código, no de MAP.md — algunos difieren).
5. Refactor del inner `while True` de FASE 1 matchmaking en `auto_deposit.py` (L1828–2147,
   ~300 líneas) a `decide_next_action` + helper `_apply_action` **del shell** (efectos y su
   orden idénticos) + `_outcome_view`/`_account_view`/`_card_view`/`_mission_view` construidos
   ANTES de cualquier mutación. FASE 2 intacta (es Fase 1b).
6. Gate: `test_bet_retry_policy.py` verde + `test_bet_retry_characterization.py` **sin editar y
   verde** + `verify_bet_suite` 13/13 + `test_auto_mission` verde. Commit + push.

Orden de fases: 0 ✅ → 1 → 1b → 2 → 3. `bet_tuner` (Fase 4) = ronda siguiente.

### Ramas de detalle exacto del inner loop de FASE 1 (orden que `decide_next_action` debe replicar)
`ok` → `BALANCE_LIMIT_EXCEEDED` → `code in MM_THREEDS_RC` (3DS→A+, 3 cuentas) → familia dead/429
+ circuit breaker → `_mm_is_real_decline or _mm_is_ambiguous_charge` (3-strikes tarjeta / 2-strikes
cuenta) → `CARD_LOCKED_OTHER_ACCOUNT` → transitorio (retry x4, `_sleep_step(25)`).
Cross-account gap `_sleep_step(MM_CROSS_ACCOUNT_GAP=5)` al final si quedan otras cuentas activas.

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
