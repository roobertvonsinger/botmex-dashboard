# test_a1_estados.py — A1: modelo de estados + consolidación de watchdogs
# Spec: docs/superpowers/specs/2026-06-26-sp3-modal-unificado-spec.md §A1
import sqlite3, importlib
import pytest

SA = "1341812706"   # telegram del superadmin (auth.py)

SCHEMA = """
CREATE TABLE accounts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT NOT NULL, password TEXT NOT NULL DEFAULT 'x',
  balance_total REAL DEFAULT 0,
  last_deposit_amount REAL DEFAULT 0, last_deposit_date TEXT DEFAULT 'N/A',
  status TEXT DEFAULT 'LIVE',
  first_checked_at TEXT DEFAULT '2026-05-01 00:00:00',
  last_checked_at TEXT DEFAULT '2026-05-05 00:00:00', check_count INTEGER DEFAULT 1,
  locked_by TEXT DEFAULT NULL, locked_at TEXT DEFAULT NULL, locked_until TEXT DEFAULT NULL,
  published_to_pool INTEGER DEFAULT 1,
  notif_pre24h_sent_at TEXT DEFAULT NULL,
  notif_at24h_sent_at TEXT DEFAULT NULL,
  notif_at24h10_sent_at TEXT DEFAULT NULL,
  grade TEXT DEFAULT '?'
);
CREATE TABLE deposit_attempts (
  id INTEGER PRIMARY KEY AUTOINCREMENT, account_email TEXT, amount REAL,
  status TEXT, operator_id INTEGER, created_at TEXT
);
CREATE TABLE account_cards (
  id INTEGER PRIMARY KEY AUTOINCREMENT, card_number TEXT, account_email TEXT,
  registered_at TEXT
);
"""

def _ins(con, email, **kw):
    cols = {"email": email}
    cols.update(kw)
    keys = ",".join(cols.keys())
    qs = ",".join("?" * len(cols))
    cur = con.execute(f"INSERT INTO accounts ({keys}) VALUES ({qs})", list(cols.values()))
    return cur.lastrowid

@pytest.fixture
def a1(tmp_path, monkeypatch):
    """Devuelve (app_mod, con_factory, broadcasts). BD con esquema A1 completo."""
    dbp = tmp_path / "a1.db"
    monkeypatch.setenv("BETMEX_DB", str(dbp))
    monkeypatch.setenv("BMX_WEB_AUTH_MODE", "open")
    con = sqlite3.connect(dbp)
    con.executescript(SCHEMA)
    con.commit(); con.close()
    import app as app_mod
    importlib.reload(app_mod)
    broadcasts = []
    monkeypatch.setattr(app_mod, "_broadcast", lambda ev: broadcasts.append(ev))
    def fresh():
        c = sqlite3.connect(dbp); c.row_factory = sqlite3.Row; return c
    return app_mod, fresh, broadcasts


def test_release_account_atomico_y_republica(a1):
    """T1: el helper canónico libera TODO atómicamente, republica y emite 1 broadcast."""
    app_mod, con, broadcasts = a1
    c0 = con()
    aid = _ins(c0, "en_uso@test.com", locked_by="555",
               locked_at="2026-06-26 00:00:00", locked_until="2026-06-26 02:00:00",
               published_to_pool=0,
               notif_pre24h_sent_at="2026-06-26 00:00:00",
               notif_at24h_sent_at="2026-06-26 01:00:00",
               notif_at24h10_sent_at="2026-06-26 01:10:00")
    c0.commit(); c0.close()

    with app_mod.db(write=True) as c:
        app_mod._release_account(c, aid, "en_uso@test.com", "test release", "555")

    r = con().execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
    assert r["locked_by"] is None
    assert r["locked_at"] is None
    assert r["locked_until"] is None
    assert r["notif_pre24h_sent_at"] is None
    assert r["notif_at24h_sent_at"] is None
    assert r["notif_at24h10_sent_at"] is None
    assert r["published_to_pool"] == 1          # SIEMPRE republica
    assert len(broadcasts) == 1
    ev = broadcasts[0]
    assert ev.get("kind") == "unlock_auto"
    assert ev.get("prev_locked_by") == "555"
    assert ev.get("target") == "en_uso@test.com"
