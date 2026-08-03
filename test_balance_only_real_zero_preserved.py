"""Forense en prod (KVM4, 2026-08-02/03): `cardenascarlosignacio94@gmail.com`
tenia balance_real=$1181.02 en BD. Cuatro refrescos manuales/automaticos
posteriores (`process_log` fase='complete', jwt_from_cache=True) reportaron
`balance_real=0.0` desde la API -- pero la BD siguio mostrando $1181.02 horas
despues. La cuenta realmente vacio su saldo real a $0 y el dashboard nunca lo
reflejo, pese a refrescos manuales explicitos ("no se estan actualizando los
balances aunque lo haga manual").

Causa raiz: `_db_upsert_balance` (prewarm.py) tiene un guard "preservar saldo
viejo" que solo debe activarse si la API fallo silenciosamente (JWT muerto,
401 enmascarado). Su chequeo `api_succeeded` NO considera
`transactions.fetched` -- la MISMA senal que `_fetch_looks_empty` (fix
2026-07-28, ver docs/ERRORS.md) ya usa para probar que la sesion sigue viva.
En `fetch_mode='balance_only'` (el modo real que usan tanto el boton de
refresh individual como el ciclo automatico) la API NUNCA trae `fullname` ni
`transactions.items` por diseno, asi que `api_succeeded` estructuralmente solo
puede ser True si hay un deposito nuevo o bonos > 0. Cualquier cuenta cuyo
saldo real genuino sea $0 (sin deposito nuevo, sin bonos) queda atrapada:
CADA refresh subsecuente descarta el $0 real y preserva el saldo viejo para
siempre, aunque la sesion este perfectamente viva y el $0 sea el dato
correcto."""
import pytest


def test_db_upsert_balance_persists_real_zero_when_session_alive(make_client):
    make_client()  # dispara reload de app_mod con BETMEX_DB seedeado

    import prewarm as pw
    from app import db

    with db(write=True) as c:
        c.execute(
            "UPDATE accounts SET balance_real=1181.02, balance_total=1181.02 "
            "WHERE email='a@test.com'"
        )

    # Fetch balance_only real: balance_real=0.0 genuino, sesion viva
    # (transactions.fetched=True certifica que la API SI respondio).
    details = {
        "balance_real": 0.0, "balance_bonos": 0.0,
        "last_deposit_amount": 0.0, "last_deposit_date": "N/A",
        "fullname": "N/A",
        "transactions": {"total_rows": 0, "pages": 0, "items": [], "fetched": True},
    }
    pw._db_upsert_balance("a@test.com", details)

    with db() as c:
        row = c.execute(
            "SELECT balance_real, balance_total FROM accounts WHERE email='a@test.com'"
        ).fetchone()

    assert row["balance_real"] == 0.0, (
        "un balance_real=0 real con sesion viva (transactions.fetched=True) "
        f"debe persistirse, no preservar el saldo viejo -- row={dict(row)}"
    )
    assert row["balance_total"] == 0.0


def test_db_upsert_balance_still_preserves_old_balance_on_truly_dead_session(make_client):
    """Control: si la sesion SI murio silenciosamente (fetched=False, sin
    fullname, sin bonos, sin deposito) el guard debe seguir protegiendo el
    saldo viejo -- este es el caso legitimo que el guard existe para cubrir."""
    make_client()

    import prewarm as pw
    from app import db

    with db(write=True) as c:
        c.execute(
            "UPDATE accounts SET balance_real=1181.02, balance_total=1181.02 "
            "WHERE email='a@test.com'"
        )

    details = {
        "balance_real": 0.0, "balance_bonos": 0.0,
        "last_deposit_amount": 0.0, "last_deposit_date": "N/A",
        "fullname": "N/A",
        "transactions": {"total_rows": 0, "pages": 0, "items": [], "fetched": False},
    }
    pw._db_upsert_balance("a@test.com", details)

    with db() as c:
        row = c.execute(
            "SELECT balance_real, balance_total FROM accounts WHERE email='a@test.com'"
        ).fetchone()

    assert row["balance_real"] == 1181.02, (
        f"sesion realmente muerta (fetched=False) debe preservar el saldo viejo -- row={dict(row)}"
    )
