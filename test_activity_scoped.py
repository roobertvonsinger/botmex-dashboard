# test_activity_scoped.py
def test_activity_operator_only_own(make_client):
    cli = make_client(role="user", telegram_id=555, username="lau")
    feed = cli.get("/api/activity").json()["feed"]
    # seed: deposit de 555 (a@) y de 1341812706 (b@). Operador solo ve el suyo.
    targets = " ".join(str(e.get("target")) for e in feed)
    assert "a@test.com" in targets
    assert "b@test.com" not in targets   # acción del SA -> invisible al operador

def test_activity_sa_sees_all(make_client):
    cli = make_client(role="superadmin", telegram_id=1341812706, username="robertvs")
    feed = cli.get("/api/activity").json()["feed"]
    targets = " ".join(str(e.get("target")) for e in feed)
    assert "a@test.com" in targets and "b@test.com" in targets


def test_recent_includes_own_interactions_and_marks(make_client):
    cli = make_client(role="user", telegram_id=555, username="lau")
    cli.post("/api/marks/toggle", json={"email": "b@test.com"})  # marca una ajena (permitido: marcar no expone)
    data = cli.get("/api/recent").json()
    emails = {r["email"] for r in data["recent"]}
    assert "a@test.com" in emails     # depósito propio + lock propio
    assert "b@test.com" in emails     # marcada por el
    assert "stats" in data and "attempts" in data["stats"]

def test_recent_stats_scoped_to_user(make_client):
    cli = make_client(role="user", telegram_id=555, username="lau")
    stats = cli.get("/api/recent").json()["stats"]
    assert isinstance(stats["attempts"], int) and isinstance(stats["approved"], int)
