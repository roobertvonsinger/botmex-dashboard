# Reorg UI dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reorganizar el layout del dashboard (strip de 3 cards, Online+buscador al sidebar, tabla compacta), agregar Actividad Live por rol, marcador privado, Recientes, gestor de Pool partido, y arreglar la persistencia del panel de depósitos cross-página — cumpliendo ley del pool y visibilidad por rol.

**Architecture:** Base = **filtrado de visibilidad server-side** (SSE + endpoints), no en front (un operador NO recibe actividad ajena ni en el payload). Se reusa scoping existente (`_visible_emails`, `/api/deposits` por `operator_id`). Frontend consume datos ya filtrados; la lógica pura (dedup, copy humano) se testea con `node`; el layout se mide objetivo con `getBoundingClientRect`.

**Tech Stack:** Backend FastAPI + SQLite (`app.py`), tests `pytest` (`conftest.py` → fixture `make_client(role=,telegram_id=,username=)`). Frontend vanilla JS/CSS (`static/app.js`, `style.css`, `depos.js`, `depos_window.js`), tests `node` (`static/*.test.js`). Deploy Docker KVM4.

## Global Constraints

- **Ley del pool:** un operador NUNCA recibe cuentas con `published_to_pool=0` (ya vigente — no romperlo). Solo el SA expone cuentas, manualmente.
- **Visibilidad (whitelisting):** SA (`role=="superadmin"`, telegram_id `1341812706`) ve TODO y es invisible a todos. admin y user ven SOLO lo suyo (sus acciones / sus cuentas). admin = igual que user para visibilidad cruzada.
- **Frictionless / TDAH:** sin pasos extra, sin ruido técnico. Errores humanizados (E-RED), sin proxy/IP/jerga.
- **Nunca `overflow:auto` en cards del strip** (compactar/ciclar, no scrollear). Scroll solo permitido en secciones de gestión (`#poolMain`, `#activityMain`).
- **Marcador = privado, puro recordatorio:** NO toca `locked_by`, `published_to_pool` ni visibilidad.
- **Medición objetiva, no a ojo:** layout verificado con `getBoundingClientRect`/`scrollWidth` contra `/static/index.html` real (`feedback_verificar_entry_real`), no harness aislado.
- **Robert telegram_id = `1341812706`. Operador de prueba = `555`.**
- **No enmascarar info sensible** (tarjetas pipe completo, combos `email:password`).
- **No tocar el motor de depósitos/login/proxies.** Esta reorg es UI + plumbing de datos.

---

# PARTE 1 — BACKEND (pytest-testable, base de todo)

### Task 1: Predicado de visibilidad de eventos (pura)

**Files:**
- Modify: `app.py` (agregar `_event_visible_to` cerca de `_resolve_who`, ~`app.py:838`)
- Test: `test_sse_visibility.py` (nuevo)

**Interfaces:**
- Produces: `_event_visible_to(event: dict, ctx: dict) -> bool`. `ctx = {"role": str, "telegram_id": int|None, "display": str}`.

- [ ] **Step 1: Write the failing test**

```python
# test_sse_visibility.py
import app

SA = {"role": "superadmin", "telegram_id": 1341812706, "display": "RobertVS"}
OP = {"role": "user", "telegram_id": 555, "display": "Lau"}

def test_sa_sees_everything():
    assert app._event_visible_to({"kind": "deposit", "who_id": 555}, SA) is True
    assert app._event_visible_to({"kind": "lock", "who": "Otro"}, SA) is True

def test_operator_sees_own_by_who_id():
    assert app._event_visible_to({"kind": "deposit", "who_id": 555}, OP) is True
    assert app._event_visible_to({"kind": "deposit", "who_id": 1341812706}, OP) is False

def test_operator_sees_own_by_display_fallback():
    assert app._event_visible_to({"kind": "lock", "who": "Lau"}, OP) is True
    assert app._event_visible_to({"kind": "lock", "who": "RobertVS"}, OP) is False

def test_operator_hidden_from_robert_actions():
    # Bug conocido: admin/op NO debe ver actividad del SA.
    assert app._event_visible_to({"kind": "deposit", "who_id": 1341812706}, OP) is False

def test_service_event_addressed_to_operator():
    assert app._event_visible_to({"type": "window_expired", "operator_id": 555}, OP) is True
    assert app._event_visible_to({"type": "window_expired", "operator_id": 1341812706}, OP) is False

def test_actorless_service_event_hidden_from_operator():
    # CapMonster bajo, proxy_down sin destinatario -> solo SA.
    assert app._event_visible_to({"type": "alert", "kind": "capmonster_low"}, OP) is False
    assert app._event_visible_to({"type": "alert", "kind": "capmonster_low"}, SA) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_sse_visibility.py -v`
Expected: FAIL — `AttributeError: module 'app' has no attribute '_event_visible_to'`

- [ ] **Step 3: Write minimal implementation** (insertar tras `_resolve_who`, ~`app.py:838`)

```python
def _event_visible_to(event: dict, ctx: dict) -> bool:
    """Whitelisting de visibilidad para SSE/feeds. SA ve todo; admin/user ven
    SOLO lo suyo. Las acciones del SA no aparecen para nadie más (fix bug
    'admin ve actividad de Robert')."""
    if ctx.get("role") == "superadmin":
        return True
    my = ctx.get("telegram_id")
    # 1) Eventos con actor (who_id telegram_id) -> solo los propios.
    who_id = event.get("who_id")
    if who_id is not None and my is not None:
        return str(who_id) == str(my)
    # 2) Fallback por display name resuelto.
    who = event.get("who")
    if who is not None:
        return who == ctx.get("display")
    # 3) Eventos de servicio dirigidos (window_*, release_*): solo al destinatario.
    for k in ("operator_id", "target_user"):
        v = event.get(k)
        if v is not None and my is not None and str(v) == str(my):
            return True
    # 4) Eventos sin actor ni destinatario (alertas globales) -> solo SA (ya retornó arriba).
    return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_sse_visibility.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add app.py test_sse_visibility.py
git commit -m "feat(sse): predicado de visibilidad por rol _event_visible_to (TDD)"
```

---

### Task 2: SSE con contexto de usuario + filtrado en `_broadcast`

**Files:**
- Modify: `app.py:245-268` (`_sse_queues`, `_broadcast`), `app.py:1869-1905` (`_sse_generator`, `/api/events`), `app.py:826-838` (`_resolve_who` + `who_id`)
- Test: `test_sse_visibility.py` (extender)

**Interfaces:**
- Consumes: `_event_visible_to` (Task 1).
- Produces: `_sse_queues: list[tuple[queue, dict]]`. `_sse_generator(ctx: dict)`. `_resolve_who(val) -> {"who","who_color","who_id"}`.

- [ ] **Step 1: Write the failing test** (append a `test_sse_visibility.py`)

```python
import queue as _q

def test_broadcast_only_enqueues_visible(monkeypatch):
    # Inyecta 2 colas con ctx distintos y verifica filtrado.
    sa_q, op_q = _q.SimpleQueue(), _q.SimpleQueue()
    app._sse_queues[:] = [(sa_q, SA), (op_q, OP)]
    try:
        app._broadcast({"type": "activity", "kind": "deposit", "who_id": 1341812706, "amount": 50})
        assert not sa_q.empty()      # SA recibe
        assert op_q.empty()          # operador NO recibe acción ajena (de Robert)
    finally:
        app._sse_queues.clear()

def test_resolve_who_carries_who_id():
    out = app._resolve_who(1341812706)
    assert out["who_id"] == 1341812706
    assert "who" in out and "who_color" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_sse_visibility.py -v`
