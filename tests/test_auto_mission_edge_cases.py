# tests/test_auto_mission_edge_cases.py
"""Tests exhaustivos de casos límite y escenarios de estrés para run_auto_mission."""
import asyncio
import json
import pytest

import auto_deposit as ad
import deposits as dep

P_A = "4111111111111111|1228|123"
P_B = "4222222222222222|1129|456"
P_C = "4333333333333333|1027|789"
P_D = "4444444444444444|0926|012"

class FakePool:
    def __init__(self):
        self.started = 0
        self.stopped = 0
    async def start_factory(self): self.started += 1
    async def prefetch(self, n): pass
    async def stop(self): self.stopped += 1

@pytest.fixture
def Harness(monkeypatch):
    h = type("H", (), {})()
    h.calls = []
    h.updates = []
    h.unlocked = []
    h.locked = []
    h.target_count = 3
    h.card_pipes = [P_A, P_B, P_C, P_D]
    h.status = "matching"

    monkeypatch.setattr(ad, "_m_update", lambda mid, **f: h.updates.append(f))
    monkeypatch.setattr(ad, "_m_status", lambda mid: h.status)
    monkeypatch.setattr(ad, "_m_load", lambda mid: {
        "amount": 150, "target_count": h.target_count,
        "card_pipes": json.dumps(h.card_pipes), "status": h.status
    })
    monkeypatch.setattr(ad, "_fetch_account",
                        lambda aid: {"id": aid, "email": f"user{aid}@bet.com", "password": f"pwd{aid}"})
    monkeypatch.setattr(ad, "_unlock", lambda aid: h.unlocked.append(aid))
    monkeypatch.setattr(ad, "_get_married_card_owners", lambda *a, **k: {})
    monkeypatch.setattr(ad, "_broadcast_mission", lambda *a, **k: None)

    monkeypatch.setattr(dep, "_load_deps", lambda: (lambda *a, **k: FakePool()))
    monkeypatch.setattr(dep, "_auto_lock_for_deposit", lambda aid, oid, user, hours=2: h.locked.append(aid))
    monkeypatch.setattr(dep, "_record_attempt", lambda *a, **k: None)
    monkeypatch.setattr(dep, "_set_account_cooldown", lambda *a, **k: None)
    monkeypatch.setattr(dep, "_mark_rate_limited_dead", lambda *a, **k: None)
    monkeypatch.setattr(dep, "_mission_sem", asyncio.Semaphore(5))

    async def _mock_run(email, password, cc_num, cc_exp, cc_cvv, amount, user, pool, phase_cb, **kw):
        h.calls.append({"email": email, "pan": cc_num, "amount": amount, **kw})
        return h.script(email, cc_num, amount, kw)

    monkeypatch.setattr(dep, "_run_deposit_with_phases", _mock_run)

    async def _mock_sleep(s):
        pass
    monkeypatch.setattr(asyncio, "sleep", _mock_sleep)
    return h


def test_scenario_multi_account_independent_match_and_fill(Harness):
    """Escenario: 4 cuentas y 4 tarjetas.
    - Cuenta 1 aprueba P_A -> P_A se jubila para las demás cuentas.
    - Cuenta 2 intenta P_B y aprueba -> P_B se jubila para las demás.
    - Cuenta 3 falla con P_C y luego aprueba P_D.
    - Cuenta 4 no tiene más tarjetas -> se desvincula limpiamente."""
    def script(email, pan, amount, kw):
        if amount == ad.PROBE_AMOUNT:
            if email == "user1@bet.com" and pan == "4111111111111111":
                return {"success": True, "result_code": "BANK_APPROVED", "jwt": "jwt1", "used_proxy": "px1"}
            if email == "user2@bet.com" and pan == "4222222222222222":
                return {"success": True, "result_code": "BANK_APPROVED", "jwt": "jwt2", "used_proxy": "px2"}
            if email == "user3@bet.com" and pan == "4333333333333333":
                return {"success": False, "result_code": "BANK_REJECTED", "error": "Declined"}
            if email == "user3@bet.com" and pan == "4444444444444444":
                return {"success": True, "result_code": "BANK_APPROVED", "jwt": "jwt3", "used_proxy": "px3"}
        # Fase 2
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": f"jwt_{email}", "used_proxy": "px"}

    Harness.script = script
    Harness.card_pipes = [P_A, P_B, P_C, P_D]
    Harness.target_count = 2

    plan = {
        "accounts": [
            {"id": 1, "email": "user1@bet.com", "grade": "B", "card_pipe": P_A},
            {"id": 2, "email": "user2@bet.com", "grade": "B", "card_pipe": P_B},
            {"id": 3, "email": "user3@bet.com", "grade": "B", "card_pipe": P_C},
            {"id": 4, "email": "user4@bet.com", "grade": "B", "card_pipe": P_D},
        ]
    }

    asyncio.run(ad.run_auto_mission("m_multi", plan, {"role": "superadmin", "telegram_id": 999}))

    # 1. P_A NUNCA fue tocada por user2, user3 o user4
    pa_calls = [c for c in Harness.calls if c["pan"] == "4111111111111111"]
    assert all(c["email"] == "user1@bet.com" for c in pa_calls), "P_A se fugó a otra cuenta!"

    # 2. P_B NUNCA fue tocada por user1, user3 o user4
    pb_calls = [c for c in Harness.calls if c["pan"] == "4222222222222222"]
    assert all(c["email"] == "user2@bet.com" for c in pb_calls), "P_B se fugó a otra cuenta!"

    # 3. P_D fue aprobada por user4 (mientras user3 estaba en cooldown), NUNCA tocada por user3
    pd_calls = [c for c in Harness.calls if c["pan"] == "4444444444444444"]
    assert len(pd_calls) > 0
    assert all(c["email"] == "user4@bet.com" for c in pd_calls), "P_D se fugó a otra cuenta!"

    # 4. user3 (que falló P_C y se quedó sin candidatas) quedó libre/desbloqueado
    assert 3 in Harness.unlocked or 3 not in Harness.locked


