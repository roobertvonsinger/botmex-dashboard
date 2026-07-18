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

    # b@ = RESERVADA_SA perpetua (locked_until NULL) → ocultar la libera + oculta.
    with app.db(write=True) as c:
        c.execute("UPDATE accounts SET published_to_pool=1, locked_by='1341812706', "
                  "locked_at='2026-07-01 00:00:00', locked_until=NULL WHERE email='b@test.com'")
    assert sa.post("/api/pool/publish", json={"emails": ["b@test.com"], "publish": False}).json()["moved"] == 1
    with app.db() as c:
        row = c.execute("SELECT published_to_pool, locked_by FROM accounts WHERE email='b@test.com'").fetchone()
    assert row[0] == 0 and row[1] is None            # oculta + lock liberado

    # lock TEMPORAL de operador (locked_until futuro) → NO se oculta, lock intacto.
    with app.db(write=True) as c:
        c.execute("UPDATE accounts SET published_to_pool=1, locked_by='555', "
                  "locked_at='2026-07-01 00:00:00', locked_until='2099-01-01 00:00:00' WHERE email='b@test.com'")
    assert sa.post("/api/pool/publish", json={"emails": ["b@test.com"], "publish": False}).json()["moved"] == 0
    with app.db() as c:
        row = c.execute("SELECT published_to_pool, locked_by FROM accounts WHERE email='b@test.com'").fetchone()
    assert row[0] == 1 and str(row[1]) == '555'      # sigue publicada + lock de operador intacto
