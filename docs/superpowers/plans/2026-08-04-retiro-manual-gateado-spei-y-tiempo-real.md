# Retiro manual gateado por SPEI + refresh caliente + anti-detección — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** El botón "Retirar" del portal del operador (`/user/{id}`) solo se habilita cuando BetMexico confirma que el SPEI aterrizó (cuenta de retiro aprobada); las cuentas con balance>$50, depósito reciente sin asentar o retiro en curso se refrescan siempre, sin importar lock/grade/pool; el portal expone solo los campos que le corresponden al operador (no historial); y la animación de misión de depósito no revela montos/cadencia reales.

**Architecture:** Todo el estado "¿aterrizó el SPEI?" se cachea en BD (`accounts.withdrawal_ready`/`withdrawal_institution`) porque hoy solo existe como llamada viva a BetMexico — el ciclo de `account_refresh.py` (ya corre cada 5min con JWT vivo) es quien lo puebla, igual que puebla `balance_real`. La selección de candidatos del refresh se separa en "hot" (bypassea todos los filtros, siempre entra) vs "normal" (reglas actuales intactas). El polling de estado de retiro ya existe (`pantalla.js`, SA-only) — se reusa el mismo endpoint relajando el rol, no se duplica lógica.

**Tech Stack:** FastAPI + SQLite (`app.py`), lógica pura testeada sin BD (`account_refresh.py`), vanilla JS sin framework (`static/portal.js`).

## Global Constraints

- Migraciones SIEMPRE aditivas (`ALTER TABLE ... ADD COLUMN`), patrón de tupla `(col, ddl)` en `app.py:_migrate()` L233-271 — nunca `DROP`/`RENAME`.
- Regla dura del repo: **NUNCA proxyless en prod** — toda llamada a BetMexico usa `proxy_pool.build_admin_proxy_url()` y skipea si no hay proxy (ver patrón en `account_refresh.py` L229-234).
- Operador NUNCA ve: historial de transacciones, cadencia/montos reales de depósitos automáticos, password. Ver `docs/FRONTEND.md` "capa operador vs backend".
- TDD obligatorio en toda lógica pura (`account_refresh.py`, endpoints). Lo visual (Task 10) va con dirección + verificación medida en navegador, no "a ojo".
- Cada task = 1 commit. Mensaje `tipo(scope): qué + por qué`. Branch: `feature/retiro-manual-gateado-spei` (ya existe, con 1 commit previo `cdc208e` de un fix de Track A no relacionado).
- Tras cada task que toque endpoint/SSE/BD/comportamiento, actualizar el doc correspondiente (`docs/ENDPOINTS.md`, `docs/SSE_EVENTS.md`, `docs/ARCHITECTURE.md`, `docs/FRONTEND.md`, `docs/AUDIT.md`) — skill `botmex-bitacora`, tabla de obligaciones.
- `test_account_refresh.py` ya tiene TDD escrito (sin commitear, working tree) para `is_hot_account` y el bypass "hot" en `select_refresh_candidates_healthy` — Tasks 2-3 lo REUSAN, no lo reescriben. Si al abrir la sesión el archivo no tiene esos tests (se perdieron/descartaron), reescribirlos tal como se listan en la Task 2/3 antes de tocar `account_refresh.py`.

---

### Task 1: Migración — `withdrawal_ready`, `withdrawal_institution`, índice en `account_withdrawals`

**Files:**
- Modify: `app.py:270` (dentro de la lista de `_migrate()`, después de `jwt_expires_at`)
- Modify: `app.py:373` (después del bloque `CREATE TABLE IF NOT EXISTS account_withdrawals`, antes del siguiente `try:` de `auto_missions`)

**Interfaces:**
- Produces: columnas `accounts.withdrawal_ready` (INTEGER, default 0) y `accounts.withdrawal_institution` (TEXT, nullable). Índice `idx_account_withdrawals_account_id`.

- [ ] **Step 1: Agregar las 2 columnas a la lista de migración**

En `app.py:270`, después de la línea `("jwt_expires_at", "ALTER TABLE accounts ADD COLUMN jwt_expires_at INTEGER"),`:

```python
        # withdrawal_ready/withdrawal_institution: cachea si BetMexico tiene
        # cuenta de retiro aprobada (accountStatus==2, aparece tras un SPEI
        # acreditado) — antes esto SOLO existía como llamada viva en
        # withdrawals.get_bank_accounts (PASO1), sin nada persistido para
        # gatear el botón del portal sin round-trip. Poblado por account_refresh.py.
        ("withdrawal_ready", "ALTER TABLE accounts ADD COLUMN withdrawal_ready INTEGER DEFAULT 0"),
        ("withdrawal_institution", "ALTER TABLE accounts ADD COLUMN withdrawal_institution TEXT"),
```

- [ ] **Step 2: Agregar el índice (bloque propio, patrón `account_withdrawals`)**

En `app.py`, inmediatamente después del bloque de `CREATE TABLE IF NOT EXISTS account_withdrawals` (cierra en `except sqlite3.OperationalError: pass` — ver L372-373):

```python
    # Índice para el EXISTS() de has_pending_withdrawal en account_refresh.py
    # (Task 4 del plan de retiro gateado) — sin esto, cada ciclo de 5min hace
    # un table scan de account_withdrawals por cada una de ~800 cuentas LIVE.
    try:
        with db(write=True) as c:
            c.execute(
                "CREATE INDEX IF NOT EXISTS idx_account_withdrawals_account_id "
                "ON account_withdrawals(account_id)"
            )
    except sqlite3.OperationalError:
        pass
```

- [ ] **Step 3: Verificar migración idempotente**

Run: `python -c "import app; app._migrate()"` (dos veces seguidas, no debe tirar error)
Expected: sin excepción en ambas corridas.

- [ ] **Step 4: Correr suite completa para confirmar que no rompe nada existente**

Run: `python -m pytest -q`
Expected: mismo verde que baseline (362 passed) — la migración es aditiva pura, no debería tocar ningún test existente.

- [ ] **Step 5: Actualizar docs/ARCHITECTURE.md (sección BD) y commit**

Agregar a la sección de esquema de `accounts`: `withdrawal_ready INTEGER DEFAULT 0` y `withdrawal_institution TEXT` — cuenta de retiro aprobada por BetMexico (cacheado, poblado por `account_refresh.py`, ver Task 5 de este plan).

```bash
git add app.py docs/ARCHITECTURE.md
git commit -m "feat(db): agregar withdrawal_ready/withdrawal_institution + índice account_withdrawals

Cachea si BetMexico tiene cuenta de retiro aprobada (SPEI aterrizado) —
antes solo existía como llamada viva, sin nada persistido para gatear
el botón de retiro del portal sin round-trip a BetMexico en cada render."
```

---

### Task 2: `is_hot_account()` — lógica pura (TDD)

**Files:**
- Modify: `account_refresh.py` (agregar función nueva, cerca de `_exp_int`, L135-141)
- Test: `test_account_refresh.py` (tests YA ESCRITOS en working tree — ver sección `# ── is_hot_account` al final del archivo. Si no están, usar el bloque de Step 1 tal cual).

**Interfaces:**
- Consumes: nada (función pura).
- Produces: `is_hot_account(row: dict, now_iso: str) -> bool`. `row` trae `balance_real` (float|None), `locked_until` (str ISO8601|None), `has_pending_withdrawal` (bool). Usado por Task 3 y Task 4.

- [ ] **Step 1: Confirmar/escribir los tests (ya deberían existir sin commitear)**

En `test_account_refresh.py`, tras el import agregar `is_hot_account` (ya está: `from account_refresh import select_refresh_candidates_healthy, is_hot_account, DEFAULT_GRADES`). Los tests (ya escritos, sección final del archivo):

