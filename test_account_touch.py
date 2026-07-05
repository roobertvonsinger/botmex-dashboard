# test_account_touch.py
# Fase 1: evento account_touch — visibilidad (actor nunca ve el suyo, ni el SA)
# + dedup 1/dia por usuario+cuenta en account_touches.

SA = {"role": "superadmin", "telegram_id": 1341812706, "display": "RobertVS"}
OP_A = {"role": "user", "telegram_id": 555, "display": "Lau"}
OP_B = {"role": "user", "telegram_id": 777, "display": "Otro"}


def test_actor_operator_does_not_see_own_touch(seed_db):
    import app
    assert app._event_visible_to({"kind": "account_touch", "who_id": 555}, OP_A) is False


def test_sa_does_not_see_own_touch(seed_db):
    import app
    ctx = {"role": "superadmin", "telegram_id": 555}
    assert app._event_visible_to({"kind": "account_touch", "who_id": 555}, ctx) is False


def test_sa_sees_others_touch(seed_db):
    import app
    assert app._event_visible_to({"kind": "account_touch", "who_id": 555}, SA) is True


def test_operator_does_not_see_others_touch(seed_db):
    import app
    assert app._event_visible_to({"kind": "account_touch", "who_id": 555}, OP_B) is False


def test_touch_dedup_one_per_day(seed_db):
    import app
    with app.db(write=True) as c:
        c.execute(
            "INSERT OR IGNORE INTO account_touches "
            "(account_id, account_email, actor_id, touched_at, touched_date) "
            "VALUES (?,?,?,?,?)",
            (1, "a@test.com", 555, "2026-07-05 10:00:00", "2026-07-05"),
        )
        c.execute(
            "INSERT OR IGNORE INTO account_touches "
            "(account_id, account_email, actor_id, touched_at, touched_date) "
            "VALUES (?,?,?,?,?)",
            (1, "a@test.com", 555, "2026-07-05 15:30:00", "2026-07-05"),
        )
    with app.db() as c:
        rows = c.execute(
            "SELECT * FROM account_touches WHERE account_id=? AND actor_id=?",
            (1, 555),
        ).fetchall()
    assert len(rows) == 1
