# Botón de Retiro Automático — Plan de Implementación

> **Ejecutar con `/Smartexe`.** Spec fuente: `docs/superpowers/specs/2026-07-24-boton-retiro-automatico-design.md`. Flujo probado en campo (5 retiros reales, $1,355, msaidrzz, 2026-07-24) en `docs/RECON_BETMEX_API.md` §"FLUJO DE RETIRO EXACTO".

**Goal:** Un botón SA-only en La Pantalla que dispara un retiro REAL de BetMexico vía API pura (5 pasos), monitorea y reporta en 2 fases, con 3 guardarrails contra bugs de campo confirmados.

**Architecture:** Módulo nuevo `withdrawals.py` (async, importable, TDD aislado con `httpx.MockTransport`) replica el patrón de `clabe_fetch.py`. Dos endpoints inline en `app.py` (gate SA + persistencia + SSE). Tabla `account_withdrawals` aditiva. UI en `pantalla.js/css` con polling 60s + SSE. `app.py` sigue sin llamar HTTP a BetMexico (ley del repo).

**Tech Stack:** FastAPI + SQLite + httpx (async) + JS vanilla + SSE. Python 3.11+. pytest.

## Context

El retiro manual vía `tools/bmx_call.py` ya retiró $1,355 en 5 retiros reales — el flujo de 5 endpoints está probado, no inferido. Faltaba volverlo un botón frictionless del dashboard para cuentas cuarentenadas (JWT cacheado funciona a nivel API aunque la UI de BetMexico no sea operable). El spec cerró 3 bugs de campo como guardarrails obligatorios: (1) un depósito SPEI reescribe la cuenta de retiro → no cachear `accountId`; (2) `status:6` BetMexico ≠ aterrizaje en banco → reportar 2 fases, no "entregado"; (3) retiro puede salir a tarjeta (gateway:1) cuando esperabas SPEI → alertar. BetMexico no permite retiros <$100, así que el smoke real es **$100 en msaidrzz (~$102)**, disparado por **Robert con click en la UI deployada** (no subagente a ciegas — dinero real).

## Global Constraints (verbatim del spec + verificados)

- **Host:** TODO el flujo de retiro va a `https://paymentsapi.betmexico.mx`. Solo identidad a `betmexico.mx/api/Users/`. Solo `betmexico.mx` para ICMP.
- **Proxy:** SIEMPRE con proxy (`proxy_pool.build_admin_proxy_url()`), NUNCA proxyless (ley `feedback_nunca_proxyless`). `begin_withdrawal` es **single-shot** (NO `call_with_proxy_failover`): un retry podría duplicar el retiro. Los GET (PASO1/2/4/5) sí pueden fallover.
- **Headers canónicos:** `{"Authorization": "Bearer {jwt}", "Accept": "application/json", "Content-Type": "application/json", "Origin": "https://betmexico.mx", "Referer": "https://betmexico.mx/"}`.
- **Body mínimo PASO3:** EXACTAMENTE `{"accountId": "<uuid>", "amount": <float>, "email": "<email>"}`. Bodies más chicos → 500; más grandes innecesarios. `amount` es float (no string).
- **JWT:** validar expiración antes de disparar (PASO0). Reusar `clabe_fetch._load_jwt_for_account(db, id)` (ya valida `int(exp) < time.time()`). **NO** reimplementar, **NO** usar `tools/bmx_call.py` (CLI-only, no importable).
- **Polling:** 60s, nunca menos (no alimentar rate-limit).
- **Rol:** solo SA (`_require_sa` / `user.get("role") != "superadmin"`). Loggear `account_touch` (SA ve toques ajenos).
- **Archivos congelados NO tocar:** `account_refresh.py`, `prewarm.py`, `deposits.py` (auditoría 2026-07-22). El flujo va en código nuevo.
- **Bot Telegram (monorepo) NO se toca** desde aquí (`feedback_no_monorepo`).
- **No loguear/pegar el JWT** completo en logs ni respuestas.

## File Structure

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `withdrawals.py` (raíz) | CREATE | 5 funcs async (PASO1-5) + orquestador + excepciones. Replica patrón `clabe_fetch.py`. Importable, testeable con `httpx.MockTransport`. |
| `app.py` | MODIFY | (1) `_migrate()`:141 añadir tabla `account_withdrawals`. (2) inline `POST /api/accounts/{id}/withdraw` + `GET .../withdraw/status/{tx_id}` antes de `if __name__`:~3300. |
| `conftest.py` | MODIFY | extender `seed_db` con `jwt_token`/`jwt_expires_at`; añadir fixture `mock_bmx_transport` (`httpx.MockTransport`). |
| `test_withdrawals.py` | CREATE | tests del módulo (PASO1-5 + guardarrails). |
| `test_withdrawals_endpoints.py` | CREATE | tests endpoints (gate SA, 409s, persistencia, broadcast, 2-fases). |
| `static/pantalla.js` | MODIFY | `renderPantallaWithdraw(d)` (botón+input), handler disparo, `renderPantallaWithdrawStatus(d)` (2 fases), polling 60s, SSE handler. |
| `static/pantalla.css` | MODIFY | estilos bloque retiro (reusar tokens `.pat-*`). |

