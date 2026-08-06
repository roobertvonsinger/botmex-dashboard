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


def test_operator_my_accounts_hides_fully_withdrawn_account(client, monkeypatch):
    """Regla de producto (Robert, 2026-08-05): una cuenta con depósito aprobado
    debe desaparecer de la vista del operador una vez que ya no queda saldo real
    que retirar (balance_real llegó a 0), NO debe seguir apareciendo para siempre
    solo por tener un deposit_attempt approved histórico. Cubre `app.py` L4288
    (AND COALESCE(a.balance_real,0) > 0 agregado sobre la pierna de aprobados)."""
    monkeypatch.delenv("BMX_WEB_AUTH_MODE", raising=False)
    from auth import USERS, create_session, sha256
    operator_id = 998833
    USERS["testop_withdrawn"] = {
        "password_hash": sha256("pass123"),
        "role": "operator",
        "telegram_id": operator_id,
        "display": "Test Op Withdrawn"
    }
    token = create_session("testop_withdrawn")
    client.cookies.set("bmx_session", token)

    from app import db
    with db(write=True) as c:
        # Depósito aprobado, pero saldo real ya en 0 (todo retirado) → NO debe salir.
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, "
            "last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at) "
            "VALUES (996, 'ya_retirada@test.com', 'p6', 'LIVE', 0.0, 0.0, 150.0, '2026-08-01T12:00:00Z', 'A', "
            "'2026-08-01T10:00:00Z', '2026-08-01T10:00:00Z')"
        )
        c.execute(
            "INSERT INTO deposit_attempts (attempt_id, account_email, amount, status, duration_ms, operator_id) "
            "VALUES ('att_withdrawn', 'ya_retirada@test.com', 150.0, 'approved', 1200, ?)",
            (operator_id,)
        )
        # Depósito aprobado con saldo real > 0 todavía → SÍ debe salir (control).
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, "
            "last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at) "
            "VALUES (997, 'con_saldo@test.com', 'p7', 'LIVE', 150.0, 0.0, 150.0, '2026-08-01T12:00:00Z', 'A', "
            "'2026-08-01T10:00:00Z', '2026-08-01T10:00:00Z')"
        )
        c.execute(
            "INSERT INTO deposit_attempts (attempt_id, account_email, amount, status, duration_ms, operator_id) "
            "VALUES ('att_con_saldo', 'con_saldo@test.com', 150.0, 'approved', 1200, ?)",
            (operator_id,)
        )

    res = client.get("/api/operator/my-accounts")
    assert res.status_code == 200
    emails = {a["email"] for a in res.json()["accounts"]}
    assert "ya_retirada@test.com" not in emails
    assert "con_saldo@test.com" in emails


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


