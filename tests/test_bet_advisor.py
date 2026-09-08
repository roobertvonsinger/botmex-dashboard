# tests/test_bet_advisor.py — Fase 3 del refactor /bet: operador LLM de pre-selección.
#
# El advisor NUNCA decide: devuelve hints (boost por cuenta) que el núcleo Python
# determinista puede ignorar. Estas pruebas fijan las 3 garantías innegociables:
#
#   1. CERO PII al 9router. `_build_advisor_request` construye campo por campo
#      (nunca dict(row)); `_assert_no_pii` es el backstop fail-closed que LANZA
#      antes de cualquier request. Property test: filas con email/PAN/jwt dentro
#      → ninguno aparece en el payload.
#   2. `_sanitize_advice` valida la respuesta contra el set elegible post-filtro:
#      descarta refs desconocidas, clampa boost ∈ [-3,3], rechaza pairings que no
#      pasan los predicados del matcher, y ante JSON con claves extra / malformado
#      descarta TODA la advice.
#   3. `maybe_advise` → None en env OFF / timeout / JSON malo / sin candidatas, y
#      escribe una fila en `bet_llm_calls` en TODO camino (incluso los fallos).

import json
import sqlite3

import httpx
import pytest

import bet_advisor as ba
import bet_policy
import support_llm


# ─────────────────────────────────────────────────────────── helpers de fixture

def _mk_inputs(n_cand=3, n_cards=1, max_accounts=6):
    """AdvisorInputs con refs opacas ya asignadas + el ref→email map."""
    candidates = []
    ref2email = {}
    for i in range(n_cand):
        ref = f"A{i}"
        email = f"user{i}@gmail.com"
        ref2email[ref] = email
        candidates.append({
            "ref": ref,
            "email": email,                       # SOLO para traducir de vuelta
            "grade": ["A+", "A", "B"][i % 3],
            "session_alive": i == 0,
            "tier_hint": ["TOP", "MID", "LOW"][i % 3],
            "window_available": 3000.0,
            "declines_1h": 0,
            "total_fails": i,
            "has_3ds_24h": i == 0,
            "mins_since_last_attempt": 500 + i,
            "cards_count": i,
            "approved_bins": ["491702"] if i == 0 else [],
            "last_activity_days": 1.0 + i,
            "hot_balance": False,
        })
    cards = [{
        "ref": f"C{j}",
        "bin": f"49170{j}",
        "bin_tier": "CORONA",
        "bin_approval_rate": 0.82,
        "bin_threeds_recent": False,
        "declines_24h": 0,
    } for j in range(n_cards)]
    mission_meta = {
        "amount": 150.0, "target_count": 9, "n_cards": n_cards,
        "max_accounts": max_accounts, "policy_digest": bet_policy.digest(),
    }
    recent = {
        "probes_per_match_avg": 2.4, "top_tier_probe_approval": 0.7,
        "mid_tier_probe_approval": 0.5, "bin_tier_approval": {"CORONA": 0.8},
    }
    return ba.AdvisorInputs(candidates, cards, mission_meta, recent), ref2email


def _leak_inputs():
    """AdvisorInputs cuyas filas de candidato traen PII cruda embebida
    (email, jwt, PAN, cvv) — el builder debe filtrarla toda."""
    inp, ref2email = _mk_inputs(n_cand=2)
    for c in inp.candidates:
        c["jwt_token"] = "eyJhbGciOiJIUzI1NiJ9.SECRETPAYLOAD.sig"
        c["password"] = "hunter2"
        c["card_number"] = "4917023456789012"
        c["proxy"] = "http://user:pass@1.2.3.4:8080"
        c["curp"] = "XEXX010101HNEXXXA4"
    return inp, ref2email


def _sse(*chunks):
    return "".join(f"data: {c}\n\n" for c in chunks).encode()


def _json_stream(obj, *, tin=90, tout=40):
    payload = json.dumps({"choices": [{"delta": {"content": json.dumps(obj)}}]})
    usage = json.dumps({"choices": [{"delta": {}}],
                        "usage": {"prompt_tokens": tin, "completion_tokens": tout}})
    return httpx.Response(200, content=_sse(payload, usage, "[DONE]"))


def _fake_client(response_obj=None, *, raw_text=None, status=200, hang=False):
    def handler(_req):
        if hang:
            raise httpx.ReadTimeout("simulated hang")
        if status != 200:
            return httpx.Response(status, json={"error": {"message": "down"}})
        if raw_text is not None:
            body = json.dumps({"choices": [{"delta": {"content": raw_text}}]})
            return httpx.Response(200, content=_sse(body, "[DONE]"))
        return _json_stream(response_obj or {})
    return support_llm.LLMClient(base_url="http://router:20128",
                                 chain=["m-a"], timeout=6.0,
                                 transport=httpx.MockTransport(handler))


