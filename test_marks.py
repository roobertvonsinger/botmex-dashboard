def test_account_marks_table_exists(make_client):
    import app
    with app.db() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(account_marks)").fetchall()]
    assert set(["user_key", "account_email"]).issubset(set(cols))


def test_toggle_is_idempotent_and_private(make_client):
    lau = make_client(role="user", telegram_id=555, username="lau")
    # marcar
    assert lau.post("/api/marks/toggle", json={"email": "a@test.com"}).json()["marked"] is True
    assert lau.get("/api/marks").json()["marks"] == ["a@test.com"]
    # toggle de nuevo = desmarcar
    assert lau.post("/api/marks/toggle", json={"email": "a@test.com"}).json()["marked"] is False
    assert lau.get("/api/marks").json()["marks"] == []


def test_marks_are_private_per_user(make_client):
    lau = make_client(role="user", telegram_id=555, username="lau")
    lau.post("/api/marks/toggle", json={"email": "a@test.com"})
    sa = make_client(role="superadmin", telegram_id=1341812706, username="robertvs")
    assert sa.get("/api/marks").json()["marks"] == []  # SA no ve la marca de Lau


def test_mark_does_not_lock_or_change_visibility(make_client):
    import app
    lau = make_client(role="user", telegram_id=555, username="lau")
    lau.post("/api/marks/toggle", json={"email": "a@test.com"})
    with app.db() as c:
        row = c.execute("SELECT locked_by, published_to_pool FROM accounts WHERE email='a@test.com'").fetchone()
    assert row["locked_by"] == 555            # el lock previo no cambió por marcar
    assert row["published_to_pool"] == 1      # visibilidad intacta