def test_operator_my_accounts_sa_own_view_excludes_stale_reservada_sa_locks(client, monkeypatch):
    """Bug reportado por Robert en vivo (2026-08-06): al ver su propio /bet vía
    /{username}?view_as={username}, veía cuentas que NO estaba procesando ahorita.
    Root cause (evidencia en prod, KVM4): cuando SA deposita, `_auto_lock_for_deposit`
    (deposits.py) deja `locked_until=NULL` a propósito (RESERVADA_SA perpetua, "ningún
    watchdog la libera") — los watchdogs de app.py que limpian locks vencidos
    (`locked_until <= datetime('now')`) NUNCA hacen match contra NULL, así que a
    diferencia de un operador normal (lock 2-4h que SÍ se autolimpia), los locks de
    SA se acumulan para siempre. En prod: 112 cuentas lockeadas por SA desde hace
    5+ semanas, mostrándose todas como "en proceso" en su propio portal.

    Fix: `operator_my_accounts` (app.py), rama scoped (view_as), solo cuenta un
    `locked_by=me` como "en proceso" si `locked_at` es reciente (ventana =
    AUTOLOCK_HOURS_SCHEDULED, la más amplia que el propio código ya usa para un
    lock de operador legítimamente activo). No toca `locked_until`/RESERVADA_SA —
    la cuenta sigue reservada/protegida para pool y refresh, solo deja de aparecer
    como "en proceso" en la vista personal una vez pasada la ventana."""
    monkeypatch.delenv("BMX_WEB_AUTH_MODE", raising=False)
    from auth import USERS, create_session, sha256
    from datetime import datetime, timezone, timedelta
    sa_id = 887711
    USERS["testsa_ownview"] = {
        "password_hash": sha256("pass123"),
        "role": "superadmin",
        "telegram_id": sa_id,
        "display": "Test SA",
    }
    token = create_session("testsa_ownview")
    client.cookies.set("bmx_session", token)

    now = datetime.now(timezone.utc)
    stale_at = (now - timedelta(hours=24)).isoformat()  # muy pasada la ventana de 4h
    fresh_at = now.isoformat()

    from app import db
    with db(write=True) as c:
        # RESERVADA_SA vieja (locked_until NULL, locked_at hace 24h) → NO debe
        # aparecer como "en proceso" en la vista propia del SA.
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, "
            "last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at, "
            "locked_by, locked_at, locked_until) "
            "VALUES (1993, 'sa_stale_lock@test.com', 'p1', 'LIVE', 0.0, 0.0, NULL, 'N/A', 'B', "
            "'2026-08-01T10:00:00Z', '2026-08-01T10:00:00Z', ?, ?, NULL)",
            (str(sa_id), stale_at)
        )
        # RESERVADA_SA fresca (locked_at ahora mismo) → SÍ debe seguir apareciendo.
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, "
            "last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at, "
            "locked_by, locked_at, locked_until) "
            "VALUES (1994, 'sa_fresh_lock@test.com', 'p2', 'LIVE', 0.0, 0.0, NULL, 'N/A', 'B', "
            "'2026-08-06T10:00:00Z', '2026-08-06T10:00:00Z', ?, ?, NULL)",
            (str(sa_id), fresh_at)
        )

    res = client.get("/api/operator/my-accounts?view_as=testsa_ownview")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    emails = {a["email"] for a in data["accounts"]}
    assert "sa_stale_lock@test.com" not in emails, (
        "lock RESERVADA_SA de hace 24h se sigue mostrando como 'en proceso' — "
        "el bug que reportó Robert sigue vivo"
    )
    assert "sa_fresh_lock@test.com" in emails


def test_operator_my_accounts_dust_balance_excluded_below_one_peso(client, monkeypatch):
    """Segundo bug reportado por Robert en la misma sesión (2026-08-06, ronda 2):
    tras el fix de locks RESERVADA_SA, seguía viendo cuentas en su portal — root
    cause en la OTRA pierna del WHERE (depósito aprobado + balance_real>0, sin
    tope de tiempo NI de monto). En prod: 31 cuentas nunca-más-tocadas desde hace
    semanas/meses seguían "en proceso" solo por tener saldo residual de $0.01 a
    $0.94 (polvo, no hay minimo de retiro documentado por BetMexico — grep en
    bundle/docs/flags.betmexico.mx no encontró uno — pero los propios datos de
    prod muestran un hueco limpio entre $0.94 y $2.57, cero casos ambiguos en medio).

    Fix: la pierna de "depósito aprobado" ahora exige balance_real >= 1 (antes > 0).
    NO toca la pierna de lock (ya cubierta por el test de recencia arriba)."""
    monkeypatch.delenv("BMX_WEB_AUTH_MODE", raising=False)
    from auth import USERS, create_session, sha256
    operator_id = 998855
    USERS["testop_dust"] = {
        "password_hash": sha256("pass123"),
        "role": "operator",
        "telegram_id": operator_id,
        "display": "Test Op Dust",
    }
    token = create_session("testop_dust")
    client.cookies.set("bmx_session", token)

    from app import db
    with db(write=True) as c:
        # Saldo polvo ($0.08) con depósito aprobado hace semanas → NO debe salir.
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, "
            "last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at) "
            "VALUES (1998, 'polvo@test.com', 'p8', 'LIVE', 0.08, 0.0, 150.0, '2026-07-01T12:00:00Z', 'B', "
            "'2026-07-01T10:00:00Z', '2026-07-01T10:00:00Z')"
        )
        c.execute(
            "INSERT INTO deposit_attempts (attempt_id, account_email, amount, status, duration_ms, operator_id) "
            "VALUES ('att_polvo', 'polvo@test.com', 150.0, 'approved', 1200, ?)",
            (operator_id,)
        )
        # Saldo real retirable ($2.57) con depósito aprobado hace semanas → SÍ debe salir.
        c.execute(
            "INSERT OR REPLACE INTO accounts (id, email, password, status, balance_real, balance_bonos, "
            "last_deposit_amount, last_deposit_date, grade, first_checked_at, last_checked_at) "
            "VALUES (1999, 'retirable@test.com', 'p9', 'LIVE', 2.57, 0.0, 150.0, '2026-07-01T12:00:00Z', 'B', "
            "'2026-07-01T10:00:00Z', '2026-07-01T10:00:00Z')"
        )
        c.execute(
            "INSERT INTO deposit_attempts (attempt_id, account_email, amount, status, duration_ms, operator_id) "
            "VALUES ('att_retirable', 'retirable@test.com', 150.0, 'approved', 1200, ?)",
            (operator_id,)
        )

    res = client.get("/api/operator/my-accounts")
    assert res.status_code == 200
    data = res.json()
    assert data["ok"] is True
    emails = {a["email"] for a in data["accounts"]}
    assert "polvo@test.com" not in emails, (
        "saldo polvo ($0.08) se sigue mostrando como 'en proceso' sin límite de "
        "tiempo ni de monto — el bug que reportó Robert sigue vivo"
    )
    assert "retirable@test.com" in emails


