# Tests Fase 3 (KPI "Cuentas a la mano"): GET /api/accounts/at-hand
# Seed (conftest): a@=asignada a 555 y lockeada por 555, b@=ajena (del SA), c@=lockeada por 555 (DEAD).
# Un solo origen de verdad server-side: pineadas (account_marks) + recientes (deposit_attempts/locks/marks),
# ambas enriquecidas con id/status/balance/grade/combo y filtradas por _visible_emails (misma ley que /api/recent).


def test_shape_has_pinned_and_recent_keys(make_client):
    cli = make_client(role="superadmin")
    r = cli.get("/api/accounts/at-hand")
    assert r.status_code == 200
    body = r.json()
    assert "pinned" in body and "recent" in body
    assert isinstance(body["pinned"], list)
    assert isinstance(body["recent"], list)


def test_pinned_account_enriched_with_id_and_combo(make_client):
    lau = make_client(role="user", telegram_id=555, username="lau")
    # a@test.com esta asignada a 555 -> dentro de su universo visible.
    assert lau.post("/api/marks/toggle", json={"email": "a@test.com"}).json()["marked"] is True

    body = lau.get("/api/accounts/at-hand").json()
    pinned = {row["email"]: row for row in body["pinned"]}
    assert "a@test.com" in pinned
    row = pinned["a@test.com"]
    assert row["id"] is not None
    assert row["status"] == "LIVE"
    assert row["balance_total"] == 100.0
    assert row["grade"] == "A"
    assert row["combo"] == "a@test.com:x"  # email:password, sin mascarar (regla no-masking)


def test_recent_account_has_id_and_last_ts(make_client):
    lau = make_client(role="user", telegram_id=555, username="lau")
    # a@test.com tiene un deposit_attempt de 555 en el seed (conftest linea 86-87).
    body = lau.get("/api/accounts/at-hand").json()
    recent = {row["email"]: row for row in body["recent"]}
    assert "a@test.com" in recent
    row = recent["a@test.com"]
    assert row["id"] is not None
    assert "last_ts" in row and row["last_ts"]


def test_operator_does_not_see_foreign_account(make_client):
    lau = make_client(role="user", telegram_id=555, username="lau")
    # b@test.com es ajena (del SA); aunque Lau intente marcarla, no debe aparecer.
    lau.post("/api/marks/toggle", json={"email": "b@test.com"})
    body = lau.get("/api/accounts/at-hand").json()
    all_emails = {row["email"] for row in body["pinned"]} | {row["email"] for row in body["recent"]}
    assert "b@test.com" not in all_emails


def test_sa_sees_own_recent_and_pinned(make_client):
    sa = make_client(role="superadmin", telegram_id=1341812706, username="robertvs")
    assert sa.post("/api/marks/toggle", json={"email": "b@test.com"}).json()["marked"] is True
    body = sa.get("/api/accounts/at-hand").json()
    pinned_emails = {row["email"] for row in body["pinned"]}
    assert "b@test.com" in pinned_emails
    # Decision de diseno: recent excluye lo que ya esta en pinned (dos listas
    # limpias, sin duplicar la misma cuenta en el KPI). b@test.com tiene ademas
    # un deposit_attempt propio del SA (conftest linea 88-89): igual no debe
    # duplicarse en recent porque ya vive en pinned.
    recent_emails = {row["email"] for row in body["recent"]}
    assert "b@test.com" not in recent_emails


def test_every_row_has_id_field_present(make_client):
    """Punto clave: el front necesita `id` para Pantalla.open(id); /api/recent no lo daba."""
    lau = make_client(role="user", telegram_id=555, username="lau")
    lau.post("/api/marks/toggle", json={"email": "a@test.com"})
    body = lau.get("/api/accounts/at-hand").json()
    for row in body["pinned"] + body["recent"]:
        assert "id" in row and row["id"] is not None