@pytest.fixture
def db_path(tmp_path, monkeypatch):
    p = tmp_path / "adv.db"
    con = sqlite3.connect(p)
    con.execute(
        "CREATE TABLE bet_llm_calls ("
        "id INTEGER PRIMARY KEY AUTOINCREMENT, kind TEXT NOT NULL, model TEXT, "
        "tokens_in INTEGER, tokens_out INTEGER, cost_usd REAL DEFAULT 0, "
        "latency_ms INTEGER, mission_id TEXT, outcome TEXT, created_at TEXT NOT NULL)"
    )
    con.commit()
    con.close()
    monkeypatch.setenv("BETMEX_DB", str(p))
    return str(p)


def _calls(db_path):
    con = sqlite3.connect(db_path)
    try:
        return [dict(zip([d[0] for d in cur.description], row))
                for cur in [con.execute("SELECT * FROM bet_llm_calls ORDER BY id")]
                for row in cur.fetchall()]
    finally:
        con.close()


# ───────────────────────────────────────────────── 1. request builder sin PII

def test_build_request_shape_is_whitelisted():
    inp, _ = _mk_inputs()
    req = ba._build_advisor_request(inp)
    assert set(req) == {"mission", "candidates", "cards", "recent_history"}
    assert set(req["candidates"][0]) == {
        "ref", "grade", "session_alive", "tier_hint", "window_available", "declines_1h",
        "total_fails", "has_3ds_24h", "mins_since_last_attempt", "cards_count",
        "approved_bins", "last_activity_days", "hot_balance",
    }
    assert req["candidates"][0]["ref"] == "A0"


def test_build_request_drops_embedded_pii():
    inp, _ = _leak_inputs()
    blob = json.dumps(ba._build_advisor_request(inp))
    for needle in ("gmail.com", "@", "eyJhbGci", "hunter2", "4917023456789012",
                   "XEXX010101", "1.2.3.4"):
        assert needle not in blob, f"PII '{needle}' se filtró al payload"


def test_assert_no_pii_passes_clean_payload():
    inp, _ = _mk_inputs()
    ba._assert_no_pii(ba._build_advisor_request(inp))  # no levanta


@pytest.mark.parametrize("bad", [
    {"candidates": [{"ref": "A0", "email": "x@y.com"}]},
    {"candidates": [{"ref": "A0", "jwt_token": "abc"}]},
    {"note": "pan 4917023456789012 here"},
    {"nested": {"deep": ["ok", "contact me @handle"]}},
])
def test_assert_no_pii_fails_closed(bad):
    with pytest.raises(ValueError):
        ba._assert_no_pii(bad)


def test_assert_no_pii_allows_bin6_and_digest():
    # BIN de 6 dígitos y sha1[:12] no deben disparar el detector de PAN (13-19).
    ba._assert_no_pii({"bin": "491702", "policy_digest": bet_policy.digest(),
                       "approved_bins": ["491702", "552011"]})


# ─────────────────────────────────────────────────── 2. sanitize_advice

def _elig():
    return {"A0", "A1", "A2"}, {"C0"}


def test_sanitize_keeps_eligible_boosts_clamped():
    eligible, cards = _elig()
    raw = {"account_priority": [
        {"ref": "A0", "boost": 2, "why": "3ds hot"},
        {"ref": "A1", "boost": 99, "why": "over"},       # clamp → 3
        {"ref": "A2", "boost": -50, "why": "under"},     # clamp → -3
        {"ref": "ZZ", "boost": 3, "why": "no elegible"}, # descartada
    ]}
    adv = ba._sanitize_advice(raw, eligible, cards, max_boosts=99)
    assert adv is not None
    assert adv.boosts == {"A0": 2, "A1": 3, "A2": -3}


def test_sanitize_rejects_unknown_top_level_keys():
    eligible, cards = _elig()
    raw = {"account_priority": [{"ref": "A0", "boost": 1}], "exec_sql": "DROP"}
    assert ba._sanitize_advice(raw, eligible, cards, max_boosts=9) is None


@pytest.mark.parametrize("raw", ["not a dict", 42, None, [], "{bad json"])
def test_sanitize_rejects_non_dict(raw):
    eligible, cards = _elig()
    assert ba._sanitize_advice(raw, eligible, cards, max_boosts=9) is None


def test_sanitize_empty_advice_is_none():
    eligible, cards = _elig()
    assert ba._sanitize_advice({"account_priority": [], "avoid": [], "pairings": []},
                               eligible, cards, max_boosts=9) is None


