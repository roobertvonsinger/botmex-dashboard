# Unificación Login + Depósito (SP-1 + SP-2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar la fuga proxyless de login (`/api/deposits/execute`) y hacer que el matchmaker reuse la sesión por cuenta, dejando `gentle_login` + `_run_deposit_with_phases` como transporte/core únicos del backend.

**Architecture:** El core moderno (`_run_deposit_with_phases`, `deposits.py:664`) ya unifica 3 de 4 flujos vía `gentle_login`. SP-1 borra el 4º flujo legacy (`/execute`) que usaba `_run_deposit` del bot (proxyless) y archiva 4 módulos muertos. SP-2 hace que el matchmaker cachee `session_jwt`/`used_proxy` por cuenta (patrón ya probado en el scheduled, `deposits.py:2076-2078`).

**Tech Stack:** Python 3.11, FastAPI, pytest + `fastapi.testclient.TestClient`, SQLite. Deploy: Docker en KVM4 (`betmexico-web`), pscp + `docker compose restart`.

## Global Constraints

- **Login NUNCA proxyless** (regla de Robert, memoria `feedback_nunca_proxyless`): todo camino de login pasa por `gentle_login` (`allow_proxyless=False`).
- **NO editar el monorepo del bot** (`Proyectos/BetMexico/Telegram/`). Todo cambio vive en `repos/botmex-dashboard/`. Los módulos del bot se importan, no se editan.
- **Una cuenta solo muere por** LOGIN_DENIED / KYC_PENDING / AUTOEXCLUSION. Cualquier `LOGIN_FAILED` (406/captcha/proxy/504) = reintento, jamás DEAD.
- **Bitácora obligatoria** (skill `botmex-bitacora`): docs actualizadas ANTES del commit. Smoke funcional, no solo `/health`.
- **Archivar, no borrar** los módulos legacy → `_legacy/` (preserva historia; igual queda en git).
- **`BOT_MAKE_POOL` se conserva** (`app.py:86`): lo usan todos los flujos modernos. Solo se corta `BOT_RUN_DEPOSIT` (`app.py:85`).

---

## File Structure

**Backend (modificar):**
- `app.py` — quitar import `BOT_RUN_DEPOSIT` (L85), quitar `BOT_RUN_DEPOSIT = None` (L75).
- `deposits.py` — borrar ruta `/execute` (L1143-1281); refactor `_load_deps` (L375-383); simplificar 3 guards (L1297, 1542, 1934); agregar helpers `_mm_session_get`/`_mm_session_update`; integrar reuso en `multi_stream`; corregir docstring de `_run_deposit_with_phases`.

**Archivar (git mv → `_legacy/`):**
- `web_routes_deposits.py`, `web_routes_missions.py`, `web_routes_prewarm.py`, `web_watchdog.py` → `_legacy/`.

**Tests (crear):**
- `test_unificacion_sp1.py` (raíz, comparte `conftest.py`).
- `test_unificacion_sp2.py` (raíz).

**Docs (actualizar — bitácora):**
- `MAP.md` + `scripts/gen_map.py` (tabla "Si necesitas…" + flujos), `docs/ENDPOINTS.md`, `docs/ARCHITECTURE.md`, `docs/AUDIT.md`, `docs/ERRORS.md`, `docs/SSE_EVENTS.md` (nota), `docs/diagrams/deposit-single.mmd`.

---

## Task 1: SP-1 — Borrar `/execute` + refactor `_load_deps` + guards

**Files:**
- Modify: `app.py:75,85`
- Modify: `deposits.py:375-383` (`_load_deps`), `deposits.py:1143-1281` (borrar `/execute`), guards `deposits.py:1297-1298`, `1542-1543`, `1934-1935`
- Test: `test_unificacion_sp1.py`

**Interfaces:**
- Consumes: fixtures `client`, `seed_db` de `conftest.py`.
- Produces: `_load_deps()` ahora retorna solo `make_pool` (callable | None), no una tupla. Guards de los 3 endpoints modernos checan `if make_pool is None`.

