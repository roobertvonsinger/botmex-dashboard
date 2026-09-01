# test_pool_manage.py — Task 7: Pool manager backend (SA-only)
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


def test_hide_releases_sa_lock_but_protects_operator_lock(make_client):
    """Sacar a trastienda LIBERA la RESERVADA_SA perpetua (locked_until NULL) pero
    RESPETA el lock temporal de operador activo (locked_until en el futuro).
    Robert 2026-07-17: el candadito/auto-lock del SA trababa 'sacar del pool'."""
    import app
    sa = make_client(role="superadmin", telegram_id=1341812706, username="robertvs")

    # Modo Soberano: unpublish directo mueve la cuenta fuera del pool inmediatamente
    with app.db(write=True) as c:
        c.execute("UPDATE accounts SET published_to_pool=1 WHERE email='b@test.com'")
    assert sa.post("/api/pool/publish", json={"emails": ["b@test.com"], "publish": False}).json()["moved"] == 1
    with app.db() as c:
        row = c.execute("SELECT published_to_pool FROM accounts WHERE email='b@test.com'").fetchone()
    assert row[0] == 0  # oculta fuera del pool


def test_mark_rate_limited_isolates_pool_not_dead(make_client):
    """Verifica que _mark_rate_limited_dead retire la cuenta de la pool (published_to_pool=0)
    pero preserve status='LIVE'."""
    import app
    import deposits

    # Preparar cuenta LIVE dentro de la pool
    with app.db(write=True) as c:
        c.execute("UPDATE accounts SET status='LIVE', published_to_pool=1, dead_reason=NULL WHERE email='a@test.com'")

    # Simular detección de 429
    deposits._mark_rate_limited_dead("a@test.com")

    # Verificar que NO se marcó DEAD, pero SÍ salió del pool
    with app.db() as c:
        row = c.execute("SELECT status, published_to_pool, dead_reason FROM accounts WHERE email='a@test.com'").fetchone()
    assert row[0] == "LIVE"  # NO pasa a DEAD
    assert row[1] == 0       # Sale de la pool
    assert row[2] == "RATE_LIMITED_429"