## Anclajes verificados (file:line)

- `app.py`: `_migrate()` :141 (boot :330), patrón CREATE TABLE IF NOT EXISTS + `except OperationalError: pass` :238-251; `_is_sa` :360, `_require_sa` :1482; `account_touches` INSERT+broadcast :2870-2879; `_broadcast` :394-412, `_resolve_who` :1076, `_event_visible_to` :1092; zona endpoints inline por account_id :~2963-3300.
- `clabe_fetch.py`: `_load_jwt_for_account(db, id)` :37 (REUSAR PASO0), `_get_admin_proxy_url()` :65, `fetch_clabes_from_betmexico(jwt, proxy)` :75 (patrón `async with httpx.AsyncClient(timeout=30.0, verify=False, proxy=proxy_url)`).
- `proxy_pool.py`: `build_admin_proxy_url() -> Optional[str]` :169, `call_with_proxy_failover` :227 (async; **NO usar en begin_withdrawal**).
- `static/pantalla.js`: `.pat-actions` :331, `.d-deposit-btn` :333, `.pat-clabes` :448, `_renderDetailView` :610 (`.pat-wrap` :617), handler clabe-refresh fetch+spinner+toast :751, `u.role === 'superadmin'` :354, `_mvResultCls` :464, `.dep-spinner` (depos.css), `window.toast(msg,type)`.
- `static/pantalla.css`: `--pat-gold` :30, `--pat-gold-soft` :31, `--pat-edge` :32, `.pat-act` :408, `.pat-act-dep` :422, `.pat-input` :758, `.pat-form` :757, `.pat-form-row` :768, `.pat-form-err` :779.
- `static/app.js`: `connectSSE()` :1855, `_onAccountRefreshed` :1835, `state.user` :447, `isSA` patrón :453.
- `conftest.py`: `seed_db` :7, `make_client(role=)` :102.

---

## Task 0: Copiar plan a canonical + worktree

**Files:** copiar este plan a `docs/superpowers/plans/2026-07-24-boton-retiro-automatico.md`.

- [x] **Step 1:** `git checkout -b feat/boton-retiro-automatico` desde `feat/auditoria-tdah-2026-07-20`.
- [x] **Step 2:** Write plan a `docs/superpowers/plans/2026-07-24-boton-retiro-automatico.md`.
- [ ] **Step 3:** Commit `docs(plan): plan botón retiro automático`.

---

## Task A: Migración tabla `account_withdrawals` [modelo: Haiku]

**Files:** Modify `app.py` (`_migrate()` después de bloque `account_deposit_clabes` :~251).

**Interfaces:**
- Produces: tabla `account_withdrawals` con `UNIQUE(transaction_id)`.

**Schema (modelada sobre `account_deposit_clabes` app.py:238):**
```python
CREATE TABLE IF NOT EXISTS account_withdrawals (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  account_id INTEGER NOT NULL,
  account_email TEXT,
  transaction_id TEXT UNIQUE NOT NULL,
  reference TEXT,
  amount REAL NOT NULL,
  account_digits TEXT,
  institution_name TEXT,
  status_api INTEGER,
  status_description TEXT,
  gateway INTEGER,
  last_modified_utc TEXT,
  disparado_por INTEGER,
  created_at TEXT NOT NULL
)
```

- [ ] **Step 1 (RED):** añadir a `tests/test_withdrawals_migrate.py`:
```python
import sqlite3, pytest
from app import _migrate, db

def test_migrate_creates_account_withdrawals():
    _migrate()
    con = db()
    cols = [r[1] for r in con.execute("PRAGMA table_info(account_withdrawals)")]
    for c in ["account_id","transaction_id","amount","status_api","gateway","last_modified_utc","disparado_por"]:
        assert c in cols, f"falta col {c}"
    # UNIQUE(transaction_id)
    con.execute("INSERT INTO account_withdrawals(account_id,transaction_id,amount,created_at) VALUES(1,'t1',100,'now')")
    with pytest.raises(sqlite3.IntegrityError):
        con.execute("INSERT INTO account_withdrawals(account_id,transaction_id,amount,created_at) VALUES(1,'t1',100,'now')")
```
- [ ] **Step 2 (verify fail):** `pytest tests/test_withdrawals_migrate.py -v` → FAIL `no such table: account_withdrawals`.
- [ ] **Step 3 (GREEN):** pegar bloque `CREATE TABLE IF NOT EXISTS` en `_migrate()` tras `account_deposit_clabes` (~:252), dentro de su `try/except sqlite3.OperationalError: pass`.
- [ ] **Step 4 (verify pass):** `pytest tests/test_withdrawals_migrate.py -v` → PASS.
- [ ] **Step 5:** commit `feat(db): tabla account_withdrawals (bitácora idempotente de retiros)`.

