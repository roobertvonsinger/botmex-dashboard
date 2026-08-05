import pytest
import asyncio
from unittest.mock import MagicMock, patch

def test_operator_my_accounts_endpoint(client, monkeypatch):
    """Verifica que /api/operator/my-accounts devuelve solo cuentas con depósitos aprobados del operador."""
    monkeypatch.delenv("BMX_WEB_AUTH_MODE", raising=False)
    from auth import USERS, create_session, sha256
    operator_id = 998877
    USERS["testop"] = {
        "password_hash": sha256("pass123"),
        "role": "operator",
        "telegram_id": operator_id,
        "display": "Test Op"
    }
    token = create_session("testop")
    client.cookies.set("bmx_session", token)

    # Insertar datos en BD
    from app import db
    with db(write=True) as c:
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at) "
            "VALUES (991, 'opacc1@test.com', 'p1', 'LIVE', 500.0, 50.0, 150.0, '2026-07-31T12:00:00Z', 'A', '2026-07-31T10:00:00Z', '2026-07-31T10:00:00Z')"
        )
        c.execute(
            "INSERT OR REPLACE INTO account_deposit_clabes (account_id, account_email, reference, user_id, full_name, clabe, integration, clabe_order, blocked, fetched_at) "
            "VALUES (991, 'opacc1@test.com', 'ref1', 'u1', 'Test Name', '646180001234567890', 'STP', 1, 0, '2026-07-31T12:00:00Z')"
        )
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at) "
            "VALUES (992, 'opacc2@test.com', 'p2', 'LIVE', 100.0, 0.0, 10.0, '2026-07-30T12:00:00Z', 'B', '2026-07-31T10:00:00Z', '2026-07-31T10:00:00Z')"
        )
        # Intento aprobado para testop
        c.execute(
            "INSERT INTO deposit_attempts (attempt_id, account_email, amount, status, duration_ms, operator_id) "
            "VALUES ('att1', 'opacc1@test.com', 150.0, 'approved', 1200, ?)",
            (operator_id,)
        )
        # Intento rechazado para testop (no debe salir)
        c.execute(
            "INSERT INTO deposit_attempts (attempt_id, account_email, amount, status, duration_ms, operator_id) "
            "VALUES ('att2', 'opacc2@test.com', 10.0, 'rejected', 1200, ?)",
            (operator_id,)
        )
        # Intento aprobado para OTRO operador (no debe salir)
        c.execute(
            "INSERT INTO deposit_attempts (attempt_id, account_email, amount, status, duration_ms, operator_id) "
            "VALUES ('att3', 'opacc2@test.com', 10.0, 'approved', 1200, 11111)",
        )

    res = client.get("/api/operator/my-accounts")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    accs = data["accounts"]
    assert len(accs) == 1
    assert accs[0]["email"] == "opacc1@test.com"
    assert accs[0]["balance_real"] == 500.0
    assert accs[0]["grade"] == "A"
    assert accs[0]["clabe_stp"] == "646180001234567890"
    # Verificar que los campos nuevos están presentes
    assert "withdrawal_ready" in accs[0]
    assert "withdrawal_institution" in accs[0]
    assert "curp" in accs[0]
    # withdrawal_ready debe ser boolean (por default False/0)
    assert isinstance(accs[0]["withdrawal_ready"], bool)
    # Asegurar que password/jwt/proxy no estén presentes en la respuesta
    assert "password" not in accs[0]
    assert "jwt" not in accs[0]