def test_sanitize_caps_boost_count():
    eligible = {f"A{i}" for i in range(10)}
    raw = {"account_priority": [{"ref": f"A{i}", "boost": (i % 3) + 1} for i in range(10)]}
    adv = ba._sanitize_advice(raw, eligible, {"C0"}, max_boosts=3)
    assert adv is not None and len(adv.boosts) == 3


def test_sanitize_pairings_run_matcher_predicate():
    eligible, cards = _elig()
    raw = {"account_priority": [{"ref": "A0", "boost": 1}],
           "pairings": [{"account_ref": "A0", "card_ref": "C0"},
                        {"account_ref": "A1", "card_ref": "C0"}]}
    # A1↔C0 lo rechaza el predicado (p.ej. BIN en cooldown 30d con esa cuenta)
    adv = ba._sanitize_advice(raw, eligible, cards, max_boosts=9,
                              pairing_ok=lambda a, c: a != "A1")
    assert adv is not None
    assert adv.pairings == (("A0", "C0"),)


# ─────────────────────────────────────────────────── 3. maybe_advise

@pytest.mark.asyncio
async def test_maybe_advise_off_by_default_returns_none_no_llm_call(db_path, monkeypatch):
    monkeypatch.delenv("BET_ADVISOR_ENABLED", raising=False)
    inp, _ = _mk_inputs()
    called = {"n": 0}

    class Boom:
        async def stream_chat(self, *a, **k):
            called["n"] += 1
            yield {"type": "error", "message": "should not be reached"}

    out = await ba.maybe_advise(inp, db_path=db_path, client=Boom(), mission_id="m1")
    assert out is None
    assert called["n"] == 0
    # OFF no debe ni tocar la tabla de costo
    assert _calls(db_path) == []


@pytest.mark.asyncio
async def test_maybe_advise_happy_path_translates_refs_to_email(db_path, monkeypatch):
    monkeypatch.setenv("BET_ADVISOR_ENABLED", "1")
    inp, ref2email = _mk_inputs()
    client = _fake_client({"account_priority": [
        {"ref": "A0", "boost": 3, "why": "sesión viva + 3ds"},
        {"ref": "A2", "boost": -2, "why": "cargada de tarjetas"},
    ], "rationale": "prioriza conversión rápida"})

    adv = await ba.maybe_advise(inp, db_path=db_path, client=client, mission_id="m2")
    assert adv is not None
    assert adv.boost_map(ref2email) == {"user0@gmail.com": 3, "user2@gmail.com": -2}

    row = _calls(db_path)[-1]
    assert row["kind"] == "plan" and row["outcome"] == "applied"
    assert row["tokens_in"] == 90 and row["tokens_out"] == 40
    assert row["mission_id"] == "m2" and row["latency_ms"] >= 0


@pytest.mark.asyncio
async def test_maybe_advise_timeout_returns_none_and_logs_cost(db_path, monkeypatch):
    monkeypatch.setenv("BET_ADVISOR_ENABLED", "1")
    monkeypatch.setattr(ba, "ADVISOR_TIMEOUT_S", 0.05)
    inp, _ = _mk_inputs()

    class Slow:
        async def stream_chat(self, *a, **k):
            import asyncio
            await asyncio.sleep(1.0)
            yield {"type": "done", "model": "m-a"}

    out = await ba.maybe_advise(inp, db_path=db_path, client=Slow(), mission_id="m3")
    assert out is None
    assert _calls(db_path)[-1]["outcome"] == "timeout"


@pytest.mark.asyncio
async def test_maybe_advise_bad_json_returns_none_and_logs_cost(db_path, monkeypatch):
    monkeypatch.setenv("BET_ADVISOR_ENABLED", "1")
    inp, _ = _mk_inputs()
    client = _fake_client(raw_text="lo siento, no puedo ayudarte con eso")

    out = await ba.maybe_advise(inp, db_path=db_path, client=client, mission_id="m4")
    assert out is None
    assert _calls(db_path)[-1]["outcome"] in ("rejected", "error")


@pytest.mark.asyncio
async def test_maybe_advise_no_candidates_returns_none(db_path, monkeypatch):
    monkeypatch.setenv("BET_ADVISOR_ENABLED", "1")
    empty = ba.AdvisorInputs([], [{"ref": "C0", "bin": "491702", "bin_tier": "CORONA",
                                   "bin_approval_rate": 0.5, "bin_threeds_recent": False,
                                   "declines_24h": 0}],
                             {"amount": 150.0, "target_count": 9, "n_cards": 1,
                              "max_accounts": 6, "policy_digest": ""}, {})
    out = await ba.maybe_advise(empty, db_path=db_path, client=_fake_client({}), mission_id="m5")
    assert out is None
    assert _calls(db_path)[-1]["outcome"] == "no_candidates"