---

## Task B: Módulo `withdrawals.py` — TDD por función [b1-b5 Sonnet, b3 Opus, b6 Opus]

**Files:** Create `withdrawals.py` (raíz), Modify `conftest.py` (fixtures).

**Interfaces:**
- Consumes: `clabe_fetch._load_jwt_for_account(db, id)`, `proxy_pool.build_admin_proxy_url()`.
- Produces:
  - `async def get_bank_accounts(jwt, proxy_url, transport=None) -> list[dict]` — PASO1. Filtra `accountStatus==2`. Lanza `NoApprovedWithdrawalAccount` si vacío, `MultipleApprovedAccounts` si >1.
  - `async def get_real_balance(jwt, proxy_url, transport=None) -> dict` — PASO2 `{Real,Bonos}`.
  - `async def begin_withdrawal(jwt, proxy_url, account_id_bmx, amount: float, email, transport=None) -> dict` — PASO3, body MÍNIMO, **single-shot** (no retry). Lanza `ConcurrentWithdrawalPending` si 400 con `THE_TRANSACTION_DOES_NOT_COMPLY`.
  - `async def get_pending_withdrawal(jwt, proxy_url, transport=None) -> dict|None` — PASO4. `None` si `id` es null.
  - `async def get_bank_transaction(jwt, proxy_url, tx_id, transport=None) -> dict` — PASO5. Devuelve dict normalizado con flags `gateway_spei:bool`, `gateway_mismatch:bool`, `digits_mismatch:bool`, `expected_digits`, `actual_digits`.
  - `async def execute_withdrawal(db_path, account_id, amount: float) -> dict` — orquesta PASO0-3. Devuelve `{transactionId, reference, accountId, accountDigits, institutionName, amount, warnings:[]}`.
  - Excepciones: `WithdrawalError` (base), `NoApprovedWithdrawalAccount`, `MultipleApprovedAccounts`, `ConcurrentWithdrawalPending`, `InsufficientBalance`, `JwtExpired`.

**Fixture `conftest.py`:**
```python
@pytest.fixture
def mock_bmx_transport():
    """Factory: retorna (httpx.MockTransport, received_requests_dict).
    Uso: transport, reqs = mock_bmx_transport(handler); await fn(..., transport=transport)."""
    def make(handler):
        reqs = {"calls": []}
        def wrap(request):
            reqs["calls"].append({"method": request.method, "url": str(request.url),
                                   "headers": dict(request.headers), "body": request.content})
            return handler(request)
        return httpx.MockTransport(wrap), reqs
    return make
```
Cada función de `withdrawals.py` acepta `transport=None`; si `None` usa `httpx.AsyncClient(...)` real, si recibe un `MockTransport` lo usa. Implementación: `client_kw = {"transport": transport} if transport else {"proxy": proxy_url, "verify": False}`; `async with httpx.AsyncClient(timeout=30.0, **client_kw) as c:`.

### B1 — `get_bank_accounts` (PASO1) [Sonnet] — 7 tests
- [ ] `test_get_bank_accounts_happy_one_approved` — handler 200 `{accounts:[{accountId:"a1",account:"1670XXXX1215",institutionName:"HEY BANCO",accountStatus:2,accountStatusDescription:"Approved"}]}` → len==1, `accountId=="a1"`.
- [ ] `test_get_bank_accounts_filters_non_approved` — 1 Approved(status2)+1 Pending(1)+1 Created(0) → solo 1.
- [ ] `test_get_bank_accounts_empty_aborts` — `{accounts:[]}` → raises `NoApprovedWithdrawalAccount`.
- [ ] `test_get_bank_accounts_multiple_approved_bug1` — 2 cuentas status==2 → raises `MultipleApprovedAccounts` con institutionName+dígitos en `str(e)`. NO adivina.
- [ ] `test_get_bank_accounts_non200_raises` — 401 → raises `RuntimeError` "BankAccounts HTTP 401".
- [ ] `test_get_bank_accounts_uses_proxy_and_canonical_headers` — asertar `reqs["calls"][0]["headers"]["authorization"]=="Bearer JWT"`, `origin`, `referer`, y que el proxy se pasó (en modo real; en mock solo verificar headers).
- [ ] `test_get_bank_accounts_timeout_raises` — handler lanza `httpx.ConnectTimeout` → raises `RuntimeError`.

### B2 — `get_real_balance` (PASO2) [Sonnet] — 3 tests
- [ ] `test_get_real_balance_happy` — `{Real:457.01,Bonos:0.0}` → dict igual.
- [ ] `test_get_real_balance_non200_raises` — 500 → `RuntimeError`.
- [ ] `test_get_real_balance_missing_real_key` — `{Bonos:10}` → `RuntimeError` "sin Real".