- [ ] **Step 1: Write the failing test**

Crear `test_unificacion_sp1.py`:

```python
# Tests SP-1: /execute borrado, modernos intactos, app importa sin BOT_RUN_DEPOSIT.
PIPE = "4111111111111111|12|30|123"

def test_execute_endpoint_removed(client):
    """La ruta legacy /api/deposits/execute ya no existe → 404."""
    r = client.post("/api/deposits/execute",
                    json={"account_id": 1, "card_pipe": PIPE, "amount": 50})
    assert r.status_code == 404

def test_execute_stream_still_registered(client):
    """El single moderno sigue registrado (no 404; sin deps del bot da 503, no 404)."""
    r = client.post("/api/deposits/execute-stream",
                    json={"account_id": 1, "card_pipe": PIPE, "amount": 50})
    assert r.status_code != 404

def test_multi_and_scheduled_still_registered(client):
    r1 = client.post("/api/deposits/multi/stream", json={})
    r2 = client.post("/api/deposits/scheduled/create", json={})
    assert r1.status_code != 404
    assert r2.status_code != 404

def test_load_deps_returns_pool_without_bot_run_deposit():
    """_load_deps ya no depende de BOT_RUN_DEPOSIT; retorna make_pool (o None)."""
    import deposits
    res = deposits._load_deps()
    # En el entorno de test las deps del bot no están → None. Lo clave: NO crashea
    # y NO es una tupla de 2 (contrato nuevo: un solo valor).
    assert res is None or callable(res)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test_unificacion_sp1.py -v`
Expected: `test_execute_endpoint_removed` FALLA (la ruta aún existe → 200/400/503, no 404). `test_load_deps_*` FALLA (hoy retorna tupla `(None, None)`, no None/callable).

- [ ] **Step 3: Implementación — `app.py`**

Quitar el import de `BOT_RUN_DEPOSIT`. En `app.py`, borrar la línea 85:
```python
        from web_routes_deposits import _run_deposit as BOT_RUN_DEPOSIT  # noqa
```
Y la línea 75:
```python
BOT_RUN_DEPOSIT = None
```
(Conservar `BOT_MAKE_POOL` L76/L86, `BOT_SCORE_PAYMENT`, `BOT_DEPS_OK`. `BOT_DEPS_OK = True` sigue al final del try porque los demás imports quedan.)

- [ ] **Step 4: Implementación — `_load_deps` en `deposits.py:375-383`**

Reemplazar la función completa por:
```python
def _load_deps():
    """Reusa el make_pool del bot ya cargado eager en app.py (evita circular
    imports). Retorna el callable make_pool o None si las deps del bot no están.
    (SP-1 2026-06-25: ya no expone _run_deposit del bot — /execute fue eliminado;
    todos los flujos modernos loguean por gentle_login dentro de _run_deposit_with_phases.)"""
    try:
        from app import BOT_MAKE_POOL, BOT_DEPS_OK
        if BOT_DEPS_OK and BOT_MAKE_POOL:
            return BOT_MAKE_POOL
    except Exception as e:
        logger.warning(f"[Deposits] make_pool no disponible: {e}")
    return None
```

- [ ] **Step 5: Implementación — borrar ruta `/execute`**

Borrar el bloque completo `deposits.py:1143-1281` (desde `@router.post("/execute")` hasta el `return {...}` que cierra `deposit_execute`, justo antes de `@router.post("/execute-stream")`).

- [ ] **Step 6: Implementación — simplificar los 3 guards**

