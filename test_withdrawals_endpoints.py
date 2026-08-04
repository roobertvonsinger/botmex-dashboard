# test_withdrawals_endpoints.py — Task C: endpoints POST /withdraw + GET /withdraw/status
import time

import pytest

import withdrawals as wd


def _acc_id(seed_db, email="a@test.com"):
    import sqlite3
    con = sqlite3.connect(seed_db)
    try:
        row = con.execute("SELECT id FROM accounts WHERE email=?", (email,)).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def _set_jwt(seed_db, email, *, expires_delta=3600, token="JWT-VIGENTE"):
    import sqlite3
    con = sqlite3.connect(seed_db)
    try:
        con.execute(
            "UPDATE accounts SET jwt_token=?, jwt_expires_at=? WHERE email=?",
            (token, int(time.time()) + expires_delta, email),
        )
        con.commit()
    finally:
        con.close()


def _clear_jwt(seed_db, email):
    import sqlite3
    con = sqlite3.connect(seed_db)
    try:
        con.execute("UPDATE accounts SET jwt_token=NULL, jwt_expires_at=NULL WHERE email=?", (email,))
        con.commit()
    finally:
        con.close()


# ── C1 — POST /api/accounts/{id}/withdraw ─────────────────────────────────

def test_withdraw_403_for_non_sa(make_client, seed_db):
    client = make_client(role="user", telegram_id=555)
    acc_id = _acc_id(seed_db)
    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": 100})
    assert r.status_code == 403


def test_withdraw_404_unknown_account(make_client, seed_db):
    client = make_client(role="superadmin")
    r = client.post("/api/accounts/999999/withdraw", json={"amount": 100})
    assert r.status_code == 404


def test_withdraw_409_jwt_expired(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)
    _set_jwt(seed_db, "a@test.com", expires_delta=-3600)

    called = {"n": 0}

    async def fake_execute(db_path, account_id, amount):
        called["n"] += 1
        raise wd.JwtExpired("expirado")

    import app
    monkeypatch.setattr(app, "execute_withdrawal", fake_execute)

    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": 100})
    assert r.status_code == 409
    assert "JWT expirado" in r.json()["detail"]
    assert called["n"] == 1


def test_withdraw_409_no_jwt(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)
    _clear_jwt(seed_db, "a@test.com")

    async def fake_execute(db_path, account_id, amount):
        raise wd.JwtExpired("sin jwt")

    import app
    monkeypatch.setattr(app, "execute_withdrawal", fake_execute)

    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": 100})
    assert r.status_code == 409


def test_withdraw_409_no_approved_account(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)

    async def fake_execute(db_path, account_id, amount):
        raise wd.NoApprovedWithdrawalAccount("sin cuenta")

    import app
    monkeypatch.setattr(app, "execute_withdrawal", fake_execute)

    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": 100})
    assert r.status_code == 409
    assert "SPEI" in r.json()["detail"]


def test_withdraw_409_multiple_approved_bug1(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)

    async def fake_execute(db_path, account_id, amount):
        raise wd.MultipleApprovedAccounts("Hay 2 cuentas de retiro aprobadas (HEY BANCO ···1215, BBVA ···0139)")

    import app
    monkeypatch.setattr(app, "execute_withdrawal", fake_execute)

    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": 100})
    assert r.status_code == 409
    assert "HEY BANCO" in r.json()["detail"]


def test_withdraw_409_insufficient_balance(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)

    async def fake_execute(db_path, account_id, amount):
        raise wd.InsufficientBalance("Saldo insuficiente: Real=$50.00, solicitado=$100.00")

    import app
    monkeypatch.setattr(app, "execute_withdrawal", fake_execute)

    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": 100})
    assert r.status_code == 409
    assert "Real=$50.00" in r.json()["detail"]


def test_withdraw_409_concurrent_pending(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)

    async def fake_execute(db_path, account_id, amount):
        raise wd.ConcurrentWithdrawalPending("ya hay uno")

    import app
    monkeypatch.setattr(app, "execute_withdrawal", fake_execute)

    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": 100})
    assert r.status_code == 409
    assert "pendiente" in r.json()["detail"]