### B3 — `begin_withdrawal` (PASO3) [Opus] — 8 tests
- [ ] `test_begin_withdrawal_happy_minimal_body` — handler 200 `{transactionId:"273..."}` → retorna `{"transactionId":"273..."}`. Assert `json.loads(reqs["calls"][0]["body"]) == {"accountId":"a1","amount":100.0,"email":"x@y.com"}` (EXACTO, sin campos extra).
- [ ] `test_begin_withdrawal_amount_is_float_not_string` — assert `isinstance(body["amount"], float)`.
- [ ] `test_begin_withdrawal_400_concurrent_pending` — 400 body `{"message":"THE_TRANSACTION_DOES_NOT_COMPLY_WITH_THE_ESTABLISHED_CONFIGURATION"}` → raises `ConcurrentWithdrawalPending`.
- [ ] `test_begin_withdrawal_401_jwt_dead` — 401 → `RuntimeError` "JWT inválido/expirado".
- [ ] `test_begin_withdrawal_500_unexpected` — 500 → `RuntimeError`.
- [ ] `test_begin_withdrawal_no_transaction_id_in_200` — 200 `{}` → `RuntimeError`.
- [ ] `test_begin_withdrawal_sends_canonical_headers` — Origin/Referer/Authorization.
- [ ] `test_begin_withdrawal_does_not_retry_on_proxy_error` — handler lanza `httpx.ConnectError` → la fn se llama **1 sola vez** (`len(reqs["calls"])==1`), no 2. **Guardarrail single-shot.**

### B4 — `get_pending_withdrawal` (PASO4) [Sonnet] — 4 tests
- [ ] `test_get_pending_withdrawal_happy` — `{id:"273",reference:"3347",transactionStatus:2,gatewayType:2}` → dict.
- [ ] `test_get_pending_withdrawal_none_when_no_pending` — `{id:null,...}` → retorna `None` (no dict con nulls).
- [ ] `test_get_pending_withdrawal_status6_returns_dict` — `{id:"273",transactionStatus:6}` → dict (aún hasta que desaparezca).
- [ ] `test_get_pending_withdrawal_non200_raises` — 500 → `RuntimeError`.

### B5 — `get_bank_transaction` (PASO5) [Sonnet] — 5 tests
- [ ] `test_get_bank_transaction_happy` — `{id,transactionStatus:6,lastModifiedUtc:"2026-07-24T18:18:35",reference,transactionTypeDescription:"Retiro",amount,gateway:2,lastAccountDigits:"1215"}` → dict normalizado.
- [ ] `test_get_bank_transaction_gateway2_spei_ok` — gateway:2 → `gateway_spei==True`, `gateway_mismatch==False`.
- [ ] `test_get_bank_transaction_gateway1_card_alert_bug3` — gateway:1 → `gateway_mismatch==True`. **bug#3.**
- [ ] `test_get_bank_transaction_digits_mismatch_alert_bug1` — `lastAccountDigits:"0139"` vs esperado `"1215"` → `digits_mismatch==True`, `actual_digits=="0139"`, `expected_digits=="1215"`. **bug#1 post-retiro.**
- [ ] `test_get_bank_transaction_non200_raises` — 404 → `RuntimeError`.

### B6 — `execute_withdrawal` (orquestador PASO0-3) [Opus] — 1 test integración
- [ ] `test_execute_withdrawal_full_flow_mocked` — mockea `_load_jwt_for_account` (jwt vigente) + las 4 funcs con `mock_bmx_transport` secuencia: BankAccounts(1 Approved)→Balance(Real:200)→BeginWithdrawal(transactionId). Verifica devuelve `{transactionId, accountId, accountDigits, amount, warnings:[]}`. Verifica que `amount<=Real` o lanza `InsufficientBalance`. Verifica JWT expirado → `JwtExpired` sin llamar API.

- [ ] **B-run:** `pytest tests/test_withdrawals.py -v` → todos PASS. `pytest -x` (regresión) → solo pre-existentes (ver `reference_pre_existing_test_failures`).
- [ ] Commit: `feat(withdrawals): módulo retiro TDD con guardarrails bug#1/#3`.

---

## Task C: Endpoints en `app.py` [C1 Sonnet+Opus review, C2 Sonnet]

**Files:** Modify `app.py` (inline antes de `if __name__` :~3300). Imports al top: `from withdrawals import (execute_withdrawal, get_pending_withdrawal, get_bank_transaction, NoApprovedWithdrawalAccount, MultipleApprovedAccounts, ConcurrentWithdrawalPending, InsufficientBalance, JwtExpired)`.