```python
NOW_ISO = "2026-08-04T12:00:00+00:00"

def _row(*, balance_real=0, locked_until=None, has_pending_withdrawal=False):
    return {
        "balance_real": balance_real,
        "locked_until": locked_until,
        "has_pending_withdrawal": has_pending_withdrawal,
    }

def test_hot_por_balance_alto():
    assert is_hot_account(_row(balance_real=50.01), NOW_ISO) is True

def test_no_hot_balance_50_exacto():
    assert is_hot_account(_row(balance_real=50.0), NOW_ISO) is False

def test_no_hot_balance_bajo_sin_lock_sin_retiro():
    assert is_hot_account(_row(balance_real=10.0), NOW_ISO) is False

def test_hot_por_ventana_de_autolock_activa():
    assert is_hot_account(_row(locked_until="2026-08-04T13:00:00+00:00"), NOW_ISO) is True

def test_no_hot_ventana_de_autolock_vencida():
    assert is_hot_account(_row(locked_until="2026-08-04T11:00:00+00:00"), NOW_ISO) is False

def test_hot_por_retiro_pendiente():
    assert is_hot_account(_row(has_pending_withdrawal=True), NOW_ISO) is True

def test_no_hot_sin_ninguna_señal():
    assert is_hot_account(_row(), NOW_ISO) is False
```

- [ ] **Step 2: Correr los tests, confirmar que fallan (RED)**

Run: `python -m pytest test_account_refresh.py -k hot -v`
Expected: FAIL — `ImportError: cannot import name 'is_hot_account'`

- [ ] **Step 3: Implementar `is_hot_account` en `account_refresh.py`**

Insertar después de `_exp_int` (L135-141):

```python
def is_hot_account(row: Dict[str, Any], now_iso: str) -> bool:
    """Cuenta que DEBE refrescarse siempre, sin importar lock/grade/pool/
    batch_max (Robert, 2026-08-04): balance_real>$50, ventana de autolock
    post-depósito activa (locked_until en el futuro — dinero de un depósito
    del mismo proceso aún sin asentar), o retiro en curso sin liberar
    (has_pending_withdrawal — hasta que status_api==6 lo saca de aquí).
    `locked_until` compara lexicográficamente contra `now_iso`: ambos son
    ISO8601 en UTC, mismo formato, el orden lexicográfico coincide con el
    cronológico."""
    balance = float(row.get("balance_real") or 0)
    if balance > 50:
        return True
    locked_until = row.get("locked_until")
    if locked_until and str(locked_until) > now_iso:
        return True
    if row.get("has_pending_withdrawal"):
        return True
    return False
```

- [ ] **Step 4: Correr los tests, confirmar verde (GREEN)**

Run: `python -m pytest test_account_refresh.py -k hot -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add account_refresh.py test_account_refresh.py
git commit -m "feat(account_refresh): agregar is_hot_account (lógica pura, TDD)

Define qué hace 'caliente' a una cuenta para el refresh en tiempo real:
balance>\$50, depósito reciente sin asentar, o retiro en curso sin liberar."
```

---

### Task 3: Hot-bypass en `select_refresh_candidates_healthy` (TDD)

**Files:**
- Modify: `account_refresh.py:82-132` (reemplaza la función completa — también limpia un dead-code: las líneas 128-132 del original tienen el `sort`+`return` DUPLICADO, la segunda copia es inalcanzable)
- Test: `test_account_refresh.py` (tests ya escritos — ver bloque "Cuentas calientes" antes de la sección `is_hot_account`)

**Interfaces:**
- Consumes: `is_hot_account` (Task 2). Cada `row` en `rows` ahora puede traer `row["hot"]` (bool, precalculado por el caller — Task 4 lo puebla; los tests lo pasan directo vía el helper `_acc(..., hot=True)`).
- Produces: `select_refresh_candidates_healthy(rows, now, *, batch_max, grades, sa_tokens=None) -> List[dict]` — MISMA firma que hoy, pero las filas con `hot=True` van SIEMPRE primero en el resultado, sin contar contra `batch_max` ni pasar por los filtros de lock/grade/pool.

- [ ] **Step 1: Confirmar/escribir los tests (ya deberían existir)**

En `test_account_refresh.py`, `_acc()` ya acepta `hot=False` como kwarg. Tests (ya escritos, sección "Cuentas calientes"):

```python
def test_hot_lockeada_por_operador_no_sa_es_candidata():
    got = _run([_acc("hot@x.com", jwt_exp=NOW + H, locked_by=555, hot=True)])
    assert [r["email"] for r in got] == ["hot@x.com"]

def test_hot_grade_no_util_es_candidata():
    got = _run([_acc("hot@x.com", grade="D", jwt_exp=NOW + H, hot=True)])
    assert [r["email"] for r in got] == ["hot@x.com"]

def test_hot_no_publicada_es_candidata():
    got = _run([_acc("hot@x.com", jwt_exp=NOW + H, published=0, hot=True)])
    assert [r["email"] for r in got] == ["hot@x.com"]

def test_hot_sin_jwt_vigente_no_es_candidata():
    got = _run([_acc("hot@x.com", jwt_exp=NOW - H, hot=True)])
    assert got == []

def test_hot_no_live_no_es_candidata():
    got = _run([_acc("hot@x.com", status="DEAD", jwt_exp=NOW + H, hot=True)])
    assert got == []

def test_hot_ignora_batch_max():
    normales = [_acc(f"n{i}@x.com", jwt_exp=NOW + H) for i in range(12)]
    hots = [_acc(f"h{i}@x.com", jwt_exp=NOW + H, locked_by=1, hot=True) for i in range(3)]
    got = _run(normales + hots, batch_max=12)
    assert len(got) == 15
    assert {r["email"] for r in got if r["email"].startswith("h")} == {f"h{i}@x.com" for i in range(3)}

def test_hot_va_primero_en_el_resultado():
    normal = _acc("normal@x.com", jwt_exp=NOW + H, last_checked_at="2026-01-01")
    hot = _acc("hot@x.com", jwt_exp=NOW + H, locked_by=1, hot=True, last_checked_at="2026-06-01")
    got = _run([normal, hot])
    assert [r["email"] for r in got] == ["hot@x.com", "normal@x.com"]
```

Todos los tests EXISTENTES (`test_jwt_vigente_es_candidata`, `test_lockeada_por_operador_se_excluye`, etc.) deben seguir pasando sin modificación — son la regresión que protege el comportamiento actual para cuentas NO hot.

- [ ] **Step 2: Correr, confirmar que los tests nuevos fallan (los existentes siguen verdes)**

Run: `python -m pytest test_account_refresh.py -v`
Expected: los 7 tests de `hot` fallan (comportamiento no implementado aún), el resto (14 tests previos) pasa.

- [ ] **Step 3: Reemplazar `select_refresh_candidates_healthy` completa**

Reemplazar `account_refresh.py` líneas 82-132 (función completa, incluyendo el dead-code duplicado del final) por:

```python
def select_refresh_candidates_healthy(
    rows: List[Dict[str, Any]],
    now: int,
    *,
    batch_max: int,
    grades: Set[str],
    sa_tokens: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """Filtra + ordena + limita las cuentas a refrescar este ciclo.

    Regla normal: viva, útil (grade en `grades`, publicada), NO lockeada por
    un operador, y con JWT que SIGUE vigente ahora. Orden: `last_checked_at`
    ascendente (la más desactualizada primero).

    Excepción RESERVADA_SA: pool=0 + locked_by del SA sí es candidata.

    Regla "hot" (Robert, 2026-08-04): una fila con `row["hot"]=True` (ver
    `is_hot_account`) SIEMPRE es candidata — bypassea lock/grade/pool y NO
    cuenta contra `batch_max` — solo requiere estar LIVE y tener JWT vigente
    (sin eso no hay forma de refrescarla). Van primero en el resultado.
    """
    sa_tokens = set(sa_tokens or [])
    hot: List[Dict[str, Any]] = []
    normal: List[Dict[str, Any]] = []
    for r in rows:
        if (r.get("status") or "") != "LIVE":
            continue
        exp = _exp_int(r.get("jwt_expires_at"))
        if exp <= now:
            continue  # sin JWT vigente → no es candidata (la toca jwt_keeper)

        if r.get("hot"):
            hot.append(r)
            continue

        grade = r.get("grade") or ""
        if grade not in grades:
            continue
        locked_by = r.get("locked_by")
        is_sa_reserved = (
            not r.get("published_to_pool")
            and str(locked_by).lower() in sa_tokens
        )
        if not is_sa_reserved:
            if not r.get("published_to_pool"):
                continue
            if locked_by is not None:
                continue
        normal.append(r)

    hot.sort(key=lambda r: (r.get("last_checked_at") or ""))
    normal.sort(key=lambda r: (r.get("last_checked_at") or ""))
    return hot + normal[:batch_max]
```

