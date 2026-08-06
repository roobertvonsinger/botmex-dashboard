"""Tests del login anti-rate-limit (3 capas) — spec 2026-06-28.

Cubre Capa 1 (JWT cache fast-path + flag from_cache) y Capa 3 parcial
(BAN/429 → code RATE_LIMITED = enfriar y saltar, sin agotar reintentos).
Helpers de cooldown persistente.
"""
import asyncio
import importlib
import time

import login_orchestrator as lo
import deposits


# ── Fakes mínimos para correr gentle_login sin las deps reales del bot ──────────
class FakeDB:
    def __init__(self, cache=None):
        self._cache = cache

    def get_jwt_cache(self, email):
        return self._cache


class FakePool:
    """CaptchaTokenPool fake: entrega un token fijo."""
    def __init__(self, token=("TKN", "tid")):
        self._token = token

    async def get_token(self, timeout=30):
        return self._token


def make_fake_checker(status):
    """Fábrica de un BetmexicoApiChecker fake (async ctx mgr) que devuelve `status`."""
    class FakeChecker:
        def __init__(self, proxy=None):
            self.proxy = proxy

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def test_login(self, email, password, captcha_token=None,
                             captcha_task_id=None, fetch_mode="minimal"):
            if status == "LIVE":
                return {"status": "LIVE", "api": {"token": "JWT_FRESH"}}
            return {"status": status}

    return FakeChecker


def _patch_primitives(monkeypatch, checker_cls, db):
    monkeypatch.setattr(
        lo, "_import_login_primitives",
        lambda: (checker_cls, lambda *a, **k: None, db),
    )


# ── LoginResult.from_cache ──────────────────────────────────────────────────────
def test_loginresult_from_cache_defaults_false():
    assert lo.LoginResult(ok=True).from_cache is False


def test_cache_hit_sets_from_cache_true(monkeypatch):
    db = FakeDB(cache={"token": "JWT_CACHED", "expires_at": time.time() + 9999})
    _patch_primitives(monkeypatch, object, db)
    res = asyncio.run(lo.gentle_login(
        "e@x.com", "pw", use_cache=True, pool=None, allow_proxyless=True))
    assert res.ok is True
    assert res.from_cache is True
    assert res.jwt == "JWT_CACHED"
    assert res.attempts == 0


def test_fresh_login_not_from_cache(monkeypatch):
    db = FakeDB(cache=None)
    _patch_primitives(monkeypatch, make_fake_checker("LIVE"), db)
    res = asyncio.run(lo.gentle_login(
        "e@x.com", "pw", use_cache=True, pool=FakePool(),
        allow_proxyless=True, throttle=False))
    assert res.ok is True
    assert res.from_cache is False
    assert res.jwt == "JWT_FRESH"


# ── BAN/429 → RATE_LIMITED (enfriar y saltar) ───────────────────────────────────
def test_ban_returns_rate_limited_immediately(monkeypatch):
    db = FakeDB(cache=None)
    _patch_primitives(monkeypatch, make_fake_checker("BAN"), db)
    res = asyncio.run(lo.gentle_login(
        "e@x.com", "pw", pool=FakePool(), max_login_retries=4,
        allow_proxyless=True, throttle=False))
    assert res.ok is False
    assert res.code == "RATE_LIMITED"
    # No debe agotar los 4 intentos martillando: enfría y sale temprano.
    assert res.attempts <= 2


# ── Cooldown persistente (enfriar y saltar) ─────────────────────────────────────
def test_cooldown_active_future():
    assert deposits._cooldown_active(int(time.time()) + 600) is True


def test_cooldown_active_past():
    assert deposits._cooldown_active(int(time.time()) - 600) is False


def test_cooldown_active_none():
    assert deposits._cooldown_active(None) is False


def test_cooldown_active_zero():
    assert deposits._cooldown_active(0) is False


def test_cooldown_remaining_min_future():
    assert deposits._cooldown_remaining_min(int(time.time()) + 30 * 60) == 30


def test_cooldown_remaining_min_inactive():
    assert deposits._cooldown_remaining_min(int(time.time()) - 60) == 0
    assert deposits._cooldown_remaining_min(None) == 0


# ── Decisión de re-login tras 401 (Capa 1) ─────────────────────────────────────
def test_relogin_when_cache_and_not_yet():
    assert deposits._should_relogin_after_401(from_cache=True, already_relogged=False) is True


def test_no_relogin_when_not_from_cache():
    assert deposits._should_relogin_after_401(from_cache=False, already_relogged=False) is False


def test_no_relogin_when_already_relogged():
    assert deposits._should_relogin_after_401(from_cache=True, already_relogged=True) is False


# ── _acquire_session_and_begin: login + begin con re-login al 401 ───────────────
class _LR:
    """LoginResult-like mínimo."""
    def __init__(self, ok, jwt=None, code="LIVE", used_proxy=None, from_cache=False, error=None):
        self.ok = ok
        self.jwt = jwt
        self.code = code
        self._used_proxy = used_proxy
        self.from_cache = from_cache
        self.error = error
        self.attempts = 1

    @property
    def used_proxy(self):
        return self._used_proxy


def _fake_gentle(results):
    calls = []

    async def gl(email, password, **kw):
        calls.append(kw)
        return results.pop(0)

    gl.calls = calls
    return gl