**Interfaces:**
- Consumes: `withdrawals.*`, `app._broadcast`, `app._resolve_who`, `clabe_fetch._load_jwt_for_account`, `proxy_pool.build_admin_proxy_url`, `require_session`, `db`.
- Produces:
  - `POST /api/accounts/{account_id}/withdraw` body `{amount}` → `{transactionId, reference, accountId, accountDigits, institutionName, amount, warnings}`.
  - `GET /api/accounts/{account_id}/withdraw/status/{tx_id}` → `{status, phase, transactionStatus, description, lastModifiedUtc, accountDigits, gateway, alerts:{gatewayMismatch, digitsMismatch}}`.

### C1 — `POST /withdraw` [Sonnet + Opus review] — 12 tests
`test_withdrawals_endpoints.py` con `make_client(role="superadmin")`, monkeypatch `withdrawals.execute_withdrawal` y `app._broadcast`.

- [ ] `test_withdraw_403_for_non_sa` — role `user` → 403.
- [ ] `test_withdraw_404_unknown_account` — id 999999 → 404.
- [ ] `test_withdraw_409_jwt_expired` — jwt_expires_at < now → 409 `"JWT expirado"`, withdrawals NO llamado.
- [ ] `test_withdraw_409_no_jwt` — sin jwt_token → 409.
- [ ] `test_withdraw_409_no_approved_account` — `execute_withdrawal` lanza `NoApprovedWithdrawalAccount` → 409 `"requiere SPEI depósito primero"`.
- [ ] `test_withdraw_409_multiple_approved_bug1` — lanza `MultipleApprovedAccounts` → 409 con lista en mensaje.
- [ ] `test_withdraw_409_insufficient_balance` — lanza `InsufficientBalance` → 409 `"saldo insuficiente (Real=$X)"`.
- [ ] `test_withdraw_409_concurrent_pending` — lanza `ConcurrentWithdrawalPending` → 409 `"ya hay retiro pendiente"`.
- [ ] `test_withdraw_happy_persists_and_broadcasts` — execute_withdrawal mock devuelve `{transactionId:"t1",accountId:"a1",accountDigits:"1215",institutionName:"HEY BANCO",amount:100,...}` → 200; assert fila en `account_withdrawals` (transactionId=t1, amount=100, disparado_por=telegram_id del user); assert `_broadcast` llamado con `kind=="withdrawal"`, `target==email`, `_resolve_who` incluido.
- [ ] `test_withdraw_amount_validation` — amount<=0 / no numérico → 400; amount>Real → 409.
- [ ] `test_withdraw_broadcast_visible_to_sa_only` — `_event_visible_to({"kind":"withdrawal","who_id":X}, ctx_sa)` True; con ctx de otro operador False (salvo que who_id match).
- [ ] `test_withdraw_persist_idempotent_unique_transaction_id` — 2 INSERTs mismo tx_id → el endpoint no crea fila duplicada (UPSERT / INSERT OR IGNORE).

**Implementación endpoint (referencia, Opus la refina):**
```python
@app.post("/api/accounts/{account_id}/withdraw")
async def withdraw(account_id: int, payload: dict, user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    try:
        amount = float(payload.get("amount"))
    except (TypeError, ValueError):
        raise HTTPException(400, "amount inválido")
    if amount <= 0:
        raise HTTPException(400, "amount debe ser > 0")
    try:
        result = await execute_withdrawal(DB_PATH, account_id, amount)
    except JwtExpired:
        raise HTTPException(409, "JWT expirado, requiere refresh")
    except InsufficientBalance as e:
        raise HTTPException(409, str(e))
    except NoApprovedWithdrawalAccount:
        raise HTTPException(409, "Sin cuenta de retiro aprobada: requiere SPEI de depósito primero")
    except MultipleApprovedAccounts as e:
        raise HTTPException(409, str(e))
    except ConcurrentWithdrawalPending:
        raise HTTPException(409, "Ya hay un retiro pendiente en esta cuenta")
    # persistir + touch + broadcast (patrón app.py:2870)
    _persist_withdrawal(account_id, user["telegram_id"], result)
    _broadcast({"type":"activity","kind":"withdrawal","ts":_now_iso(),
                 "target": result.get("account_email"),"amount":amount,
                 "transactionId":result["transactionId"], **_resolve_who(user["telegram_id"])})
    return result
```

