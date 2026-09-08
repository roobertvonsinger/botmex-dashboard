# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `.` o `/botmex`. Cierra con `/cerrar-bmx` o `/cerrar`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

---

## ▶ ARRANQUE INMEDIATO (2026-09-08) — Refactor `/bet` a nodos + operador inteligente

**Rama activa:** `feat/bet-nodes-refactor` (pusheada, tip `b525cb1`).
**Plan completo:** `C:\Users\rober\.claude\plans\como-podriamos-hacer-un-dynamic-cupcake.md`
**Estado vivo del refactor:** `docs/BET_POLICY.md`

### Fase 3 COMPLETA (2026-09-08) — advisor OFF, mergeable · falta smoke de Robert
Tip `8cd909f`. Commits A `c6f671c` · B `2267121` · C código `719111d` + docs `b525cb1`
· D `8cd909f`. Gate: `verify_bet_suite` 13/13 · caracterización 28/28 **sin editar**
· 251 passed. Pre-existentes rojos (fixture sin JWT, idénticos en `014efe2`, NO míos):
8× `test_auto_deposit.py::test_plan_*` + `test_telegram_bot_mock.py::test_bet_input_five_cards`.

**Colisión multi-sesión resuelta:** otra de 5 sesiones commiteó `719111d` que
absorbió mi Commit C + su propio cambio ("matchmaking continuo multi-tarjeta" —
conducta INTENCIONAL por regla Robert, con test — + 403/429 desambiguados IP-vs-cuenta
+ retry cross-IP en `gentle_login`). **Revisado y sano**, documentado en `docs/AUDIT.md`
(esa sesión saltó la bitácora). Lección → memoria `feedback_multi_sesion_mismo_dir_colision`.

### Qué es
Descomponer `auto_deposit.py::run_auto_mission` (~1000 líneas) en un pipeline de nodos puros +
extraer la lógica de retry a `bet_retry_policy.py` + centralizar las ~32 constantes en
`bet_policy.BetPolicyConfig` + un advisor LLM (`bet_advisor.py`, 9router) para la pre-selección
de cuentas. El LLM NUNCA en el hot path por-depósito.

### Hecho
- **Fase 2** (esta sesión): `bet_policy` gana `load_policy()` (override disco
  `$BET_POLICY_FILE`\|`/data/bet_policy.json`, nunca lanza), `_SANE_BOUNDS` (bound
  por campo tuneable), `digest()` (sha1[:12] estable), CLI `apply(<proposal.json>)`
  (rechaza `_LOCKED`/out-of-bounds/desconocido, ASCII-only por consola Windows).
  `POLICY_VERSION` 1→2 (+`sched_first_dep_floor_min_s/max_s`). `auto_deposit.py`:
  `POLICY = load_policy()` snapshot congelado al inicio de `run_auto_mission` **y**
  `plan_auto_mission`; shell + `_apply_action`/`_apply_sched_action` + los 2
  call-sites de `decide_next_action` leen `POLICY.*` (antes `bet_policy.DEFAULT`);
  las constantes de módulo quedan como alias `= bet_policy.DEFAULT.x`;
  `random.uniform(45,60)` → `POLICY.sched_first_dep_floor_*`. **`deposits.py` NO se
  tocó** (parada corta: su path scheduled legacy no es matchmaking `/bet`).
  Migración aditiva `auto_missions.policy_digest` (`app.py::_migrate` +
  `plan_auto_mission` devuelve `policy_digest` + `_persist_auto_mission` lo mete al
  INSERT). **Cero cambio de conducta**: sin `/data/bet_policy.json` en prod →
  `load_policy()`==`DEFAULT`. Gate: `test_bet_policy` 14/14 · caracterización
  **28/28 sin editar** · `verify_bet_suite` 13/13 ·
  `test_auto_mission`/`scheduler`/`selection`/`endpoints` verdes. Pre-existentes
  rojos NO tocados (8× `test_plan_*` JWT-fixture + `test_confirm_gate` contaminación
  cross-módulo — pasa aislado; ambos confirmados idénticos en `29fcd30` via stash).
- **Fase 0** (`efab82b`): `tests/test_bet_retry_characterization.py` — 12 golden-master.
- **Fase 1a** (`28cb65d`): `bet_policy.BetPolicyConfig`+`DEFAULT` (10 escalares, defaults =
  constantes vivas, `_LOCKED_FIELDS` protege inv. 4/5/7/10) + `bet_retry_policy.decide_next_action`
  (función PURA, réplica del orden de ramas de FASE 1). 51 tests nuevos. `verify_bet_suite` "9"→"13".
- **Fase 1** (`8879660`): cableado en el inner loop de FASE 1 matchmaking —
  `_outcome_view/_account_view/_card_view/_mission_view` (pre-mutación) → `decide_next_action`
  → `_apply_action` (helper del shell, efectos verbatim). Las 6 ramas `if code...` (~200 L) →
  12 L. El `if ok:` de match sigue inline. **Cero cambio de conducta** (caracterización 12/12
  SIN editar).