Expected: FAIL — `_broadcast` encola a todas; `_resolve_who` no tiene `who_id`.

- [ ] **Step 3: Implement** — tres ediciones:

(3a) `_resolve_who` (`app.py:828-838`) → agregar `who_id`:
```python
def _resolve_who(val):
    """Para broadcasts SSE: {who, who_color, who_id}. who_id = telegram_id del
    actor (para filtrado server-side por rol)."""
    wid = None
    try:
        wid = int(val)
    except (TypeError, ValueError):
        u = _auth.USERS.get(str(val).lower()) if val is not None else None
        wid = u["telegram_id"] if u else None
    return {
        "who": _resolve_operator(val),
        "who_color": _operator_color(val),
        "who_id": wid,
    }
```

(3b) `_broadcast` (`app.py:249-268`) → filtrar por ctx:
```python
def _broadcast(event: dict) -> None:
    """Push event a los SSE clients VISIBLES para cada uno (whitelisting por rol)."""
    msg = f"data: {_json.dumps(event)}\n\n"
    with _sse_lock:
        targets = list(_sse_queues)            # snapshot de (q, ctx)
        n_clients = len(targets)
        q_ids = [id(q) for (q, _ctx) in targets]
    for q, ctx in targets:
        if _event_visible_to(event, ctx):
            q.put(msg)
    kind = event.get("kind") or event.get("type", "?")
    if kind in ("scheduled_started", "scheduled_phase", "scheduled",
                "scheduled_aborted", "scheduled_cancelled"):
        import logging as _lg
        _lg.getLogger("betmexico.dashboard.sse").info(
            f"[SSE broadcast] kind={kind} clients={n_clients} q_ids={q_ids} "
            f"sched_id={event.get('sched_id')} iter={event.get('iter')} "
            f"phase_name={event.get('name')}"
        )
```

(3c) `_sse_generator` + `/api/events` (`app.py:1869-1905`) → llevar ctx:
```python
async def _sse_generator(ctx: dict):
    q = _stdlib_queue.SimpleQueue()
    q_id = id(q)
    import logging as _lg
    _sse_log = _lg.getLogger("betmexico.dashboard.sse")
    with _sse_lock:
        _sse_queues.append((q, ctx))
        n_after_join = len(_sse_queues)
        all_ids = [id(x) for (x, _c) in _sse_queues]
    _sse_log.info(f"[SSE] cliente conectado q_id={q_id} role={ctx.get('role')} total={n_after_join} all_ids={all_ids}")
    try:
        yield ": heartbeat\n\n"
        while True:
            msg = await asyncio.get_running_loop().run_in_executor(
                None, _dequeue_blocking, q, 25.0
            )
            yield msg
    except Exception as e:
        _sse_log.warning(f"[SSE] q_id={q_id} excepción no-Cancelled: {type(e).__name__}: {e}")
        raise
    finally:
        with _sse_lock:
            before = len(_sse_queues)
            _sse_queues[:] = [(qq, cc) for (qq, cc) in _sse_queues if qq is not q]
            n_after_leave = len(_sse_queues)
        _sse_log.info(f"[SSE] cliente desconectado q_id={q_id} removed={before - n_after_leave} total={n_after_leave}")


@app.get("/api/events")
async def events(user: dict = Depends(require_session)):
    ctx = {
        "role": user.get("role"),
        "telegram_id": user.get("telegram_id"),
        "display": user.get("display") or user.get("username"),
    }
    return StreamingResponse(
        _sse_generator(ctx),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

- [ ] **Step 4: Run tests**

Run: `pytest test_sse_visibility.py -v`
Expected: PASS (8 tests). Luego `pytest test_anti_rate_limit.py -v` (regresión SSE de scheduled) → PASS.

- [ ] **Step 5: Commit**

```bash
git add app.py test_sse_visibility.py
git commit -m "feat(sse): filtrado server-side por usuario en _broadcast + ctx en /api/events"
```

---

### Task 3: Migración `account_marks` (marcador privado)

**Files:**
- Modify: `app.py:141-185` (`_migrate()`)
- Test: `test_marks.py` (nuevo)

**Interfaces:**
- Produces: tabla `account_marks(id, user_key, account_email, created_at, UNIQUE(user_key, account_email))`.

- [ ] **Step 1: Write the failing test**

```python
# test_marks.py
def test_account_marks_table_exists(make_client):
    import app
    with app.db() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(account_marks)").fetchall()]
    assert set(["user_key", "account_email"]).issubset(set(cols))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_marks.py -v`
Expected: FAIL — tabla no existe (`PRAGMA` devuelve vacío → assert falla).

- [ ] **Step 3: Implement** — agregar al final del `for` de `_migrate()`, después del último ALTER y ANTES del backfill A1, un `CREATE TABLE IF NOT EXISTS`:

```python
    # Marcador privado por usuario (spec 2026-06-29): apartar una cuenta para
    # trabajarla luego. NO bloquea, NO cambia visibilidad. Privado por user_key.
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE TABLE IF NOT EXISTS account_marks ("
                "id INTEGER PRIMARY KEY AUTOINCREMENT, "
                "user_key TEXT NOT NULL, account_email TEXT NOT NULL, "
                "created_at TEXT, UNIQUE(user_key, account_email))"
            )
    except sqlite3.OperationalError:
        pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_marks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add app.py test_marks.py
git commit -m "feat(marks): migracion account_marks (marcador privado por usuario)"
```

---

### Task 4: Endpoints del marcador (`/api/marks` GET + toggle)

**Files:**
- Modify: `app.py` (agregar handlers; usar `require_session`)
- Test: `test_marks.py` (extender)

**Interfaces:**
- Consumes: `require_session`, `db()`, tabla `account_marks`.
- Produces: `GET /api/marks -> {"marks": [email,...]}`; `POST /api/marks/toggle {email} -> {"marked": bool}`.
- `user_key` = `str(user["telegram_id"])` (estable por usuario).

- [ ] **Step 1: Write the failing test**

```python
def test_toggle_is_idempotent_and_private(make_client):
    lau = make_client(role="user", telegram_id=555, username="lau")
    # marcar
    assert lau.post("/api/marks/toggle", json={"email": "a@test.com"}).json()["marked"] is True
    assert lau.get("/api/marks").json()["marks"] == ["a@test.com"]
    # toggle de nuevo = desmarcar
    assert lau.post("/api/marks/toggle", json={"email": "a@test.com"}).json()["marked"] is False
    assert lau.get("/api/marks").json()["marks"] == []

def test_marks_are_private_per_user(make_client):
    lau = make_client(role="user", telegram_id=555, username="lau")
    lau.post("/api/marks/toggle", json={"email": "a@test.com"})
    sa = make_client(role="superadmin", telegram_id=1341812706, username="robertvs")
    assert sa.get("/api/marks").json()["marks"] == []  # SA no ve la marca de Lau