### C2 — `GET /withdraw/status/{tx_id}` [Sonnet] — 8 tests
- [ ] `test_status_403_non_sa` → 403.
- [ ] `test_status_404_unknown_tx` → 404.
- [ ] `test_status_happy_pending` — `get_pending_withdrawal` `{transactionStatus:2,...}` → 200 `{status:"pending",transactionStatus:2,...}`.
- [ ] `test_status_happy_successful_two_phase_bug2` — PASO4 status:6 + PASO5 `{transactionStatus:6,gateway:2,lastAccountDigits:"1215",lastModifiedUtc:"..."}` → 200 `{status:"successful",phase:"executed"}` (**NO "delivered"**), copy `"confirma en tu banco"`, `lastModifiedUtc` presente. **bug#2.**
- [ ] `test_status_gateway_mismatch_alert_bug3` — PASO5 gateway:1 → `alerts.gatewayMismatch==True`. **bug#3.**
- [ ] `test_status_digits_mismatch_alert_bug1` — lastAccountDigits != esperado → `alerts.digitsMismatch==True`. **bug#1.**
- [ ] `test_status_no_pending_returns_idle` — `get_pending_withdrawal==None`; si último tx Successful → `{status:"completed"}`, si Failed → `{status:"failed"}`, si no hay tx → `{status:"idle"}`.
- [ ] `test_status_updates_db_row` — tras status, fila `account_withdrawals` tiene `status_api`+`last_modified_utc` actualizados (UPSERT).

- [ ] **C-run:** `pytest tests/test_withdrawals_endpoints.py -v` → PASS. `pytest -x` sin nueva regresión.
- [ ] Commit: `feat(api): endpoints withdraw + status con guardarrails bug#1/#2/#3`.

---

## Task D: SSE event visibility [Sonnet] — 1 test
- [ ] `test_withdrawal_event_sa_only` (ya en C1, test_withdraw_broadcast_visible_to_sa_only) — confirma `_event_visible_to` trata `kind:"withdrawal"` como `account_touch`-like (SA ve ajenos, operador solo los propios).
- [ ] Commit junto con C.

---

## Task E: Persistencia — verificación aislada [Haiku]
- [ ] `test_persist_withdrawal_upsert` — `_persist_withdrawal` INSERT nueva fila, luego UPDATE status_api no duplica. Cubierto por C1/C2; test explícito si falta cobertura.
- [ ] Commit con C si no requiere código nuevo.

---

## Task F: Frontend — botón + input + estado [Sonnet]

**Files:** Modify `static/pantalla.js` (+ `.pat-actions` :331, `_renderDetailView` :610), `static/pantalla.css`.

**Interfaces:**
- Consumes: `GET /api/accounts/{id}/details` (añadir `last_withdrawal` al payload de `account_details` app.py:2581), `POST /api/accounts/{id}/withdraw`, `GET .../withdraw/status/{tx_id}`, `window.state.user.role`, `window.toast`, `.dep-spinner`.
- Produce: `renderPantallaWithdraw(d)` (botón SA-only + input monto + Disparar), `renderPantallaWithdrawStatus(d)` (2 fases + alertas), handler `.d-withdraw-fire`, `_startWithdrawPoll(accId, txId)`.

- [ ] **F1 `renderPantallaWithdraw(d)`:** bloque bajo `.pat-clabes` (patrón `renderPantallaClabes` :422). Solo si `isSA = window.state?.user?.role === 'superadmin'`. Markup reusando `.pat-form`/`.pat-input`/`.pat-btn`:
```html
<div class="pat-wd" data-acc="${d.id}">
  <div class="pat-sv-h">Retiro (SA)</div>
  <div class="pat-form">
    <input class="pat-input pat-wd-amount" type="number" min="100" step="0.01" placeholder="monto (min $100)">
    <button class="pat-btn pat-btn-save d-withdraw-fire">Disparar retiro</button>
  </div>
  <div class="pat-wd-status"></div>
</div>
```
Si `!isSA` → no renderizar (ley `feedback_deshabilitar_invisible_no_redirect`).
- [ ] **F2 handler disparo:** listener en `.d-withdraw-fire` (patrón clabe-refresh :751: fetch + `.dep-spinner` + `window.toast`). POST `/api/accounts/${accId}/withdraw` `{amount}`. On 200 → `renderPantallaWithdrawStatus` con el resultado + inicia `_startWithdrawPoll`. On 409 concurrente → bloquear botón (disabled, `.pat-wd` attr `data-pending`). On otro 4xx → toast error.
- [ ] **F3 `renderPantallaWithdrawStatus(d)`:** muestra `reference`, `amount`, fase actual. **bug#2 copy:** `transactionStatus==6` → `"✓ BetMexico procesó el retiro (ref {ref}). Confirma en tu banco."` (NO "llegó"). Pending → `"⏳ Retiro en proceso (ref {ref})..."` con `.dep-spinner`. **bug#3 alert:** `alerts.gatewayMismatch` → borde rojo `"⚠️ BetMexico mandó el retiro a TARJETA, no a SPEI."`. **bug#1 alert:** `alerts.digitsMismatch` → `"⚠️ El retiro fue a {actualDigits}, no a la cuenta esperada {expectedDigits}."`.
- [ ] **F4 CSS:** `.pat-wd` (contenedor), `.pat-wd-status` (zona estado), variantes `.pat-wd.pending`/`.pat-wd.alert` (borde ámbar/rojo). Reusar `--pat-gold`/`--pat-edge`/`.pat-mv.fail` para alertas.

