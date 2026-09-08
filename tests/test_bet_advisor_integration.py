# tests/test_bet_advisor_integration.py — Fase 3, Commit D.
#
# El advisor aplicado de punta a punta (LLMClient FALSO con advice canned):
#   - el boost reordena la selección de `plan_auto_mission`…
#   - …pero NUNCA rescata una cuenta excluida por filtro duro (DEAD/KYC/pool),
#   - ni cambia la asignación de tier,
#   - y `advise_from_inputs` traduce ref opaca → email correctamente.
#
# Espeja el flujo real de los 3 entry points: plan_auto_mission(_advisor_sink=…)
# → advise_from_inputs(sink[0], client=fake) → plan_auto_mission(advisor_hint=…).

import json
import sqlite3
import time

import httpx
import pytest

import auto_deposit as ad
import bet_advisor as ba
import support_llm


def _seed(tmp_path, n_live=4, with_dead=True):
    db = tmp_path / "int.db"
    con = sqlite3.connect(db)
    con.executescript(
        "CREATE TABLE accounts (id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE, "
        "password TEXT, status TEXT DEFAULT 'LIVE', grade TEXT DEFAULT 'A', grade_score INT DEFAULT 60, "
        "kyc_verified INT DEFAULT 1, published_to_pool INT DEFAULT 1, locked_by INT, cooldown_until INT, "
        "balance_real REAL DEFAULT 0, dead_reason TEXT, dead_at TEXT, last_checked_at TEXT, "
        "jwt_token TEXT DEFAULT 'jwt_live_placeholder_0123456789', jwt_expires_at INT DEFAULT 2147483647, "
        "a_plus_decline_streak INT DEFAULT 0);"
        "CREATE TABLE deposit_attempts (id INTEGER PRIMARY KEY AUTOINCREMENT, account_email TEXT, amount REAL, "
        "status TEXT, rejection_reason TEXT, card_pipe TEXT, created_at TEXT);"
        "CREATE TABLE account_transactions (id INTEGER PRIMARY KEY AUTOINCREMENT, account_email TEXT, txn_date TEXT, "
        "amount REAL, status INT, txn_type INT, gateway INT);"
        "CREATE TABLE account_cards (id INTEGER PRIMARY KEY AUTOINCREMENT, account_email TEXT, card_number TEXT, "
        "registered_at TEXT, status TEXT DEFAULT 'ACTIVE');"
        "CREATE TABLE bin_stats (bin TEXT PRIMARY KEY, total_attempts INT DEFAULT 0, total_approved INT DEFAULT 0, "
        "total_rejected INT DEFAULT 0, total_3ds INT DEFAULT 0, last_3ds_at TEXT, updated_at TEXT);"
    )
    for i in range(n_live):
        con.execute("INSERT INTO accounts (email, password, grade) VALUES (?,?,?)",
                    (f"live{i}@gmail.com", "pw", "A"))
    if with_dead:
        con.execute("INSERT INTO accounts (email, password, grade, status, dead_reason) "
                    "VALUES ('dead@gmail.com','pw','A','DEAD','rate limited 429')")
    con.commit()
    con.close()
    return str(db)


def _fake_client(advice: dict):
    def handler(_req):
        body = json.dumps({"choices": [{"delta": {"content": json.dumps(advice)}}]})
        usage = json.dumps({"choices": [{"delta": {}}],
                            "usage": {"prompt_tokens": 50, "completion_tokens": 20}})
        content = f"data: {body}\n\ndata: {usage}\n\ndata: [DONE]\n\n".encode()
        return httpx.Response(200, content=content)
    return support_llm.LLMClient(base_url="http://r:1", chain=["m"], timeout=6.0,
                                 transport=httpx.MockTransport(handler))