def test_mark_does_not_lock_or_change_visibility(make_client):
    import app
    lau = make_client(role="user", telegram_id=555, username="lau")
    lau.post("/api/marks/toggle", json={"email": "a@test.com"})
    with app.db() as c:
        row = c.execute("SELECT locked_by, published_to_pool FROM accounts WHERE email='a@test.com'").fetchone()
    assert row["locked_by"] == 555            # el lock previo no cambió por marcar
    assert row["published_to_pool"] == 1      # visibilidad intacta
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_marks.py -v`
Expected: FAIL — 404 en `/api/marks` (no existen los handlers).

- [ ] **Step 3: Implement** (agregar handlers, p.ej. junto a otros `@app.get`/`@app.post`):

```python
@app.get("/api/marks")
def api_marks_list(user: dict = Depends(require_session)):
    uk = str(user.get("telegram_id"))
    with db() as c:
        rows = c.execute(
            "SELECT account_email FROM account_marks WHERE user_key=? ORDER BY id DESC",
            (uk,),
        ).fetchall()
    return {"marks": [r["account_email"] for r in rows]}


@app.post("/api/marks/toggle")
def api_marks_toggle(payload: dict, user: dict = Depends(require_session)):
    email = (payload or {}).get("email")
    if not email:
        raise HTTPException(status_code=400, detail="email requerido")
    uk = str(user.get("telegram_id"))
    with db(write=True) as c:
        existing = c.execute(
            "SELECT id FROM account_marks WHERE user_key=? AND account_email=?",
            (uk, email),
        ).fetchone()
        if existing:
            c.execute("DELETE FROM account_marks WHERE id=?", (existing["id"],))
            return {"marked": False}
        c.execute(
            "INSERT INTO account_marks (user_key, account_email, created_at) "
            "VALUES (?,?,datetime('now'))",
            (uk, email),
        )
    return {"marked": True}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_marks.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add app.py test_marks.py
git commit -m "feat(marks): endpoints GET /api/marks + POST /api/marks/toggle (idempotente, privado)"
```

---

### Task 5: `/api/activity` — feed scoped por rol

**Files:**
- Modify: `app.py` (nuevo handler; reusa el armado de `feed` de kpis L921-967)
- Test: `test_activity_scoped.py` (nuevo)

**Interfaces:**
- Consumes: `require_session`, `_resolve_operator`, `_operator_color`, `db()`.
- Produces: `GET /api/activity -> {"feed": [evento,...]}` (hasta 30). SA = todo; operador = solo sus acciones (deposits con su `operator_id` + locks con su `locked_by`).

- [ ] **Step 1: Write the failing test**

```python
# test_activity_scoped.py
def test_activity_operator_only_own(make_client):
    cli = make_client(role="user", telegram_id=555, username="lau")
    feed = cli.get("/api/activity").json()["feed"]
    # seed: deposit de 555 (a@) y de 1341812706 (b@). Operador solo ve el suyo.
    targets = " ".join(str(e.get("target")) for e in feed)
    assert "a@test.com" in targets
    assert "b@test.com" not in targets   # acción del SA -> invisible al operador

def test_activity_sa_sees_all(make_client):
    cli = make_client(role="superadmin", telegram_id=1341812706, username="robertvs")
    feed = cli.get("/api/activity").json()["feed"]
    targets = " ".join(str(e.get("target")) for e in feed)
    assert "a@test.com" in targets and "b@test.com" in targets
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_activity_scoped.py -v`
Expected: FAIL — 404 (handler inexistente).

- [ ] **Step 3: Implement** — handler que arma feed con filtro por operador (espejo de kpis L921-967 pero parametrizado):

```python
@app.get("/api/activity")
def api_activity(user: dict = Depends(require_session)):
    is_sa = user.get("role") == "superadmin"
    my = user.get("telegram_id")
    feed = []
    with db() as c:
        pw_cache: dict = {}
        def _combo(email: str) -> str:
            if not email:
                return ""
            if email not in pw_cache:
                row = c.execute("SELECT password FROM accounts WHERE email=? LIMIT 1", (email,)).fetchone()
                pw_cache[email] = row["password"] if row else ""
            pw = pw_cache.get(email) or ""
            return f"{email}:{pw}" if pw else email

        dep_sql = ("SELECT account_email, amount, status, operator_id, created_at "
                   "FROM deposit_attempts ")
        dep_args: tuple = ()
        if not is_sa:
            dep_sql += "WHERE operator_id = ? "
            dep_args = (my,)
        dep_sql += "ORDER BY id DESC LIMIT 30"
        try:
            for r in c.execute(dep_sql, dep_args).fetchall():
                feed.append({
                    "kind": "deposit", "ts": r["created_at"],
                    "who": _resolve_operator(r["operator_id"]),
                    "who_color": _operator_color(r["operator_id"]),
                    "who_id": r["operator_id"],
                    "target": _combo(r["account_email"]),
                    "amount": r["amount"], "status": r["status"],
                })
        except sqlite3.OperationalError:
            pass

        lock_sql = "SELECT email, locked_by, locked_at FROM accounts WHERE locked_by IS NOT NULL "
        lock_args: tuple = ()
        if not is_sa:
            lock_sql += "AND locked_by = ? "
            lock_args = (str(my),)
        lock_sql += "ORDER BY locked_at DESC LIMIT 30"
        for r in c.execute(lock_sql, lock_args).fetchall():
            feed.append({
                "kind": "lock", "ts": r["locked_at"],
                "who": _resolve_operator(r["locked_by"]),
                "who_id": r["locked_by"],
                "target": _combo(r["email"]),
            })
    feed.sort(key=lambda e: str(e.get("ts", "")), reverse=True)
    return {"feed": feed[:30]}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_activity_scoped.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add app.py test_activity_scoped.py
git commit -m "feat(activity): GET /api/activity feed scoped por rol (operador solo lo suyo)"
```

---

### Task 6: `/api/recent` — cuentas recientes + stats del día (scoped)

**Files:**
- Modify: `app.py` (nuevo handler)
- Test: `test_activity_scoped.py` (extender)

**Interfaces:**
- Consumes: `require_session`, `db()`, `account_marks`.
- Produces: `GET /api/recent -> {"recent": [{email, combo, last_ts, reason}], "stats": {attempts, approved, amount, rate}}`. `reason ∈ {deposit, lock, mark}`. Scoped: operador = lo suyo; SA = lo suyo (Robert). Stats = del día (hoy), por operador.

- [ ] **Step 1: Write the failing test**

```python
def test_recent_includes_own_interactions_and_marks(make_client):
    cli = make_client(role="user", telegram_id=555, username="lau")
    cli.post("/api/marks/toggle", json={"email": "b@test.com"})  # marca una ajena (permitido: marcar no expone)
    data = cli.get("/api/recent").json()
    emails = {r["email"] for r in data["recent"]}
    assert "a@test.com" in emails     # depósito propio + lock propio
    assert "b@test.com" in emails     # marcada por el
    assert "stats" in data and "attempts" in data["stats"]

def test_recent_stats_scoped_to_user(make_client):
    cli = make_client(role="user", telegram_id=555, username="lau")
    stats = cli.get("/api/recent").json()["stats"]
    assert isinstance(stats["attempts"], int) and isinstance(stats["approved"], int)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_activity_scoped.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: Implement**:

```python
@app.get("/api/recent")
def api_recent(user: dict = Depends(require_session)):
    is_sa = user.get("role") == "superadmin"
    my = user.get("telegram_id")
    uk = str(my)
    recent: dict = {}  # email -> {email, combo, last_ts, reason}
    with db() as c:
        def _combo(email):
            row = c.execute("SELECT password FROM accounts WHERE email=? LIMIT 1", (email,)).fetchone()
            pw = (row["password"] if row else "") or ""
            return f"{email}:{pw}" if pw else email

        def _add(email, ts, reason):
            if not email:
                return
            cur = recent.get(email)
            if cur is None or str(ts or "") > str(cur["last_ts"] or ""):
                recent[email] = {"email": email, "combo": _combo(email),
                                 "last_ts": ts, "reason": reason}

        # depósitos propios (o todos si SA = los de Robert)
        dsql = "SELECT account_email, created_at FROM deposit_attempts "
        dargs: tuple = ()
        if not is_sa:
            dsql += "WHERE operator_id=? "
            dargs = (my,)
        else:
            dsql += "WHERE operator_id=? "
            dargs = (my,)   # SA tambien ve SUS recientes aqui (vista global = /api/activity)
        dsql += "ORDER BY id DESC LIMIT 50"
        try:
            for r in c.execute(dsql, dargs).fetchall():
                _add(r["account_email"], r["created_at"], "deposit")
        except sqlite3.OperationalError:
            pass

        # locks propios (en uso)
        for r in c.execute(
            "SELECT email, locked_at FROM accounts WHERE locked_by=? ORDER BY locked_at DESC LIMIT 50",
            (str(my),),
        ).fetchall():
            _add(r["email"], r["locked_at"], "lock")

        # marcadas
        for r in c.execute(
            "SELECT account_email, created_at FROM account_marks WHERE user_key=? ORDER BY id DESC LIMIT 50",
            (uk,),
        ).fetchall():
            _add(r["account_email"], r["created_at"], "mark")

        # stats del día (por operador)
        try:
            st = c.execute(
                "SELECT COUNT(*) n, "
                "SUM(CASE WHEN lower(status)='approved' THEN 1 ELSE 0 END) ok, "
                "SUM(CASE WHEN lower(status)='approved' THEN amount ELSE 0 END) amt "
                "FROM deposit_attempts WHERE operator_id=? AND created_at >= date('now')",
                (my,),
            ).fetchone()
            attempts = st["n"] or 0
            approved = st["ok"] or 0
            amount = float(st["amt"] or 0)
        except sqlite3.OperationalError:
            attempts = approved = 0
            amount = 0.0
    rec = sorted(recent.values(), key=lambda x: str(x["last_ts"] or ""), reverse=True)[:20]
    rate = round(100.0 * approved / attempts, 1) if attempts else 0.0
    return {"recent": rec, "stats": {"attempts": attempts, "approved": approved, "amount": amount, "rate": rate}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_activity_scoped.py -v`
Expected: PASS (4 tests total)

- [ ] **Step 5: Commit**

```bash
git add app.py test_activity_scoped.py
git commit -m "feat(recent): GET /api/recent cuentas recientes + stats del dia (scoped por operador)"
```

---

### Task 7: Pool manager backend — `/api/pool/split` + `/api/pool/publish` (SA-only, bulk)

**Files:**
- Modify: `app.py` (handlers + broadcast `pool_move`)
- Test: `test_pool_manage.py` (nuevo)

**Interfaces:**
- Consumes: `require_session`, `db(write=True)`, `_broadcast`, `_resolve_who`.
- Produces:
  - `GET /api/pool/split -> {"inside": [{email,combo}], "outside": [{email,combo}]}` (solo SA; 403 si no).
  - `POST /api/pool/publish {emails:[...], publish: bool} -> {"moved": int}` (solo SA). `publish=True` set `published_to_pool=1`; `False` set `0`.
- Helper de gate SA: `_is_sa(user)` ya existe (`app.py:215-217`).

- [ ] **Step 1: Write the failing test**

```python
# test_pool_manage.py
def test_split_sa_only(make_client):
    op = make_client(role="user", telegram_id=555, username="lau")
    assert op.get("/api/pool/split").status_code == 403
    sa = make_client(role="superadmin", telegram_id=1341812706, username="robertvs")
    body = sa.get("/api/pool/split").json()
    assert "inside" in body and "outside" in body

def test_publish_moves_accounts(make_client):
    import app
    sa = make_client(role="superadmin", telegram_id=1341812706, username="robertvs")
    # sacar a@ del pool
    r = sa.post("/api/pool/publish", json={"emails": ["a@test.com"], "publish": False})
    assert r.json()["moved"] == 1
    with app.db() as c:
        v = c.execute("SELECT published_to_pool FROM accounts WHERE email='a@test.com'").fetchone()[0]
    assert v == 0
    # reexponer
    sa.post("/api/pool/publish", json={"emails": ["a@test.com"], "publish": True})
    with app.db() as c:
        v = c.execute("SELECT published_to_pool FROM accounts WHERE email='a@test.com'").fetchone()[0]
    assert v == 1

def test_publish_forbidden_for_operator(make_client):
    op = make_client(role="user", telegram_id=555, username="lau")
    assert op.post("/api/pool/publish", json={"emails": ["a@test.com"], "publish": True}).status_code == 403
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest test_pool_manage.py -v`
Expected: FAIL — 404.

- [ ] **Step 3: Implement**:

```python
@app.get("/api/pool/split")
def api_pool_split(user: dict = Depends(require_session)):
    if not _is_sa(user):
        raise HTTPException(status_code=403, detail="solo superadmin")
    def _combo(c, email, pw):
        return f"{email}:{pw}" if pw else email
    inside, outside = [], []
    with db() as c:
        for r in c.execute(
            "SELECT email, password, COALESCE(published_to_pool,1) p FROM accounts "
            "WHERE status='LIVE' ORDER BY email"
        ).fetchall():
            item = {"email": r["email"], "combo": _combo(c, r["email"], r["password"])}
            (inside if r["p"] == 1 else outside).append(item)
    return {"inside": inside, "outside": outside}


@app.post("/api/pool/publish")
def api_pool_publish(payload: dict, user: dict = Depends(require_session)):
    if not _is_sa(user):
        raise HTTPException(status_code=403, detail="solo superadmin")
    emails = (payload or {}).get("emails") or []
    publish = 1 if (payload or {}).get("publish") else 0
    if not emails:
        return {"moved": 0}
    with db(write=True) as c:
        qmarks = ",".join("?" for _ in emails)
        c.execute(
            f"UPDATE accounts SET published_to_pool=? WHERE email IN ({qmarks})",
            (publish, *emails),
        )
        moved = c.execute("SELECT changes()").fetchone()[0]
    _broadcast({
        "type": "activity", "kind": "pool_move",
        "publish": bool(publish), "count": len(emails),
        "ts": datetime.now(timezone.utc).isoformat(),
        **_resolve_who(user.get("telegram_id")),
    })
    return {"moved": moved}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest test_pool_manage.py -v`
Expected: PASS (3 tests). Verificar también que `pool_move` solo lo ve el SA: ya cubierto por `_event_visible_to` (Task 1, sin who_id de otro → operador no lo recibe; con who_id del SA → operador filtra; SA siempre).