- [ ] **Step 4: Correr toda la suite de `test_account_refresh.py`, confirmar verde**

Run: `python -m pytest test_account_refresh.py -v`
Expected: 21 passed (14 existentes + 7 nuevos de hot).

- [ ] **Step 5: Commit**

```bash
git add account_refresh.py test_account_refresh.py
git commit -m "feat(account_refresh): bypass de filtros para cuentas hot en select_refresh_candidates_healthy

Las cuentas hot (balance>\$50, autolock activo, retiro en curso) ahora
se refrescan siempre — antes el loop las EXCLUÍA si estaban lockeadas
por un operador no-SA, que es el caso normal durante depósito/retiro.
De paso elimina un dead-code duplicado (sort+return inalcanzable al
final de la función original)."
```

---

### Task 4: `_load_candidate_rows` — traer balance_real/locked_until/has_pending_withdrawal + computar hot

**Files:**
- Modify: `account_refresh.py:144-178` (`_SELECT_COLS` y `_load_candidate_rows`)
- Test: `test_account_refresh.py` (nuevo test de integración con BD real, usar fixture de `conftest.py`)

**Interfaces:**
- Consumes: `is_hot_account` (Task 2), `app.db()` (context manager existente).
- Produces: `_load_candidate_rows() -> List[dict]` — MISMA firma, pero cada dict ahora incluye `id`, `balance_real`, `locked_until`, `has_pending_withdrawal`, `hot`. Usado por `run_refresh_cycle` (ya existente, sin cambios en esta task).

- [ ] **Step 1: Escribir el test de integración (RED)**

Agregar a `test_account_refresh.py` (requiere `db_conn` o fixture equivalente de `conftest.py` — revisar el fixture existente antes de escribir, seguir el mismo patrón que usa `test_a1_estados.py` para poblar `accounts`):

```python
import time as _time
from datetime import datetime, timezone as _tz
import account_refresh as _ar


def test_load_candidate_rows_marca_hot_por_balance(db_conn):
    now = int(_time.time())
    db_conn.execute(
        "INSERT INTO accounts (email, status, grade, jwt_expires_at, "
        "published_to_pool, balance_real) VALUES (?,?,?,?,?,?)",
        ("hot@x.com", "LIVE", "B", now + 3600, 1, 75.0),
    )
    db_conn.commit()
    rows = _ar._load_candidate_rows()
    row = next(r for r in rows if r["email"] == "hot@x.com")
    assert row["hot"] is True


def test_load_candidate_rows_marca_hot_por_retiro_pendiente(db_conn):
    now = int(_time.time())
    cur = db_conn.execute(
        "INSERT INTO accounts (email, status, grade, jwt_expires_at, "
        "published_to_pool, balance_real) VALUES (?,?,?,?,?,?)",
        ("wd@x.com", "LIVE", "B", now + 3600, 1, 0.0),
    )
    acc_id = cur.lastrowid
    db_conn.execute(
        "INSERT INTO account_withdrawals (account_id, transaction_id, amount, created_at) "
        "VALUES (?,?,?,?)",
        (acc_id, "tx1", 100.0, datetime.now(_tz.utc).isoformat()),
    )
    db_conn.commit()
    rows = _ar._load_candidate_rows()
    row = next(r for r in rows if r["email"] == "wd@x.com")
    assert row["hot"] is True
    assert row["has_pending_withdrawal"] is True


def test_load_candidate_rows_no_hot_normal():
    # cuenta LIVE, publicada, sin balance/lock/retiro — no hot
    now = int(_time.time())
    import app
    with app.db(write=True) as c:
        c.execute(
            "INSERT INTO accounts (email, status, grade, jwt_expires_at, "
            "published_to_pool, balance_real) VALUES (?,?,?,?,?,?)",
            ("normal@x.com", "LIVE", "B", now + 3600, 1, 5.0),
        )
    rows = _ar._load_candidate_rows()
    row = next(r for r in rows if r["email"] == "normal@x.com")
    assert row["hot"] is False
```

**Nota para quien ejecute:** revisar primero cómo `conftest.py` expone la conexión de test (fixture `db_conn` o el patrón que ya usan `test_account_touch.py`/`test_jwt_keeper.py` — todos insertan contra la misma BD en memoria que usa `app.db()`). Ajustar el fixture usado en los 3 tests arriba a lo que el conftest real ofrezca — el contrato (insertar fila, llamar `_load_candidate_rows()`, verificar `hot`) no cambia.

- [ ] **Step 2: Correr, confirmar que fallan**

Run: `python -m pytest test_account_refresh.py -k load_candidate -v`
Expected: FAIL — `has_pending_withdrawal`/`hot` no existen en las filas devueltas hoy (el SELECT actual no las trae).

- [ ] **Step 3: Reemplazar `_SELECT_COLS` y `_load_candidate_rows`**

Reemplazar `account_refresh.py` líneas 144-178 por:

```python
# ── I/O de BD (aislado; usa el context manager de app) ────────────────────────
_SELECT_COLS = ("id", "email", "status", "grade", "jwt_expires_at",
                "locked_by", "published_to_pool", "last_checked_at",
                "balance_real", "locked_until")

_PENDING_WD_EXISTS_SQL = (
    "EXISTS(SELECT 1 FROM account_withdrawals w WHERE w.account_id = accounts.id "
    "AND (w.status_api IS NULL OR (w.status_api >= 0 AND w.status_api != 6)))"
)


def _load_candidate_rows() -> List[Dict[str, Any]]:
    """Trae TODAS las cuentas LIVE (universo ~800-900, ver docstring del
    módulo) y computa `hot` en Python vía `is_hot_account` — el filtro
    grade/pool/lock para cuentas NO-hot sigue viviendo únicamente en
    `select_refresh_candidates_healthy` (una sola fuente de verdad, antes
    estaba parcialmente duplicado en el WHERE de este SELECT).

    Antes el WHERE excluía cuentas no publicadas/lockeadas a nivel SQL —
    eso escondía por completo las cuentas hot que están lockeadas por un
    operador no-SA (el caso normal durante depósito/retiro en curso).
    """
    import app  # lazy: evita ciclo de import
    now_iso = datetime.now(timezone.utc).isoformat()
    with app.db() as conn:
        cur = conn.execute(
            f"SELECT {', '.join(_SELECT_COLS)}, "
            f"{_PENDING_WD_EXISTS_SQL} AS has_pending_withdrawal "
            "FROM accounts WHERE status='LIVE'"
        )
        rows = [dict(row) for row in cur.fetchall()]
    for r in rows:
        r["has_pending_withdrawal"] = bool(r.get("has_pending_withdrawal"))
        r["hot"] = is_hot_account(r, now_iso)
    return rows
```

- [ ] **Step 4: Correr, confirmar verde**

Run: `python -m pytest test_account_refresh.py -v`
Expected: 24 passed (21 previos + 3 nuevos).

- [ ] **Step 5: Correr suite completa (por si algún otro test depende de `_SELECT_COLS`/`_load_candidate_rows`)**

Run: `python -m pytest -q`
Expected: verde completo.

- [ ] **Step 6: Commit**