@pytest.mark.asyncio
async def test_boost_reorders_selection(tmp_path, monkeypatch):
    monkeypatch.setenv("BET_ADVISOR_ENABLED", "1")
    db = _seed(tmp_path, n_live=4, with_dead=False)
    # 4 BINs distintos → matching 1:1 puede casar hasta 4 cuentas → el orden de
    # `plan["accounts"]` refleja el de `select_accounts_for_auto`.
    pipes = [
        "491702000000000{}|12|30|123".format(i) for i in range(4)
    ]

    # 1. plan base (sin advisor aplicado) + bundle para las refs
    sink = []
    base = ad.plan_auto_mission(db, pipes, 150, 4, max_accounts=6, _advisor_sink=sink)
    base_emails = [a["email"] for a in base["accounts"]]
    assert len(base_emails) >= 2
    inp, ref2email = sink[0]

    # 2. el advisor empuja la ÚLTIMA cuenta de la selección base al frente
    victim = base_emails[-1]
    victim_ref = next(r for r, e in ref2email.items() if e == victim)
    hint = await ba.advise_from_inputs(
        (inp, ref2email), db_path=db, mission_id="itg",
        client=_fake_client({"account_priority": [{"ref": victim_ref, "boost": 3, "why": "x"}]}),
    )
    assert hint == {victim: 3}

    # 3. re-plan con el hint → victim ahora es la primera
    boosted = ad.plan_auto_mission(db, pipes, 150, 4, max_accounts=6, advisor_hint=hint)
    assert [a["email"] for a in boosted["accounts"]][0] == victim


@pytest.mark.asyncio
async def test_boost_cannot_rescue_dead_account(tmp_path, monkeypatch):
    db = _seed(tmp_path, n_live=3, with_dead=True)
    pipes = ["4917020000000009|12|30|123"]
    monkeypatch.setenv("BET_ADVISOR_ENABLED", "1")
    sink = []
    ad.plan_auto_mission(db, pipes, 150, 9, max_accounts=6, _advisor_sink=sink)
    inp, ref2email = sink[0]
    # la cuenta DEAD ni siquiera está en el set de refs elegibles
    assert "dead@gmail.com" not in ref2email.values()
    # aun forzando un boost a un ref inventado, _sanitize_advice lo descarta
    hint = await ba.advise_from_inputs(
        (inp, ref2email), db_path=db, mission_id="itg3",
        client=_fake_client({"account_priority": [{"ref": "A99", "boost": 3, "why": "x"}]}),
    )
    assert hint is None  # nada aplicable → plan determinista
    plan = ad.plan_auto_mission(db, pipes, 150, 9, max_accounts=6, advisor_hint=hint)
    assert "dead@gmail.com" not in [a["email"] for a in plan["accounts"]]


def test_plan_not_worse_guardrail():
    """`plan_not_worse` (guardarraíl del hint): el plan boosteado se descarta si
    sale con menos cuentas o vuelve infactible un base factible."""
    feas3 = {"feasible": True, "accounts": [1, 2, 3]}
    feas2 = {"feasible": True, "accounts": [1, 2]}
    infeas0 = {"feasible": False, "accounts": []}
    # mismo tamaño / distinto set → adoptable (reordenamiento legítimo)
    assert ba.plan_not_worse(feas3, {"feasible": True, "accounts": [9, 8, 7]}) is True
    # menos cuentas → NO adoptable
    assert ba.plan_not_worse(feas3, feas2) is False
    # tumba un base factible → NO adoptable
    assert ba.plan_not_worse(feas3, infeas0) is False
    # base ya infactible y el boost lo arregla → adoptable
    assert ba.plan_not_worse(infeas0, feas2) is True
    # basura / tipos raros → NO adoptable (fail-closed)
    assert ba.plan_not_worse(None, feas3) is False
    assert ba.plan_not_worse(feas3, "nope") is False