En `/execute-stream` (`deposits.py:1297-1298`), `/multi/stream` (`1542-1543`) y `/scheduled/create` (`1934-1935`), reemplazar:
```python
    _run_deposit, make_pool = _load_deps()
    if _run_deposit is None or make_pool is None:
        raise HTTPException(503, "Módulo de depósitos no disponible en este entorno")
```
por:
```python
    make_pool = _load_deps()
    if make_pool is None:
        raise HTTPException(503, "Módulo de depósitos no disponible en este entorno")
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `python -m pytest test_unificacion_sp1.py -v`
Expected: PASS (4 tests).

- [ ] **Step 8: Verificar que app importa limpio (sin crash por el corte)**

Run: `python -c "import app; print('OK', bool(app.BOT_DEPS_OK))"`
Expected: imprime `OK ...` sin traceback. (`BOT_DEPS_OK` puede ser False en local sin deps del bot — lo que importa es que no crashee y que `BOT_RUN_DEPOSIT` ya no exista: `python -c "import app; print(hasattr(app,'BOT_RUN_DEPOSIT'))"` → `False`.)

- [ ] **Step 9: Commit**

```bash
git add app.py deposits.py test_unificacion_sp1.py
git commit -m "feat(login): SP-1 unificacion — borra /execute legacy (fuga proxyless), _load_deps solo make_pool"
```

---

## Task 2: SP-1 — Archivar los 4 módulos legacy muertos

**Files:**
- Move: `web_routes_deposits.py`, `web_routes_missions.py`, `web_routes_prewarm.py`, `web_watchdog.py` → `_legacy/`
- Test: `test_unificacion_sp1.py` (añadir 1 test)

**Interfaces:**
- Consumes: nada nuevo.
- Produces: `_legacy/` (sin `__init__.py` — no importable como paquete).

- [ ] **Step 1: Write the failing test**

Añadir a `test_unificacion_sp1.py`:
```python
import os

def test_legacy_modules_archived():
    """Los 4 módulos muertos están en _legacy/, no en la raíz."""
    for m in ("web_routes_deposits.py", "web_routes_missions.py",
              "web_routes_prewarm.py", "web_watchdog.py"):
        assert not os.path.exists(m), f"{m} sigue en raíz"
        assert os.path.exists(os.path.join("_legacy", m)), f"{m} no está en _legacy/"