- [ ] **F-run:** verificar en navegador (no automatizable a ojo — `feedback_ui_ancla_medida_no_pixel_inventado`). Medir con `getBoundingClientRect` que el bloque encaja en `.pat-col-ident` sin overflow (comparar con `.pat-clabes`).
- [ ] Commit: `feat(ui): botón de retiro SA + estado 2-fases en La Pantalla`.

> **Frontend assets rule:** añadir `pantalla.js`/`pantalla.css` ya están en `FRONTEND_ASSETS` (app.py) para auto-reload — confirmar, si no, sumar (ERRORS.md entry 2026-07-06).

---

## Task G: Polling + SSE frontend [Sonnet]

**Files:** Modify `static/pantalla.js` (`_startWithdrawPoll`), `static/app.js` (`connectSSE` :1855, `_onAccountRefreshed` :1835).

- [ ] **G1 `_startWithdrawPoll(accId, txId)`:** `setInterval` **60000ms**. Fetch `GET /api/accounts/${accId}/withdraw/status/${txId}`. Render estado (F3). Para el interval al `status=="completed"|"failed"` o al cerrar La Pantalla. Guardarrail: **60s nunca menos**.
- [ ] **G2 SSE handler:** en `connectSSE`, agregar listener evento `withdrawal` → si la cuenta abierta matchea → re-fetch `/details` (`_onAccountRefreshed` patrón :1835). Así multiples operadores ven el retiro en vivo.
- [ ] **G3 verif visual:** smoke manual en navegador — disparar retiro de prueba, ver polling actualizar.
- [ ] Commit: `feat(ui): polling 60s + SSE para estado de retiro en vivo`.

---

## Task H: Smoke HTTP tras deploy [Haiku]

**Files:** none (verificación).

- [ ] **H1 deploy KVM4:** `pscp` + restart `betmexico-web` + `docker exec ... python3 -c import withdrawals` (disco). Confirmar `StartedAt > mtime` (ley `feedback_verificar_deploy_proceso_vivo`).
- [ ] **H2 health:** `curl https://botmexico.com.mx/api/health` → 200.
- [ ] **H3 smoke endpoint (sin mover dinero):** `POST /api/accounts/{msaidrzz_id}/withdraw` con amount que falle en PASO2 (ej. amount=99999 → 409 `InsufficientBalance`). Verifica que el flujo llega a PASO2 sin disparar retiro. **Esto prueba el cableo end-to-end sin tocar dinero.**
- [ ] **H4 smoke status:** `GET /withdraw/status/{tx_inexistente}` → 404.
- [ ] Commit: `chore(smoke): verificación HTTP post-deploy retiros`.

---

## Task I: Retiro REAL $100 por Robert [Humano — NO automatizar]

**Cuenta:** `msaidrzz@gmail.com` (~$102, ya probada). **1 sola oportunidad real** (suficiente).

- [ ] Robert abre La Pantalla de msaidrzz → botón "Retirar" → monto `100` → "Disparar".
- [ ] Botón bloquea (concurrente), polling 60s arranca.
- [ ] Verificar: `transactionStatus` avanza a 6 (executed), copy dice "confirma en tu banco" (no "llegó"). **bug#2.**
- [ ] Verificar PASO5: `gateway==2` (SPEI, no tarjeta). **bug#3.** `lastAccountDigits` coincide con `accountId` del PASO1. **bug#1.**
- [ ] Verificar fila en `account_withdrawals` (BD) con `status_api`, `gateway`, `last_modified_utc`, `disparado_por`.
- [ ] Robert confirms aterrizaje en banco (fase 2 manual).
- [ ] Si falla → `superpowers:systematic-debugging` (root cause, no parche).

---

## 🔧 ORQUESTACIÓN (obligatoria)

### Modelos por subagente (criterio de consumo + riesgo)
| Task | Modelo | Criterio |
|---|---|---|
| A (migración) | Haiku 4.5 | copy-paste patrón app.py:238 |
| B1,B2,B4,B5 | Sonnet 5 | replica clabe_fetch, lógica directa |
| **B3 (begin_withdrawal)** | **Opus 4.8** | **dinero real, body MÍNIMO crítico, no-retry, excepciones** |
| **B6 (execute_withdrawal)** | **Opus 4.8** | orquestación dinero real |
| C1 (POST /withdraw) | Sonnet 5 + **Opus review** | gate+persist+broadcast, dinero |
| C2 (GET /status) | Sonnet 5 | 2-fases bug#2 |
| D (SSE) | Sonnet 5 | patrón _event_visible_to |
| E (persist) | Haiku 4.5 | SQL directo |
| F1-F4 (UI) | Sonnet 5 | patrones pantalla.js, premium medido |
| G1-G2 (polling/SSE) | Sonnet 5 | setInterval 60s + EventSource |
| G3 (verif visual) | Haiku 4.5 | smoke |
| H (smoke HTTP) | Haiku 4.5 | mecánico post-deploy |
| I (retiro $100) | **Robert (humano)** | NO automatizar — dinero real |