def test_scenario_phase2_one_account_declines_other_continues(Harness):
    """En Fase 2 (Scheduled): Si la Cuenta 1 falla en su 2o depósito,
    la Cuenta 1 se aborta pero la Cuenta 2 continúa exitosamente hasta completar sus 3 depósitos."""
    cuenta1_f2_attempts = 0

    def script(email, pan, amount, kw):
        nonlocal cuenta1_f2_attempts
        if amount == ad.PROBE_AMOUNT:
            return {"success": True, "result_code": "BANK_APPROVED", "jwt": "jwt_ok", "used_proxy": "px"}
        # Fase 2: $150
        if email == "user1@bet.com":
            cuenta1_f2_attempts += 1
            if cuenta1_f2_attempts == 1:
                return {"success": True, "result_code": "BANK_APPROVED", "jwt": "jwt_ok", "used_proxy": "px"}
            # Falla en el segundo depósito de $150
            return {"success": False, "result_code": "BANK_REJECTED", "error": "Declined 51"}
        # Cuenta 2 siempre aprueba
        return {"success": True, "result_code": "BANK_APPROVED", "jwt": "jwt_ok", "used_proxy": "px"}

    Harness.script = script
    Harness.card_pipes = [P_A, P_B]
    Harness.target_count = 3

    plan = {
        "accounts": [
            {"id": 1, "email": "user1@bet.com", "grade": "A", "card_pipe": P_A},
            {"id": 2, "email": "user2@bet.com", "grade": "A", "card_pipe": P_B},
        ]
    }

    asyncio.run(ad.run_auto_mission("m_f2_isol", plan, {"role": "superadmin", "telegram_id": 999}))

    # Cuenta 1 hizo: 1 probe de $10 + 1 éxito de $150 + 1 fallo de $150 = 3 intentos
    u1_calls = [c for c in Harness.calls if c["email"] == "user1@bet.com"]
    assert len(u1_calls) == 3
    assert u1_calls[0]["amount"] == 10.0
    assert u1_calls[1]["amount"] == 150.0
    assert u1_calls[2]["amount"] == 150.0

    # Cuenta 2 hizo: 1 probe de $10 + 3 éxitos de $150 = 4 intentos (completó su cuota entera!)
    u2_calls = [c for c in Harness.calls if c["email"] == "user2@bet.com"]
    assert len(u2_calls) == 4
    assert [c["amount"] for c in u2_calls] == [10.0, 150.0, 150.0, 150.0]


def test_scenario_clean_account_bank_rejected_retires_card_for_all(Harness):
    """Regla Robert 2026-09-02: Si una cuenta recibe BANK_REJECTED, la tarjeta rota por
    hasta 3 cuentas distintas. Al 3er rechazo en cuentas distintas, la tarjeta
    queda jubilada definitivamente y NO toca una 4a cuenta."""
    Harness.script = lambda email, pan, amt, kw: {"success": False, "result_code": "BANK_REJECTED", "error": "Declined"}
    Harness.card_pipes = [P_A]

    plan = {
        "accounts": [
            {"id": 1, "email": "user1@bet.com", "grade": "A+", "card_pipe": P_A},
            {"id": 2, "email": "user2@bet.com", "grade": "A", "card_pipe": P_A},
            {"id": 3, "email": "user3@bet.com", "grade": "A", "card_pipe": P_A},
            {"id": 4, "email": "user4@bet.com", "grade": "A", "card_pipe": P_A},
        ]
    }

    asyncio.run(ad.run_auto_mission("m_clean_rej", plan, {"role": "superadmin", "telegram_id": 999}))

    # user1, user2 y user3 intentaron P_A (3 rechazos). user4 fue purgado al instante y NO la intentó
    assert len(Harness.calls) == 3
    assert Harness.calls[0]["email"] == "user1@bet.com"
    assert Harness.calls[1]["email"] == "user2@bet.com"
    assert Harness.calls[2]["email"] == "user3@bet.com"
    assert 1 in Harness.unlocked
    assert 2 in Harness.unlocked
    assert 3 in Harness.unlocked
    assert 4 in Harness.unlocked or 4 not in Harness.locked