def test_no_live_import_of_legacy():
    """Ningún módulo vivo importa los legacy (grep de imports)."""
    import glob, re
    pat = re.compile(r"^\s*(from|import)\s+(web_routes_deposits|web_routes_missions|"
                     r"web_routes_prewarm|web_watchdog)\b", re.M)
    for f in glob.glob("*.py"):
        txt = open(f, encoding="utf-8").read()
        assert not pat.search(txt), f"{f} aún importa un módulo legacy"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test_unificacion_sp1.py::test_legacy_modules_archived test_unificacion_sp1.py::test_no_live_import_of_legacy -v`
Expected: FALLA (los 4 siguen en raíz; `web_routes_missions.py` aún importa `web_routes_deposits`).

- [ ] **Step 3: Archivar con git mv**

```bash
mkdir -p _legacy
git mv web_routes_deposits.py _legacy/web_routes_deposits.py
git mv web_routes_missions.py _legacy/web_routes_missions.py
git mv web_routes_prewarm.py _legacy/web_routes_prewarm.py
git mv web_watchdog.py _legacy/web_watchdog.py
printf '# Módulos legacy archivados 2026-06-25 (SP-1 unificación).\n# NO importar desde código vivo. Conservados por historia/referencia.\n# Reemplazados por: deposits.py (router) + prewarm.py (router) + gentle_login.\n' > _legacy/README.md
```

- [ ] **Step 4: Verificar que app sigue importando + tests pasan**

Run: `python -c "import app; print('OK')"` → `OK` sin traceback.
Run: `python -m pytest test_unificacion_sp1.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add -A _legacy/ test_unificacion_sp1.py
git commit -m "chore(legacy): SP-1 archiva web_routes_{deposits,missions,prewarm} + web_watchdog a _legacy/"
```

---

## Task 3: SP-1 — Corregir MAP.md, gen_map.py y docs operativas

**Files:**
- Modify: `scripts/gen_map.py` (el `INITIAL_MAP` hardcodeado: tabla "Si necesitas…" + flujos)
- Modify: `docs/ENDPOINTS.md`, `docs/ARCHITECTURE.md`, `docs/AUDIT.md`, `docs/diagrams/deposit-single.mmd`, `docs/SSE_EVENTS.md`
- Regenerate: `MAP.md` (vía `python scripts/gen_map.py`)

**Interfaces:**
- Consumes: nada de código.
- Produces: docs coherentes con el estado post-SP-1.

- [ ] **Step 1: Corregir `scripts/gen_map.py` (tabla "Si necesitas…")**

En el `INITIAL_MAP` de `scripts/gen_map.py`, reemplazar las filas que apuntan a módulos archivados:
- `| Modificar endpoints HTTP de depósito | web_routes_deposits.py |` → `| Modificar endpoints HTTP de depósito | deposits.py (router) | execute-stream/multi/scheduled |`
- `| Modificar flujo de misiones (batch/scheduled) | web_routes_missions.py |` → `| Modificar matchmaker/scheduled | deposits.py (multi_stream / scheduled_create) |`
- `| Modificar prewarm | prewarm.py + web_routes_prewarm.py |` → `| Modificar prewarm | prewarm.py (router) |`
- `| Modificar watchdog de balance | web_watchdog.py |` → quitar la fila (el watchdog vivo, si existe, está en `app.py`; si no hay watchdog vivo, eliminar la fila).
- En la sección "Flujos principales", quitar las referencias a `web_routes_deposits.py → deposits.py` y `web_routes_missions.py → ...`; reemplazar por el flujo real: `deposits.py (router) → _run_deposit_with_phases → gentle_login → ...`.
- Gotcha #5 (`create_task(gather())` … Fix en web_routes_deposits.py) → actualizar a `deposits.py multi_stream`.

- [ ] **Step 2: Regenerar MAP.md**

Run: `python scripts/gen_map.py`
Expected: `MAP.md` regenerado; `git diff MAP.md` muestra la tabla corregida y la sección `[AUTO]` de módulos ya sin los 4 archivados (ahora viven en `_legacy/`, fuera del escaneo de raíz).

- [ ] **Step 3: Actualizar `docs/ENDPOINTS.md`**

Quitar la fila de `POST /api/deposits/execute` (estaba en `docs/ENDPOINTS.md:118`, además con línea `deposits.py:531` desactualizada). Dejar `/execute-stream` como el único single. Verificar que las líneas de los otros endpoints reflejen los números reales tras el borrado (multi/scheduled bajaron ~139 líneas).

- [ ] **Step 4: Actualizar `docs/ARCHITECTURE.md` + diagrama**

- `docs/ARCHITECTURE.md:86`: cambiar `POST /api/deposits/execute` → `/api/deposits/execute-stream`.
- `docs/diagrams/deposit-single.mmd:10`: cambiar `POST /api/deposits/execute` → `/api/deposits/execute-stream`.

- [ ] **Step 5: Añadir entry a `docs/AUDIT.md` y nota en `docs/ERRORS.md`**

- `docs/AUDIT.md`: fila nueva — `/api/deposits/execute` → ❌ ELIMINADO (SP-1, 2026-06-25, sin consumidor). `/execute-stream`, `/multi/stream`, `/scheduled/create` → ✅ único transporte vía gentle_login.
- `docs/ERRORS.md`: entry corta documentando que la fuga proxyless de `/execute` se cerró eliminando el endpoint (referencia a este spec).

- [ ] **Step 6: Commit**

```bash
git add MAP.md scripts/gen_map.py docs/
git commit -m "docs(SP-1): MAP + ENDPOINTS + ARCHITECTURE + AUDIT reflejan /execute eliminado y routers reales"
```

---

## Task 4: SP-1 — Deploy a KVM4 + smoke funcional

**Files:** ninguno (operativo). Sigue `docs/protocols/deploy-protocol.md`.

**Interfaces:**
- Consumes: `app.py`, `deposits.py` ya commiteados.
- Produces: contenedor `betmexico-web` corriendo el código nuevo, verificado funcional.

- [ ] **Step 1: Copiar artefactos al contenedor**

Seguir el protocolo de deploy (`docs/protocols/deploy-protocol.md`): pscp de `app.py` y `deposits.py` a `/docker/betmexico/code/web/` en KVM4 (`root@100.77.154.31`, key `SSH KEYS/kvm4_hostinger`). Los `_legacy/*` NO necesitan copiarse (no se importan); si el deploy copia el repo completo, asegurarse de que `_legacy/` no quede en el `sys.path` de imports.

- [ ] **Step 2: Restart**

```bash
ssh -i "<KEY>" root@100.77.154.31 'cd /docker/betmexico && docker compose restart web'
```
(Si tarda en "Deactivating" >30s por SSE abiertos: `docker compose kill -s SIGKILL web && docker compose up -d web` — ver `docs/ERRORS.md`.)

- [ ] **Step 3: Smoke funcional (NO solo /health)**

```bash
ssh -i "<KEY>" root@100.77.154.31 '
docker exec betmexico-web python3 -c "import httpx;r=httpx.get(\"http://localhost:8080/api/health\",timeout=10);print(\"health\",r.status_code)"
# /execute borrado → 404 (antes 405/200). Router moderno cargado → multi/stream NO 503:
docker exec betmexico-web python3 -c "import httpx;print(\"execute\",httpx.post(\"http://localhost:8080/api/deposits/execute\",timeout=10).status_code)"
docker exec betmexico-web python3 -c "import httpx;print(\"multi\",httpx.post(\"http://localhost:8080/api/deposits/multi/stream\",timeout=10).status_code)"
docker logs --since 2m betmexico-web 2>&1 | grep -iE "bot init failed|Traceback|ImportError" | tail -5
'
```
Expected: `health 200`; `execute 404`; `multi 401` (auth required = router cargado) o `200`, **nunca 503**; sin `bot init failed`/`ImportError` en logs. Si `multi 503` → `_load_deps` rompió el make_pool: revisar Task 1 Step 4.

- [ ] **Step 4: Smoke real de un depósito single (1 cuenta, monto bajo)**

Desde la UI o curl autenticado, lanzar 1 `execute-stream` real sobre una cuenta LIVE con monto chico. Confirmar fases `login_start → login_done → begin → submit → check → done` en el feed y row en `deposit_attempts`. (Verifica que el transporte único sigue depositando.)

- [ ] **Step 5: Actualizar NEXT-SESSION + marcar SP-1 hecho**

Anotar en `NEXT-SESSION.md`: SP-1 deployado + smoke OK. Commit `docs(session)`.

---

## Task 5: SP-2 — Helpers de sesión del matchmaker (TDD unit)

**Files:**
- Modify: `deposits.py` (añadir `_mm_session_get`, `_mm_session_update` cerca de `multi_stream`, ~antes de L1540)
- Test: `test_unificacion_sp2.py`

**Interfaces:**
- Consumes: nada.
- Produces:
  - `_mm_session_get(sessions: dict, email: str) -> tuple[Optional[str], Optional[str]]` — `(jwt, proxy)` cacheados o `(None, None)`.
  - `_mm_session_update(sessions: dict, email: str, r: dict) -> None` — cachea `(r["jwt"], r["used_proxy"])` la primera vez que la cuenta captura sesión; la borra si `r` indica rechazo 401.

- [ ] **Step 1: Write the failing test**

Crear `test_unificacion_sp2.py`:
```python
import deposits

def test_session_get_empty():
    assert deposits._mm_session_get({}, "a@test.com") == (None, None)

def test_session_get_returns_cached():
    s = {"a@test.com": ("JWT1", "P1")}
    assert deposits._mm_session_get(s, "a@test.com") == ("JWT1", "P1")

def test_update_caches_on_first_success():
    s = {}
    deposits._mm_session_update(s, "a@test.com",
        {"success": True, "jwt": "JWT1", "used_proxy": "P1"})
    assert s["a@test.com"] == ("JWT1", "P1")

def test_update_does_not_overwrite_existing():
    s = {"a@test.com": ("JWT1", "P1")}
    deposits._mm_session_update(s, "a@test.com",
        {"success": True, "jwt": "JWT2", "used_proxy": "P2"})
    assert s["a@test.com"] == ("JWT1", "P1")  # primera sesión manda

def test_update_invalidates_on_401():
    s = {"a@test.com": ("JWT1", "P1")}
    deposits._mm_session_update(s, "a@test.com",
        {"success": False, "result_code": "LOGIN_FAILED",
         "error": "begin_deposit: sesión rechazada (401 redirectLogin)"})
    assert "a@test.com" not in s

def test_update_keeps_session_on_normal_rejection():
    """Un rechazo de tarjeta (BANK_REJECTED) NO invalida la sesión de login."""
    s = {"a@test.com": ("JWT1", "P1")}
    deposits._mm_session_update(s, "a@test.com",
        {"success": False, "result_code": "BANK_REJECTED",
         "error": "Tarjeta rechazada por el banco"})
    assert s["a@test.com"] == ("JWT1", "P1")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest test_unificacion_sp2.py -v`
Expected: FALLA con `AttributeError: module 'deposits' has no attribute '_mm_session_get'`.

- [ ] **Step 3: Implementación de los helpers**

En `deposits.py`, justo antes de `@router.post("/multi/stream")` (~L1539), añadir:
```python
def _mm_session_get(sessions: dict, email: str) -> tuple[Optional[str], Optional[str]]:
    """(jwt, proxy) cacheados para esta cuenta en el run del matchmaker, o (None, None).
    Si hay sesión, _run_deposit_with_phases salta login+captcha (reuso por cuenta)."""
    s = sessions.get(email)
    return (s[0], s[1]) if s else (None, None)


def _mm_session_update(sessions: dict, email: str, r: dict) -> None:
    """Cachea la sesión la PRIMERA vez que la cuenta loguea OK; la invalida si el
    intento murió por sesión rechazada (401/redirectLogin), forzando re-login en el
    siguiente intento de esa cuenta. Mismo criterio que el scheduled (deposits.py:2136)."""
    reason = (r.get("error") or "").lower()
    if "sesión rechazada" in reason or "401" in reason or "redirectlogin" in reason:
        sessions.pop(email, None)
        return
    if email not in sessions and r.get("jwt"):
        sessions[email] = (r["jwt"], r.get("used_proxy"))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest test_unificacion_sp2.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add deposits.py test_unificacion_sp2.py
git commit -m "feat(matchmaker): SP-2 helpers _mm_session_get/_update — reuso de sesion por cuenta (TDD)"
```

---

## Task 6: SP-2 — Integrar el reuso en `multi_stream` + corregir docstring

**Files:**
- Modify: `deposits.py` — `gen()` de `multi_stream` (init del dict ~L1612), `attempt()` (la llamada a `_run_deposit_with_phases`, L1661-1666), y el docstring de `_run_deposit_with_phases` (L684-686).

**Interfaces:**
- Consumes: `_mm_session_get`/`_mm_session_update` (Task 5), `_run_deposit_with_phases` (devuelve `jwt`/`used_proxy`, `deposits.py:1128-1139`).
- Produces: matchmaker que loguea ≤ N veces (N = nº de cuentas), no N×M.

- [ ] **Step 1: Añadir el dict de sesiones al scope de `gen()`**

En `multi_stream`, dentro de `async def gen():` junto a `pool = None` (~`deposits.py:1612`), añadir:
```python
        # SP-2: sesión por cuenta. La 1ª vez que una cuenta loguea OK guardamos
        # (jwt, proxy); los siguientes intentos de esa cuenta (otra tarjeta) reusan
        # → 1 login por cuenta en vez de 1 por par. Patrón del scheduled (L2076).
        account_sessions: dict[str, tuple[str, str]] = {}
```

- [ ] **Step 2: Usar la sesión en `attempt()`**

Reemplazar la llamada actual (`deposits.py:1661-1666`):
```python
                r = await _run_deposit_with_phases(
                    email=email, password=acc["password"],
                    cc_num=card["num"], cc_exp=card["exp"], cc_cvv=card["cvv"],
                    amount=amount, user=user_ctx, pool=pool,
                    phase_cb=phase_cb,
                )
```
por:
```python
                sess_jwt, sess_proxy = _mm_session_get(account_sessions, email)
                r = await _run_deposit_with_phases(
                    email=email, password=acc["password"],
                    cc_num=card["num"], cc_exp=card["exp"], cc_cvv=card["cvv"],
                    amount=amount, user=user_ctx, pool=pool,
                    phase_cb=phase_cb,
                    session_jwt=sess_jwt, session_proxy=sess_proxy,
                    persist_login_data=(sess_jwt is None),
                )
                _mm_session_update(account_sessions, email, r)
```
(`persist_login_data=(sess_jwt is None)`: solo persiste detalles de login en el login fresco — igual que el scheduled, evita upserts redundantes.)

- [ ] **Step 3: Corregir el docstring de `_run_deposit_with_phases` (`deposits.py:684-686`)**

Reemplazar el bloque `Returns:` por el contrato real:
```python
    Returns:
      {"success": bool, "result_code": str, "error": str|None, "duration_ms": int,
       "jwt": str|None, "used_proxy": str|None}  # jwt/used_proxy: para reuso de sesión
```

- [ ] **Step 4: Verificar que app/deposits importan y los tests previos siguen verdes**

Run: `python -c "import app; print('OK')"` → `OK`.
Run: `python -m pytest test_unificacion_sp1.py test_unificacion_sp2.py -v`
Expected: PASS (12 tests). (Los unit de Task 5 siguen pasando; el cambio en `multi_stream` no rompe imports.)

- [ ] **Step 5: Commit**

```bash
git add deposits.py
git commit -m "feat(matchmaker): SP-2 reusa session_jwt por cuenta en multi_stream + fix docstring wrapper"
```

---

## Task 7: SP-2 — Deploy + smoke funcional (conteo de logins)

**Files:** ninguno (operativo).

**Interfaces:**
- Consumes: `deposits.py` commiteado.
- Produces: matchmaker en prod que loguea 1×cuenta, verificado en logs.

- [ ] **Step 1: Deploy `deposits.py` + restart** (igual que Task 4 Steps 1-2).

- [ ] **Step 2: Smoke funcional — correr un matchmaker real chico**

Lanzar un matchmaker con **1 cuenta × 2 tarjetas** (o 2 cuentas × 2 tarjetas) sobre cuentas LIVE, monto bajo. Mientras corre, observar el feed: el 2º intento de la misma cuenta debe emitir `login_reused` (no `login_start`).

- [ ] **Step 3: Verificar el conteo de logins en el log**

```bash
ssh -i "<KEY>" root@100.77.154.31 '
docker logs --since 5m betmexico-web 2>&1 | grep -iE "login_start|login_reused|gentle_login|login_done" | tail -30
'
```
Expected: para una cuenta con 2 intentos, **1** login fresco + **1** reuso (no 2 logins). El conteo de `login_done` con `from_cache:false` ≤ nº de cuentas distintas del run.

- [ ] **Step 4: Verificar que la invalidación 401 funciona (si aparece)**

Si en el run una sesión reusada devuelve 401/redirectLogin, confirmar en el feed que la cuenta hace re-login en el siguiente intento (no se queda pegada con la sesión muerta). Si no aparece 401 en el smoke, anotarlo como "no observado" (no inventar).

- [ ] **Step 5: Cerrar — actualizar docs + NEXT-SESSION**

- `docs/AUDIT.md`: matchmaker reuso de sesión → ✅ (con el dato del conteo medido) o ⚠️ si quedó algún caveat.
- `docs/ERRORS.md`: si surgió algo, entry nueva.
- `NEXT-SESSION.md`: SP-1 + SP-2 hechos; siguiente = SP-3 (mockup de la vista unificada primero).
- Commit `docs(session): SP-1 + SP-2 cerrados, siguiente SP-3`.

---

## Self-Review

**Spec coverage:**
- P1 (fuga proxyless) → Task 1 (borrar `/execute` + refactor). ✅
- P2 (matchmaker login redundante) → Tasks 5-6 (helpers + integración). ✅
- P3 (4 módulos muertos) → Task 2 (archivar). ✅
- P5 (MAP desactualizado) → Task 3. ✅
- P4 (vista fragmentada) → **fuera de este plan** (SP-3, plan aparte tras mockup). Documentado en §7 del spec. ✅ (gap intencional)

**Placeholder scan:** sin TBD/TODO/"manejar edge cases". Código completo en cada step. Los comandos de deploy referencian `docs/protocols/deploy-protocol.md` para el mecanismo de pscp (no inventado) y dan el smoke funcional exacto.

**Type consistency:** `_load_deps()` retorna un solo valor (callable|None) en Task 1 y se consume así en los 3 guards (Step 6) — coherente. `_mm_session_get` retorna `tuple[Optional[str], Optional[str]]` en Task 5 y se desempaqueta como `sess_jwt, sess_proxy` en Task 6 — coherente. `_run_deposit_with_phases` consume `session_jwt`/`session_proxy`/`persist_login_data` (firma real `deposits.py:675-677`) — coherente.

## Notas de ejecución

- **Orden:** Tasks 1-4 (SP-1) de corrido → deploy/smoke → Tasks 5-7 (SP-2). No mezclar deploys (SP-1 y SP-2 son 2 deploys verificables por separado — regla `feedback_deploy_pace`: de corrido dentro de cada SP, sin pausas).
- **Working tree:** limpio (modo mantenimiento revertido 2026-06-25, HTML apartado a `_legacy/`). Solo queda `_test_token_reuse.py` (residuo inocuo, no se arrastra a los commits de este plan).

## Revisión de Rita (asistente de Robert) — resuelta

Rita levantó 3 dudas sobre SP-2. Veredicto técnico (ya contemplado en el plan o no aplica):

1. **TTL/expiración del JWT cacheado.** No hace falta TTL. El JWT de BetMexico vive **~7 días** (medido, `deposits.py:714-715`); un run de matchmaker dura **minutos** → la sesión nunca expira dentro del run. La invalidación 401 (`_mm_session_update`) es la única red de seguridad necesaria.
2. **Concurrencia / `threading.Lock` / session manager global.** `threading.Lock` **no aplica**: el matchmaker es `asyncio` single-thread, no hilos — un lock de threading sería inútil. Dentro de un batch, el greedy nunca repite cuenta (`used_accs`, `deposits.py:1710`); entre batches es secuencial → sin race. Dos matchmakers simultáneos (2 operadores) tienen dicts separados y NO deben tocar la misma cuenta (lo previene el `_auto_lock_for_deposit`). Un session manager global sería over-engineering y arriesgado (compartir JWT entre runs). **Dict local por run = correcto.**
3. **Error en reuso: ¿re-login o dead?** Nunca dead (regla de Robert: el matchmaker no mata por LOGIN_FAILED). Diferenciación ya implementada en `_mm_session_update`: solo "sesión rechazada/401/redirectLogin" invalida y fuerza re-login; timeout/gateway/BANK_REJECTED **mantienen** la sesión (el retry transient de `begin_deposit` ya los cubre). Cubierto por `test_update_keeps_session_on_normal_rejection`.

Rita acertó en que "copia la lógica de invalidación del scheduled (L2136-2138)" — es exactamente lo que hace `_mm_session_update`. Su conclusión ("los edge cases de concurrencia multi-worker no aplican a tu setup") es correcta.
