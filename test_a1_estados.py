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


def test_backfill_legacy_no_toca_reservada_sa(a1):
    """T2: _migrate re-temporiza locks legacy sin locked_until; deja intacta la RESERVADA_SA."""
    app_mod, con, _ = a1
    c0 = con()
    legacy = _ins(c0, "legacy@test.com", locked_by="777",
                  locked_at="2026-06-20 00:00:00", locked_until=None)
    sa = _ins(c0, "reservada@test.com", locked_by=SA,
              locked_at="2026-06-20 00:00:00", locked_until=None)
    pool = _ins(c0, "pool@test.com")  # sin lock
    c0.commit(); c0.close()

    app_mod._migrate()   # idempotente; backfill defensivo

    r = con().execute("SELECT id,locked_until FROM accounts").fetchall()
    by_id = {x["id"]: x["locked_until"] for x in r}
    assert by_id[legacy] == "2026-06-21 00:00:00"   # locked_at + 24h
    assert by_id[sa] is None                          # RESERVADA_SA intacta
    assert by_id[pool] is None                        # sin lock, sin cambio

    # idempotencia: 2da corrida no altera el ya-seteado
    app_mod._migrate()
    again = con().execute("SELECT locked_until FROM accounts WHERE id=?", (legacy,)).fetchone()
    assert again["locked_until"] == "2026-06-21 00:00:00"


def test_janitor_unico_liberador_republica_y_respeta_sa(a1):
    """T6: janitor libera vía _release_account (republica+limpia notif) y NO toca RESERVADA_SA."""
    app_mod, con, broadcasts = a1
    c0 = con()
    venc = _ins(c0, "vencida@test.com", locked_by="555",
                locked_at="2020-01-01 00:00:00", locked_until="2020-01-01 02:00:00",
                published_to_pool=0, notif_at24h_sent_at="2020-01-01 00:00:00")
    sa = _ins(c0, "reservada@test.com", locked_by=SA, locked_until=None)
    c0.commit(); c0.close()

    freed = app_mod._run_lock_janitor()

    rows = {x["id"]: x for x in con().execute("SELECT * FROM accounts").fetchall()}
    assert freed == 1
    assert rows[venc]["locked_by"] is None
    assert rows[venc]["published_to_pool"] == 1          # republica (antes NO lo hacía)
    assert rows[venc]["notif_at24h_sent_at"] is None     # limpia notif (antes NO)
    assert rows[sa]["locked_by"] == SA                    # RESERVADA_SA intocable
    assert any(b.get("kind") == "unlock_auto" for b in broadcasts)


def test_window_watcher_notifica_normal_pero_no_a_sa_ni_libera(a1):
    """T3: guard RESERVADA_SA (no notif). T6: ya no libera (fase 3 muerta eliminada)."""
    from datetime import datetime, timezone, timedelta
    app_mod, con, broadcasts = a1
    # depósito hace ~24h05m -> mins_left ≈ -5 -> fase 2 (expired) para cuenta normal
    ts = (datetime.now(timezone.utc) - timedelta(hours=24, minutes=5)).strftime("%Y-%m-%d %H:%M:%S")
    c0 = con()
    normal = _ins(c0, "wnormal@test.com", locked_by="555",
                  locked_at="2026-06-20 00:00:00", locked_until="2026-06-27 00:00:00")
    sa = _ins(c0, "wsa@test.com", locked_by=SA, locked_until=None)  # RESERVADA_SA
    for em in ("wnormal@test.com", "wsa@test.com"):
        c0.execute("INSERT INTO deposit_attempts (account_email,amount,status,operator_id,created_at) "
                   "VALUES (?,?,?,?,?)", (em, 50, "approved", 555, ts))
    c0.commit(); c0.close()

    out = app_mod._run_window_watcher()

    # cuenta normal: notificada (fase 2 expired); RESERVADA_SA: ninguna notif
    assert any(b.get("email") == "wnormal@test.com" for b in broadcasts)
    assert not any(b.get("email") == "wsa@test.com" for b in broadcasts)
    # T6: window_watcher ya no libera a nadie (sin fase 3)
    assert out["released"] == 0
    rows = {x["id"]: x for x in con().execute("SELECT * FROM accounts").fetchall()}
    assert rows[normal]["locked_by"] == "555"
    assert rows[sa]["locked_by"] == SA


def test_release_watchdog_no_autorelease_y_guard_sa(a1):
    """T6: release_watchdog pierde el auto-release 27h. T3: no notifica a RESERVADA_SA."""
    app_mod, con, broadcasts = a1
    c0 = con()
    enuso = _ins(c0, "enuso@test.com", locked_by="555",
                 locked_at="2026-06-20 00:00:00", locked_until="2026-12-31 00:00:00",
                 last_deposit_date="01/01/2026 00:00")          # hace >27h -> antes auto-release
    sa = _ins(c0, "reservada@test.com", locked_by=SA, locked_until=None,
              last_deposit_date="01/01/2026 00:00")
    c0.commit(); c0.close()

    app_mod._release_watchdog_tick()

    rows = {x["id"]: x for x in con().execute("SELECT * FROM accounts").fetchall()}
    assert rows[enuso]["locked_by"] == "555"                    # NO auto-liberada
    assert not any(b.get("kind") == "unlock_auto" for b in broadcasts)
    # RESERVADA_SA: ninguna notif (guard locked_until IS NOT NULL)
    assert not any(b.get("account_id") == sa for b in broadcasts)