- [ ] **Step 5: Commit**

```bash
git add app.py test_pool_manage.py
git commit -m "feat(pool): GET /api/pool/split + POST /api/pool/publish bulk (SA-only) + broadcast pool_move"
```

---

# PARTE 2 — FRONTEND

### Task 8: Lógica pura de actividad (node-testable)

**Files:**
- Create: `static/activity_logic.js` (IIFE/UMD estilo `depos_logic.js`)
- Test: `static/activity_logic.test.js`

**Interfaces:**
- Produces:
  - `dedupeActivity(events) -> events` — key `sched_id+iter` si hay sched_id, si no `kind+target+amount+ts_minuto`. Conserva el más reciente, mantiene orden.
  - `formatActivityCopy(ev, viewerIsSA) -> {icon, text, ok|fail|neutral}` — titular humano (§9 del spec). Para no-SA, `who` se muestra como "tú".

- [ ] **Step 1: Write the failing test**

```javascript
// static/activity_logic.test.js
const A = require('./activity_logic.js');
let fails = 0;
function eq(got, exp, msg){ if(JSON.stringify(got)!==JSON.stringify(exp)){console.error('FAIL',msg,'got',got,'exp',exp);fails++;} }

// dedupe scheduled doble-evento -> 1
const deduped = A.dedupeActivity([
  {kind:'scheduled', sched_id:'s1', iter:1, ts:'2026-06-29T10:00:00'},
  {kind:'scheduled_aborted', sched_id:'s1', iter:1, ts:'2026-06-29T10:00:01'},
]);
eq(deduped.length, 1, 'scheduled doble-evento colapsa a 1');

// copy humano deposito aprobado
const c1 = A.formatActivityCopy({kind:'deposit', status:'approved', who:'Lau', target:'a@x.com:p', amount:300}, true);
eq(c1.icon, '💰', 'icono deposito ok');
eq(c1.cls, 'ok', 'clase ok');
if(!/Lau/.test(c1.text) || !/300/.test(c1.text) || !/aprobad/i.test(c1.text)){console.error('FAIL copy deposito', c1.text);fails++;}

// no-SA ve 'tú' en vez de su nombre
const c2 = A.formatActivityCopy({kind:'lock', who:'Lau', target:'a@x.com'}, false);
if(!/tú|Tú/.test(c2.text)){console.error('FAIL no-SA debe decir tú', c2.text);fails++;}

if(fails){console.error(fails+' FALLOS');process.exit(1);} else {console.log('OK activity_logic');}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `node static/activity_logic.test.js`
Expected: FAIL — `Cannot find module './activity_logic.js'`

- [ ] **Step 3: Implement** `static/activity_logic.js`:

```javascript
(function (root) {
  function _minute(ts) { return String(ts || '').slice(0, 16); }
  function dedupeActivity(events) {
    const seen = new Map();
    const out = [];
    for (const ev of events) {
      const key = ev.sched_id != null
        ? `s:${ev.sched_id}:${ev.iter}`
        : `${ev.kind}:${ev.target || ev.email || ''}:${ev.amount ?? ''}:${_minute(ev.ts)}`;
      if (seen.has(key)) continue;
      seen.set(key, true);
      out.push(ev);
    }
    return out;
  }
  function _who(ev, viewerIsSA) { return viewerIsSA ? (ev.who || '—') : 'Tú'; }
  function _email(t) { return String(t || '').split(':')[0]; }
  function formatActivityCopy(ev, viewerIsSA) {
    const who = _who(ev, viewerIsSA);
    const email = _email(ev.target || ev.email);
    const amt = ev.amount != null ? `$${ev.amount}` : '';
    if (ev.kind === 'deposit') {
      if (ev.status === 'approved') return { icon: '💰', cls: 'ok', text: `${who} depositó ${amt} a ${email} — aprobado` };
      if (ev.code === '3DS_REQUIRED' || ev.reason === '3DS') return { icon: '🔐', cls: 'neutral', text: `${who} ${amt} a ${email} — pidió verificación 3DS` };
      return { icon: '✗', cls: 'fail', text: `${who} intentó ${amt} a ${email} — rechazado (banco)` };
    }
    if (ev.kind === 'lock') return { icon: '🔒', cls: 'neutral', text: `${who} tomó ${email}` };
    if (ev.kind === 'unlock' || ev.kind === 'unlock_auto') return { icon: '🔓', cls: 'neutral', text: `${email} liberada` };
    if (ev.kind === 'account_cooling') return { icon: '⏸', cls: 'neutral', text: `${email} en pausa ~${ev.minutes || ''}m (muchos intentos)` };
    if (ev.kind === 'mark') return { icon: '📌', cls: 'neutral', text: `${who} fijó ${email}` };
    if (ev.kind === 'pool_move') return { icon: ev.publish ? '↘' : '↗', cls: 'neutral', text: `${who} ${ev.publish ? 'expuso' : 'retiró'} ${ev.count || ''} cuenta(s) ${ev.publish ? 'al' : 'del'} pool` };
    if (ev.kind === 'critical_error') return { icon: '⚠', cls: 'fail', text: ev.msg || 'Problema de conexión' };
    return { icon: '·', cls: 'neutral', text: `${who} ${email}` };
  }
  const api = { dedupeActivity, formatActivityCopy };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.ActivityLogic = api;
})(typeof window !== 'undefined' ? window : globalThis);
```

- [ ] **Step 4: Run test to verify it passes**

Run: `node static/activity_logic.test.js`
Expected: `OK activity_logic`

- [ ] **Step 5: Commit**

```bash
git add static/activity_logic.js static/activity_logic.test.js
git commit -m "feat(activity): logica pura dedupe + copy humano (TDD node)"
```

---

### Task 9: HTML — strip de 3 cards + des-ocultar para operadores

**Files:**
- Modify: `static/index.html:82-128` (`#adminPanel`), `static/index.html:998-1001` (script + cache bump)

**Interfaces:**
- Produces: strip con 3 cards: `.lp-activity` (era `.lp-feed`), `.lp-recientes` (era `.lp-alerts`), `.lp-pool`. Online (`.lp-online`) ELIMINADA del strip (se reubica en Task 15).

- [ ] **Step 1:** Leer el markup actual `#adminPanel` (`index.html:82-128`). Reemplazar el bloque de 4 cards por 3:
  - Quitar `<div class="lp-card lp-online">…</div>` (84-91).
  - Renombrar la card del feed: `class="lp-card lp-feed lp-activity"`, header sigue con `data-nav="activity"`, contenedor `id="lpActivity"` (marquesina). Quitar el `id="lpFeed"` viejo o conservarlo como alias — usar `lpActivity`.
  - Renombrar Alertas → Recientes: `class="lp-card lp-recientes"`, label "Recientes", contenedor `id="lpRecientes"`.
  - Pool card: igual estructura, agregar `id="lpPoolCard"` al contenedor para alternar SA/operador.

- [ ] **Step 2:** Agregar `<script src="/static/activity_logic.js?v=YYYYMMDD"></script>` antes de `app.js` (`index.html:998-1001`) y **bump** del `?v=` de `app.js`/`style.css` a la fecha de hoy (cache-bust — ver `feedback_diagnostico_interfaz_vieja`: feature lista = default, no caché).