@pytest.mark.asyncio
async def test_advise_from_inputs_returns_email_boost_map(db_path, monkeypatch):
    monkeypatch.setenv("BET_ADVISOR_ENABLED", "1")
    inp, ref2email = _mk_inputs()
    client = _fake_client({"account_priority": [{"ref": "A1", "boost": 2, "why": "x"}]})
    out = await ba.advise_from_inputs((inp, ref2email), db_path=db_path,
                                      client=client, mission_id="m7")
    assert out == {"user1@gmail.com": 2}


@pytest.mark.asyncio
async def test_advise_from_inputs_none_when_off(db_path, monkeypatch):
    monkeypatch.delenv("BET_ADVISOR_ENABLED", raising=False)
    inp, ref2email = _mk_inputs()
    out = await ba.advise_from_inputs((inp, ref2email), db_path=db_path,
                                      client=_fake_client({}), mission_id="m8")
    assert out is None


def test_plan_auto_mission_advisor_sink_is_pii_free(tmp_path):
    """El bundle que `plan_auto_mission` deposita en `_advisor_sink` debe pasar
    `_assert_no_pii` — ninguna cuenta filtra email/jwt/PAN aunque las filas de
    `accounts` los tengan."""
    import auto_deposit as ad

    db = tmp_path / "plan.db"
    con = sqlite3.connect(db)
    con.executescript(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, "
        "password TEXT, status TEXT DEFAULT 'LIVE', grade TEXT DEFAULT 'A', grade_score INT DEFAULT 60, "
        "kyc_verified INT DEFAULT 1, published_to_pool INT DEFAULT 1, locked_by INT, cooldown_until INT, "
        "balance_real REAL DEFAULT 0, dead_reason TEXT, dead_at TEXT, last_checked_at TEXT, "
        "jwt_token TEXT, jwt_expires_at INT DEFAULT 2147483647, a_plus_decline_streak INT DEFAULT 0);"
        "CREATE TABLE deposit_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, account_email TEXT, amount REAL, "
        "status TEXT, rejection_reason TEXT, card_pipe TEXT, created_at TEXT);"
        "CREATE TABLE account_transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, account_email TEXT, txn_date TEXT, "
        "amount REAL, status INT, txn_type INT, gateway INT);"
        "CREATE TABLE account_cards (id INTEGER PRIMARY KEY AUTOINCREMENT, account_email TEXT, card_number TEXT, "
        "registered_at TEXT, status TEXT DEFAULT 'ACTIVE');"
        "CREATE TABLE bin_stats (bin TEXT PRIMARY KEY, total_attempts INT DEFAULT 0, total_approved INT DEFAULT 0, "
        "total_rejected INT DEFAULT 0, total_3ds INT DEFAULT 0, last_3ds_at TEXT, updated_at TEXT);"
    )
    for i in range(3):
        con.execute(
            "INSERT INTO accounts (email, password, jwt_token) VALUES (?,?,?)",
            (f"cuenta{i}@gmail.com", "secretpass", "eyJhbGciOiJIUzI1NiJ9.LEAK.sig"),
        )
    con.commit()
    con.close()

    sink = []
    ad.plan_auto_mission(str(db), ["4917020000000009|12|30|123"], 150, 9,
                         _advisor_sink=sink)
    assert sink, "el sink quedó vacío"
    inp, ref2email = sink[0]
    ba._assert_no_pii(ba._build_advisor_request(inp))  # no levanta
    blob = json.dumps(ba._build_advisor_request(inp))
    assert "gmail.com" not in blob and "eyJhbGci" not in blob
    assert all(r.startswith("A") for r in ref2email)


@pytest.mark.asyncio
async def test_maybe_advise_pii_leak_fails_closed_before_network(db_path, monkeypatch):
    monkeypatch.setenv("BET_ADVISOR_ENABLED", "1")
    inp, _ = _mk_inputs()
    # forzar una fuga: un campo whitelisted con basura que el detector debe cazar
    inp.candidates[0]["tier_hint"] = "contacto: fulano@gmail.com"
    net = {"hit": False}

    class Watch:
        async def stream_chat(self, *a, **k):
            net["hit"] = True
            yield {"type": "done", "model": "m-a"}

    out = await ba.maybe_advise(inp, db_path=db_path, client=Watch(), mission_id="m6")
    assert out is None
    assert net["hit"] is False
    assert _calls(db_path)[-1]["outcome"] == "error"