```bash
git add account_refresh.py test_account_refresh.py
git commit -m "feat(account_refresh): _load_candidate_rows trae balance/lock/retiro-pendiente y computa hot

Universo pasa de 'LIVE+publicada+libre' a 'LIVE' completo (~800-900
cuentas, filtro barato por índice de status) — el filtro fino para
cuentas NO-hot sigue siendo exclusivo de select_refresh_candidates_healthy,
una sola fuente de verdad en vez de duplicarlo en SQL."
```

---

### Task 5: `run_refresh_cycle` — persistir `withdrawal_ready`/`withdrawal_institution` + broadcast SSE

**Files:**
- Modify: `account_refresh.py:214-293` (dentro del loop `for i, r in enumerate(cands):`, después del bloque que persiste balance — L269-287)
- Test: `test_account_refresh.py` (test de integración con `mock_bmx_transport` — mismo fixture que usa `test_withdrawals.py`)

**Interfaces:**
- Consumes: `withdrawals.get_bank_accounts(jwt, proxy_url, transport=None)` (existente, `withdrawals.py:83-126`), `withdrawals.NoApprovedWithdrawalAccount`/`MultipleApprovedAccounts` (existentes).
- Produces: helpers `_db_get_withdrawal_ready(email) -> Optional[int]` y `_db_set_withdrawal_ready(email, ready: bool, institution: Optional[str]) -> None` en `account_refresh.py`. Evento SSE nuevo `kind: "withdrawal_ready_changed"` — documentar en `docs/SSE_EVENTS.md`.

- [ ] **Step 1: Escribir el test (RED)**

Este test necesita mockear `BetmexicoApiChecker`/`get_bank_accounts` — dado que `run_refresh_cycle` ya importa `betmexico_login_api`/`betmexico_db`/`prewarm`/`proxy_pool` dinámicamente (L204-212) y esos módulos no tienen mocks triviales en este repo, el patrón más simple es testear el HELPER nuevo de forma aislada (no todo `run_refresh_cycle` end-to-end, que ya no se testea end-to-end hoy tampoco — confirmarlo leyendo si existe algún test de `run_refresh_cycle` antes de escribir uno nuevo; si no existe, seguir el mismo nivel de cobertura):

```python
def test_db_set_and_get_withdrawal_ready(db_conn):
    import app
    import time as _time
    now = int(_time.time())
    with app.db(write=True) as c:
        c.execute(
            "INSERT INTO accounts (email, status, grade, jwt_expires_at, published_to_pool) "
            "VALUES (?,?,?,?,?)",
            ("wr@x.com", "LIVE", "B", now + 3600, 1),
        )
    assert _ar._db_get_withdrawal_ready("wr@x.com") == 0
    _ar._db_set_withdrawal_ready("wr@x.com", True, "HEY BANCO")
    assert _ar._db_get_withdrawal_ready("wr@x.com") == 1
    with app.db() as c:
        row = c.execute(
            "SELECT withdrawal_ready, withdrawal_institution FROM accounts WHERE email=?",
            ("wr@x.com",),
        ).fetchone()
    assert row["withdrawal_ready"] == 1
    assert row["withdrawal_institution"] == "HEY BANCO"
```

- [ ] **Step 2: Correr, confirmar que falla**

Run: `python -m pytest test_account_refresh.py -k withdrawal_ready -v`
Expected: FAIL — `AttributeError: module 'account_refresh' has no attribute '_db_get_withdrawal_ready'`

- [ ] **Step 3: Implementar los helpers de BD**

Agregar a `account_refresh.py`, cerca de `_load_candidate_rows`:

```python
def _db_get_withdrawal_ready(email: str) -> int:
    import app
    with app.db() as c:
        row = c.execute(
            "SELECT withdrawal_ready FROM accounts WHERE email=?", (email,)
        ).fetchone()
    return int(row["withdrawal_ready"] or 0) if row else 0


def _db_set_withdrawal_ready(email: str, ready: bool, institution: Optional[str]) -> None:
    import app
    with app.db(write=True) as c:
        c.execute(
            "UPDATE accounts SET withdrawal_ready=?, withdrawal_institution=? WHERE email=?",
            (1 if ready else 0, institution, email),
        )
```

- [ ] **Step 4: Correr, confirmar verde**

Run: `python -m pytest test_account_refresh.py -k withdrawal_ready -v`
Expected: 1 passed.

- [ ] **Step 5: Enganchar la verificación dentro de `run_refresh_cycle`**

En `account_refresh.py`, dentro del `try` que hoy persiste balance (L269-287), justo después del bloque `_broadcast({"kind": "account_refreshed", ...})` (antes del `except Exception as e:` que cierra ese try en L288):

```python
            # withdrawal_ready: PASO1 de withdrawals.py es la única fuente de
            # verdad de "¿aterrizó el SPEI?" — se verifica en el mismo ciclo
            # que ya refresca balance con el mismo JWT/proxy, sin llamada extra
            # de login/captcha. Robert, 2026-08-04: gatea el botón de retiro
            # del portal sin exponer un round-trip vivo a BetMexico en cada render.
            try:
                from withdrawals import (
                    get_bank_accounts, NoApprovedWithdrawalAccount, MultipleApprovedAccounts,
                )
                ready: Optional[bool] = None
                institution: Optional[str] = None
                try:
                    approved = await get_bank_accounts(jwt, proxy_url)
                    ready, institution = True, approved[0].get("institutionName")
                except NoApprovedWithdrawalAccount:
                    ready, institution = False, None
                except MultipleApprovedAccounts:
                    # SPEI SÍ aterrizó (hay >1 cuenta aprobada) — el operador puede
                    # intentar retirar; execute_withdrawal decide con más detalle
                    # en el momento del click. No se puede elegir "la" institución.
                    ready, institution = True, "Múltiples cuentas — revisar"
                except Exception as e:
                    logger.info(f"[account_refresh] {email} check withdrawal_ready falló: {str(e)[:120]}")

                if ready is not None:
                    prev = _db_get_withdrawal_ready(email)
                    if prev != (1 if ready else 0):
                        _db_set_withdrawal_ready(email, ready, institution)
                        try:
                            from app import _broadcast
                            _broadcast({
                                "type": "activity", "kind": "withdrawal_ready_changed",
                                "ts": datetime.now(timezone.utc).isoformat(),
                                "email": email, "withdrawal_ready": ready,
                                "withdrawal_institution": institution,
                            })
                        except Exception:
                            pass
            except Exception as e:
                logger.warning(f"[account_refresh] {email} withdrawal_ready check error: {str(e)[:120]}")
```

- [ ] **Step 6: Correr suite completa**

Run: `python -m pytest -q`
Expected: verde completo.

- [ ] **Step 7: Documentar el evento SSE nuevo + commit**

Agregar a `docs/SSE_EVENTS.md`: `withdrawal_ready_changed` — `{type:"activity", kind:"withdrawal_ready_changed", email, withdrawal_ready: bool, withdrawal_institution: str|null}`. Emitido por `account_refresh.run_refresh_cycle` SOLO cuando el valor cambia respecto al ciclo anterior (no en cada ciclo).

```bash
git add account_refresh.py docs/SSE_EVENTS.md test_account_refresh.py
git commit -m "feat(account_refresh): persistir withdrawal_ready/institution + SSE en cambio

Reusa el JWT/proxy ya vivo del ciclo de refresh de balance (mismo request
budget) para verificar PASO1 de withdrawals.py y cachear el resultado —
antes 'SPEI aterrizado' solo existía como llamada viva sin cachear."
```

---

### Task 6: Exponer `withdrawal_ready`/`withdrawal_institution`/`curp` en `/api/operator/my-accounts`

**Files:**
- Modify: `app.py:4236-4270` (`operator_my_accounts`)
- Test: `tests/test_api.py` (o el archivo de test que ya cubra `/api/operator/my-accounts` — buscar con `grep -rn "operator/my-accounts" tests/ test_*.py` antes de escribir, seguir el patrón existente si hay uno)