def test_withdraw_happy_persists_and_broadcasts(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin", telegram_id=1341812706)
    acc_id = _acc_id(seed_db)

    async def fake_execute(db_path, account_id, amount):
        return {
            "transactionId": "t1", "reference": "r1", "accountId": "a1",
            "accountDigits": "1215", "institutionName": "HEY BANCO",
            "amount": amount, "account_email": "a@test.com", "warnings": [],
        }

    import app
    monkeypatch.setattr(app, "execute_withdrawal", fake_execute)

    broadcasts = []
    monkeypatch.setattr(app, "_broadcast", lambda e: broadcasts.append(e))

    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": 100})
    assert r.status_code == 200

    with app.db() as c:
        row = c.execute(
            "SELECT * FROM account_withdrawals WHERE transaction_id=?", ("t1",)
        ).fetchone()
    assert row is not None
    assert row["amount"] == 100.0
    assert row["disparado_por"] == 1341812706

    assert len(broadcasts) == 1
    assert broadcasts[0]["kind"] == "withdrawal"
    assert broadcasts[0]["who_id"] == 1341812706


def test_withdraw_amount_validation(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)

    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": 0})
    assert r.status_code == 400

    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": "abc"})
    assert r.status_code == 400

    async def fake_execute(db_path, account_id, amount):
        raise wd.InsufficientBalance("Saldo insuficiente")

    import app
    monkeypatch.setattr(app, "execute_withdrawal", fake_execute)
    r = client.post(f"/api/accounts/{acc_id}/withdraw", json={"amount": 99999})
    assert r.status_code == 409


def test_withdraw_broadcast_visible_to_sa_only(seed_db):
    import app
    event = {"kind": "withdrawal", "who_id": 1341812706}
    sa_ctx = {"role": "superadmin", "telegram_id": 1341812706}
    other_ctx = {"role": "user", "telegram_id": 555}
    assert app._event_visible_to(event, sa_ctx) is True
    assert app._event_visible_to(event, other_ctx) is False


def test_withdraw_persist_idempotent_unique_transaction_id(seed_db):
    import app
    result = {
        "transactionId": "t-dup", "reference": "r1", "amount": 100.0,
        "accountDigits": "1215", "institutionName": "HEY BANCO",
        "account_email": "a@test.com",
    }
    app._persist_withdrawal(1, 1341812706, result)
    app._persist_withdrawal(1, 1341812706, result)
    with app.db() as c:
        rows = c.execute(
            "SELECT * FROM account_withdrawals WHERE transaction_id=?", ("t-dup",)
        ).fetchall()
    assert len(rows) == 1


# ── C2 — GET /api/accounts/{id}/withdraw/status/{tx_id} ──────────────────

def test_status_403_non_sa(make_client, seed_db):
    """Operador SIN relación con la cuenta (ni account_assignments ni locked_by) -> 403.
    b@test.com es del SA en el seed (a@/c@ son las relacionadas con 555)."""
    client = make_client(role="user", telegram_id=555)
    acc_id = _acc_id(seed_db, "b@test.com")
    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/tx1")
    assert r.status_code == 403


def test_withdraw_status_operador_dueno_puede_consultar(make_client, seed_db, monkeypatch):
    """Operador dueño de la cuenta (via account_assignments) puede consultar su status. a@test.com
    está asignada a 555 en el seed de conftest.py."""
    client = make_client(role="user", telegram_id=555)
    acc_id = _acc_id(seed_db, "a@test.com")
    _set_jwt(seed_db, "a@test.com")

    import app
    app._persist_withdrawal(acc_id, 555, {
        "transactionId": "tx-owner", "reference": "r1", "amount": 100.0,
        "accountDigits": "1215", "institutionName": "HEY BANCO",
        "account_email": "a@test.com",
    })

    async def fake_get_pending(jwt, proxy_url, transport=None):
        return {"id": "tx-owner", "transactionStatus": 2, "transactionStatusDescription": "En proceso"}

    monkeypatch.setattr(app, "get_pending_withdrawal", fake_get_pending)

    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/tx-owner")
    assert r.status_code == 200
    assert r.json()["status"] == "pending"


def test_withdraw_status_operador_ajeno_403(make_client, seed_db):
    """Operador SIN ownership sobre la cuenta -> 403, no filtra status de retiro ajeno.
    b@test.com no está asignada ni lockeada a 555 en el seed."""
    client = make_client(role="user", telegram_id=555)
    acc_id = _acc_id(seed_db, "b@test.com")
    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/tx-anything")
    assert r.status_code == 403


def test_withdraw_status_operador_no_puede_leer_tx_de_otra_cuenta_via_account_id_propio(make_client, seed_db):
    """IDOR: operador dueño de a@test.com pasa SU PROPIO account_id (que sí pertenece a
    su universo visible, pasando el chequeo de ownership) pero el tx_id de un retiro que
    pertenece a b@test.com (cuenta ajena, no lockeada/asignada a 555). Antes del fix el
    SELECT de account_withdrawals filtraba SOLO por transaction_id, sin cruzar contra el
    account_id de la URL -> filtraba dígitos/institución de la cuenta ajena en un 200.
    Debe dar 404 (retiro no encontrado para ESA cuenta), no 200 con datos ajenos."""
    client = make_client(role="user", telegram_id=555)
    a_id = _acc_id(seed_db, "a@test.com")
    b_id = _acc_id(seed_db, "b@test.com")

    import app
    app._persist_withdrawal(b_id, 1341812706, {
        "transactionId": "tx-belongs-to-b", "reference": "r1", "amount": 100.0,
        "accountDigits": "9999", "institutionName": "SECRET BANK OF B",
        "account_email": "b@test.com",
    })

    r = client.get(f"/api/accounts/{a_id}/withdraw/status/tx-belongs-to-b")
    assert r.status_code == 404
    assert "9999" not in r.text
    assert "SECRET BANK OF B" not in r.text


def test_status_404_unknown_tx(make_client, seed_db):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)
    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/nope")
    assert r.status_code == 404


