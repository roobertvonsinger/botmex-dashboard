# test_withdrawals_migrate.py — Task A: verifica que _migrate() crea account_withdrawals
import sqlite3
import pytest


def test_migrate_creates_account_withdrawals(seed_db, monkeypatch):
    """_migrate() debe crear la tabla account_withdrawals con las columnas requeridas."""
    import app
    app._migrate()

    with app.db() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(account_withdrawals)")]

    required = [
        "account_id", "transaction_id", "amount", "status_api",
        "gateway", "last_modified_utc", "disparado_por", "account_email",
        "reference", "account_digits", "institution_name",
        "status_description", "created_at",
    ]
    for col in required:
        assert col in cols, f"falta columna: {col}"


def test_migrate_transaction_id_unique(seed_db):
    """UNIQUE(transaction_id) impide filas duplicadas."""
    import app
    app._migrate()

    with app.db(write=True) as c:
        c.execute(
            "INSERT INTO account_withdrawals(account_id, transaction_id, amount, created_at) "
            "VALUES(1, 'tx-unique-test', 100.0, '2026-07-24T00:00:00')"
        )
    with pytest.raises(sqlite3.IntegrityError):
        with app.db(write=True) as c:
            c.execute(
                "INSERT INTO account_withdrawals(account_id, transaction_id, amount, created_at) "
                "VALUES(1, 'tx-unique-test', 200.0, '2026-07-24T00:00:00')"
            )


def test_migrate_idempotent(seed_db):
    """Llamar _migrate() dos veces no falla."""
    import app
    app._migrate()
    app._migrate()  # no debe lanzar
