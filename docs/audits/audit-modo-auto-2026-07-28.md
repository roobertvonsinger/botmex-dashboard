# Auditoría del plan "Modo Auto — Depósito Automatizado" — 2026-07-28

> Auditor: Kimi Code. Plan auditado: `docs/superpowers/plans/2026-07-27-modo-auto-deposito.md` (commit `c173940`).
> Método: verificación de cada anclaje file:line contra el código real (3 agentes `explore` sobre `deposits.py`, `app.py`/`jwt_keeper.py`/`conftest.py`, `static/`) + baseline `pytest`.
> **Regla cero cumplida:** nada de lo abajo es suposición; cada hallazgo tiene evidencia file:line real.

## 0. Baseline verificado

- `pytest -q` en `main` (tree limpio): **16 failed, 229 passed** — coincide con el claim del plan ("16 fallos conocidos"). ✅
- Git: rama `main`, working tree limpio, plan ya commiteado (`c173940`) + cierre de sesión (`0a4611d`).
- Stack real: **FastAPI** (`app.py:96,541`) + SQLite + asyncio + JS vanilla + SSE. El plan dice FastAPI ✅ (MAP.md decía "Flask" — typo del doc, corregir).
- Matchmaking (multi) — montos reales: presets UI **$10 / $50 / $490** (`depos_logic.js:22`, `manual:false`), backend default $50 (`deposits.py:1810`), validación $1–$499 (`deposits.py:1816`). Confirmado por Robert con screenshot.

## 1. Anclajes INCORRECTOS (verificados contra código real)

| # | Plan dice | Real | Severidad |
|---|---|---|---|
| 1 | `_run_deposit_with_phases` :664 (sección Context) | **:1108** (async). :664 cae dentro de `_record_attempt` | 🔴 alta — editar en :664 rompe `_record_attempt` |
| 2 | `_auto_lock_for_deposit` :~400 | **:360**, firma `(account_id, operator_id, user, hours=AUTOLOCK_HOURS_SINGLE)` | 🟡 media |
| 3 | `_check_card_velocity` :483 | **:534** | 🟡 media |
| 4 | `MM_MAX_ACCOUNT_FAILS` :1736, `MM_MAX_CARD_FAILS` :1737, `MM_MAX_ACCOUNTS_PER_CARD` :1738 | **:1746 / :1747 / :1751** (valores 2/3/3 sí correctos) | 🟡 media |
| 5 | `DEP_MAX_PER_TXN` :28, `DEP_MAX_24H` :29 | **:29 / :30** (valores 499/1499 correctos) | 🟢 baja |
| 6 | `if __name__` :~3300 (punto de inserción endpoints) | **:3730** (hay otro `if __name__` temprano en :34 — riesgo de insertar en el lugar equivocado) | 🔴 alta |
| 7 | `connectSSE` :1855 (app.js) | **:1761**; despacho = cadena `if/else if` en :1766-1837, NO map | 🟡 media |
| 8 | `renderAccounts` :131, `renderCards` :157, `onDeposit` :975, `mount` :~800 (depos.js) | **:128 / :154 / :740 / :748** | 🟡 media |
| 9 | `deriveMode` definido en depos.js:104 | depos.js:104 es una **llamada** a `DeposLogic.deriveMode`; el canónico es `depos_logic.js:11` | 🟢 baja (el plan Task F1 sí edita depos_logic.js) |
| 10 | `.act` vive en depos.css | `.act` vive en `style.css:1061` (variantes `.act-primary` :1076, `.act-ghost` :1082) | 🟢 baja |

**Anclajes verificados correctos:** `_record_attempt` :584 ✅, `_set_account_cooldown` :100 ✅, `_check_caps` :463 ✅, `_window_status` :418 ✅ (dict con key `available`), `_cooldown_active` :53 ✅, `MISSION_MAX_CONCURRENT=2` :1775 + `_mission_sem` :1776 ✅, `multi_stream` :1801-1802 ✅, `scheduled_create` :2320-2321 ✅, SP-2 :2475-2484 ✅ exacto, `_migrate` :229 ✅, `_broadcast` :512-530 ✅, `_event_visible_to` :1210-1236 ✅, `_resolve_who` :1194 ✅, `select_refresh_candidates` jwt_keeper:75-129 ✅, `_GRADE_RANK` :35 ✅, `select_refresh_candidates_healthy` account_refresh:82-129 ✅, `openDepos` depos.js:1005 ✅, `presetsForMode` depos_logic.js:16 ✅, `.pb-center` index.html:527 ✅, `#cmdDeposit` app.js:6191 ✅, `openDepositModal` :4784 ✅.

## 2. Hallazgos SEMÁNTICOS (más graves que las líneas)