@pytest.mark.asyncio
async def test_negative_boost_shrinks_plan_guardrail_keeps_base(tmp_path, monkeypatch):
    """R1 (Smartreview 2026-09-08): un boost NEGATIVO a una cuenta seleccionada la
    saca de la ventana `[:max_accounts]`; una cuenta de backfill sin tarjeta
    asignable (cooldown-BIN-30d) ocupa el slot → el plan boosteado sale con menos
    cuentas que el base. El guardarraíl `plan_not_worse` lo rechaza y el caller
    conserva el plan determinista (regla Robert: el bet jamás se queda sin cuentas)."""
    monkeypatch.setenv("BET_ADVISOR_ENABLED", "1")
    db = _seed(tmp_path, n_live=3, with_dead=False)
    con = sqlite3.connect(db)
    # live2: APROBÓ hace 10d con OTRO pipe de CADA BIN del pool → cooldown-30d
    #        bloquea AMBOS pipes del pool para esta cuenta (card-unviable)…
    con.execute("INSERT INTO deposit_attempts (account_email, amount, status, card_pipe, created_at) "
                "VALUES ('live2@gmail.com', 150, 'APPROVED', '4917021111111111|12|30|123', "
                "datetime('now','-10 days'))")
    con.execute("INSERT INTO deposit_attempts (account_email, amount, status, card_pipe, created_at) "
                "VALUES ('live2@gmail.com', 150, 'APPROVED', '4999991111111111|12|30|123', "
                "datetime('now','-10 days'))")
    # …+ un REJECTED viejo (>1h) → has_fails=1 → sin boost live2 sortea AL FINAL,
    #    fuera de la ventana base [:2] (live0/live1 no tienen fails).
    con.execute("INSERT INTO deposit_attempts (account_email, amount, status, created_at) "
                "VALUES ('live2@gmail.com', 150, 'REJECTED', datetime('now','-5 days'))")
    con.commit()
    con.close()

    pipes = ["4917020000000009|12|30|123", "4999990000000009|12|30|123"]  # 2 BINs
    sink = []
    base = ad.plan_auto_mission(db, pipes, 150, 2, max_accounts=2, _advisor_sink=sink)
    base_emails = [a["email"] for a in base["accounts"]]
    assert base["feasible"] and len(base_emails) == 2 and "live2@gmail.com" not in base_emails
    inp, ref2email = sink[0]

    # boost NEGATIVO a la 1ª cuenta seleccionada → cae fuera de [:2]; live2 (backfill
    # determinista, card-unviable) toma el slot.
    victim = base_emails[0]
    victim_ref = next(r for r, e in ref2email.items() if e == victim)
    hint = await ba.advise_from_inputs(
        (inp, ref2email), db_path=db, mission_id="r1",
        client=_fake_client({"account_priority": [{"ref": victim_ref, "boost": -3, "why": "x"}]}),
    )
    assert hint == {victim: -3}

    boosted = ad.plan_auto_mission(db, pipes, 150, 2, max_accounts=2, advisor_hint=hint)
    assert len(boosted["accounts"]) < len(base["accounts"])   # el boost encogió el plan…
    assert ba.plan_not_worse(base, boosted) is False          # …y el guardarraíl lo rechaza
    # el caller (entry points) conserva `base` → la misión corre con 2 cuentas


@pytest.mark.asyncio
async def test_advisor_off_bundle_absent(tmp_path, monkeypatch):
    monkeypatch.delenv("BET_ADVISOR_ENABLED", raising=False)
    db = _seed(tmp_path, n_live=3, with_dead=False)
    pipes = ["4917020000000009|12|30|123"]
    sink = []
    # el caller solo pasa sink si enabled(); simulamos que NO
    assert ba.enabled() is False
    plan_off = ad.plan_auto_mission(db, pipes, 150, 4, max_accounts=6)
    plan_sink_none = ad.plan_auto_mission(db, pipes, 150, 4, max_accounts=6, _advisor_sink=None)
    assert [a["email"] for a in plan_off["accounts"]] == [a["email"] for a in plan_sink_none["accounts"]]