def test_unlock_manual_republica_via_helper(a1):
    """T6: unlock manual pasa por _release_account → republica + limpia notif (antes NO republicaba)."""
    from fastapi.testclient import TestClient
    app_mod, con, broadcasts = a1
    c0 = con()
    aid = _ins(c0, "manual@test.com", locked_by="555",
               locked_at="2026-06-26 00:00:00", locked_until="2026-06-26 02:00:00",
               published_to_pool=0, notif_at24h_sent_at="2026-06-26 01:00:00")
    c0.commit(); c0.close()

    app_mod.app.dependency_overrides[app_mod.require_session] = lambda: {
        "role": "superadmin", "telegram_id": 1341812706, "username": "robertvs"}
    try:
        cli = TestClient(app_mod.app)
        rsp = cli.post(f"/api/accounts/{aid}/unlock")
        assert rsp.status_code == 200
    finally:
        app_mod.app.dependency_overrides.clear()

    r = con().execute("SELECT * FROM accounts WHERE id=?", (aid,)).fetchone()
    assert r["locked_by"] is None
    assert r["published_to_pool"] == 1                 # republica (antes NO)
    assert r["notif_at24h_sent_at"] is None
    assert any(b.get("kind") == "unlock" for b in broadcasts)


def _client(app_mod, role="superadmin", tg=1341812706, username="robertvs"):
    from fastapi.testclient import TestClient
    app_mod.app.dependency_overrides[app_mod.require_session] = lambda: {
        "role": role, "telegram_id": tg, "username": username, "display": username}
    return TestClient(app_mod.app)


def test_lock_sa_override_y_perpetuo(a1):
    """T5: SA lockea cuenta YA ocupada por operador → override + locked_until NULL (RESERVADA_SA)."""
    app_mod, con, _ = a1
    c0 = con(); aid = _ins(c0, "ocupada@test.com", locked_by="555",
                           locked_at="2026-06-26 00:00:00", locked_until="2026-06-26 02:00:00")
    c0.commit(); c0.close()
    try:
        rsp = _client(app_mod).post(f"/api/accounts/{aid}/lock", json={"operator": "robertvs", "hours": 2})
    finally:
        app_mod.app.dependency_overrides.clear()
    assert rsp.status_code == 200
    assert rsp.json()["locked_until"] is None          # perpetuo
    r = con().execute("SELECT locked_by, locked_until FROM accounts WHERE id=?", (aid,)).fetchone()
    assert r["locked_by"] == "robertvs"
    assert r["locked_until"] is None


def test_lock_operador_409_si_ocupada_y_temporal_si_libre(a1):
    """T5: operador NO hace override (409 si ocupada); si libre, lock temporal (locked_until no-nulo)."""
    app_mod, con, _ = a1
    c0 = con()
    ocup = _ins(c0, "ocup@test.com", locked_by="555", locked_at="2026-06-26 00:00:00",
                locked_until="2026-06-26 02:00:00")
    libre = _ins(c0, "libre@test.com")
    c0.commit(); c0.close()
    try:
        r409 = _client(app_mod, role="user", tg=999, username="op999").post(
            f"/api/accounts/{ocup}/lock", json={"operator": "op999", "hours": 2})
        rok = _client(app_mod, role="user", tg=999, username="op999").post(
            f"/api/accounts/{libre}/lock", json={"operator": "op999", "hours": 2})
    finally:
        app_mod.app.dependency_overrides.clear()
    assert r409.status_code == 409
    assert rok.status_code == 200 and rok.json()["locked_until"] is not None


def test_publish_hide_no_oculta_cuentas_en_uso(a1):
    """T4: publish/hide NO oculta (published=0) cuentas lockeadas → evita fantasma."""
    app_mod, con, _ = a1
    c0 = con()
    enuso = _ins(c0, "enuso@test.com", locked_by="555", locked_at="2026-06-26 00:00:00",
                 locked_until="2026-06-26 02:00:00", published_to_pool=1)
    libre = _ins(c0, "libre@test.com", published_to_pool=1)
    c0.commit(); c0.close()
    try:
        cli = _client(app_mod)
        cli.post("/api/accounts/publish", json={"ids": [enuso, libre], "publish": False})
        cli.post("/api/accounts/hide-all")
    finally:
        app_mod.app.dependency_overrides.clear()
    rows = {x["id"]: x["published_to_pool"] for x in con().execute("SELECT id,published_to_pool FROM accounts").fetchall()}
    assert rows[enuso] == 1     # lockeada NO se oculta
    assert rows[libre] == 0     # libre sí