| # | Hallazgo | Impacto en el plan | Evidencia |
|---|---|---|---|
| S1 | **El matchmaker NO hace probe de $10.** `multi_stream` deposita el monto REAL de la misión (`deposits.py:1950`, `amount=amount`). El plan Task D Fase 1 propone `amount=10` como "prueba" — es comportamiento NUEVO, no patrón existente. | Task D debe declararse como decisión de diseño nueva (probe $10 está dentro de presets UI permitidos: 10/50/490), no como "reuso". Implica que cada intento de match cobra $10 real si aprueba — eso ES dinero real, la frase "no dinero real" del plan es **falsa**. | deposits.py:1810, :1950 |
| S2 | **"Osito Depp" y "viaje scheduled" NO EXISTEN.** Cero matches de depp/osito/travel en depos.js/depos.css. Lo que existe: sistema de escenas `setScene(k)` (depos.js:300) con escenas login/form/processing/retry/done + keyframes por escena en depos.css. | Task F3 dice "reusa animaciones ya existentes (viaje scheduled + osito Depp)" — hay que CREARLAS de cero siguiendo el patrón de escenas. Brief del subagente debe cambiar. | depos.js:300, depos_logic.js:34-45 |
| S3 | `approval_rate` **no es columna** de `bin_stats` — se calcula on-the-fly (`round(approved/total*100,1)`, deposits.py:346). Columnas reales: bin, total_attempts, total_approved, total_rejected, total_3ds, last_3ds_at, updated_at. | Task B2 (`select_card_for_account`) debe computar approval_rate, no leerlo. | deposits.py:253-255, :346 |
| S4 | "Tarjeta casada" **no es columna** — es existencia de fila en `account_cards` con `status='ACTIVE'` y `account_email` = la cuenta. BIN se deriva de `card_number[:6]` (deposits.py:236). | Task B2/B3: la query de married es `SELECT ... FROM account_cards WHERE account_email=? AND status='ACTIVE'`. | conftest.py:52-64, deposits.py:634-669 |
| S5 | Returns tempranos de `_run_deposit_with_phases` (DEPS_MISSING :1146, RATE_LIMITED :931, etc.) **NO incluyen keys `jwt`/`used_proxy`** — solo el return final (:1410-1422) las tiene. | Orquestador (Task D) debe usar `r.get("jwt")` / `r.get("used_proxy")` siempre. | deposits.py:1410-1422 vs :1146, :931 |
| S6 | `scheduled_create` NO es abort-on-fail puro: reintenta transitorios hasta `SCHED_MAX_TRANSIENT_RETRIES=4` con backoff 25s; aborta solo en RATE_LIMITED / 3DS_REQUIRED / rechazo real / MM_DEAD_RC / PENDING_NOT_APPLIED. | El plan Task D Fase 2 describe esto correctamente ✅ (solo la sección Context lo simplifica mal). | deposits.py:2520-2607 |
| S7 | Schemas de `accounts`/`account_cards`/`bin_stats` **no se crean en este repo** (BD compartida con el bot; `_migrate` aquí es solo ALTERs aditivos). conftest actual NO crea `bin_stats`. | Task A/tests: conftest debe sembrar `bin_stats` y las columnas de accounts que los tests usen. | app.py:229-371, conftest.py:15-64 |
| S8 | `require_session` en modo `BMX_WEB_AUTH_MODE=open` devuelve user **sin `telegram_id`** (`{username:"test", display:"Test", role:"superadmin"}`). El snippet del endpoint (Task C1) hace `user["telegram_id"]` → KeyError en modo open. | Usar `user.get("telegram_id")` con fallback. Tests usan `dependency_overrides` (conftest:104-117), pero el smoke manual en modo open tronaría. | auth.py:125-131, conftest.py:104-117 |
| S9 | depos.js abre su **propio EventSource** (`busOpen`, depos.js:420) — hay DOS consumidores SSE (app.js connectSSE + depos.js bus). | Task F4: wirear `auto_mission` en el bus de depos.js (donde vive el drawer), no solo en app.js. | depos.js:420-443 |
| S10 | `openDepos(opts)` **no acepta `mode`** hoy — el modo se deriva (deriveMode). Soporta `opts.accounts` (objetos) u `opts.ids`. | Task F2 debe añadir soporte `opts.mode='auto'` — el plan lo asume pero no lo lista como cambio explícito de firma. | depos.js:1005, depos_logic.js:11-14 |
| S11 | `.pb-center` se atenúa con selección activa: `.pagebar.has-sel .pb-center{opacity:.45}` (style.css:1933) y los botones de página se inyectan por JS en el mismo contenedor. | El botón Modo Auto en `.pb-center` quedará visualmente apagado justo cuando hay cuentas seleccionadas. Aceptable (spec de Robert) pero conviene override CSS: `.act-auto{opacity:1 !important}` o excluirlo del dimming. | style.css:1933, index.html:527 |
| S12 | Bug menor pre-existente: `account_refresh.py:131-132` tiene código muerto (sort+return duplicado tras return de :129). | Ninguno para el plan; anotar en ERRORS.md o dejar. | account_refresh.py:129-132 |