- [ ] **Step 3:** Verificar sintaxis HTML (abrir en navegador local no es necesario aún). Commit.

```bash
git add static/index.html
git commit -m "feat(ui): strip a 3 cards (Actividad/Recientes/Pool); quitar Online del strip; cache bump"
```

> Acceptance de Task 9-16 es de layout/runtime: se valida junta al final con medición objetiva (Task 16 + smoke). No hay test unitario de DOM.

---

### Task 10: CSS — grid 3 cards, Actividad −15-20%, sin overflow:auto, marquesina

**Files:**
- Modify: `static/style.css:398-427` (`.lpanel` grid), `:448-577` (cards), responsive `:2180-2181`

- [ ] **Step 1:** `#adminPanel` grid de `220px 1fr 220px 200px` → 3 columnas. Actividad Live −15-20% vs su `1fr` previo: usar `grid-template-columns: minmax(0, 1.7fr) minmax(0, 1.1fr) 210px` (Actividad la más ancha pero recortada respecto al `1fr` puro que antes ocupaba todo el centro; Recientes y Pool a su derecha). Ajustar el responsive (`:2180`) a 3 columnas.

- [ ] **Step 2:** En `.lp-feed-rows`/nueva `.lp-activity .rows`: **quitar `overflow-y:auto` + `max-height`**. Implementar marquesina: contenedor altura fija para ~10 filas; animación de desfile (CSS `@keyframes` translateY o reemplazo de filas vía JS cada N s). Filas 1 registro/línea, `white-space:nowrap; text-overflow:ellipsis` SOLO si imprescindible — meta es que NO truncar (medición Task 16).

- [ ] **Step 3:** `.lp-recientes` y `.lp-online` (sidebar) sin `overflow:auto` — caben/ciclan.

- [ ] **Step 4:** Verificar en `/static/index.html` real (no harness). Commit.

```bash
git add static/style.css
git commit -m "style(ui): grid 3 cards, Actividad -15-20%, marquesina sin overflow:auto"
```

---

### Task 11: JS — render de la marquesina Actividad Live

**Files:**
- Modify: `static/app.js` — nueva `renderActivityMarquee()`; `loadMe()` quitar gate que oculta `#adminPanel` a no-SA (`app.js:415-418`); `connectSSE()` (`:1331`) y `pushActivityEvent` (`:997`) alimentar la marquesina; init carga `/api/activity`.

**Interfaces:**
- Consumes: `ActivityLogic.dedupeActivity`, `ActivityLogic.formatActivityCopy`, `state.user.role`, `openDetailModal(email)` (`app.js:3088`), `showSection('activity')`.

- [ ] **Step 1:** En `loadMe()` (`app.js:415-418`), **quitar** el `$('#adminPanel').style.display='none'` para no-SA (el strip ahora es visible a todos). Conservar `document.body.classList.add('no-kpis')` si se usa para otros gates, pero NO ocultar el strip. (Verificar usos de `.no-kpis` en `style.css` antes de quitarlo; si solo ocultaba el strip, eliminar esa regla.)

- [ ] **Step 2:** Nueva función:
```javascript
async function loadActivityMarquee() {
  try {
    const r = await fetch('/api/activity');
    const data = await r.json();
    activityRows = data.feed || [];   // ya viene scoped por backend
    renderActivityMarquee();
  } catch {}
}
function renderActivityMarquee() {
  const host = document.getElementById('lpActivity');
  if (!host) return;
  const isSA = state.user?.role === 'superadmin';
  const rows = ActivityLogic.dedupeActivity(activityRows).slice(0, 30);
  $('#lpFeedCount').textContent = rows.length ? `${rows.length} eventos` : '—';
  host.innerHTML = rows.length === 0
    ? '<div class="lp-empty dim mono">esperando actividad…</div>'
    : rows.slice(0, 10).map(ev => {
        const c = ActivityLogic.formatActivityCopy(ev, isSA);
        const email = String(ev.target || ev.email || '').split(':')[0];
        return `<div class="lp-feed-row lp-feed-${c.cls} lp-feed-clickable" data-open-detail="${esc(email)}" title="Abrir cuenta">
          <span class="lp-feed-ic">${c.icon}</span>
          <span class="lp-feed-txt">${esc(c.text)}</span>
          <span class="lp-feed-time mono dim">${fmtAgo(ev.ts)}</span>
        </div>`;
      }).join('');
}
```

- [ ] **Step 3:** Handlers de click (delegación global, donde estén los otros listeners): fila `[data-open-detail]` → `openDetailModal(email)`; header de la card (`data-nav="activity"`) → `showSection('activity')` (ya existe el patrón `data-nav`).

- [ ] **Step 4:** En `connectSSE()` → tras `pushActivityEvent(ev)`, si la card existe, llamar `renderActivityMarquee()`. En `pushActivityEvent` (`:997`) ya hace `activityRows.unshift` — agregar `renderActivityMarquee()` al final (además del `renderActivity()` del panel).

- [ ] **Step 4b (errores críticos humanizados — D4/D6, sin tocar el motor):** En `connectSSE()`, las ramas `ev.type === 'alert'` (`capmonster_low`/`proxy_down`) y `ev.type === 'health_warning'` ya existen (`app.js:1382-1387`). Agregar: empujar a `activityRows` un `{kind:'critical_error', msg:_humanizeCritical(ev), ts:nowISO}` y `renderActivityMarquee()`. `_humanizeCritical` mapea sin jerga (E-RED): `capmonster_low`→"Servicio de verificación sin saldo", `proxy_down`→"Problema de conexión con la pasarela", `health_warning`→"Servicio degradado, reintentando". Estos son fallos GLOBALES (bloquean a todos) → visibles a todos (no requieren `who_id`). Dedup/rate-limit: `dedupeActivity` ya colapsa por `kind+minuto`.
- [ ] **Step 5:** Llamar `loadActivityMarquee()` en el init (junto a `loadMe()`/`refreshKpis()`). Quitar de `refreshKpis()` el Bloque 2 (feed) viejo que ya no aplica (el feed ahora viene de `/api/activity`, no de kpis) — o dejar kpis solo para SA-sidebar. Commit.

```bash
git add static/app.js
git commit -m "feat(activity): marquesina render por rol (dedupe+copy), click->detalle, header->panel"
```

---

### Task 12: JS — Recientes + botón marcador (tabla + detalle)

**Files:**
- Modify: `static/app.js` — `loadRecientes()`/`renderRecientes()`; botón 📌 en `renderTable()` (`:490`) y en `openDetailModal` (`:3088`); estado `markedSet`.

**Interfaces:**
- Consumes: `GET /api/recent`, `GET /api/marks`, `POST /api/marks/toggle`.

- [ ] **Step 1:** Al cargar: `markedSet = new Set((await fetch('/api/marks')).json().marks)`. `loadRecientes()` → `fetch('/api/recent')` → render en `#lpRecientes` (combo + razón: depositó/en uso/fijada + ago). Sin overflow:auto.

- [ ] **Step 2:** Botón 📌 en cada fila de tabla (`renderTable`) y en el detalle. Estado activo si `markedSet.has(email)`. Click → `POST /api/marks/toggle {email}` → actualizar `markedSet` + repintar botón + `loadRecientes()`. NO recargar tabla (marcar no cambia visibilidad — frictionless).

