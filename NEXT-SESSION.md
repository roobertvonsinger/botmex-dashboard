# NEXT-SESSION — botmex-dashboard

> Fuente de verdad. Arranca con `.` o `/botmex`. Cierra con `/cerrar-bmx` o `/cerrar`.
> **Lente rectora:** `feedback_frictionless_norte`. BOTMEXICO = frictionless, le GANA a BetMexico directo.

---

## ▶ ARRANQUE INMEDIATO (2026-09-08) — Refactor `/bet` a nodos + operador inteligente

**Rama activa:** `feat/bet-nodes-refactor` (pusheada).
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

### PRIMERA ACCIÓN próxima sesión → Fase 2 (centralizar config)
1. Test primero: extender `tests/test_bet_policy.py` — sin archivo→DEFAULT; merge válido;
   versión mala→DEFAULT; fuera de `_SANE_BOUNDS`→campo cae a default; `_LOCKED` ignorado;
   `digest()` (sha1[:12]) estable.
2. `bet_policy.py` gana `load_policy()`, `_SANE_BOUNDS`, CLI `apply(<proposal.json>)`.
   `auto_deposit.py`: `POLICY = bet_policy.load_policy()` al inicio de `run_auto_mission` y
   `plan_auto_mission`; reemplazar las constantes de módulo por `POLICY.*` (incl.
   `random.uniform(45,60)`, `asyncio.sleep(60)` → `POLICY.sched_rep_gap_s`, el `>=2` del CB).
   Dejar las constantes viejas como alias `= bet_policy.DEFAULT.x` para importadores externos.
3. Migración aditiva `auto_missions.policy_digest` en `app.py::_migrate` (estilo
   `try/except OperationalError` existente).
4. Gate: las 4 suites verdes (defaults idénticos → cero cambio) + `test_bet_policy.py`. Commit + push.

Orden de fases: 0 ✅ → 1a ✅ → 1 ✅ → 1b ✅ → **2** (`load_policy()`+disco) → 3 (advisor OFF).
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

- **Rama `main`:** al día con `origin/main` (`29bf812 1453167 51992d0 7211c2e` YA están en
  `origin/main` — el flag de "sin pushear" de la sesión previa quedó obsoleto). Son ancestros de
  `feat/bet-nodes-refactor`.
- **Remoto canónico:** `github.com/roobertvonsinger/botmex-dashboard` (ya no Forgejo).
- **KVM4-Karen (`2.25.98.162`):** API `/bet` viva (`:8001` → 302). No se deployó nada esta sesión.
- **9router:** `http://2.25.98.162:20128/v1` VIVO (requiere API key). Es el gateway para el
  advisor de Fase 3. Cliente reutilizable: `git show feat/support-agent:support_llm.py`.

## 📌 Pendientes previos (estado sin verificar esta sesión — cruzar con git log antes de re-ejecutar)
- DNS Cutover Hostinger: `botmex` A → `2.25.98.162` en zona `2puty.tech`.
- AUTO-1 (Gateway de Retiros por Telegram) sobre `SPEC_AUTOMATIZACIONES_ALTO_IMPACTO.md`.

## 🛡️ Suite Canónica /bet (innegociable)
Todo cambio en auto-depósito/matchmaking: `python tools/verify_bet_suite.py` → 13/13 antes de commit.