def test_status_happy_pending(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)
    _set_jwt(seed_db, "a@test.com")

    import app
    app._persist_withdrawal(acc_id, 1341812706, {
        "transactionId": "tx-pending", "reference": "r1", "amount": 100.0,
        "accountDigits": "1215", "institutionName": "HEY BANCO",
        "account_email": "a@test.com",
    })

    async def fake_get_pending(jwt, proxy_url, transport=None):
        return {"id": "tx-pending", "transactionStatus": 2, "transactionStatusDescription": "En proceso"}

    monkeypatch.setattr(app, "get_pending_withdrawal", fake_get_pending)

    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/tx-pending")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "pending"
    assert body["transactionStatus"] == 2


def test_status_happy_successful_two_phase_bug2(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)
    _set_jwt(seed_db, "a@test.com")

    import app
    app._persist_withdrawal(acc_id, 1341812706, {
        "transactionId": "tx-done", "reference": "r1", "amount": 100.0,
        "accountDigits": "1215", "institutionName": "HEY BANCO",
        "account_email": "a@test.com",
    })

    async def fake_get_pending(jwt, proxy_url, transport=None):
        return {"id": "tx-done", "transactionStatus": 6}

    async def fake_get_bank_tx(jwt, proxy_url, tx_id, expected_digits=None, transport=None):
        return {
            "gateway": 2, "lastAccountDigits": "1215",
            "lastModifiedUtc": "2026-07-24T18:18:35",
            "gateway_spei": True, "gateway_mismatch": False, "digits_mismatch": False,
        }

    monkeypatch.setattr(app, "get_pending_withdrawal", fake_get_pending)
    monkeypatch.setattr(app, "get_bank_transaction", fake_get_bank_tx)

    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/tx-done")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "successful"
    assert body["phase"] == "executed"
    assert body["phase"] != "delivered"
    assert "confirma en tu banco" in body["description"]
    assert body["lastModifiedUtc"] == "2026-07-24T18:18:35"


