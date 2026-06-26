# Tests A2.1: el dashboard no avienta info de mas — cada operador ve solo su universo.
# Seed (conftest): a@=asignada a 555, c@=lockeada por 555, b@=ajena (del SA 1341812706).


# ── Task 1: helper _visible_emails ─────────────────────────────────────────────
def test_visible_emails_sa_sees_all(make_client):
    import app
    with app.db() as c:
        assert app._visible_emails({"role": "superadmin", "telegram_id": 1341812706}, c) is None

def test_visible_emails_operator_scoped(make_client):
    import app
    with app.db() as c:
        vis = app._visible_emails({"role": "user", "telegram_id": 555, "username": "lau"}, c)
    assert vis == {"a@test.com", "c@test.com"}  # asignada + lockeada por el, NO b@


# ── Task 2: /api/cards/all ─────────────────────────────────────────────────────
def test_cards_all_sa_sees_both(make_client):
    cli = make_client(role="superadmin")
    rows = cli.get("/api/cards/all").json()["rows"]
    emails = {r["account_email"] for r in rows}
    assert {"a@test.com", "b@test.com"} <= emails

def test_cards_all_operator_scoped(make_client):
    cli = make_client(role="user", telegram_id=555, username="lau")
    rows = cli.get("/api/cards/all").json()["rows"]
    emails = {r["account_email"] for r in rows}
    assert "a@test.com" in emails        # suya (asignada)
    assert "b@test.com" not in emails     # ajena -> NO la ve


# ── Task 3: pass-map + combos ──────────────────────────────────────────────────
def test_pass_map_operator_scoped(make_client):
    cli = make_client(role="user", telegram_id=555, username="lau")
    m = cli.get("/api/accounts/pass-map").json()
    assert "a@test.com" in m and "b@test.com" not in m

def test_combos_operator_cannot_get_foreign(make_client):
    cli = make_client(role="user", telegram_id=555, username="lau")
    combos = cli.post("/api/accounts/combos", json={"ids": [1, 2]}).json()["combos"]
    got = {c["email"] for c in combos}
    assert "a@test.com" in got and "b@test.com" not in got


# ── Task 4: /api/deposits ──────────────────────────────────────────────────────
def test_deposits_operator_only_own(make_client):
    cli = make_client(role="user", telegram_id=555, username="lau")
    rows = cli.get("/api/deposits").json()
    assert {r["operator_id"] for r in rows} <= {555}
    rows2 = cli.get("/api/deposits?operator_id=1341812706").json()
    assert all(r["operator_id"] == 555 for r in rows2)

def test_deposits_sa_sees_all(make_client):
    cli = make_client(role="superadmin")
    rows = cli.get("/api/deposits").json()
    assert {555, 1341812706} <= {r["operator_id"] for r in rows}