def _fake_begin(results):
    calls = []

    async def bd(client, jwt, amount):
        calls.append(jwt)
        return results.pop(0)

    bd.calls = calls
    return bd


async def _noop_phase(name, payload):
    return None


def _run_acquire(monkeypatch, *, gentle, begin, proxies=("http://pool:1",),
                 invalidated=None, session_jwt=None, marked_dead=None):
    import login_orchestrator as _lo
    monkeypatch.setattr(_lo, "gentle_login", gentle)
    monkeypatch.setattr("proxy_pool.shuffled_proxy_urls", lambda: list(proxies))

    async def _fake_ax(jwt, proxy=None):
        return None
    import autoexclusion as _ax
    monkeypatch.setattr(_ax, "check_autoexclusion", _fake_ax)

    import prewarm as _pw
    inv = invalidated if invalidated is not None else []
    monkeypatch.setattr(_pw, "_db_invalidate_jwt", lambda e: inv.append(e))
    if marked_dead is not None:
        monkeypatch.setattr(
            _pw, "_db_mark_dead",
            lambda e, reason: marked_dead.append((e, reason)))

    return asyncio.run(deposits._acquire_session_and_begin(
        "e@x.com", "pw", 50.0, pool=object(), proxy=None,
        phase_cb=_noop_phase, user={"telegram_id": 0},
        session_jwt=session_jwt, session_proxy=None,
        persist_login_data=False, use_jwt_cache=True,
        begin_deposit_fn=begin,
    )), inv


def test_acquire_fresh_login_then_begin_ok(monkeypatch):
    gentle = _fake_gentle([_LR(True, jwt="JWT1", used_proxy="http://login:1")])
    begin = _fake_begin([{"orderId": "O1", "transactionId": "T1"}])
    res, inv = _run_acquire(monkeypatch, gentle=gentle, begin=begin)
    assert "fail" not in res
    assert res["jwt"] == "JWT1"
    assert res["used_proxy"] == "http://login:1"
    assert res["step1"]["orderId"] == "O1"
    asyncio.run(res["client"].aclose())


def test_acquire_cache_hit_assigns_pool_proxy_not_proxyless(monkeypatch):
    # cache hit → gentle devuelve from_cache=True SIN proxy → debe tomar uno del pool
    gentle = _fake_gentle([_LR(True, jwt="JWTC", used_proxy=None, from_cache=True)])
    begin = _fake_begin([{"orderId": "O1", "transactionId": "T1"}])
    res, inv = _run_acquire(monkeypatch, gentle=gentle, begin=begin, proxies=("http://pool:9",))
    assert "fail" not in res
    assert res["used_proxy"] == "http://pool:9"   # NUNCA None (proxyless)
    asyncio.run(res["client"].aclose())


def test_acquire_cache_401_invalidates_and_relogins(monkeypatch):
    # 1ª: cache hit (JWTC) → begin da 401. 2ª: login fresco (JWT2) → begin OK.
    gentle = _fake_gentle([
        _LR(True, jwt="JWTC", used_proxy="http://p:1", from_cache=True),
        _LR(True, jwt="JWT2", used_proxy="http://p:2", from_cache=False),
    ])
    begin = _fake_begin([
        {"error": "401 redirectLogin true"},
        {"orderId": "O2", "transactionId": "T2"},
    ])
    res, inv = _run_acquire(monkeypatch, gentle=gentle, begin=begin)
    assert "fail" not in res
    assert res["jwt"] == "JWT2"                 # usó el login fresco
    assert res["step1"]["orderId"] == "O2"
    assert inv == ["e@x.com"]                   # invalidó el cache muerto
    # la 2ª llamada a gentle NO debe usar cache
    assert gentle.calls[1].get("use_cache") is False
    asyncio.run(res["client"].aclose())


def test_acquire_rate_limited_marks_dead_and_fails(monkeypatch):
    # Robert 2026-08-06: ya no enfriar-y-reintentar — a la primera, DEAD.
    dead = []
    gentle = _fake_gentle([_LR(False, jwt=None, code="RATE_LIMITED",
                               error="rate-limit")])
    begin = _fake_begin([])
    res, inv = _run_acquire(monkeypatch, gentle=gentle, begin=begin, marked_dead=dead)
    assert "fail" in res
    assert res["fail"]["result_code"] == "RATE_LIMITED"
    assert dead == [("e@x.com", "RATE_LIMITED_INSTANT (429 — fuera al primer golpe, Robert 2026-08-06)")]


def test_set_account_cooldown_persists(seed_db):
    """_migrate crea cooldown_until; _set_account_cooldown lo escribe en BD."""
    import app as app_mod
    importlib.reload(app_mod)  # corre _migrate() sobre la BD seed → agrega columna
    until = deposits._set_account_cooldown("a@test.com", minutes=30)
    with app_mod.db() as c:
        row = c.execute(
            "SELECT cooldown_until FROM accounts WHERE email=?",
            ("a@test.com",),
        ).fetchone()
    assert row["cooldown_until"] == until
    assert deposits._cooldown_active(row["cooldown_until"]) is True
    # ~30 min en el futuro
    assert 29 * 60 <= (until - int(time.time())) <= 31 * 60