def test_username_portal_page_renders_for_own_user(client, monkeypatch):
    """La URL del portal /bet cambió de /user/{telegram_id} a /{username}
    (Robert, 2026-08-06: "la url deberia ser botmexico.net/(apodo del usuario,
    Lau, Luisito)"). /{username} con sesión válida y username propio debe
    servir portal.html (200), no un redirect."""
    monkeypatch.delenv("BMX_WEB_AUTH_MODE", raising=False)
    from auth import USERS, create_session, sha256
    USERS["testop_urlname"] = {
        "password_hash": sha256("pass123"), "role": "operator",
        "telegram_id": 991122, "display": "Test Urlname",
    }
    token = create_session("testop_urlname")
    client.cookies.set("bmx_session", token)

    res = client.get("/testop_urlname", follow_redirects=False)
    assert res.status_code == 200
    assert "acc-card" in res.text or "accountsGrid" in res.text


def test_username_portal_page_404_for_unknown_username(client, monkeypatch):
    """Un segmento de 1 nivel que no es un username real (typo, ruta random)
    NO debe tragarse silenciosamente como si fuera un portal — 404 explícito,
    no un portal vacío de nadie."""
    monkeypatch.delenv("BMX_WEB_AUTH_MODE", raising=False)
    from auth import USERS, create_session, sha256
    USERS["testop_404check"] = {
        "password_hash": sha256("pass123"), "role": "operator",
        "telegram_id": 991133, "display": "Test 404check",
    }
    token = create_session("testop_404check")
    client.cookies.set("bmx_session", token)

    res = client.get("/esto-no-es-un-usuario-real", follow_redirects=False)
    assert res.status_code == 404


def test_username_portal_page_canonicalizes_non_sa_to_own_username(client, monkeypatch):
    """Un operador (no-SA) que visita el /{username} de OTRO operador se
    canoniza (302) a su propia URL — los endpoints /api/operator/* ya scopean
    por sesión, esto es solo coherencia visual de la URL."""
    monkeypatch.delenv("BMX_WEB_AUTH_MODE", raising=False)
    from auth import USERS, create_session, sha256
    USERS["testop_self"] = {
        "password_hash": sha256("pass123"), "role": "operator",
        "telegram_id": 991144, "display": "Test Self",
    }
    USERS["testop_other"] = {
        "password_hash": sha256("pass123"), "role": "operator",
        "telegram_id": 991155, "display": "Test Other",
    }
    token = create_session("testop_self")
    client.cookies.set("bmx_session", token)

    res = client.get("/testop_other", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/testop_self"


def test_legacy_user_id_url_redirects_to_username(client, monkeypatch):
    """Compat: links viejos a /user/{telegram_id} (pre 2026-08-06) siguen
    funcionando — 302 al nuevo /{username} en vez de 404 muerto para quien
    tenga un bookmark o link viejo del bot."""
    monkeypatch.delenv("BMX_WEB_AUTH_MODE", raising=False)
    from auth import USERS, create_session, sha256
    USERS["testop_legacyurl"] = {
        "password_hash": sha256("pass123"), "role": "operator",
        "telegram_id": 991166, "display": "Test Legacy",
    }
    token = create_session("testop_legacyurl")
    client.cookies.set("bmx_session", token)

    res = client.get("/user/991166", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/testop_legacyurl"

    res404 = client.get("/user/8887776665", follow_redirects=False)
    assert res404.status_code == 404


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
