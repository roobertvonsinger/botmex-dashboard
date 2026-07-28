# test_auto_missions_migrate.py — Task A: verifica que _migrate() crea auto_missions
# + reaper de misiones zombie (plan 2026-07-28-modo-auto-deposito-v2.md)
import sqlite3
import pytest

_AUTO_MISSIONS_DDL = """
    CREATE TABLE IF NOT EXISTS auto_missions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        mission_id TEXT UNIQUE NOT NULL,
        operator_id INTEGER,
        card_pipes TEXT NOT NULL,
        amount REAL NOT NULL DEFAULT 150,
        target_count INTEGER NOT NULL DEFAULT 9,
        accounts_selected TEXT,
        matches TEXT,
        status TEXT NOT NULL DEFAULT 'pending',
        phase_detail TEXT,
        total_deposited REAL DEFAULT 0,
        total_approved INTEGER DEFAULT 0,
        total_failed INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        completed_at TEXT
    )
"""


def test_migrate_creates_auto_missions(seed_db):
    """_migrate() debe crear la tabla auto_missions con las columnas requeridas."""
    import app
    app._migrate()

    with app.db() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(auto_missions)")]

    required = [
        "mission_id", "operator_id", "card_pipes", "amount", "target_count",
        "accounts_selected", "matches", "status", "phase_detail",
        "total_deposited", "total_approved", "total_failed",
        "created_at", "updated_at", "completed_at",
    ]
    for col in required:
        assert col in cols, f"falta columna: {col}"


def test_migrate_mission_id_unique(seed_db):
    """UNIQUE(mission_id) impide filas duplicadas."""
    import app
    app._migrate()

    with app.db(write=True) as c:
        c.execute(
            "INSERT INTO auto_missions(mission_id, card_pipes, created_at, updated_at) "
            "VALUES('m-unique-test', '[]', '2026-07-28T00:00:00', '2026-07-28T00:00:00')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        with app.db(write=True) as c:
            c.execute(
                "INSERT INTO auto_missions(mission_id, card_pipes, created_at, updated_at) "
                "VALUES('m-unique-test', '[]', '2026-07-28T00:00:00', '2026-07-28T00:00:00')"
            )


def test_auto_missions_defaults(seed_db):
    """Defaults: status='pending', total_deposited=0, amount=150, target_count=9."""
    import app
    app._migrate()

    with app.db(write=True) as c:
        c.execute(
            "INSERT INTO auto_missions(mission_id, card_pipes, created_at, updated_at) "
            "VALUES('m-defaults', '[]', '2026-07-28T00:00:00', '2026-07-28T00:00:00')"
        )
    with app.db() as c:
        row = c.execute(
            "SELECT status, total_deposited, amount, target_count "
            "FROM auto_missions WHERE mission_id='m-defaults'"
        ).fetchone()
    assert row["status"] == "pending"
    assert row["total_deposited"] == 0
    assert row["amount"] == 150
    assert row["target_count"] == 9


def test_reaper_fails_zombie_and_releases_lock(seed_db):
    """Reaper: misión pre-existente en 'matching' → 'failed' al migrar, y libera
    el lock de su cuenta (fix auditor B2). La cuenta 1 (a@test.com) viene
    lockeada por el seed (locked_by='555')."""
    import app
    with app.db(write=True) as c:
        c.execute(_AUTO_MISSIONS_DDL)
        c.execute(
            "INSERT INTO auto_missions(mission_id, card_pipes, accounts_selected, "
            "matches, status, created_at, updated_at) "
            "VALUES('m-zombie', '[]', '[1]', "
            "'[{\"account_id\": 1, \"card_pipe\": \"p\", \"email\": \"a@test.com\"}]', "
            "'matching', '2026-07-28T00:00:00', '2026-07-28T00:00:00')"
        )
    app._migrate()

    with app.db() as c:
        m = c.execute(
            "SELECT status, phase_detail, completed_at "
            "FROM auto_missions WHERE mission_id='m-zombie'"
        ).fetchone()
        acct = c.execute(
            "SELECT locked_by, locked_until FROM accounts WHERE id=1"
        ).fetchone()
    assert m["status"] == "failed"
    assert m["phase_detail"] == "proceso reiniciado a mitad de misión"
    assert m["completed_at"] is not None
    assert acct["locked_by"] is None
    assert acct["locked_until"] is None


def test_migrate_idempotent(seed_db):
    """Llamar _migrate() dos veces no falla ni re-marca misiones ya reapeadas."""
    import app
    app._migrate()
    app._migrate()  # no debe lanzar
