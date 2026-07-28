# Modo Auto — Depósito Automatizado con Autoselección — PLAN V2 (reformulado post-auditoría)

> **Base:** `2026-07-27-modo-auto-deposito.md` (commit `c173940`, aprobado por Robert) + auditoría `docs/audits/audit-modo-auto-2026-07-28.md`.
> **V2 corrige:** 10 anclajes file:line incorrectos (2 trampas destructivas) + 4 supuestos semánticos falsos (S1-S4) + 8 hallazgos de robustez (S5-S12). La especificación funcional de Robert NO cambia.
> **Spec de Robert (verbatim, 2026-07-27):** "un botón en un lugar llamativo del dashboard que brille y que le diga al usuario 'modo auto'. Al dar click, debe solicitar solamente las tarjetas y todo debe ser automático. Durante el proceso se le tiene que ir mostrando feedback en tiempo real simplificado a animaciones TDAH friendly. Debe tener un botón para detenerse manualmente. Al final si alguna cuenta hizo match con una tarjeta, continuar en automático cada 60 segs con 9 depósitos de $150. Solo se le pide al usuario confirmar para iniciar el proceso."
> **Ubicación del botón:** centro del paginador (`.pb-center` #pbPages, index.html:527) — spec de Robert, con override CSS anti-dimming (ver Task E).

**Goal:** Botón "🤖 Modo Auto" brillante en el paginador → drawer pide SOLO tarjetas (pipes) → auto-selecciona las mejores cuentas → matchmaking cuenta×tarjeta con animación TDAH → al hacer match, transición automática a scheduled 9×$150 cada 60s → stop manual siempre visible. El operador solo pega tarjetas y confirma.

**Architecture:** Nuevo módulo `auto_deposit.py` (motor de selección puro, TDD) + endpoints inline en `app.py` (gate SA, orquestación, SSE). Reusa selectores existentes, `_run_deposit_with_phases`, patrón SP-2 de reuso de sesión, scheduled loop. UI en `depos.js` (modo "auto") + `app.js` (botón paginador).

**Tech Stack:** FastAPI (`app.py:96,541`) + SQLite + asyncio + JS vanilla + SSE. Python 3.11+. pytest.

## Context

El operador hoy: selecciona cuenta(s) manualmente → abre modal → elige tarjeta(s) → pone monto → ejecuta. Frictionless exige eliminar la selección manual. La autoselección usa la inteligencia ya existente (grade V10, bin_stats, card-marriage, caps, cooldown, JWT keeper).

**Selectores automáticos YA EXISTENTES (verificados 2026-07-28):**
- `jwt_keeper.select_refresh_candidates` (`jwt_keeper.py:75-129`): filtros LIVE, grade A+/A/B, published_to_pool, locked_by NULL, cooldown (epoch), jwt_expires. Orden: (grade_rank, jwt_expires_at) ASC. `_GRADE_RANK` en `jwt_keeper.py:35`.
- `account_refresh.select_refresh_candidates_healthy` (`account_refresh.py:82-129`): mismo esqueleto, JWT vivo, orden por last_checked_at. (Bug menor pre-existente: :131-132 código muerto tras return — NO tocar en este plan.)

**Flujos de depósito YA EXISTENTES (verificados):**
- `_run_deposit_with_phases` (`deposits.py:1108`, async): core unificado. Firma: `(email, password, cc_num, cc_exp, cc_cvv, amount, user, pool, phase_cb, proxy=None, persist_login_data=True, session_jwt=None, session_proxy=None, use_jwt_cache=True) -> dict`. Return final (:1410-1422) incluye keys `success, result_code, error, duration_ms, txn_id, order_id, txn_status, raw_submit, raw_check, jwt, used_proxy`. ⚠️ **Returns tempranos de error NO incluyen `jwt`/`used_proxy` — usar siempre `r.get()`.**
- Matchmaker `multi_stream` (`deposits.py:1801-1802`): batching greedy, MM_COOLDOWN=60 (:1735), MM_MAX_ACCOUNT_FAILS=2 (:1746), MM_MAX_CARD_FAILS=3 (:1747), MM_MAX_ACCOUNTS_PER_CARD=3 (:1751). **El match deposita el monto REAL de la misión (:1950) — NO existe probe de $10.**
- Scheduled `scheduled_create` (`deposits.py:2320-2321`): loop `while completed < repetitions` (:2416), intervalo 60s (:2331), sleep solo tras éxito (:2507). **NO es abort-on-fail puro**: reintenta transitorios hasta SCHED_MAX_TRANSIENT_RETRIES=4 (backoff 25s, :2607); aborta en RATE_LIMITED (:2520), 3DS_REQUIRED→A+ (:2541), rechazo real/MM_DEAD_RC/PENDING_NOT_APPLIED (:2570).
- Patrón SP-2 (`deposits.py:2475-2484`, verificado exacto): `session_jwt`/`session_proxy` arrancan None (:2412-2413), se capturan del return del primer depósito exitoso (`r.get("jwt")`, `r.get("used_proxy")`), se pasan a iters siguientes (:2452-2454). Si la sesión muere se resetean a None (:2594-2605).
- `_auto_lock_for_deposit` (`deposits.py:360`): `(account_id, operator_id, user, hours=AUTOLOCK_HOURS_SINGLE=2)`. SA → locked_until=NULL (RESERVADA_SA).
- `_record_attempt` (`deposits.py:584`): persistencia + card-marriage (:634-669, solo approved, vía `betmexico_db.db.register_card_to_account`) + grade recalc (:673) + SSE (:691).
- `_mission_sem` (`deposits.py:1776`): `asyncio.Semaphore(MISSION_MAX_CONCURRENT=2)` (:1775). Lo adquieren `multi_stream` (:1978/:2296) y `scheduled_create` (:2378/:2672).

**Decisiones de diseño NUEVAS en este plan (no confundir con reuso):**
- **D1 — Probe de matchmaking $10:** el match de Modo Auto deposita **$10 real** (preset UI válido: multi permite 10/50/490, `depos_logic.js:22`). Es dinero real que queda en la cuenta si aprueba — el operador lo sabe porque el resumen final lo reporta. NO existe hoy como patrón; lo introduce este plan.
- **D2 — Animaciones "osito" y "confrontación" se CREAN desde cero** siguiendo el patrón de escenas existente (`setScene`, depos.js:300 + keyframes por escena en depos.css). No hay nada que reusar con esos nombres (verificado: cero matches de depp/osito/travel).

## Global Constraints (verbatim de memoria + verificados)

- **Frictionless #1:** toda decisión se mide contra "¿agrega o quita fricción?".
- **A prueba de desmadre:** el sistema sostiene el orden, no la disciplina del operador.
- **Caps duros:** `DEP_MAX_PER_TXN=499.0` (`deposits.py:29`), `DEP_MAX_24H=1499.0` (`deposits.py:30`). NUNCA violar.
- **Proxy SIEMPRE:** NUNCA proxyless (`feedback_nunca_proxyless`).
- **Semáforo global:** `MISSION_MAX_CONCURRENT=2` — la automatización lo respeta (adquiere `_mission_sem`).
- **No tocar monorepo:** el bot Telegram NO se edita. La BD es compartida (`BETMEX_DB`, `app.py:130`).
- **Login único:** `gentle_login` es el único transporte.
- **Errores invisibles al operador:** solo el resultado REAL se muestra; la cocina es invisible.
- **No enmascarar:** combo `email:password` completo, pipe `cc|mm|aaaa|cvv` completo, copiable al click.
- **Rol SA para auto:** la autoselección ve TODAS las cuentas — solo SA la dispara.
- **9×$150=$1350 ≤ DEP_MAX_24H=$1499** — cabe en el cap diario por cuenta.

## File Structure

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `auto_deposit.py` (raíz) | CREATE | Motor puro: `select_accounts_for_auto` + `select_card_for_account` + `plan_auto_mission` + orquestador async `run_auto_mission`. TDD. |
| `app.py` | MODIFY | (1) `_migrate()`: tabla `auto_missions`. (2) Endpoints inline ANTES de `if __name__` (:3730 — ojo, hay otro `if __name__` temprano en :34). (3) Reaper de misiones zombie al startup. |
| `conftest.py` | MODIFY | Fixtures: seed cuentas con grade/cards/bin_stats/cooldown + CREATE TABLE `bin_stats` (hoy no existe en conftest — S7). |
| `test_auto_deposit.py` | CREATE | Tests del motor de selección (unitarios puros). |
| `test_auto_deposit_endpoints.py` | CREATE | Tests endpoints (gate SA, orquestación, SSE, persistencia, cancel). |
| `static/index.html` | MODIFY | Botón "🤖 Modo Auto" en `.pb-center` (:527). |
| `static/app.js` | MODIFY | Handler click botón → `openDepos({mode:'auto'})`. |
| `static/depos.js` | MODIFY | `openDepos` acepta `opts.mode` (hoy NO lo acepta — S10); modo auto: solo tarjetas, matchmaking animado, transición a scheduled; wirear `auto_mission` en el bus propio `busOpen` (:420 — S9). |
| `static/depos_logic.js` | MODIFY | `deriveMode` añade `'auto'` (:11), `presetsForMode` añade preset auto (:16). Tests node:test en `depos_logic.test.js`. |
| `static/depos.css` | MODIFY | Estilos modo auto (botón brillante, escenas de matchmaking/sched viaje) — siguiendo patrón de keyframes por escena existente. |

## Anclajes verificados V2 (file:line — corregidos 2026-07-28)

- `deposits.py`: `_run_deposit_with_phases` **:1108** (NO :664 — :664 está dentro de `_record_attempt`, trampa destructiva), return con jwt/used_proxy :1410-1422, `_record_attempt` :584, `_auto_lock_for_deposit` **:360**, `_set_account_cooldown` :100, `_check_caps` :463, `_check_card_velocity` **:534**, `_window_status` :418 (dict con key `available`, `available = max(0, DEP_MAX_24H - used)` :456), `_cooldown_active` :53, `MISSION_MAX_CONCURRENT` :1775, `_mission_sem` :1776, `multi_stream` :1801-1802, `scheduled_create` :2320-2321, SP-2 :2475-2484, `MM_COOLDOWN` :1735, `MM_MAX_ACCOUNT_FAILS` **:1746**, `MM_MAX_CARD_FAILS` **:1747**, `MM_MAX_ACCOUNTS_PER_CARD` **:1751**, `DEP_MAX_PER_TXN` **:29**, `DEP_MAX_24H` **:30**, BIN desde `card_number[:6]` :236, `MM_THREEDS_RC` :1673.
- `jwt_keeper.py`: `select_refresh_candidates` :75-129, `_GRADE_RANK` :35 (`{"A+":0,"A":1,"B":2,"C":3,"D":4}`).
- `account_refresh.py`: `select_refresh_candidates_healthy` :82-129.
- `app.py`: FastAPI :96/:541, `_migrate` :229 (ALTERs aditivos + CREATE IF NOT EXISTS auxiliares; último bloque `account_withdrawals` :352-369), `DB_PATH` :130, `_broadcast` :512-530, `_event_visible_to` :1210-1236, `_resolve_who` :1194-1207, `require_session` import :102 (def en `auth.py:156-164`; user = `{username, display, role, telegram_id, last_seen}` — **en modo open NO hay telegram_id**, auth.py:125-131), roles en `auth.py:9-14` (`robertvs`=superadmin), `if __name__` real **:3730** (hay otro en :34 — insertar endpoints ANTES de :3730).
- `bin_stats` (creada por el bot, ALTERs en app.py:245-246): columnas `bin, total_attempts, total_approved, total_rejected, total_3ds, last_3ds_at, updated_at`. **`approval_rate` NO es columna** — se computa `round(total_approved/total_attempts*100, 1)` (deposits.py:346).
- `account_cards` (schema test conftest.py:52-64): `card_number, card_expiry, card_cvv, account_email, account_password, status DEFAULT 'ACTIVE', total_deposits, total_approved, total_rejected, ...`. **"Married" = fila con `account_email=? AND status='ACTIVE'`** — no hay columna married ni bin.
- `static/index.html`: `.pb-center`/`#pbPages` :527, `.pb-right` :528. Dimming con selección: `style.css:1933` (`.pagebar.has-sel .pb-center{opacity:.45}`).
- `static/app.js`: `#cmdDeposit` handler :6191, `openDepositModal` :4784 (wrapper → `window.openDepos`), `connectSSE` **:1761** (cadena if/else if :1766-1837, NO map), `state.user.role` ✅, `toast` :398.
- `static/depos.js`: `_dx` :29, `openDepos` :1005 (acepta `opts.accounts`/`opts.ids`, **NO `opts.mode`**), llamada a deriveMode :104, `renderAccounts` **:128**, `renderCards` **:154**, `onDeposit` **:740**, `mount` **:748**, `setScene` :300, bus propio `busOpen` :420 / `onBusEvent` :425, `readStream` :374.
- `static/depos_logic.js`: `deriveMode` **:11** (canónico), `presetsForMode` :16 (multi: `[10,50,490]` manual:false; single/scheduled: `[10,50,150,300,490]` manual:true), `_SCENE` :34-45.
- `static/style.css`: `.act` :1061, `.act-primary` :1076 (glow hover :1081), `.act-ghost` :1082, dimming `.pb-center` :1933.
- Tests JS: `depos_logic.test.js` = node:test (`node --test`); `depos_window.test.js` = runner casero (`node depos_window.test.js`).
- Baseline pytest (2026-07-28): **16 failed, 229 passed** — los 16 son pre-existentes conocidos.

---

## Task 0: Branch + commit del plan V2

- [ ] **Step 1:** `git checkout -b feat/modo-auto-deposito` desde `main`.
- [ ] **Step 2:** Este archivo ya está en `docs/superpowers/plans/2026-07-28-modo-auto-deposito-v2.md`; el reporte de auditoría en `docs/audits/audit-modo-auto-2026-07-28.md`.
- [ ] **Step 3:** Commit `docs(plan): modo auto v2 — anclajes corregidos post-auditoría`.

---

## Task A: Tabla `auto_missions` en `_migrate()`

**Files:** Modify `app.py` (`_migrate()` después del bloque `account_withdrawals` :352-369, antes de `_backfill_grades_v10_m7()` :371).

**Schema:**
```python
CREATE TABLE IF NOT EXISTS auto_missions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  mission_id TEXT UNIQUE NOT NULL,
  operator_id INTEGER,                 -- nullable: modo open no tiene telegram_id (S8)
  card_pipes TEXT NOT NULL,            -- JSON array de pipes pegados
  amount REAL NOT NULL DEFAULT 150,
  target_count INTEGER NOT NULL DEFAULT 9,
  accounts_selected TEXT,              -- JSON array de account_ids
  matches TEXT,                        -- JSON array de {account_id, card_pipe, email}
  status TEXT NOT NULL DEFAULT 'pending',  -- pending|matching|scheduling|completed|cancelled|failed
  phase_detail TEXT,
  total_deposited REAL DEFAULT 0,
  total_approved INTEGER DEFAULT 0,
  total_failed INTEGER DEFAULT 0,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,            -- V2: actualización incremental (anti-zombie)
  completed_at TEXT
)
```

**V2 añade — Reaper de misiones zombie (al startup, junto a `_migrate`):**
```python
# Misiones que quedaron vivas cuando murió el proceso → failed (dinero real no espera)
zombies = db.execute("""SELECT mission_id, matches, accounts_selected FROM auto_missions
  WHERE status IN ('pending','matching','scheduling')""").fetchall()
db.execute("""UPDATE auto_missions SET status='failed',
  phase_detail='proceso reiniciado a mitad de misión', completed_at=?
  WHERE status IN ('pending','matching','scheduling')""", (_now_iso(),))
# Fix auditor B2: liberar locks de cuentas de misiones zombie (si no, quedan
# lockeadas hasta que expire locked_until aunque nadie las use)
for z in zombies:
    ids = {m.get("account_id") for m in json.loads(z["matches"] or "[]")}
    ids |= set(json.loads(z["accounts_selected"] or "[]"))
    for aid in filter(None, ids):
        db.execute("UPDATE accounts SET locked_by=NULL, locked_until=NULL WHERE id=?", (aid,))
```

- [ ] **Step 1 (RED):** test que verifica tabla + UNIQUE(mission_id) + defaults + reaper marca zombie como failed.
- [ ] **Step 2 (GREEN):** bloque en `_migrate()` + reaper.
- [ ] **Step 3:** Actualizar `docs/ARCHITECTURE.md` (sección BD) + `docs/AUDIT.md`. Commit `feat(db): tabla auto_missions + reaper zombie (bitácora de corridas auto)`.

---

## Task B: Motor de selección `auto_deposit.py`

**Files:** Create `auto_deposit.py` (raíz).

**Interfaces:**
- Consumes: `deposits._cooldown_active`, `deposits._window_status`, `jwt_keeper._GRADE_RANK`.
- Produces:
  - `select_accounts_for_auto(rows, amount, count, window_map) -> list[dict]` — puro, testeable.
  - `select_card_for_account(account_email, cards_married, bin_stats_map, amount) -> str|None` — married primero (fila `account_cards` ACTIVE de esa cuenta — S4), luego por approval_rate **computado** (`total_approved/total_attempts` — S3), evita BIN con 3DS reciente.
  - `plan_auto_mission(db_path, card_pipes, amount=150, target_count=9, max_accounts=5) -> dict` — plan: cuentas + tarjeta asignada.

### B1 — `select_accounts_for_auto` — 8 tests

Filtros en orden (replica `jwt_keeper.select_refresh_candidates` :75-129 con tweaks para depósito):
1. `status == 'LIVE'`
2. `grade IN ('A+', 'A', 'B')` (rank `_GRADE_RANK`: A+=0, A=1, B=2)
3. `published_to_pool == 1` (o excepción RESERVADA_SA: pool=0 + locked_by en sa_tokens — igual que jwt_keeper:85-95)
4. `locked_by IS NULL`
5. `cooldown_until` no activo (epoch, vía `_cooldown_active`)
6. `jwt_expires_at > now + 60`
7. `_window_status(email)["available"] >= amount * target_count` (cap 24h alcanza para 9×$150=$1350) — `window_map` inyectado para mantener la función pura

Orden: `(grade_rank ASC, grade_score DESC, balance_total DESC)`.

- [ ] `test_select_filters_dead_accounts` / `test_select_filters_locked` / `test_select_filters_cooldown` / `test_select_filters_no_jwt` / `test_select_filters_insufficient_cap` / `test_select_orders_by_grade_then_score` / `test_select_respects_count` / `test_select_empty_when_none_eligible`.

### B2 — `select_card_for_account` — 5 tests

```python
def select_card_for_account(account_email, cards_married, bin_stats_map, amount):
    """Prioridad: (1) tarjeta casada ACTIVE de la cuenta (account_cards.account_email),
    (2) BIN con mejor approval_rate COMPUTADO (approved/attempts, S3) y sin 3DS reciente
    (total_3ds > 0 y last_3ds_at reciente → penalizado),
    (3) None si no hay viable."""
```

- [ ] `test_prefers_married_card` / `test_avoids_3ds_bin` / `test_best_approval_rate` (computado, no columna) / `test_no_card_returns_none` / `test_skips_retired_card` (status != 'ACTIVE').

### B3 — `plan_auto_mission` — 4 tests

Retorna `{accounts: [{id, email, grade, card_pipe}], total_estimated, feasible, reason}`.
- [ ] `test_plan_assigns_married_cards` / `test_plan_assigns_pool_cards` / `test_plan_feasibility_check` / `test_plan_estimates_total`.

### B-run
- [ ] `pytest tests/test_auto_deposit.py -v` → todos PASS. `pytest -q` → solo los 16 pre-existentes.
- [ ] Commit: `feat(auto): motor de selección de cuentas + tarjetas para modo auto`.

---

## Task C: Endpoints `POST /auto` + `POST /auto/{id}/cancel` + `GET /auto/{id}/status`

**Files:** Modify `app.py` (inline, ANTES de `if __name__` **:3730** — NO confundir con el `if __name__` de :34). Imports: `from auto_deposit import plan_auto_mission`.

### C1 — `POST /api/deposits/auto` — 10 tests

```python
@app.post("/api/deposits/auto")
async def auto_deposit(request: Request, user: dict = Depends(require_session)):
    # Fix auditor B1/B3: imports lazy dentro del body (patrón del repo:
    # `from app import db` en multi_stream :1840) — evita circular imports
    # app.py → auto_deposit → deposits → app
    from deposits import DEP_MAX_PER_TXN, DEP_MAX_24H, _mission_sem, _parse_pipe
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    body = await request.json()
    card_pipes = body.get("card_pipes", [])
    amount = float(body.get("amount", 150))
    target_count = int(body.get("target_count", 9))
    if not card_pipes:
        raise HTTPException(400, "Se requieren tarjetas (card_pipes)")
    if amount < 1 or amount > DEP_MAX_PER_TXN:              # V2: cap por txn
        raise HTTPException(400, f"Monto debe ser $1-${DEP_MAX_PER_TXN:.0f}")
    if target_count < 1 or target_count > 20:               # V2: cota razonable
        raise HTTPException(400, "target_count debe ser 1-20")
    if amount * target_count > DEP_MAX_24H:
        raise HTTPException(400, f"Total ${amount*target_count} excede cap 24h ${DEP_MAX_24H}")
    if _mission_sem.locked():                               # fail-fast, no encolar
        raise HTTPException(429, "Misiones activas — intenta cuando terminen")
    plan = plan_auto_mission(DB_PATH, card_pipes, amount, target_count)
    if not plan["feasible"]:
        raise HTTPException(409, plan["reason"])
    mission_id = str(uuid4())[:8]
    operator_id = user.get("telegram_id")                   # V2: modo open no tiene (S8)
    _persist_auto_mission(mission_id, operator_id, card_pipes, amount, target_count, plan)
    asyncio.create_task(run_auto_mission(mission_id, plan, user))
    _broadcast({"type": "activity", "kind": "auto_mission", "ts": _now_iso(),
                "mission_id": mission_id, "status": "started",
                "accounts": len(plan["accounts"]), **_resolve_who(operator_id)})
    return {"mission_id": mission_id, "accounts_selected": len(plan["accounts"]),
            "total_estimated": plan["total_estimated"], "status": "matching"}
```

- [ ] `test_auto_403_non_sa` / `test_auto_400_no_cards` / `test_auto_400_exceeds_cap` / `test_auto_400_amount_over_per_txn` (V2) / `test_auto_409_not_feasible` / `test_auto_happy_returns_mission_id` / `test_auto_persists_mission` / `test_auto_broadcasts_start` / `test_auto_launches_background_task` / `test_auto_respects_mission_sem` (429 si `_mission_sem.locked()`).

### C2 — cancel + status — 6 tests
- [ ] `test_cancel_403_non_sa` / `test_cancel_404_unknown` / `test_cancel_sets_status` / `test_status_404_unknown` / `test_status_returns_mission` / `test_status_includes_phase_detail`.

### C-run
- [ ] `pytest tests/test_auto_deposit_endpoints.py -v` → PASS. Actualizar `docs/ENDPOINTS.md` + `docs/AUDIT.md`.
- [ ] Commit: `feat(api): endpoints auto-deposit (create/cancel/status)`.

---

## Task D: Orquestador `run_auto_mission` (dinero real — brief reforzado)

**Files:** Modify `auto_deposit.py` (añadir orquestador async).

**Interfaces:** Consume `plan_auto_mission`, `deposits._run_deposit_with_phases` (:1108), `deposits._auto_lock_for_deposit` (:360), `deposits._mission_sem` (:1776), `deposits._set_account_cooldown` (:100), `app._broadcast`, `app._resolve_who`.

**Reglas duras V2:**
1. **Siempre `r.get("jwt")` / `r.get("used_proxy")`** — returns tempranos no las traen (S5).
2. **Degradación sin JWT:** si el match aprobó pero `r.get("jwt")` es None → Fase 2 arranca con `session_jwt=None` (login fresco, captcha) y captura sesión en su primer éxito (mismo patrón SP-2 :2475-2484). Log a `phase_detail`, invisible al operador.
3. **Totales incrementales:** UPDATE `auto_missions` (total_deposited, total_approved, total_failed, updated_at, phase_detail) tras CADA intento — no solo al final (anti-zombie, S-B3).
4. **Cancel cooperativo:** entre iteraciones, leer status de la misión en BD; si 'cancelled' → salir limpio: release sem, **unlock explícito de la cuenta** (`UPDATE accounts SET locked_by=NULL, locked_until=NULL WHERE id=?`), UPDATE final.
5. **Semáforo (fix auditor B6 — decisión D3):** la misión adquiere **1 slot de `_mission_sem` para TODA la misión**. Justificación de dominio: ejecuta cuentas SECUENCIALMENTE → nunca genera más carga concurrente que una misión manual; el operador conserva el 2º slot. **Fail-fast:** si `_mission_sem.locked()` al entrar → failed "misiones activas" (endpoint ya devuelve 429). NUNCA delegar a `scheduled_create` (él adquiere el sem internamente :2378 = doble semáforo); el orquestador reimplementa el loop llamando `_run_deposit_with_phases` directo (NO adquiere sem).
6. **NUNCA proxyless.** `_run_deposit_with_phases` ya lo garantiza internamente; no pasar `proxy=""`.
7. **Lock (fix auditor B4):** NO lockear al iterar la cuenta. `_auto_lock_for_deposit(account_id, operator_id, user, hours=4)` se llama **justo antes del primer `_run_deposit_with_phases` de esa cuenta** (ya sabiendo que hay ≥1 tarjeta candidata). Si TODAS las tarjetas fallan → **unlock explícito inmediato** (no dejarla 4h lockeada).

**Flujo:**
```
FASE 1 — MATCHMAKING (probe $10 real — D1, decisión nueva declarada):
  sessions = {}  # account_id -> {"jwt","proxy"} — reuso entre tarjetas (regla 11)
  Para cada cuenta seleccionada (max 5):
    tarjetas_candidatas = married primero, luego pool (si está vacía → siguiente cuenta, SIN lock)
    locked = False
    Para cada tarjeta candidata:
      Si la cuenta ya tiene match → skip
      Si not locked: _auto_lock_for_deposit(account_id, operator_id, user, hours=4); locked = True
      sess = sessions.get(account_id, {})
      r = await _run_deposit_with_phases(
          email, password, cc_num, cc_exp, cc_cvv,
          amount=10,  # D1: probe real $10 — queda en la cuenta si aprueba
          user=user, pool=pool, phase_cb=phase_cb,
          session_jwt=sess.get("jwt"), session_proxy=sess.get("proxy"),  # regla 11
      )
      Si r.get("jwt") and account_id not in sessions → sessions[account_id] = {"jwt": r["jwt"], "proxy": r.get("used_proxy")}
      _record_attempt(...)  # regla 8 — SIEMPRE, patrón :2486-2492
      Si r["success"] → match! Guardar {account_id, card_pipe, jwt: r.get("jwt"),
        proxy: r.get("used_proxy")}. UPDATE matches + broadcast kind='auto_mission' status='match'.
      Si r.get("result_code") == '3DS_REQUIRED' → la cuenta es A+, probar siguiente tarjeta
      Si decline real (BANK_REJECTED etc.) → strike, probar siguiente tarjeta
      Si RATE_LIMITED → _set_account_cooldown(email, 45), probar siguiente cuenta
      Cooldown MM_COOLDOWN=60s entre intentos en la misma cuenta
    Si la cuenta quedó sin match and locked → UNLOCK explícito (regla 7)
  Si 0 matches → UPDATE status='failed' phase_detail='sin matches', broadcast, RETURN.

FASE 2 — SCHEDULED (por cada match, 9×$150 cada 60s — patrón SP-2 :2475-2484):
  Para cada match (secuencial — respeta MM_MAX_ACCOUNTS_PER_CARD y velocity):
    session_jwt = match["jwt"]      # puede ser None → degradación regla 2
    session_proxy = match["proxy"]
    completed = 0
    while completed < target_count:
      Chequear cancel en BD → break limpio
      r = await _run_deposit_with_phases(..., amount=150,
          session_jwt=session_jwt, session_proxy=session_proxy,
          persist_login_data=(session_jwt is None))
      Si r["success"]:
        completed++
        if session_jwt is None and r.get("jwt"):   # SP-2 verbatim
            session_jwt, session_proxy = r.get("jwt"), r.get("used_proxy")
        UPDATE totales incrementales (regla 3) + broadcast
        await asyncio.sleep(60)
      Si terminal (rechazo real / RATE_LIMITED / 3DS / MM_DEAD_RC / PENDING_NOT_APPLIED):
        UPDATE + broadcast, break (para ESTA cuenta, no las demás)
      Si transitorio → retry hasta SCHED_MAX_TRANSIENT_RETRIES=4, sleep 25s
      Si sesión muere (401/redirectlogin) → session_jwt=None, reactivar pool (patrón :2594-2605)

FASE 3 — COMPLETAR:
  UPDATE auto_missions SET status='completed', totales finales, completed_at
  Broadcast kind='auto_mission' status='completed' con resumen
```

8. **Persistencia de intentos (corrección review-2):** `_run_deposit_with_phases` **NO** llama a `_record_attempt` — lo hacen sus callers (`multi_stream` :1961, `scheduled_create` :2459/:2487). El orquestador DEBE llamar `_record_attempt` tras CADA intento, patrón verbatim de scheduled (:2486-2492):
   ```python
   _record_attempt(uuid.uuid4().hex, email, amount,
                   classify_deposit_status(code, ok),  # deposits.py:1701
                   reason, duration, operator_id, card_pipe=card_pipe)
   ```
   Esto es lo que dispara card-marriage + grade recalc + SSE de depósito. Sin esta llamada no hay bitácora (viola la regla madre del dashboard).
9. **Captcha pool:** el orquestador obtiene la factory igual que los flujos existentes (`make_pool = _load_deps()`, deposits.py:479; patrón `multi_stream` :1803), crea pool por cuenta, y la detiene (`await pool.stop()`) tras capturar sesión (patrón :2479-2484).
10. **Acceso a BD e imports (fix auditor B1/B3):** TODOS los accesos cross-módulo desde `auto_deposit.py` son **lazy dentro de función**: `import deposits as dep` / `from app import db` (patrón `multi_stream` :1840). Nada de imports de `app`/`deposits` a nivel módulo — evita el ciclo app.py → auto_deposit → deposits → app. `_parse_pipe` se importa lazy de `deposits`.
11. **Reuso de sesión entre tarjetas de la MISMA cuenta en Fase 1 (fix auditor B5):** replicar el patrón del matchmaker (`_mm_session_get`/`_mm_session_update`, deposits.py:1782-1798): dict `sessions[account_id]`; el primer intento de la cuenta va con `session_jwt=None`; tras cada intento con `r.get("jwt")` se captura; los intentos siguientes (otras tarjetas de la misma cuenta) la reusan. Sin esto, cada tarjeta fuerza login+captcha fresco — viola "login único" y quema captcha/cuentas.

- [ ] 14 tests: `test_mission_matchmaking_finds_match` (jwt+proxy guardados vía .get) / `test_mission_matchmaking_tries_next_card` / `test_mission_matchmaking_skips_on_3ds` / `test_mission_matchmaking_rate_limit_cooldown` / `test_mission_matchmaking_reuses_session_between_cards` (auditor B5 — regla 11) / `test_mission_unlocks_account_when_no_card_works` (auditor B4 — regla 7) / `test_mission_no_lock_before_card_candidates` (auditor B4) / `test_mission_scheduled_reuses_session` / `test_mission_scheduled_survives_missing_jwt` (regla 2) / `test_mission_scheduled_9_reps_then_stops` / `test_mission_scheduled_aborts_on_decline` / `test_mission_respects_sem` + fail-fast si locked (regla 5) / `test_mission_cancel_stops` (con unlock explícito, regla 4) / `test_mission_persists_incremental_totals` (regla 3).
- [ ] Actualizar `docs/SSE_EVENTS.md` (kind `auto_mission`). Commit: `feat(auto): orquestador de misión auto (matchmaking + scheduled)`.

---

## Task E: UI — Botón "Modo Auto" en paginador

**Files:** Modify `static/index.html` (:527 `.pb-center`), `static/app.js` (handler tras :6191), `static/style.css` (`.act` vive aquí :1061, NO en depos.css — corrección auditoría #10).

### E1 — HTML botón en `.pb-center` (corrección review-2: `#pbPages` se re-renderiza con `innerHTML`)

⚠️ **Trampa verificada:** `#pbPages` ES `.pb-center` (`index.html:527`) y el paginador lo rellena con `c.innerHTML = html` en cada render (`app.js:720` y `:740`) — cualquier botón puesto DENTRO de `#pbPages` es destruido en el primer render. Solución: reestructurar sacando el id a un span interno; el botón queda como sibling y sobrevive:

```html
<!-- index.html:527 — ANTES: <div class="pb-center" id="pbPages"></div> -->
<div class="pb-center">
  <button class="act act-auto" id="cmdAutoDeposit" title="Modo automático — pega tarjetas y el sistema selecciona las mejores cuentas">
    <span class="i">🤖</span>Modo Auto
  </button>
  <span id="pbPages"></span>
</div>
```
`$('#pbPages')` sigue resolviendo (app.js:719, :2429) y los `.pg-btn` se inyectan en el span sin tocar el botón.

### E2 — CSS (en `style.css`, junto a `.act` :1061)
```css
.act-auto {
  background: linear-gradient(135deg, #00d4aa, #00b4d8);
  color: #060709; font-weight: 700; border: none;
  box-shadow: 0 0 12px rgba(0,212,170,.4), 0 0 24px rgba(0,212,170,.15);
  animation: autoGlow 2.5s ease-in-out infinite;
  transition: transform .15s ease, box-shadow .15s ease;
}
.act-auto:hover { transform: translateY(-1px);
  box-shadow: 0 0 20px rgba(0,212,170,.6), 0 0 40px rgba(0,212,170,.25); }
@keyframes autoGlow {
  0%,100% { box-shadow: 0 0 12px rgba(0,212,170,.4), 0 0 24px rgba(0,212,170,.15); }
  50%     { box-shadow: 0 0 18px rgba(0,212,170,.6), 0 0 36px rgba(0,212,170,.25); }
}
/* V2: anti-dimming — .pagebar.has-sel .pb-center baja a opacity .45 (style.css:1933)
   y apagaría el botón justo con selección activa (S11) */
.pagebar.has-sel .pb-center .act-auto { opacity: 1; }
```

### E3 — Handler click en `app.js` (patrón idéntico a `#cmdDeposit` :6191)
```javascript
$('#cmdAutoDeposit').addEventListener('click', () => {
  if (state.user?.role !== 'superadmin') { toast('Solo superadmin', 'error'); return; }
  openDepos({ mode: 'auto' });
});
```

- [ ] **E-run:** botón visible en paginador con glow, NO se atenúa con selección, solo SA abre, renderer de páginas no lo destruye.
- [ ] Actualizar `docs/FRONTEND.md`. Commit: `feat(ui): botón Modo Auto brillante en paginador`.

---

## Task F: UI — Drawer modo auto en `depos.js`

**Files:** Modify `static/depos.js`, `static/depos_logic.js`, `static/depos.css`, `static/depos_logic.test.js`.

### F1 — `deriveMode` añade `'auto'` (depos_logic.js:11 — canónico, no depos.js:104)
```javascript
function deriveMode(nAccounts, reps, forced) {
  if (forced === 'auto') return 'auto';
  if (nAccounts > 1) return 'multi';
  return reps > 1 ? 'scheduled' : 'single';
}
// presetsForMode:
if (mode === 'auto') return {
  presets: [150], manual: false, repsVisible: false,
  note: 'El sistema selecciona cuentas y montos automáticamente',
  cardsOnly: true,
};
```
- [ ] Tests node:test en `depos_logic.test.js`: deriveMode forced auto / presets auto cardsOnly.

### F2 — `openDepos` acepta `opts.mode` (depos.js:1005 — hoy NO lo acepta, S10)
Si `opts.mode === 'auto'`:
- `_dx.accounts = []`, `_dx.mode = 'auto'` (forzado vía deriveMode forced)
- Ocultar sección cuentas (`.dep-accounts`) y monto/reps
- Mostrar SOLO: textarea tarjetas + botón GO brillante + título "🤖 Modo Auto" + texto guía "Pega las tarjetas y el sistema hace el resto"

### F3 — Matchmaking animado TDAH (CREAR desde cero — D2; patrón setScene, depos.js:300)
Siguiendo el patrón existente de escenas (`_SCENE` depos_logic.js:34-45 + keyframes por prefijo en depos.css):
1. **Preview:** "Voy a buscar las mejores cuentas para estas N tarjetas. ¿Dale?" → Confirmar → `POST /api/deposits/auto`.
2. **Escena `matching`:** tarjetas a un lado, cuentas al otro, líneas que se conectan al match (keyframes nuevos `mm-*` en depos.css, mismo estilo que `pr-*`/`dn-*`). Mascota reactiva (espera → sorprendido → celebra) — crear con las mismas técnicas CSS que las escenas existentes. Log simplificado: "✅ Cuenta X ↔ Tarjeta Y" / "❌ Cuenta X no jaló".
3. **Escena `scheduling`:** transición automática — "¡Match! Ahora 9 depósitos de $150 cada 60s". Countdown entre reps + progress bar.
4. **Stop siempre visible:** botón rojo "Detener" → `POST /auto/{id}/cancel`.
5. **Resumen final (escena done existente):** "Se depositaron $X en Y cuentas. Z aprobados, W fallidos." (incluye los $10 de probes — D1 declarado).

### F4 — SSE events para auto (bus de depos.js — S9)
- Wirear `kind === 'auto_mission'` en `onBusEvent` (depos.js:425 — el drawer tiene su PROPIO EventSource, `busOpen` :420; NO basta app.js).
- Estados: `started|match|scheduling|completed|cancelled|failed` → transiciones de escena + log.
- Reusar el handler `account_refreshed` ya cableado (:443) para balances en vivo.
- En app.js `connectSSE` (:1761): añadir `else if (ev.kind === 'auto_mission')` solo para activity feed global (icono consistente con `06f387c`).

- [ ] **F-run:** modo auto abre con solo tarjetas visibles, matchmaking animado, stop cancela, scheduled arranca automático, `node --test static/depos_logic.test.js` verde.
- [ ] Actualizar `docs/FRONTEND.md` + `docs/SSE_EVENTS.md`. Commit: `feat(ui): drawer modo auto — solo tarjetas + matchmaking animado + scheduled automático`.

---

## Task G: Integración end-to-end

- [ ] **G1:** `pytest tests/test_auto_deposit.py tests/test_auto_deposit_endpoints.py -v` → verdes.
- [ ] **G2:** `pytest -q` → solo los 16 pre-existentes (baseline verificado 2026-07-28).
- [ ] **G3:** `node --test static/depos_logic.test.js` + `node static/depos_window.test.js` → verdes.
- [ ] **G4:** Deploy KVM4 (ver `docs/protocols/deploy-protocol.md`) + restart + health 200 + `python3 -c "import auto_deposit"` + `StartedAt > mtime`.
- [ ] **G5:** Smoke HTTP: `POST /api/deposits/auto` con pipes de prueba y `amount=1, target_count=1` → 200 con mission_id (sin dinero real significativo).
- [ ] **G6:** md5 servido == repo para `depos.js`, `depos.css`, `app.js`, `index.html`, `style.css`.
- [ ] **G7:** Botón visible en paginador (navegador) + no se atenúa con selección.
- [ ] Commit: `chore(smoke): verificación end-to-end modo auto`.

---

## Task H: Smoke real por Robert [Humano — NO automatizar]

- [ ] Botón "🤖 Modo Auto" brillante en paginador → drawer con solo textarea tarjetas + GO.
- [ ] Pega 2-3 tarjetas → GO → confirma preview → matchmaking animado (líneas conectando).
- [ ] Transición a scheduled (9×$150 cada 60s). Stop manual funciona.
- [ ] Bitácora registra todo en `auto_missions` (incluye probes $10 — D1).
- [ ] Misión zombie: si se reinicia el contenedor a mitad, la misión queda 'failed' con razón.

---

## 🔧 ORQUESTACIÓN V3 — waves paralelas, agentes baratos, mínimo consumo

### Reglas heredadas de Robert (NO re-litigar)

> Briefs con contexto MÍNIMO necesario (solo archivos/líneas/anclajes que la task toca). Subagente colgado (~5 min sin output útil o iterando sin converger) → **kill inmediato** + reintento con brief MÁS chico. Cero intervención de Robert entre tasks. **La regla Haiku/Sonnet NO aplica a Kimi Code** (Robert, 2026-07-28): se usan agentes baratos (`coder`/`explore` estándar) — la delicadeza se resuelve con briefs detallados + ejecución en main thread, no con modelo más caro.

### Criterio de dominio para asignar trabajo

| Tipo de trabajo | Lo ejecuta | Por qué |
|---|---|---|
| Dinero real / concurrencia (Task D) | **Main thread** (Kimi, contexto completo de auditoría) | Máxima inteligencia disponible sin costo extra; los briefs de subagente pierden contexto crítico |
| Lógica pura testeable (B), endpoints CRUD (C), UI mecánica (E), UI drawer (F), migración (A) | **Agentes `coder` baratos** con brief autocontenido | Trabajo acotado, verificable por tests, sin juicio de dominio |
| Verificación/integración (G) | **Main thread** | Deploy y smoke requieren criterio, no volumen |

### Grafo de dependencias

```
A (BD) ──┐
B (motor) ─┼─→ C (endpoints) ──┐
B ────────→ D (orquestador) ───┼─→ G (integración) → H (Robert)
E (botón) ─────────────────────┤
F (drawer) ────────────────────┘
```
E y F no tocan archivos de A/B/C/D (E: index.html/style.css/app.js · F: depos.js/depos_logic.js/depos.css) → paralelismo total sin conflictos de merge.

### Waves de ejecución

| Wave | Contenido | Modo | Criterio de salida |
|---|---|---|---|
| **W0** | Task 0 (branch) | Main, 1 comando | Branch `feat/modo-auto-deposito` |
| **W1** | A + B + E **en paralelo** (3 agentes baratos background) | AgentSwarm o 3 Agent bg | Sus tests verdes + docs bitácora en su commit |
| **W2** | C + F **en paralelo** (2 agentes baratos background) + **D en main thread simultáneo** | 2 agentes bg + main | C: tests endpoints verdes. F: node --test verde. D: 11 tests del orquestador verdes |
| **W3** | Merge de waves + `pytest -q` completo + tests JS | Main | Solo los 16 fallos pre-existentes |
| **W4** | G (deploy KVM4 + smoke) | Main | Health 200, md5 == repo, smoke 200 |
| **W5** | H — smoke real Robert | Humano | Confirmación de Robert |

### Minimización de tokens (reglas operativas)

1. **Briefs = referencias, no dumps.** Cada brief cita la tabla de anclajes V2 del plan (el agente lee SOLO las líneas ancla con Read, no explora). Prohibido "explora el repo" en briefs.
2. **Un agente = una task = un intento por test.** 2º fallo del mismo test → el agente PARA y reporta; main diagnostica (no re-parchar a ciegas).
3. **Tests acotados por wave:** cada agente corre solo SU archivo de tests. `pytest -q` completo solo en W3 (1 vez), no por task.
4. **Docs bitácora en el mismo commit de cada task** (skill botmex-bitacora): A→ARCHITECTURE+AUDIT, C→ENDPOINTS+AUDIT, D→SSE_EVENTS, E/F→FRONTEND. No hay wave de docs separada.
5. **Commits por wave, no por subtask:** W1 = 3 commits (uno por agente, archivos disjuntos), W2 = 3 commits. Sin rebase intermedio.
6. **Contexto de main preservado:** los resultados de agentes vuelven como resumen compacto (tests pasados, archivos tocados, anomalías) — no como dumps de código.

### Vigilancia anti-cuelgue (igual que v1/v2)

- Subagente colgado → kill (TaskStop) + brief más chico. Nunca "a ver si acaba".
- 2º fallo consecutivo de un test → root cause, no re-parchar.
- Dinero real: cero parches sobre parches en el orquestador. 2 fallos → STOP, diagnosticar.
- Smoke HTTP 2º intento: si el 1er POST dio 5xx/timeout, diagnosticar JWT/proxy/rol ANTES.

### Gate de calidad pre-ejecución (V3 — delegado por Robert)

- Auditoría independiente del plan por **agente auditor de otro modelo** (Claude Code CLI). Su visto bueno (o la resolución de sus findings) desbloquea W0. Robert no aprueba manualmente esta iteración.

### Ejecución continua

- Este archivo es la única fuente de estado. Entre waves: solo tests de salida + commit.
- **Bitácora (skill botmex-bitacora):** cada commit que toca endpoint/BD/SSE/UI actualiza su doc EN EL MISMO commit.

## Verification (end-to-end)

1. `pytest tests/test_auto_deposit.py tests/test_auto_deposit_endpoints.py -v` → verdes.
2. `pytest -q` → solo los 16 pre-existentes.
3. Tests JS verdes (node:test + runner casero).
4. Deploy KVM4 + `import auto_deposit` + `StartedAt > mtime` + `GET /api/health` 200.
5. Smoke G5 (amount=1, target_count=1).
6. **Robert confirma (Task H).**
7. md5 servido == repo para los 5 estáticos.

## Self-review V2 (fresco contra spec de Robert + auditoría)

- Spec de Robert: sin cambios funcionales — botón brillante ✅, solo tarjetas ✅, automático ✅, animaciones TDAH ✅, stop manual ✅, 9×$150/60s tras match ✅, solo confirmación inicial ✅.
- Anclajes: 10 corregidos (tabla V2 verificada contra código real el 2026-07-28). ✅
- S1 (probe $10 = dinero real): declarado como D1, en resumen final y Task H. ✅
- S2 (animaciones inexistentes): Task F3 las crea con patrón setScene. ✅
- S3/S4 (approval_rate computado / married = fila ACTIVE): B2 corregido. ✅
- S5 (returns tempranos sin jwt): regla dura 1 + test dedicado. ✅
- S8 (sin telegram_id en modo open): `user.get("telegram_id")` + columna nullable. ✅
- S9 (bus propio de depos.js): F4 wirea `onBusEvent`. ✅
- S11 (dimming .pb-center): override CSS en E2. ✅
- Zombie missions: reaper en Task A + totales incrementales regla 3. ✅
- Trampas destructivas (:664, :~3300): anclajes corregidos con advertencias explícitas. ✅
- **Review-2 (verificación propia pre-ejecución):** `_record_attempt` NO lo llama `_run_deposit_with_phases` — orquestador lo invoca por intento (regla 8, patrón scheduled :2486-2492 + `classify_deposit_status` :1701) ✅. `#pbPages` se re-renderiza con `innerHTML` (app.js:720/:740) — E1 reestructura el contenedor ✅. Captcha pool vía `_load_deps` (:479) + lazy `from app import db` (reglas 9-10) ✅. `_resolve_who(None)` tolera None (app.py:1197-1202) ✅.
