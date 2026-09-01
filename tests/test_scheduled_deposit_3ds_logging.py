"""Regresión: el depósito programado (La Pantalla, /api/deposits/scheduled/create)
debe DEJAR RASTRO EN LOGS cuando aborta por 3DS — antes esa rama no logueaba nada
(solo el SSE broadcast), por eso el corte era invisible en `docker logs` (ver
docs/superpowers/specs/2026-08-01-logs-system-redesign-brief.md, hallazgo del
caso ALBERTOcr7 / espinoza.arellano.alberto.205@gmail.com).
"""
import logging

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
    # scheduled_create hace `from app import db` en cada llamada, pero `db()`
    # lee el global `app.DB_PATH` — una constante calculada UNA vez al importar
    # el módulo desde BETMEX_DB (app.py:133). Si otro archivo de test importó
    # `app` primero en este mismo proceso pytest, `DB_PATH` ya quedó fijo en
    # SU seed_db y `monkeypatch.setenv` (que solo cambia el env var) no lo
    # mueve. Apuntamos DB_PATH directo — quirúrgico, sin recargar el módulo
    # completo (un `importlib.reload(app)` completo re-ejecuta side effects
    # de nivel de módulo y deja referencias `from app import db` de OTROS
    # módulos ya importados —p.ej. telegram_bot_mock/bot.py— apuntando al
    # objeto de módulo viejo, rompiendo tests de archivos vecinos).
    import app
    monkeypatch.setattr(app, "DB_PATH", seed_db)

    monkeypatch.setattr(deposits, "_load_deps", lambda: (lambda cap_key, size=1, workers=1: _FakePool()))
    monkeypatch.setattr(deposits, "_check_caps", lambda *a, **k: None)
    monkeypatch.setattr(deposits, "_check_card_velocity", lambda *a, **k: None)
    monkeypatch.setattr(deposits, "_auto_lock_for_deposit", lambda *a, **k: None)

    broadcasts = []
    monkeypatch.setattr(app, "_broadcast", lambda ev: broadcasts.append(ev))

    async def _fake_run_deposit(*a, **k):
        return {
            "success": False,
            "result_code": "3DS_REQUIRED",
            "error": "3DS_REQUIRED — Tarjeta requiere autenticación",
            "duration_ms": 10,
        }
    monkeypatch.setattr(deposits, "_run_deposit_with_phases", _fake_run_deposit)

    return broadcasts


@pytest.mark.asyncio
async def test_scheduled_3ds_abort_logs_it(seed_db, sched_harness, caplog):
    """Antes: la rama `code in MM_THREEDS_RC` del loop de scheduled_create no
    tenía ni un solo logger.*() — solo dos _broadcast(). Si el operador no
    estaba viendo la pantalla en ese instante exacto, no había forma de
    reconstruir qué pasó desde los logs del contenedor.

    create + await del task en la MISMA corrida de event loop: asyncio.run()
    cancela tasks pendientes en su cleanup, así que crear el schedule y
    esperarlo en llamadas asyncio.run() separadas borra `_active_schedules`
    antes de poder engancharlo (CancelledError -> finally -> pop)."""
    body = {"account_id": 1, "card_pipe": "4111111111111111|1230|123", "amount": 150, "repetitions": 9}
    user = {"telegram_id": 555, "role": "superadmin", "username": "robertvs"}

    with caplog.at_level(logging.INFO, logger="betmexico.dashboard.deposits"):
        result = await deposits.scheduled_create(_FakeRequest(body), user)
        sched_id = result["sched_id"]
        task = deposits._active_schedules[sched_id]["task"]
        await task

    matching = [r for r in caplog.records if sched_id in r.message and "3DS" in r.message]
    assert matching, (
        f"esperaba un log mencionando 3DS y sched_id={sched_id!r} en la rama de "
        f"aborto — no se encontró ninguno. Records vistos: "
        f"{[r.message for r in caplog.records]}"
    )