**Interfaces:**
- Consumes: columnas `accounts.withdrawal_ready`, `accounts.withdrawal_institution`, `accounts.curp` (existente — confirmado en `app.py:1026`).
- Produces: cada item de `GET /api/operator/my-accounts` → `accounts[]` ahora incluye `withdrawal_ready` (bool), `withdrawal_institution` (str|null), `curp` (str|null). Consumido por Task 7 (`portal.js`).

- [ ] **Step 1: Localizar o escribir el test existente de este endpoint**

Run: `grep -rn "operator/my-accounts\|operator_my_accounts" test_*.py tests/*.py`

Si existe un test que arma una cuenta de prueba y llama al endpoint, extenderlo con las 3 columnas nuevas. Si NO existe ninguno, escribir:

```python
def test_operator_my_accounts_incluye_withdrawal_ready_e_institucion(client, db_conn):
    # client/db_conn: usar el fixture real de conftest.py que ya monte accounts +
    # deposit_attempts con status='approved' (mismo requisito que usa la query
    # actual del endpoint, ver app.py:4248 JOIN deposit_attempts).
    ...
    r = client.get("/api/operator/my-accounts", headers=auth_headers)
    assert r.status_code == 200
    acc = r.json()["accounts"][0]
    assert "withdrawal_ready" in acc
    assert "withdrawal_institution" in acc
    assert "curp" in acc
```

**Nota para quien ejecute:** revisar primero `conftest.py` (fixtures `client`, sesión autenticada) y CUALQUIER test existente de `/api/operator/my-accounts` o `/api/operator/accounts/{id}/withdraw` para copiar el setup exacto (headers de sesión, cómo se inserta `deposit_attempts` con `status='approved'`) — no inventar un fixture nuevo si ya hay uno que arma este escenario.

- [ ] **Step 2: Correr, confirmar que falla (los campos no están en la respuesta hoy)**

Run: `python -m pytest -k "my_accounts and withdrawal_ready" -v`
Expected: FAIL — `AssertionError` o `KeyError`.

- [ ] **Step 3: Agregar las columnas al SELECT (ambas ramas, SA y operador)**

En `app.py:4236-4262`, en AMBOS `SELECT DISTINCT` (rama `is_sa` y rama `else`), agregar `a.withdrawal_ready, a.withdrawal_institution, a.curp` a la lista de columnas — por ejemplo la rama operador queda:

```python
            rows = c.execute(
                "SELECT DISTINCT a.id, a.email, a.balance_real, a.balance_bonos, "
                "a.last_deposit_amount, a.last_deposit_date, a.grade, "
                "a.locked_by, a.locked_until, a.status, "
                "a.withdrawal_ready, a.withdrawal_institution, a.curp, "
                "c.clabe AS clabe_stp "
                "FROM deposit_attempts d JOIN accounts a ON d.account_email = a.email "
                "LEFT JOIN account_deposit_clabes c ON (a.id = c.account_id AND (c.integration = 'STP' OR c.integration = '2')) "
                "WHERE d.operator_id=? AND d.status='approved' ORDER BY a.last_deposit_date DESC",
                (operator_id,)
            ).fetchall()
```

(Mismo cambio en la rama `is_sa`, línea equivalente.)

Y en el post-proceso (L4264-4269), castear el bool:

```python
        for r in rows:
            d = dict(r)
            d["is_locked"] = bool(d.get("locked_by"))
            d["withdrawal_ready"] = bool(d.get("withdrawal_ready"))
            d.pop("locked_by", None)
            d.pop("locked_until", None)
            result.append(d)
```

- [ ] **Step 4: Correr, confirmar verde**

Run: `python -m pytest -k "my_accounts and withdrawal_ready" -v`
Expected: passed.

- [ ] **Step 5: Correr suite completa**

Run: `python -m pytest -q`
Expected: verde completo.

- [ ] **Step 6: Actualizar docs/ENDPOINTS.md y commit**

Agregar a la entrada de `GET /api/operator/my-accounts` los 3 campos nuevos en el shape de respuesta.

```bash
git add app.py docs/ENDPOINTS.md test_api.py  # o el archivo de test que corresponda
git commit -m "feat(api): exponer withdrawal_ready/withdrawal_institution/curp en /api/operator/my-accounts

Campos que el portal necesita para gatear el botón Retirar y mostrar
CURP/método de retiro sin exponer historial de transacciones."
```

---

### Task 7: Gatear botón "Retirar" en `portal.js` + mostrar CURP/institución

**Files:**
- Modify: `static/portal.js` (`renderAccountCard`, actualmente L307-341 — confirmar línea exacta al abrir el archivo, pudo moverse por el commit `cdc208e` de Track A)
- Test: verificación manual en navegador (no hay harness JS de DOM en este repo — `pantalla_logic.test.js` solo cubre lógica pura). Usar `preview_start` + `read_page`/`javascript_tool`.

**Interfaces:**
- Consumes: `acc.withdrawal_ready` (bool), `acc.withdrawal_institution` (str|null), `acc.curp` (str|null) — de Task 6.
- Produces: atributo `data-ready` en `.btn-withdraw`, botón `disabled` cuando `!acc.withdrawal_ready`.

- [ ] **Step 1: Localizar `renderAccountCard` actual (línea puede haber cambiado)**

Run: `grep -n "function renderAccountCard\|btn-withdraw" static/portal.js`

- [ ] **Step 2: Modificar el render del botón + agregar CURP/institución al meta**

Reemplazar el bloque `acc-meta` y el botón `btn-withdraw` (contenido exacto, adaptar a la indentación real encontrada en Step 1):

```javascript
    const curpHtml = acc.curp ? '<div>• CURP: ' + acc.curp + '</div>' : '';
    const wdInstHtml = acc.withdrawal_ready
      ? '<div>• Retiro: <span style="color:var(--green-bright)">' + (acc.withdrawal_institution || 'Aprobado') + '</span></div>'
      : '<div style="color:var(--text-dim)">• Retiro: esperando SPEI…</div>';

    return '<div class="acc-card' + (isLocked ? ' locked' : '') + '" data-id="' + acc.id + '" data-email="' + (acc.email || '') + '">' +
      '<div class="acc-top">' +
        '<span class="acc-email">' + (acc.email || '') + '</span>' +
        '<span class="acc-grade ' + gradeCls + '">' + grade + '</span>' +
      '</div>' +
      '<div class="acc-balance">' + fmtMoney(balReal) + ' <span class="cur">MXN</span></div>' +
      '<div class="acc-meta">' +
        '<div>• Bonos: ' + fmtMoney(balBonos) + '</div>' +
        '<div>• Último: ' + lastDep + (lastDate ? ' (' + lastDate + ')' : '') + '</div>' +
        curpHtml + wdInstHtml +
        (isLocked ? '<div class="acc-locked-badge">🔒 Bloqueada</div>' : '') +
      '</div>' +
      clabeHtml +
      '<div class="acc-actions">' +
        '<button class="btn btn-sm btn-primary btn-withdraw"' +
          (acc.withdrawal_ready ? '' : ' disabled title="Esperando confirmación de SPEI en BetMexico"') +
          ' data-bal="' + balReal + '">💸 Retirar</button>' +
        (isLocked ? '<button class="btn btn-sm btn-danger btn-release">🔓 Liberar</button>' : '') +
      '</div>' +
    '</div>';
```

- [ ] **Step 3: Reaccionar al evento SSE `withdrawal_ready_changed` (Task 5) para refrescar sin reload completo**

En `onBusEvent` (`portal.js`, cerca de la línea que ya maneja `account_refreshed`/`withdrawal`/`withdrawal_status`), agregar `withdrawal_ready_changed` a la misma condición que dispara `loadAccounts()`:

```javascript
    if (ev.type === 'activity' && (ev.kind === 'account_refreshed' || ev.kind === 'withdrawal' || ev.kind === 'withdrawal_status' || ev.kind === 'withdrawal_ready_changed')) {
      if (!activeMissionId) loadAccounts();
    }
```

- [ ] **Step 4: Verificar en navegador (server local con DB de prueba)**

