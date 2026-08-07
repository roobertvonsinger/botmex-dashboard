"""Regresión: el depósito programado (/api/deposits/scheduled/create) no debe
reintentar CARD_LOCKED_OTHER_ACCOUNT — es el candado DB de deposits.py (tarjeta
ya ligada a otro email), determinístico, jamás cambia entre intentos. Bug
2026-08-07: no estaba en la lista terminal del loop de scheduled_create y caía
al branch TRANSITORIO, quemando los SCHED_MAX_TRANSIENT_RETRIES reintentos
(25s c/u) contra un resultado que nunca iba a cambiar (mismo hueco que en
auto_deposit.py, ver test_mission_matchmaking_terminal_on_card_locked).
"""
import asyncio

import pytest

import deposits


class _FakePool:
    async def start_factory(self):
        pass

    async def prefetch(self, n):
        pass

    async def stop(self):
        pass


class _FakeRequest:
    def __init__(self, body):
        self._body = body

    async def json(self):
        return self._body


@pytest.fixture
def sched_harness(seed_db, monkeypatch):
    import app
    monkeypatch.setattr(app, "DB_PATH", seed_db)

    monkeypatch.setattr(deposits, "_load_deps", lambda: (lambda cap_key, size=1, workers=1: _FakePool()))
    monkeypatch.setattr(deposits, "_check_caps", lambda *a, **k: None)
    monkeypatch.setattr(deposits, "_check_card_velocity", lambda *a, **k: None)
    monkeypatch.setattr(deposits, "_auto_lock_for_deposit", lambda *a, **k: None)

    broadcasts = []
    monkeypatch.setattr(app, "_broadcast", lambda ev: broadcasts.append(ev))

    async def _sleep(s):
        pass
    monkeypatch.setattr(asyncio, "sleep", _sleep)

    calls = {"n": 0}

    async def _fake_run_deposit(*a, **k):
        calls["n"] += 1
        return {
            "success": False,
            "result_code": "CARD_LOCKED_OTHER_ACCOUNT",
            "error": "Tarjeta ya aprobada en otro@x.com — bloqueada para otras cuentas",
            "duration_ms": 10,
        }
    monkeypatch.setattr(deposits, "_run_deposit_with_phases", _fake_run_deposit)

    return calls


@pytest.mark.asyncio
async def test_scheduled_card_locked_aborts_without_retry(seed_db, sched_harness):
    body = {"account_id": 1, "card_pipe": "4111111111111111|1230|123", "amount": 150, "repetitions": 9}
    user = {"telegram_id": 555, "role": "superadmin", "username": "robertvs"}

    result = await deposits.scheduled_create(_FakeRequest(body), user)
    sched_id = result["sched_id"]
    task = deposits._active_schedules[sched_id]["task"]
    await task

    assert sched_harness["n"] == 1, (
        f"debió abortar en el primer intento (candado determinístico), "
        f"hizo {sched_harness['n']} intentos"
    )