def test_status_gateway_mismatch_alert_bug3(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)
    _set_jwt(seed_db, "a@test.com")

    import app
    app._persist_withdrawal(acc_id, 1341812706, {
        "transactionId": "tx-card", "reference": "r1", "amount": 100.0,
        "accountDigits": "1215", "institutionName": "HEY BANCO",
        "account_email": "a@test.com",
    })

    async def fake_get_pending(jwt, proxy_url, transport=None):
        return {"id": "tx-card", "transactionStatus": 6}

    async def fake_get_bank_tx(jwt, proxy_url, tx_id, expected_digits=None, transport=None):
        return {
            "gateway": 1, "lastAccountDigits": "1215",
            "lastModifiedUtc": "2026-07-24T18:18:35",
            "gateway_spei": False, "gateway_mismatch": True, "digits_mismatch": False,
        }

    monkeypatch.setattr(app, "get_pending_withdrawal", fake_get_pending)
    monkeypatch.setattr(app, "get_bank_transaction", fake_get_bank_tx)

    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/tx-card")
    assert r.json()["alerts"]["gatewayMismatch"] is True


def test_status_digits_mismatch_alert_bug1(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)
    _set_jwt(seed_db, "a@test.com")

    import app
    app._persist_withdrawal(acc_id, 1341812706, {
        "transactionId": "tx-mismatch", "reference": "r1", "amount": 100.0,
        "accountDigits": "1215", "institutionName": "HEY BANCO",
        "account_email": "a@test.com",
    })

    async def fake_get_pending(jwt, proxy_url, transport=None):
        return {"id": "tx-mismatch", "transactionStatus": 6}

    async def fake_get_bank_tx(jwt, proxy_url, tx_id, expected_digits=None, transport=None):
        return {
            "gateway": 2, "lastAccountDigits": "0139",
            "lastModifiedUtc": "2026-07-24T18:18:35",
            "gateway_spei": True, "gateway_mismatch": False, "digits_mismatch": True,
        }

    monkeypatch.setattr(app, "get_pending_withdrawal", fake_get_pending)
    monkeypatch.setattr(app, "get_bank_transaction", fake_get_bank_tx)

    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/tx-mismatch")
    assert r.json()["alerts"]["digitsMismatch"] is True


def test_status_no_pending_returns_idle(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)
    _set_jwt(seed_db, "a@test.com")

    import app
    app._persist_withdrawal(acc_id, 1341812706, {
        "transactionId": "tx-idle", "reference": "r1", "amount": 100.0,
        "accountDigits": "1215", "institutionName": "HEY BANCO",
        "account_email": "a@test.com",
    })

    async def fake_get_pending(jwt, proxy_url, transport=None):
        return None

    monkeypatch.setattr(app, "get_pending_withdrawal", fake_get_pending)

    r = client.get(f"/api/accounts/{acc_id}/withdraw/status/tx-idle")
    assert r.status_code == 200
    assert r.json()["status"] == "idle"


def test_status_updates_db_row(make_client, seed_db, monkeypatch):
    client = make_client(role="superadmin")
    acc_id = _acc_id(seed_db)
    _set_jwt(seed_db, "a@test.com")

    import app
    app._persist_withdrawal(acc_id, 1341812706, {
        "transactionId": "tx-updates", "reference": "r1", "amount": 100.0,
        "accountDigits": "1215", "institutionName": "HEY BANCO",
        "account_email": "a@test.com",
    })

    async def fake_get_pending(jwt, proxy_url, transport=None):
        return {"id": "tx-updates", "transactionStatus": 6}

    async def fake_get_bank_tx(jwt, proxy_url, tx_id, expected_digits=None, transport=None):
        return {
            "gateway": 2, "lastAccountDigits": "1215",
            "lastModifiedUtc": "2026-07-24T18:18:35",
            "gateway_spei": True, "gateway_mismatch": False, "digits_mismatch": False,
        }

    monkeypatch.setattr(app, "get_pending_withdrawal", fake_get_pending)
    monkeypatch.setattr(app, "get_bank_transaction", fake_get_bank_tx)

    client.get(f"/api/accounts/{acc_id}/withdraw/status/tx-updates")

    with app.db() as c:
        row = c.execute(
            "SELECT status_api, last_modified_utc FROM account_withdrawals WHERE transaction_id=?",
            ("tx-updates",),
        ).fetchone()
    assert row["status_api"] == 6
    assert row["last_modified_utc"] == "2026-07-24T18:18:35"