`preview_start` con el server local (ver `.claude/launch.json` si existe, o `uvicorn app:app --reload` contra una copia de BD con al menos 1 cuenta con `withdrawal_ready=0` y otra con `=1`). Confirmar vía `read_page`: el botón de la cuenta `ready=0` tiene atributo `disabled` y el tooltip correcto; la cuenta `ready=1` tiene el botón habilitado y muestra la institución.

- [ ] **Step 5: `node --check` + commit**

```bash
node --check static/portal.js
git add static/portal.js
git commit -m "feat(portal): gatear botón Retirar por withdrawal_ready + mostrar CURP/institución

El botón ya no es siempre clickeable (antes fallaba server-side con
NoApprovedWithdrawalAccount) — ahora refleja el estado real cacheado
por account_refresh.py, con tooltip explicando por qué está deshabilitado."
```

---

### Task 8: Extender `/api/accounts/{id}/withdraw/status/{tx_id}` a operadores dueños

**Files:**
- Modify: `app.py:3642-3654` (chequeo de rol al inicio de `withdraw_status`)
- Test: buscar/extender test existente de este endpoint (`grep -rn "withdraw/status" test_*.py tests/*.py`)

**Interfaces:**
- Consumes: `_visible_emails(user, c)` (helper existente, mismo usado por `operator_release_account`/`operator_withdraw` en `app.py:4283-4286`/`4310-4314`).
- Produces: `GET /api/accounts/{account_id}/withdraw/status/{tx_id}` — MISMO shape de respuesta, pero ahora 200 para operador dueño de la cuenta (antes 403 siempre), 403 si el operador no es dueño, 200 sin cambios para SA.

- [ ] **Step 1: Localizar el test existente (si hay) del chequeo 403**

Run: `grep -rn "withdraw/status\|withdraw_status" test_*.py tests/*.py`

- [ ] **Step 2: Escribir/extender el test (RED)**

```python
def test_withdraw_status_operador_dueno_puede_consultar(client, db_conn, operator_session):
    # operator_session: sesión de operador (no-SA) dueño de la cuenta —
    # seguir el patrón que ya usa test_withdrawals_endpoints.py para operator_withdraw.
    ...
    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/{tx_id}", headers=operator_headers)
    assert r.status_code == 200


def test_withdraw_status_operador_ajeno_403(client, db_conn, operator_session):
    # cuenta de OTRO operador
    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/{tx_id}", headers=operator_headers)
    assert r.status_code == 403
```

**Nota para quien ejecute:** copiar el setup de sesión/fixtures de `test_withdrawals_endpoints.py` (ya cubre `operator_withdraw` con ownership) — no inventar un fixture de sesión de operador nuevo si ya existe uno ahí.

- [ ] **Step 3: Correr, confirmar que el primer test falla (403 hoy para cualquier no-SA)**

Run: `python -m pytest -k withdraw_status_operador -v`
Expected: `test_withdraw_status_operador_dueno_puede_consultar` FAILS (recibe 403).

- [ ] **Step 4: Relajar el chequeo de rol**

En `app.py:3643-3646`, reemplazar:

```python
async def withdraw_status(account_id: int, tx_id: str, user: dict = Depends(require_session)):
    if user.get("role") != "superadmin":
        raise HTTPException(403, "Solo superadmin")
    with db() as c:
        acc = c.execute(
            "SELECT id, jwt_token FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
```

por:

```python
async def withdraw_status(account_id: int, tx_id: str, user: dict = Depends(require_session)):
    with db() as c:
        acc = c.execute(
            "SELECT id, email, jwt_token FROM accounts WHERE id=?", (account_id,)
        ).fetchone()
        if user.get("role") != "superadmin":
            vis = _visible_emails(user, c)
            if not acc or (vis is not None and acc["email"] not in vis):
                raise HTTPException(403, "No tienes permiso sobre esta cuenta")
```

(Nota: el chequeo `if not acc` original vivía más abajo, en `if not acc or not row:` L3653 — queda intacto, este cambio solo mueve el `SELECT` un poco antes para poder resolver `email` y no duplica la validación de existencia.)

- [ ] **Step 5: Correr, confirmar verde**

Run: `python -m pytest -k withdraw_status_operador -v`
Expected: 2 passed.

- [ ] **Step 6: Correr suite completa**

Run: `python -m pytest -q`
Expected: verde completo (confirmar que ningún test SA-only de este endpoint se rompió).

- [ ] **Step 7: Actualizar docs/ENDPOINTS.md y commit**

Actualizar la entrada de `GET /api/accounts/{account_id}/withdraw/status/{tx_id}`: de "SA-only" a "SA o operador dueño de la cuenta (ownership vía `_visible_emails`)".

```bash
git add app.py docs/ENDPOINTS.md test_withdrawals_endpoints.py
git commit -m "feat(api): permitir a operadores dueños consultar withdraw/status

Antes solo SA podía pollear el estado de un retiro (403 para cualquier
operador) — el portal necesita esto para trackear 'liberado por completo'
sin depender de que SA abra La Pantalla."
```

---

### Task 9: Poll de estado en `portal.js` tras disparar retiro

**Files:**
- Modify: `static/portal.js` (`showWithdrawModal`, actualmente cerca de L390+ — confirmar línea exacta)

**Interfaces:**
- Consumes: `GET /api/accounts/{id}/withdraw/status/{tx_id}` (Task 8, ahora accesible a operadores).
- Produces: mismo patrón que `pantalla.js` (`WD_POLL_FAST_MS`/`WD_POLL_SLOW_MS`, ya verificados en `static/pantalla.js:668-669` = 15000/60000) pero scoped a `portal.js`.

- [ ] **Step 1: Agregar constantes + estado de poll**

Cerca de las demás variables de módulo en `portal.js` (junto a `let sse = null;` etc.):

```javascript
  const WD_POLL_FAST_MS = 15000;
  let wdPollTimer = null;
```

- [ ] **Step 2: Agregar la función de poll (mismo patrón que `pantalla.js:610-663`, simplificado — sin cache de detalle, portal no tiene panel de detalle)**

```javascript
  function stopWithdrawPoll() {
    if (wdPollTimer) { clearInterval(wdPollTimer); wdPollTimer = null; }
  }

  async function fetchWithdrawStatus(accountId, txId, cardEl) {
    try {
      const res = await fetch(apiUrl('/api/accounts/' + accountId + '/withdraw/status/' + txId));
      if (!res.ok) return;
      const st = await res.json();
      const terminal = st.status === 'successful' || st.status === 'completed' || st.status === 'failed';
      if (terminal) {
        stopWithdrawPoll();
        const ok = st.status !== 'failed';
        showToast(ok ? '✅ Retiro liberado' : '❌ Retiro falló', ok ? 'ok' : 'err');
        loadAccounts();
      }
    } catch (_) { /* best-effort, el próximo tick reintenta */ }
  }

  function startWithdrawPoll(accountId, txId, cardEl) {
    stopWithdrawPoll();
    fetchWithdrawStatus(accountId, txId, cardEl);
    wdPollTimer = setInterval(() => fetchWithdrawStatus(accountId, txId, cardEl), WD_POLL_FAST_MS);
  }
```

- [ ] **Step 3: Enganchar tras un retiro exitoso, dentro de `showWithdrawModal` → handler de `confirm.addEventListener('click', ...)`**

En el bloque `if (res.ok) { showToast(...); close(); loadAccounts(); }` (dentro de `showWithdrawModal`), agregar la llamada a `startWithdrawPoll` usando el `transactionId` que ya devuelve la respuesta:

```javascript
        if (res.ok) {
          showToast('Retiro enviado: ' + (d.transactionId || ''), 'ok');
          close();
          loadAccounts();
          if (d.transactionId) startWithdrawPoll(accountId, d.transactionId);
        } else {
```

- [ ] **Step 4: `node --check` + verificación manual en navegador**

`node --check static/portal.js`. Luego, con `preview_start` + una cuenta con retiro simulado pendiente en BD de prueba, confirmar vía `read_network_requests` que el poll golpea el endpoint cada 15s y se detiene al llegar a estado terminal.

