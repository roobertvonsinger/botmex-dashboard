# test_account_touch_isolated.py
# Fase 2: el touch de auditoría sale del path síncrono de account_details.
# _record_account_touch es la unidad testeable; account_details la despacha
# fire-and-forget en thread daemon (no abre db(write=True) en el request).
# Caza 2026-07-25: lock sostenido en account_details:2952 bajo contención bot↔web.
# Commit 3b59fe7 instrumentó el lock; este commit lo mata de raíz sacándolo del
# path de lectura.

import importlib
import app as app_mod


def _reload_with_seed_db():
    """El módulo `app` cachea DB_PATH al importar. seed_db setea la env var pero
    el módulo YA está cargado → hay que recargar para que recoja la nueva BD.
    Igual que hace el fixture `client`/`make_client` del conftest."""
    importlib.reload(app_mod)


def test_record_touch_persists_new_touch(seed_db):
    """Primer toque del día → persiste, devuelve True."""
    _reload_with_seed_db()
    assert app_mod._record_account_touch(1, "a@test.com", 555) is True
    with app_mod.db() as c:
        rows = c.execute(
            "SELECT actor_id, touched_date FROM account_touches WHERE account_id=1"
        ).fetchall()
    assert len(rows) == 1
    assert rows[0]["actor_id"] == 555


def test_record_touch_dedup_same_day_returns_false(seed_db):
    """Segundo toque el MISMO día → dedup, devuelve False, no inserta dup."""
    _reload_with_seed_db()
    assert app_mod._record_account_touch(1, "a@test.com", 555) is True
    assert app_mod._record_account_touch(1, "a@test.com", 555) is False
    with app_mod.db() as c:
        count = c.execute(
            "SELECT COUNT(*) FROM account_touches WHERE account_id=1 AND actor_id=555"
        ).fetchone()[0]
    assert count == 1


def test_record_touch_different_actors_both_persist(seed_db):
    """Dos operadores distintos tocan la misma cuenta el mismo día → ambos persisten."""
    _reload_with_seed_db()
    assert app_mod._record_account_touch(1, "a@test.com", 555) is True
    assert app_mod._record_account_touch(1, "a@test.com", 777) is True
    with app_mod.db() as c:
        count = c.execute(
            "SELECT COUNT(*) FROM account_touches WHERE account_id=1"
        ).fetchone()[0]
    assert count == 2


def test_record_touch_traps_locked_silently(seed_db, monkeypatch):
    """Si la BD está lockeada, _record_account_touch NO lanza — devuelve False.
    El touch es bitácora, no transacción: perderlo es aceptable, bloquear La
    Pantalla no. Simula el lock forzando que db(write=True) levante OperationalError."""
    _reload_with_seed_db()
    import sqlite3

    orig_db = app_mod.db

    class _LockedCtx:
        def __enter__(self):
            raise sqlite3.OperationalError("database is locked")
        def __exit__(self, *a):
            return False

    def fake_db(write=False):
        if write:
            return _LockedCtx()
        return orig_db()

    monkeypatch.setattr(app_mod, "db", fake_db)
    # No lanza; devuelve False.
    assert app_mod._record_account_touch(1, "a@test.com", 555) is False


def test_account_details_dispatches_touch_off_request_path():
    """REGRESIÓN: account_details NO abre db(write=True) en el path síncrono del
    request. Antes (pre-este-commit) el touch vivía con `with db(write=True)`
    inline → bajo contención bot↔web lanzaba `database is locked` sostenido
    (caza 2026-07-25, commit 3b59fe7). Ahora el touch corre en thread daemon
    FUERA del request.

    Validación estructural (no via HTTP — el conftest tiene un gap de schema que
    impide correr account_details end-to-end, ver memoria conftest_schema_gap):
    el source de account_details debe (a) llamar a _record_account_touch dentro
    de un threading.Thread(target=..., daemon=True) y (b) NO contener
    `with db(write=True)` inline en su cuerpo (el único write del touch vive en
    _record_account_touch, despachado off-request).
    """
    import inspect, app, ast

    src = inspect.getsource(app.account_details)
    # (a) el touch se despacha a un thread daemon, no se ejecuta inline.
    assert "threading.Thread(" in src and "daemon=True" in src, (
        "account_details debe despachar el touch fire-and-forget en thread daemon — "
        "no ejecutarlo síncrono (regresión del lock 2026-07-25)"
    )
    assert "_record_account_touch" in src, (
        "account_details debe llamar a _record_account_touch (no inline el INSERT)"
    )
    # (b) no debe haber un `with db(write=True)` inline en el cuerpo TOP-LEVEL de
    #     account_details (el write del touch vive dentro de _record_account_touch,
    #     en el thread). Las funciones anidadas que corren en daemon thread (como
    #     _async_val_renapo) SÍ pueden tener db(write=True) — no están en el path
    #     síncrono del request. Usamos AST para examinar solo el cuerpo directo.
    tree = ast.parse(inspect.getsource(app.account_details))
    # La función wrapper es el primer FunctionDef del módulo parseado
    func_def = next(
        (n for n in tree.body if isinstance(n, ast.FunctionDef)), None
    )
    assert func_def is not None, "no se encontró FunctionDef en el source"
    violating = []
    for stmt in func_def.body:
        # Buscar `with db(write=True)` — ast.withitem → ast.Call con keyword write=True
        if isinstance(stmt, ast.With):
            for item in stmt.items:
                call = item.context_expr
                if (
                    isinstance(call, ast.Call)
                    and isinstance(call.func, ast.Name)
                    and call.func.id == "db"
                    and any(
                        kw.arg == "write" and isinstance(kw.value, ast.Constant) and kw.value.value is True
                        for kw in call.keywords
                    )
                ):
                    violating.append(ast.get_source_segment(src, stmt))
    assert not violating, (
        f"account_details tiene {len(violating)} `db(write=True)` en el cuerpo "
        "top-level (no en función anidada) — el único write del touch debe vivir "
        "en _record_account_touch (thread daemon), no en el path síncrono. "
        "Líneas: " + " | ".join(v.strip() for v in violating)
    )