- [ ] **Step 3:** Render de "Mis stats del día" cae en Task 13 (card Pool, operador). Recientes ya muestra las marcadas. Commit.

```bash
git add static/app.js static/style.css
git commit -m "feat(recientes): card Recientes + marcador privado (boton 📌 tabla/detalle, toggle sin recargar)"
```

---

### Task 13: JS — card Pool por rol (SA salud+botón / operador stats)

**Files:**
- Modify: `static/app.js` — `renderPoolCard()`; usa `state.user.role`, `k.pool` (SA) y `/api/recent` `stats` (operador).

- [ ] **Step 1:** Si SA: pintar `#lpPoolCard` con la grid 2×2 actual (Pool/En uso/Trastienda/Rebotadas de `k.pool`, ya en `refreshKpis` Bloque 4) **+ botón "Gestionar pool"** → `showSection('pool')`.

- [ ] **Step 2:** Si operador: pintar "Mis stats del día" desde `/api/recent` → `stats` (intentos / aprobados / monto / tasa). Layout compacto, sin overflow:auto.

- [ ] **Step 3:** Mover el Bloque 4 de `refreshKpis` (`:1545-1551`) dentro de `renderPoolCard()` (rama SA). Commit.

```bash
git add static/app.js
git commit -m "feat(pool-card): salud+gestor para SA, Mis stats del dia para operador"
```

---

### Task 14: Mover buscador al sidebar (arriba de "Principal")

**Files:**
- Modify: `static/index.html:63-67` (sacar de `.topbar`), `static/index.html:24-55` (insertar en sidebar entre `sb-greet` y `sb-section "Principal"`), `static/style.css` (`.search` reposicionado)

- [ ] **Step 1:** Mover el bloque `<div class="search">…#searchInput…</div>` del topbar al sidebar, entre `sb-greet` (L~30) y `<div class="sb-section">Principal</div>`. **Conservar el `id="searchInput"`** — el listener (`app.js:1912`) sigue funcionando (manda `q=` al backend, confirmado).

- [ ] **Step 2:** CSS: adaptar `.search` al ancho del sidebar (full width, padding compacto). Quitar el `<kbd>Ctrl K</kbd>` si no cabe, o reducirlo. Verificar `Ctrl+K` sigue enfocando.

- [ ] **Step 3:** Verificar en `/static/index.html`: escribir en el buscador filtra la tabla (pega a `/api/accounts?q=`). Commit.

```bash
git add static/index.html static/style.css
git commit -m "feat(ui): buscador incrustado en sidebar (arriba de Principal); conserva cableado backend"
```

---

### Task 15: Mover Online al sidebar (bajo BINes, compacto, solo-SA)

**Files:**
- Modify: `static/index.html` (insertar card Online compacta en sidebar tras el nav BINes), `static/app.js` `loadMe()`+`refreshKpis()` Bloque 1, `static/style.css`

- [ ] **Step 1:** Insertar en el sidebar, **después** del `<button class="nav" data-section="bin-stats">▣ BINes</button>`, un bloque compacto Online (avatares + contador) con los mismos IDs (`#lpOnlineActive`, `#lpOnlineTotal`, `#lpOps`) para reusar el Bloque 1 de `refreshKpis` (`app.js:1496-1507`) sin cambiarlo.

- [ ] **Step 2:** Solo-SA: en `loadMe()` (`:415`), ocultar el bloque Online del sidebar para no-SA (`if (!isSuper) onlineBlock.style.display='none'`). Compacto, sin overflow:auto (`feedback_no_quitar_compactar`).

- [ ] **Step 3:** CSS compacto para el bloque en el sidebar (avatares chicos, una línea por op o grid). Verificar. Commit.

```bash
git add static/index.html static/app.js static/style.css
git commit -m "feat(ui): Online compacto en sidebar bajo BINes (solo-SA)"
```

---

### Task 16: Compactar tabla (ancho + alto de filas) — medición objetiva

**Files:**
- Modify: `static/style.css:341-395` (`.tablewrap`, `table`, `td`), `static/app.js:497` (`--combo-width` si aplica)

- [ ] **Step 1:** Reducir alto de fila: `tbody td { padding: 8px 14px }` → `padding: 4px 12px` (`style.css:395`). `thead th` padding proporcional.

- [ ] **Step 2:** Reducir desperdicio a la derecha: revisar por qué la tabla deja hueco (probable `width:100%` con columnas que no llenan). Acotar `--combo-width` o agregar `max-width` sensato / redistribuir. NO quitar columnas (`feedback_no_quitar_compactar`).

- [ ] **Step 3 (medición objetiva):** En `/static/index.html` real, medir antes/después con DevTools/preview:
```js
// filas visibles en el viewport de la tabla:
const rows=[...document.querySelectorAll('#accTable tbody tr')];
const wrap=document.querySelector('.tablewrap').getBoundingClientRect();
rows.filter(r=>{const b=r.getBoundingClientRect();return b.top>=wrap.top&&b.bottom<=wrap.bottom;}).length
// alto de fila:
document.querySelector('#accTable tbody tr').getBoundingClientRect().height
```
Criterio: alto de fila menor y MÁS filas visibles que antes. Registrar números.

- [ ] **Step 4:** Commit.

```bash
git add static/style.css static/app.js
git commit -m "style(table): filas mas bajas + menos desperdicio a la derecha (medido objetivo)"
```

---

### Task 17: HTML — gestor de Pool partido (`#poolMain`)

**Files:**
- Modify: `static/index.html` (sección `#poolMain` — hoy existe; rehacer su contenido a vista partida)

- [ ] **Step 1:** Leer el `#poolMain` actual. Reemplazar su contenido por **2 columnas**: "Fuera del pool" (`#poolOutside`) y "En el pool" (`#poolInside`), cada una con: header + contador, **input de búsqueda** (`#poolSearchOut`/`#poolSearchIn`), lista de chips (combo) seleccionables, y barra de acción bulk (`#poolBtnExpose` "Mandar N al pool →", `#poolBtnHide` "← Sacar N"). Scroll permitido en cada columna (sección de gestión).

- [ ] **Step 2:** Commit.

```bash
git add static/index.html
git commit -m "feat(pool-manager): markup vista partida Fuera|Dentro con search + bulk"
```

---

### Task 18: JS — gestor de Pool (drag-drop + multi-select + bulk + confirm-al-exponer)

**Files:**
- Modify: `static/app.js` — `reloadPool()` (ya llamado por `showSection('pool')`, `:1142`)

**Interfaces:**
- Consumes: `GET /api/pool/split`, `POST /api/pool/publish`, `state.user.role`.

- [ ] **Step 1:** `reloadPool()` → `fetch('/api/pool/split')` → render chips en `#poolOutside`/`#poolInside`. Filtrado en vivo por los inputs de búsqueda. Multi-selección (click toggle `.selected`).

- [ ] **Step 2:** Bulk: botón "Mandar al pool" (outside→inside) → **confirmación** (`confirm()` o modal) → `POST /api/pool/publish {emails:[seleccionados], publish:true}` → recargar. Botón "Sacar" (inside→outside) → **sin confirmación** → `publish:false` → recargar. (D2.)