- [ ] **Step 5: Commit**

```bash
git add static/portal.js
git commit -m "feat(portal): poll de estado tras disparar retiro (15s hasta terminal)

Antes el portal disparaba el retiro y no volvía a preguntar — el
operador nunca se enteraba de si se liberó. Reusa el mismo patrón
15s que ya existe en pantalla.js, ahora accesible al operador (Task 8)."
```

---

### Task 10: Animación anti-detección (odómetro) para la misión de depósito automático

**Files:**
- Modify: `static/portal.js` (`onMissionEvent`/`renderMission`, actualmente L142-273 tras el fix de Track A — confirmar líneas exactas)

**Interfaces:**
- Consumes: eventos SSE `auto_mission` (existentes, sin cambios de backend en esta task).
- Produces: `missionState.displayPct`/`missionState.displayLabel` — valores INTERPOLADOS que el DOM pinta, nunca los crudos del evento.

**Contexto de diseño (spec parqueada, `docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md`, escrita para retiro automático — mismo patrón aplica a la misión de depósito ya existente):**
> Animación de conteo suave/continuo, sincronizada con el valor real del backend SOLO en checkpoints periódicos (no cada tick), de forma invisible — el valor mostrado es una interpolación visual, no un espejo 1:1 del evento real. Nunca saltos discretos en bloques del monto/intervalo real.

Esta task NO construye el motor de auto-retiro (sigue parqueado, spec sin tocar) — solo aplica el patrón de interpolación visual a la misión de depósito que YA CORRE hoy.

- [ ] **Step 1: Agregar el motor de interpolación (nuevo, sin dependencias del resto del archivo)**

```javascript
  // ── Interpolación de progreso (anti-detección) ──────────────────────────
  // checkpoint real del backend llega en eventos discretos (cada match/completed
  // de scheduling); esto interpola visualmente ENTRE checkpoints con
  // requestAnimationFrame, para que el operador nunca vea el salto discreto
  // real (que delataría cadencia/monto). Robert, 2026-08-04.
  let _rafId = null;
  let _animFrom = 0;
  let _animTo = 0;
  let _animStart = 0;
  const ANIM_DURATION_MS = 2200; // tiempo de "viaje" visual entre checkpoints — NO ligado al intervalo real

  function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

  function animateProgressTo(targetPct, onFrame) {
    if (_rafId) cancelAnimationFrame(_rafId);
    _animFrom = missionState ? (missionState.displayPct || 0) : 0;
    _animTo = Math.max(_animFrom, targetPct); // nunca retrocede visualmente
    _animStart = performance.now();
    function step(now) {
      const elapsed = now - _animStart;
      const t = Math.min(1, elapsed / ANIM_DURATION_MS);
      const val = _animFrom + (_animTo - _animFrom) * easeOutCubic(t);
      if (missionState) missionState.displayPct = val;
      onFrame();
      if (t < 1) { _rafId = requestAnimationFrame(step); } else { _rafId = null; }
    }
    _rafId = requestAnimationFrame(step);
  }

  function stopProgressAnim() {
    if (_rafId) { cancelAnimationFrame(_rafId); _rafId = null; }
  }
```

- [ ] **Step 2: Enganchar en `onMissionEvent` — reemplazar las asignaciones directas de `missionState.pct` por `animateProgressTo`**

Cada línea existente de la forma `missionState.pct = <valor>;` dentro de `onMissionEvent` pasa a disparar la animación en vez de pintar directo. Por ejemplo, el caso `'match'` (hoy `missionState.pct = Math.min(85, 25 + missionState.matches.length * 15);`) pasa a:

```javascript
      case 'match':
        missionState.status = 'matching';
        missionState.matches.push({ email: ev.email, card_tail: ev.card_tail });
        missionState.sub = '✅ <span class="email">' + shortEmail(ev.email) + '</span> ↔ ' + (ev.card_tail || '');
        animateProgressTo(Math.min(85, 25 + missionState.matches.length * 15), renderMission);
        return; // renderMission ya se llama en cada frame del RAF, no de nuevo al final
```

Aplicar el mismo patrón (`animateProgressTo(<mismo cálculo de antes>, renderMission); return;` en vez de asignar `missionState.pct` y caer al `renderMission()` del final de la función) en los casos `'started'/'matching'`, `'logging_in'`, `'scheduling'` (rama `ev.completed != null`), y `'completed'` (pct=100). Los casos que NO cambian pct numérico (`'cooldown'`, `'awaiting_confirmation'`, rama `aborted` de scheduling) siguen cayendo al `renderMission()` normal del final — no tocarlos.

- [ ] **Step 3: `renderMission` usa `displayPct` en vez de `pct` para la barra**

En `renderMission`, cambiar `width:' + (s.pct || 0) + '%'` por `width:' + (s.displayPct != null ? s.displayPct : (s.pct || 0)) + '%'` — fallback a `s.pct` cubre el primer render antes de que cualquier animación haya corrido (ej. al llamar `loadMission()` con datos ya completados desde `/api/deposits/auto/{mid}/status`, que no pasan por `onMissionEvent`).

- [ ] **Step 4: Detener la animación al salir de la misión**

En `exitMission()`, agregar `stopProgressAnim();` junto a `missionState = null;`.

- [ ] **Step 5: Verificación medida en navegador (NO "a ojo" — dirección visual + medición real)**

`preview_start`, disparar (o simular vía consola) una secuencia de eventos `auto_mission` con `pct` saltando en bloques grandes (ej. 15→30→70→85→100). Con `javascript_tool`, verificar que `document.querySelector('.mv-progress-fill').style.width` cambia GRADUALMENTE frame a frame (leer el valor 3-4 veces en ~500ms de diferencia) en vez de saltar directo al valor final — esa es la prueba objetiva de que la interpolación corre, no una apreciación visual.

- [ ] **Step 6: `node --check` + commit**

```bash
node --check static/portal.js
git add static/portal.js
git commit -m "feat(portal): interpolación visual del progreso de misión (anti-detección)

La barra de progreso ya no salta en los bloques discretos reales del
backend (que revelarían el patrón de matching/scheduling) — se anima
suave entre checkpoints con requestAnimationFrame, patrón ya especificado
en docs/plans/2026-08-03-spec-auto-retiro-obfuscado.md para retiro
automático, aplicado aquí a la misión de depósito que ya corre en prod."
```

---

### Task 11 (verificación, sin código): confirmar que el "fetch mínimo" ya está satisfecho

**Files:**
- Modify: `docs/AUDIT.md` (agregar fila)

**Contexto:** Robert pidió que cualquier refresh contra BetMexico traiga solo lo variable (balance, cuenta de retiro, estado), sin re-fetchear constantes ya consolidadas (nombre/dirección). Verificado en `prewarm.py:229-235`: `fetch_mode='balance_only'` (el modo que `account_refresh.py:239` YA usa exclusivamente, confirmado en `checker.fetch_account_details_parallel(jwt, fetch_mode="balance_only")`) por diseño de la API **nunca** trae `fullname`/`items` — ver comentario existente "fullname/items SIEMPRE ausentes por diseño de la API". Esto YA satisface el requisito — no hace falta ningún cambio de código.

- [ ] **Step 1: Confirmar leyendo el código (no solo el comentario)**

Run: `grep -n "fetch_mode" prewarm.py account_refresh.py` — confirmar que `account_refresh.py` es el ÚNICO caller relevante para el ciclo periódico y usa `balance_only` (ya verificado al escribir este plan, re-confirmar no está desactualizado si pasó tiempo entre plan y ejecución).

- [ ] **Step 2: Agregar fila a `docs/AUDIT.md`**

```markdown
| Fetch mínimo contra BetMexico en refresh periódico | ✅ | `account_refresh.py` usa `fetch_mode='balance_only'` (prewarm.py:229-235) — nunca re-fetchea fullname/dirección/constantes, por diseño de la API. Verificado 2026-08-04, sin cambio de código necesario. |
```