def test_operator_my_accounts_visibility_in_process_lock(client, monkeypatch):
    """Regla de vista única (2026-08-04): una cuenta SIN depósito aprobado aún
    debe aparecer si está lockeada por el operador (misión en curso), pero NO
    si está lockeada por otro operador. Cubre el cambio de JOIN de app.py:
    operator_my_accounts pasó de INNER JOIN deposit_attempts a LEFT JOIN +
    `OR a.locked_by IS NOT NULL` — comportamiento nunca antes cubierto por test."""
    monkeypatch.delenv("BMX_WEB_AUTH_MODE", raising=False)
    from auth import USERS, create_session, sha256
    operator_id = 998811
    other_operator_id = 998822
    USERS["testop_lock"] = {
        "password_hash": sha256("pass123"),
        "role": "operator",
        "telegram_id": operator_id,
        "display": "Test Op Lock"
    }
    token = create_session("testop_lock")
    client.cookies.set("bmx_session", token)

    from app import db
    with db(write=True) as c:
        # Lockeada por el propio operador, SIN deposit_attempts todavía
        # (misión recién arrancó, aún no hay intento registrado) → debe salir.
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, "
            "last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at, locked_by) "
            "VALUES (993, 'inproc_own@test.com', 'p3', 'LIVE', 0.0, 0.0, NULL, 'N/A', 'B', "
            "'2026-08-04T10:00:00Z', '2026-08-04T10:00:00Z', ?)",
            (str(operator_id),)
        )
        # Lockeada por OTRO operador, sin deposit_attempts → NO debe salir.
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, "
            "last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at, locked_by) "
            "VALUES (994, 'inproc_other@test.com', 'p4', 'LIVE', 0.0, 0.0, NULL, 'N/A', 'B', "
            "'2026-08-04T10:00:00Z', '2026-08-04T10:00:00Z', ?)",
            (str(other_operator_id),)
        )
        # Libre (locked_by NULL), sin deposit_attempts → NO debe salir.
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, "
            "last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at) "
            "VALUES (995, 'free_unlocked@test.com', 'p5', 'LIVE', 0.0, 0.0, NULL, 'N/A', 'B', "
            "'2026-08-04T10:00:00Z', '2026-08-04T10:00:00Z')"
        )

    res = client.get("/api/operator/my-accounts")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    emails = {a["email"] for a in data["accounts"]}
    assert "inproc_own@test.com" in emails
    assert "inproc_other@test.com" not in emails
    assert "free_unlocked@test.com" not in emails
    own = next(a for a in data["accounts"] if a["email"] == "inproc_own@test.com")
    assert own["is_locked"] is True


@pytest.mark.asyncio
async def test_confirm_gate_in_auto_deposit(seed_db):
    """Verifica que confirm_gate se invoque y que si retorna False no se ejecute la Fase 2."""
    from auto_deposit import run_auto_mission, _m_load
    from app import _persist_auto_mission, db, _migrate
    _migrate()  # Asegura tabla auto_missions
    mission_id = "test_gate_m1"
    plan = {"accounts": [{"id": 991, "email": "testgate@acc.com", "card_pipe": "4111111111111111|12|28|123"}]}
    user = {"telegram_id": 12345}

    with db(write=True) as c:
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, first_checked_at, last_checked_at) "
            "VALUES (991, 'testgate@acc.com', 'pass', 'LIVE', '2026-07-31T10:00:00Z', '2026-07-31T10:00:00Z')"
        )

    gate_called = False
    async def dummy_gate(info):
        nonlocal gate_called
        gate_called = True
        assert info["mission_id"] == mission_id
        return False  # Detener aquí

    _persist_auto_mission(mission_id, 12345, ["4111111111111111|12|28|123"], 150.0, 9, plan)

    mock_pool = MagicMock()
    mock_pool.start_factory = MagicMock(return_value=asyncio.sleep(0))
    mock_pool.prefetch = MagicMock(return_value=asyncio.sleep(0))
    mock_pool.stop = MagicMock(return_value=asyncio.sleep(0))

    with patch("deposits._load_deps", return_value=lambda *a, **kw: mock_pool), \
         patch("deposits._run_deposit_with_phases") as mock_dep, \
         patch("deposits._record_attempt") as mock_rec, \
         patch("deposits._auto_lock_for_deposit") as mock_lock, \
         patch("auto_deposit._unlock") as mock_unlock:
        mock_dep.return_value = {"success": True, "result_code": "SUCCESS", "jwt": "mockjwt"}
        await run_auto_mission(mission_id, plan, user, confirm_gate=dummy_gate)

    assert gate_called is True
    m_row = _m_load(mission_id)
    assert m_row["status"] == "completed"
    assert "detenido por el operador" in m_row["phase_detail"]
