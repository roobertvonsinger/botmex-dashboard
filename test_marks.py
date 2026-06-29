def test_account_marks_table_exists(make_client):
    import app
    with app.db() as c:
        cols = [r[1] for r in c.execute("PRAGMA table_info(account_marks)").fetchall()]
    assert set(["user_key", "account_email"]).issubset(set(cols))