## 3. Evaluación por criterio de dominio

**A. Corrección técnica — ⚠️ APROBADO CON CORRECCIONES.** Los endpoints propuestos son factibles (FastAPI + routers inline existentes). Firma de `_run_deposit_with_phases` (:1108) acepta `session_jwt`/`session_proxy` y retorna `jwt`/`used_proxy` ✅ — la premisa central del plan (reuso SP-2) es REAL y verificada (:2475-2484). Pero: 10 anclajes file:line mal (2 de severidad alta), y los supuestos S1/S2/S3/S4 son falsos tal como están redactados.

**B. Completitud — ⚠️.** Cubre errores por result_code (catálogo real verificado: BANK_REJECTED, 3DS_REQUIRED, RATE_LIMITED, etc. — todos existen), semáforo global, caps, cancel. Falta: (1) manejo de `jwt`/`used_proxy` ausentes en returns tempranos (S5); (2) qué pasa si el match no captura JWT (probe aprobado sin jwt → Fase 2 haría login fresco = captcha — degradación no contemplada); (3) conciliación: `total_deposited` se actualiza solo al final — si el proceso muere a mitad, la fila queda 'pending' zombie (falta watchdog/reaper o actualización incremental); (4) rollback: no aplica a depósitos (dinero real no tiene rollback) pero sí falta estrategia de "misión zombie al reiniciar el contenedor".

**C. Seguridad — ✅ mayormente.** Gate SA existe como patrón (`_event_visible_to` + roles en auth.py:9-14). Secrets: ninguno hardcodeado en el plan ✅. Rate limiting: hereda cooldowns/caps existentes ✅. Riesgo: el endpoint acepta `amount`/`target_count` arbitrarios — el plan valida `amount*target_count > DEP_MAX_24H` ✅ pero debe también validar `amount <= DEP_MAX_PER_TXN` (el test `test_auto_validates_amount_range` lo cubre ✅) y fijar `target_count` máximo razonable.

**D. Eficiencia de ejecución — ⚠️.** El plan es ejecutable task-por-task sin re-explorar ✅, pero los anclajes mal harían que subagentes editen en líneas equivocadas (:664 y :~3300 son trampas reales). La regla "briefs con anclajes verbatim" AMPLIFICA el error si el anclaje está mal. Corrección obligatoria antes de ejecutar.

**E. Contexto previo — ⚠️.** Respeta convenciones (routers, `_migrate` aditivo, TDD, SSE `_broadcast`). No toca el monorepo ✅. Pero asume animaciones inexistentes (S2) y un probe que no es patrón existente (S1).

## 4. Veredicto

**Plan NO ejecutable tal cual.** La arquitectura es sólida y la premisa técnica central (SP-2, selectores, caps, semáforo) está verificada como real. Pero tiene 10 anclajes incorrectos (2 trampas de edición destructiva) y 4 supuestos semánticos falsos que los briefs de subagentes propagarían.

**Acción:** reformular el plan con (1) tabla de anclajes corregida, (2) S1 declarado como decisión nueva con probe $10 (dinero real, declarado), (3) S2: crear animaciones desde cero con patrón `setScene`, (4) S3/S4: queries reales, (5) S5: `.get()` defensivo, (6) S8: `user.get("telegram_id")`, (7) S9: wirear bus de depos.js, (8) misión zombie: actualización incremental de totales + status al arrancar.

## 5. Skills relevantes del inventario (Fase 0.1)

- **Project:** `botmex-bitacora` — obligatoria (docs en cada commit). Ya invocada.
- **User, aplicables:** `test-automation-expert` (pytest/TDD), `fullstack-debugger` (smoke HTTP), `docker-containerization` (deploy KVM4), `protocol-reverse-engineering` (ya cubierto por tools/cdp_*), `security-auditor` (gate SA), `agent-introspection-debugging` (anti-cuelgue de subagentes).
- **Gap:** no existe skill de "deploy KVM4" — el procedimiento vive en `docs/protocols/deploy-protocol.md` + `DEPLOY.md`. Suficiente; no crear skill nueva para esto.
- `/sub-skill` no existe como comando en Kimi Code — el inventario se tomó del listing de sesión.