- [ ] **Step 3: Commit**

```bash
git add docs/AUDIT.md
git commit -m "docs(audit): confirmar que fetch mínimo contra BetMexico ya está satisfecho

fetch_mode=balance_only (ya en uso exclusivo por account_refresh.py)
nunca trae constantes — no había gap que cerrar, solo faltaba documentarlo."
```

---

## Orquestación (obligatoria — `feedback_planes_orquestacion`)

### Orden de ejecución (bloqueos)

```
Task 1 (migración) ──┬─→ Task 2 (is_hot_account) ─→ Task 3 (bypass) ─→ Task 4 (_load_candidate_rows) ─→ Task 5 (persistir+SSE)
                      │                                                                                        │
                      └─→ Task 6 (my-accounts expone campos) ←──────────────────────────────────────────────┘
                                    │
                                    ├─→ Task 7 (gate botón portal)
                                    │
Task 8 (relajar rol status) ───────┴─→ Task 9 (poll portal)

Task 10 (animación) — independiente, puede correr en paralelo a 6-9 (no comparte archivos backend)
Task 11 (doc) — independiente, puede correr en cualquier momento
```

Task 6 depende de Task 1 (columnas deben existir) pero NO de 2-5 (puede leer `withdrawal_ready` aunque todavía esté en default `0` para todas — el llenado real lo hace Task 5). Si se ejecuta con subagentes en paralelo, Task 6 puede arrancar apenas Task 1 cierra, sin esperar 2-5.

### Modelos por subagente

| Task | Modelo | Justificación |
|---|---|---|
| 1 (migración) | Haiku 4.5 | Mecánico: tupla + CREATE INDEX, patrón ya establecido, cero ambigüedad |
| 2 (is_hot_account) | Sonnet 5 | Lógica pura con TDD, tests ya escritos — implementación directa pero requiere leer bien los tests |
| 3 (bypass select_refresh) | Sonnet 5 | Reescribe función con reglas de negocio (hot vs normal vs RESERVADA_SA) — requiere criterio |
| 4 (_load_candidate_rows) | Sonnet 5 | Toca SQL + integra con Task 2, requiere entender el fixture de test existente antes de escribir |
| 5 (persistir+SSE) | Sonnet 5 | Integra con withdrawals.py (excepciones específicas), maneja el caso MultipleApprovedAccounts con criterio |
| 6 (my-accounts) | Haiku 4.5 | Mecánico: agregar columnas a 2 SELECTs ya existentes, patrón idéntico al de al lado |
| 7 (gate botón) | Sonnet 5 | Frontend con lógica condicional + verificación en navegador |
| 8 (relajar rol) | Sonnet 5 | Cambio de autorización — requiere criterio de seguridad (ownership correcto, no solo "quitar el 403") |
| 9 (poll portal) | Sonnet 5 | Reimplementa un patrón async existente (pantalla.js) en contexto nuevo |
| 10 (animación) | Opus 4.8 | Única task de diseño/UX con riesgo real (mal hecho, sigue revelando cadencia) — vale la inversión |
| 11 (doc) | Haiku 4.5 | Mecánico: confirmar + 1 fila de tabla |

### Goals medibles

- Task 1: `python -c "import app; app._migrate()"` corre 2 veces sin error; suite completa sigue en 362 passed.
- Tasks 2-4: `pytest test_account_refresh.py -v` pasa de 14 → 21 → 24 tests verdes, 0 rotos.
- Task 5: nuevo evento `withdrawal_ready_changed` visible en `docs/SSE_EVENTS.md`; suite completa verde.
- Task 6: response de `/api/operator/my-accounts` incluye las 3 keys nuevas en el JSON (test explícito lo verifica).
- Task 7: en navegador, botón con `disabled` presente cuando `withdrawal_ready=false`, ausente cuando `true` (verificado vía `read_page`, no descripción visual).
- Task 8: 2 tests nuevos verdes (dueño 200, ajeno 403); suite completa verde.
- Task 9: `read_network_requests` muestra el endpoint de status golpeado cada ~15s tras un retiro simulado, y el poll se detiene en estado terminal (0 requests 20s después de terminal).
- Task 10: medición de `style.width` en 3+ timestamps muestra progresión gradual, no salto directo al valor final.
- Task 11: fila nueva en `docs/AUDIT.md`, sin diff de código.

### Loops y condición de salida

- **TDD (Tasks 1-6, 8):** RED (test falla) → GREEN (implementación mínima) → suite completa verde. Salida: verde confirmado por `pytest -q`, no por lectura de código.
- **Verificación visual (Tasks 7, 9, 10):** implementar → `preview_start` → medir con `read_page`/`read_network_requests`/`javascript_tool` → si no cumple el Goal medible, ajustar → re-medir. Tope: **3 iteraciones** por task antes de escalar.

### Vigilancia anti-cuelgue

- Tope de iteraciones en loops visuales (Tasks 7, 9, 10): **máx 3**. Al 3er intento sin cumplir el Goal medible, PARAR y reportar el valor real medido vs el esperado — no seguir iterando en silencio.
- Al **2º fallo consecutivo** de cualquier test en una task: invocar `superpowers:systematic-debugging` (root cause, no re-parchar el mismo síntoma).
- Timeout de verificación en navegador: si `preview_start`/`read_network_requests` no responde en un tiempo razonable, no reintentar en loop — reportar el bloqueo y pasar a la siguiente task si es independiente (Task 10 y 11 no bloquean nada más).
- Task 4 y 6 dependen de fixtures de `conftest.py` que este plan NO pudo verificar línea por línea sin abrir el archivo completo — el primer paso de ambas tasks es leer `conftest.py` y CUALQUIER test existente del mismo endpoint/función antes de escribir el test nuevo. Si el fixture esperado no existe tal como se describe aquí, adaptar el test al fixture real (el contrato de la aserción no cambia, el setup sí puede).

---

## Self-review (Paso 5, ya aplicado antes de guardar)

**Cobertura vs. lo pedido por Robert:**
1. Gate del botón por SPEI real → Tasks 1, 5, 6, 7. ✅
2. Refresh tiempo real 3 categorías calientes → Tasks 2, 3, 4. ✅ (incluye el bug real encontrado: locked accounts excluidas)
3. Retiro en curso hasta liberar (tiempo real) → Tasks 8, 9 (reusa poll existente de pantalla.js, antes SA-only). ✅
4. Fetch mínimo contra BetMexico → Task 11 (ya satisfecho, verificado y documentado). ✅
5. Campos por rol en portal (email/CURP/CLABE/balance/último depósito/método retiro, sin historial) → Task 6 (CURP+institución) + Task 7 (render). Portal YA no expone historial hoy (confirmado: no existe llamada a ningún endpoint de detalle/transacciones en `portal.js` — no hace falta task de "recorte", ya está scoped correctamente). ✅
6. Animación anti-detección → Task 10. ✅

**Placeholder scan:** sin "TBD"/"manejar apropiadamente" — cada step trae código real o un comando `grep`/`pytest` concreto. Las 2 notas "confirmar con el fixture real de conftest.py" (Tasks 4, 6, 8) son deliberadas, no placeholders — son puntos donde el plan depende de un archivo que no se leyó completo por presupuesto de contexto, y se marcan explícitamente como el primer paso a verificar, con el contrato (qué debe quedar probado) ya fijado.

**Consistencia de nombres:** `is_hot_account`, `_load_candidate_rows`, `select_refresh_candidates_healthy`, `_db_get_withdrawal_ready`/`_db_set_withdrawal_ready`, `startWithdrawPoll`/`stopWithdrawPoll`, `animateProgressTo`/`stopProgressAnim` — mismo nombre en la task que los define y en las que los consumen.

**Alcance:** un solo plan ejecutable — todas las tasks tocan el mismo subsistema (`/bet` portal + retiro) y comparten la migración de Task 1. Task 10 es la única visualmente independiente pero se dejó en el mismo plan porque comparte archivo (`portal.js`) y branch.