- **Fase 1b** (esta sesión): `decide_next_action` enruta `m.phase=="SCHEDULED"` → `_decide_scheduled`
  (PROGRESS / ABORT_ACCOUNT terminal-con-broadcast / RETRY_SAME → ABORT_ACCOUNT sin broadcast).
  `_apply_sched_action` (2º helper del shell) replica los efectos de BD de L2399-2447. `reset_session`
  (`"401"`/`"redirectlogin"`/`"sesión rechazada"` + jwt vivo) lo aplica el shell ANTES del helper
  (orden verbatim L2482). Fallback $190→$150 se queda en el shell. `bet_policy` gana
  `sched_max_transient_retries=4` / `sched_retry_backoff_s=25` / `sched_rep_gap_s=60`.
  El FASE 2 `while completed < target_count` (~95 L de ramas) → ~30 L de ruteo. **Cero cambio de
  conducta**: caracterización 20/20 (12 viejas SIN editar + 8 FASE 2 nuevas). Gate:
  `verify_bet_suite` 13/13 · `test_bet_retry_policy` 70 · `test_auto_mission`/`test_auto_deposit_scheduler`
  verdes · 128 en la corrida agregada. Los 8 `test_plan_*` de `test_auto_deposit.py` siguen rojos
  (pre-existentes, JWT en fixture — ver más abajo).

### Fase 3 — advisor / operador inteligente (default OFF `BET_ADVISOR_ENABLED`)
- **Commit A ✅ `c6f671c`** — vendor `support_llm.py` + `tests/test_support_llm.py` (10/10), aislado.
- **Commit B ✅ `2267121`** — `bet_advisor.py` (módulo PURO: `AdvisorInputs`,
  `_build_advisor_request` whitelist, `_assert_no_pii` fail-closed, `_sanitize_advice`,
  `maybe_advise` OFF-by-default + `asyncio.wait_for(6s)`, `_record_llm_call`) +
  `tests/test_bet_advisor.py` (24) + migración aditiva `bet_llm_calls`.
- **Commit C ✅ (código en `719111d`, docs en `b525cb1`)** — `select_accounts_for_auto(
  ..., advisor_boost)` (prepend al `sort_key`, puro desempate) + `plan_auto_mission(
  ..., advisor_hint, _advisor_sink)` + `_build_advisor_bundle`/`_advisor_recent_history`
  (read-only, cero query) + `bet_advisor.enabled()`/`advise_from_inputs` + 3 entry points
  async. Advisor OFF → conducta idéntica. Gate 13/13 · caracterización 28/28 sin editar.
- **Commit D ✅ `8cd909f`** — recálculo dinámico en `run_auto_mission` dentro de
  `if need_backup and active_cards` (mismo patrón que los entry points: `_advisor_sink`
  sobre el `plan_auto_mission` de respaldo → `advise_from_inputs(kind="recalc")` →
  re-plan con `advisor_hint`). Es una pausa de re-plan que YA existía. OFF → idéntico.
  `tests/test_bet_advisor_integration.py` (3, `LLMClient` falso).

Orden de fases: 0 ✅ → 1a ✅ → 1 ✅ → 1b ✅ → 2 ✅ → **3 ✅ (A/B/C/D)** → 4 (`bet_tuner`, diferido).

### PRIMERA ACCIÓN próxima sesión
1. **Smoke de Fase 3** (Robert): mergear `feat/bet-nodes-refactor` a `main` (advisor
   OFF, cero cambio) → deploy KVM4 → `export BET_ADVISOR_ENABLED=1` +
   `BET_ADVISOR_MODEL_CHAIN=...` (fijar tras probar tool-calling contra 9router vivo
   `:20128`) → lanzar un `/bet` real de 1 tarjeta / `target_count` bajo desde `@betmexbot`
   → verificar en logs: (a) advisor respondió o cayó a fallback limpio, (b) fila en
   `bet_llm_calls` con tokens medidos, (c) `deposit_attempts`/`auto_missions` consistentes,
   (d) plan respetó KYC/pool/429. Ver `docs/BET_POLICY.md` §"Verificación e2e".
2. **Fase 4** (`bet_tuner`, diferido) o pendientes pos-merge del advisor (pairings,
   `recent_history` con probes reales, biasing de `_pull_fresh_live_account`).

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

- **Rama `feat/bet-nodes-refactor`:** Fase 2 commiteada + pusheada. Sin mergear a `main`
  todavía (checkpoint tras Fase 3 o cuando Robert lo pida).
- **Rama `main`:** al día con `origin/main` (`29bf812 1453167 51992d0 7211c2e` YA están en
  `origin/main`). Son ancestros de `feat/bet-nodes-refactor`.
- **Remoto canónico:** `github.com/roobertvonsinger/botmex-dashboard` (ya no Forgejo).
- **KVM4-Karen (`2.25.98.162`):** API `/bet` viva (`:8001` → 302). No se deployó nada esta sesión.
- **9router:** `http://2.25.98.162:20128/v1` VIVO (requiere API key). Es el gateway para el
  advisor de Fase 3. Cliente reutilizable: `git show feat/support-agent:support_llm.py`.

## 📌 Pendientes previos (estado sin verificar esta sesión — cruzar con git log antes de re-ejecutar)
- DNS Cutover Hostinger: `botmex` A → `2.25.98.162` en zona `2puty.tech`.
- AUTO-1 (Gateway de Retiros por Telegram) sobre `SPEC_AUTOMATIZACIONES_ALTO_IMPACTO.md`.

## 🛡️ Suite Canónica /bet (innegociable)
Todo cambio en auto-depósito/matchmaking: `python tools/verify_bet_suite.py` → 13/13 antes de commit.