### Goals medibles
- A: tabla `account_withdrawals` creada + UNIQUE(transaction_id) probado.
- B: `pytest tests/test_withdrawals.py` verde (28 tests: 7+3+8+4+5+1). Cero regresión en suite existente (salvo pre-existentes).
- C: `pytest tests/test_withdrawals_endpoints.py` verde (20 tests). Endpoint responde 200/4xx según caso.
- F/G: bloque retiro renderiza solo-SA, encaja en `.pat-col-ident` sin overflow (medido), polling 60s funciona.
- H: smoke HTTP 200/4xx sin mover dinero (amount=99999 → 409 sin disparar).
- I: **1 retiro real $100 end-to-end** con 3 guardarrails verificados (gateway==2, digits coinciden, 2-fases no "entregado").

### Loops (con condición de salida)
- **TDD RED→GREEN** por cada función: max **3 ciclos**. Salida = test verde + `pytest -x` sin regresión.
- **UI encaje (F):** max **2 iteraciones** CSS/JS por sub-task. Salida = `getBoundingClientRect` del bloque ≤ alto de `.pat-col-ident` sin overflow.
- **Smoke H:** **1 intento** por sub-check. Salida = 200/4xx esperado.

### Vigilancia anti-cuelgue
- **2º fallo consecutivo** de un test → `superpowers:systematic-debugging` (root cause, NO re-parchear). Dinero real: cero parches sobre parches.
- **3ª iteración sin encajar** (UI o medición) → PARAR, reportar número real vs esperado. No iterar en silencio.
- **Síntoma cambia entre 2 intentos** = mal entendimiento del dominio, no flakiness → systematic-debugging.
- **Regresión en tests ajenos** (clabes/touches/grading) → STOP, el cambio no está aislado.
- **Smoke HTTP (H3) 2do intento:** si el 1er POST dio 5xx/timeout, diagnosticar JWT/proxy/rol ANTES del 2do — un 2do POST podría duplicar retiro si el 1ro disparó pero la respuesta se perdió.
- **Tests async colgados >5s** = bug en el mock handler (MockTransport es síncrono), no en prod.

---

## Verification (end-to-end)

1. `pytest tests/test_withdrawals.py tests/test_withdrawals_endpoints.py -v` → todos verdes.
2. `pytest -x` suite completa → solo pre-existentes (16 fallos conocidos `reference_pre_existing_test_failures`).
3. Deploy KVM4 + `python3 -c "import withdrawals"` + `StartedAt > mtime` + `GET /api/health` 200.
4. Smoke H3 (amount=99999 → 409 sin dinero) — cableo probado.
5. **Retiro real $100 (Task I)**: 3 guardarrails verificados en BD + UI. Fila `account_withdrawals` completa.
6. `md5` servido == repo para `pantalla.js`/`pantalla.css` (ley `feedback_verify_http_response_after_deploy`).

## Self-review (fresco contra spec)

- **Spec §1-2 (objetivo, alcance):** botón SA-only + endpoint + monitoreo + persistencia + bitácora → Tasks A,B,C,F,G. ✅
- **Spec §3 (5 pasos):** cada PASO = 1 función B + test. ✅
- **Spec §4 (endpoints):** POST/withdraw + GET/status → Task C. ✅
- **Spec §5 bug#1 (no cachear accountId):** B1 multiple_approved + B5 digits_mismatch + C1 409. ✅
- **Spec §5 bug#2 (status:6 ≠ entregado, 2 fases):** C2 phase:"executed" + F3 copy. ✅
- **Spec §5 bug#3 (gateway tarjeta):** B5 gateway_mismatch + C2 alert + F3. ✅
- **Spec §5 concurrencia (2do retiro 400):** B3 ConcurrentWithdrawalPending + C1 409 + F2 bloquea. ✅
- **Spec §6 (UI):** botón + input + estado en vivo → Task F. ✅
- **Spec §7 (persistencia):** tabla → Task A; fila por retiro → C1. ✅
- **Spec §8 no-go:** no cachear (B1 fresh), no "entregado" (C2), no JWT muerto (B6), no proxyless (Constraints), no tocar congelados (Constraints), no monorepo (Constraints). ✅
- **Spec §9 verificación:** smoke $1→**corregido a $100** (BetMexico mínimo $100), 3 guardarrails, smoke HTTP, fila BD. ✅
- **Spec §10 secuencia:** backend→tabla→UI→polling→smoke→deploy = Tasks A→I. ✅
- **Placeholder scan:** ninguno; cada step tiene código o test concreto.
- **Consistencia tipos:** `execute_withdrawal` firma igual en B6 (produce) y C1 (consume). Excepciones importadas en C0.
