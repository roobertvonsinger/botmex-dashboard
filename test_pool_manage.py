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