- [ ] **Step 3:** Drag-drop bidireccional (HTML5 `draggable`): soltar en la columna destino dispara el mismo flujo que el bulk (exponer pide confirm; ocultar directo). Para 1 ítem.

- [ ] **Step 4:** Verificar en runtime (interactivo — Robert). Commit.

```bash
git add static/app.js
git commit -m "feat(pool-manager): split fetch + drag-drop + multi-select + bulk; confirm al exponer, directo al sacar"
```

---

### Task 19: Panel Actividad completo (`#activityMain`) — coherente y organizado

**Files:**
- Modify: `static/app.js` `renderActivity()`/`reloadActivity()` (`showSection('activity')` los llama, `:1143`), `static/index.html` `#activityMain`, `static/style.css`

**Interfaces:**
- Consumes: `GET /api/activity` (scoped), `ActivityLogic.formatActivityCopy`.

- [ ] **Step 1:** `reloadActivity()` → `fetch('/api/activity')` (ya scoped). Render **agrupado por día** (Hoy / Ayer / fecha), **un registro por línea** con `formatActivityCopy` + hora exacta + monto/resultado/motivo coherente por tipo.

- [ ] **Step 2:** Filtros: por tipo (depósito/lock/marca/enfriamiento/error) y por cuenta (input). Filtro por operador SOLO visible para SA (el backend ya no manda ajenos a operadores). Búsqueda por email.

- [ ] **Step 3:** Click en fila → `openDetailModal(email)`. Scroll vertical permitido (vista de consulta). Verificar coherencia por cada tipo de evento. Commit.

```bash
git add static/app.js static/index.html static/style.css
git commit -m "feat(activity-panel): vista organizada por dia + filtros + coherencia por caso (scoped)"
```

---

### Task 20: Panel de depósitos persistente cross-página

**Files:**
- Modify: `static/depos_window.js` (re-anclaje dock), `static/app.js` `showSection()` (`:1125`) hook

- [ ] **Step 1:** Leer `depos_window.js` — localizar dónde aplica el estado dock (mide rect de `#accDockZone`) y la función pública (`_win.show()`/dock). Identificar el setter de modo (float/dock-l/dock-r).

- [ ] **Step 2:** Exponer en el controlador (`window.DeposWindow`) un método `reanchorForSection(isAccountsActive)`: si el panel está acoplado y `!isAccountsActive` → cambiar a **flotante** (sin destruir el dock guardado en `localStorage`: recordarlo para volver). Si vuelve a accounts y había dock guardado → re-acoplar.

- [ ] **Step 3:** En `showSection(name)` (`app.js:1125`), al final, añadir:
```javascript
  if (window.DeposWindow && _dx && _dx.open) {
    window.DeposWindow.reanchorForSection(name === 'accounts');
  }
```

- [ ] **Step 4 (acceptance):** En runtime: abrir panel acoplado en Cuentas → cambiar a otra sección → el panel **sigue presente** (flotante), funcional; volver a Cuentas → re-acopla. Cierra solo con X/Esc. Commit.

```bash
git add static/depos_window.js static/app.js
git commit -m "fix(depos): panel persiste cross-pagina (fallback flotante fuera de Cuentas, re-acopla al volver)"
```

---

# PARTE 3 — DOCS + DEPLOY

### Task 21: Actualizar docs (bitácora obligatoria)

**Files:** `docs/SSE_EVENTS.md`, `docs/ENDPOINTS.md`, `docs/FRONTEND.md`, `docs/AUDIT.md`, `docs/ARCHITECTURE.md`

- [ ] **Step 1:** `docs/SSE_EVENTS.md`: filtrado por rol en `/api/events`; nuevo kind `pool_move`; nota de que el feed ahora es server-side scoped.
- [ ] **Step 2:** `docs/ENDPOINTS.md`: `/api/marks` (GET+toggle), `/api/activity`, `/api/recent`, `/api/pool/split`, `/api/pool/publish`.
- [ ] **Step 3:** `docs/FRONTEND.md`: strip 3 cards, marquesina, Recientes+marcador, pool manager, Online/buscador en sidebar, panel persistente.
- [ ] **Step 4:** `docs/ARCHITECTURE.md`: tabla `account_marks`; SSE scoped. `docs/AUDIT.md`: filas de las funciones nuevas (estado ✅ tras verificación / ⚠️ runtime-pending).
- [ ] **Step 5:** Commit.

```bash
git add docs/
git commit -m "docs(bitacora): reorg UI — SSE scoped, endpoints nuevos, marcador, pool manager, strip 3 cards"
```

---

### Task 22: Deploy a KVM4 + smoke funcional

**Files:** ninguno (deploy)

- [ ] **Step 1:** `pscp` de los archivos cambiados a `/docker/betmexico/code/` (ver `DEPLOY.md`/`docs/protocols/deploy-protocol.md`). Restart `betmexico-web` (`docker compose kill -s SIGKILL web && up -d web` por SSE, gotcha de ERRORS.md).
- [ ] **Step 2:** Verificar proceso vivo (`feedback_verificar_deploy_proceso_vivo`): `StartedAt > mtime` de archivos + migración `account_marks` aplicada (`PRAGMA table_info`).
- [ ] **Step 3 (smoke funcional, no solo /health):**
  - `GET /api/health` 200.
  - md5 de bundles servidos == repo (`feedback_no_alucinar`).
  - Login como SA: ve strip 3 cards, marquesina con todo, gestor de pool.
  - Login como operador (o `make_client` role=user en local): NO recibe actividad ajena en `/api/activity`, ve "Mis stats", NO ve Online ni gestor de pool.
  - Marcar una cuenta → aparece en Recientes, NO la bloquea.
  - Panel de depósitos persiste al cambiar de sección.
- [ ] **Step 4:** Actualizar `NEXT-SESSION.md` + `docs/ERRORS.md` si surge algo. Commit + push a Forgejo.

---

## Self-Review (cobertura del spec)

- §3 visibilidad por rol → Task 1, 2, 5, 6 (whitelisting server-side; fix bug admin-ve-Robert en test_activity_operator_only_own).
- §4 mecánica (Online/buscador/tabla) → Task 14, 15, 16.
- §5 strip 3 cards (Actividad/Recientes/Pool por rol) → Task 8-13.
- §6 pool manager → Task 7, 17, 18.
- §7 backend (SSE/marcador/scoped/pool) → Task 1-7.
- §8 panel persistente → Task 20.
- §9 copys → Task 8 (`formatActivityCopy`).
- §10 errores críticos → cubierto con fuentes EXISTENTES (Task 8 `formatActivityCopy` kind `critical_error` + Task 11 Step 4b enruta `alert`/`health_warning` ya emitidos por kpis/watchdog, humanizados). NO toca el motor.
- §11 aceptación → tests de Task 1-8 + medición Task 16 + smoke Task 22.

**Alcance de errores críticos (honesto):** los fallos globales (CapMonster sin saldo, proxy/pasarela caída, salud degradada) SÍ se cubren reusando los eventos SSE existentes — sin tocar `deposits.py`/`proxy_pool.py`. Lo ÚNICO fuera de este plan es la instrumentación granular "pool seco / pasarela caída para el run específico de un operador" (requeriría emitir SSE desde el motor) — trabajo futuro, no bloquea esta tanda. `formatActivityCopy` ya soporta el kind para cuando se agregue esa fuente fina.
```
