def test_never_attempted_accounts_prioritized_over_attempted(tmp_path):
    """Cuentas con 0 intentos o intento más antiguo tienen oportunidad justa.
    Verifica que el ORDER BY (SELECT COUNT(*)...) ASC en plan_auto_mission funcione."""
    import sqlite3
    import auto_deposit as ad

    def _make_db(tmp_path):
        db_file = tmp_path / "test_betmexico.db"
        con = sqlite3.connect(str(db_file))
        con.executescript("""
        CREATE TABLE accounts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT UNIQUE,
            password TEXT,
            fullname TEXT,
            status TEXT DEFAULT 'LIVE',
            grade TEXT DEFAULT 'B',
            grade_score INTEGER DEFAULT 70,
            kyc_verified INTEGER DEFAULT 1,
            published_to_pool INTEGER DEFAULT 0,
            locked_by INTEGER,
            cooldown_until INTEGER,
            balance_real REAL,
            withdrawal_ready INTEGER DEFAULT 0,
            dead_reason TEXT,
            dead_at TEXT,
            jwt_expires_at INTEGER DEFAULT 2147483647,
            last_checked_at TEXT
        );

        CREATE TABLE deposit_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            account_email TEXT,
            amount REAL,
            status TEXT,
            rejection_reason TEXT,
            card_pipe TEXT,
            created_at TEXT
        );
        """)
        con.close()
        return db_file

    db = _make_db(tmp_path)
    con = sqlite3.connect(str(db))
    # 3 cuentas LIVE: 0 intentos, 1 intento reciente, 1 intento antiguo
    con.execute('INSERT INTO accounts (email, status, grade, published_to_pool, kyc_verified, last_checked_at, jwt_expires_at) VALUES ("never@t.com", "LIVE", "D", 1, 1, "2026-01-01", 9999999999)')
    con.execute('INSERT INTO accounts (email, status, grade, published_to_pool, kyc_verified, last_checked_at, jwt_expires_at) VALUES ("recent@t.com", "LIVE", "D", 1, 1, "2026-01-02", 9999999999)')
    con.execute('INSERT INTO accounts (email, status, grade, published_to_pool, kyc_verified, last_checked_at, jwt_expires_at) VALUES ("old@t.com", "LIVE", "D", 1, 1, "2026-01-03", 9999999999)')
    # Intento reciente (5 min)
    con.execute('INSERT INTO deposit_attempts (account_email, amount, status, created_at) VALUES ("recent@t.com", 10, "rejected", datetime("now", "-5 minutes"))')
    # Intento antiguo (30 días)
    con.execute('INSERT INTO deposit_attempts (account_email, amount, status, created_at) VALUES ("old@t.com", 10, "rejected", datetime("now", "-30 days"))')
    con.commit()
    con.close()

    # Test directo a select_accounts_for_auto (evita dependencias de plan_auto_mission)
    con = sqlite3.connect(str(db))
    con.row_factory = sqlite3.Row
    rows = [dict(r) for r in con.execute("SELECT * FROM accounts WHERE published_to_pool=1").fetchall()]
    con.close()

    window_map = {
        "never@t.com": {"available": 5000.0},
        "recent@t.com": {"available": 5000.0},
        "old@t.com": {"available": 5000.0},
    }
    meta_map = {
        "never@t.com": {
            "mins_since_last_attempt": 99999,  # Nunca intentada
            "total_fails": 0,
            "cards_count": 0,
            "has_3ds_24h": False,
            "has_dashboard_approved_48h": False,
            "has_spei_48h": False,
            "has_pending_withdrawal": False,
            "is_validation_blocked": False,
            "is_dead_blocked": False,
            "is_rate_limited": False
        },
        "recent@t.com": {
            "mins_since_last_attempt": 5,    # Intentada hace 5 minutos
            "total_fails": 0,
            "cards_count": 0,
            "has_3ds_24h": False,
            "has_dashboard_approved_48h": False,
            "has_spei_48h": False,
            "has_pending_withdrawal": False,
            "is_validation_blocked": False,
            "is_dead_blocked": False,
            "is_rate_limited": False
        },
        "old@t.com": {
            "mins_since_last_attempt": 43200,   # Intentada hace 30 días
            "total_fails": 0,
            "cards_count": 0,
            "has_3ds_24h": False,
            "has_dashboard_approved_48h": False,
            "has_spei_48h": False,
            "has_pending_withdrawal": False,
            "is_validation_blocked": False,
            "is_dead_blocked": False,
            "is_rate_limited": False
        },
    }

    selected = ad.select_accounts_for_auto(rows, 150, 3, window_map, meta_map=meta_map)
    emails = [a["email"] for a in selected]
    print("Selected emails:", emails)
    # Las 3 cuentas deben estar presentes
    assert len(emails) == 3
    # never@t.com (0 intentos) debe ir primero
    assert emails[0] == "never@t.com"
    # old@t.com (intento antiguo) debe ir antes que recent@t.com (intento reciente)
    assert emails.index("old@t.com") < emails.index("recent@t.com")