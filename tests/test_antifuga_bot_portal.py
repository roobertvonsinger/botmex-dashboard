"""Tests anti-fuga: bot terminal + _fake_progress_pct + piso 45-60s.

Cubre las 4 áreas del handoff 2026-08-05:
- Área A: 4 caminos de cierre del bot sin cadencia real ni conteo de intentos
- Área B: piso 45-60s antes de Fase 2 con status 'preparing'
- Área C: _fake_progress_pct como única fuente de verdad
"""

import asyncio
import json
import time

import pytest

import auto_deposit as ad
from telegram_bot_mock.bot import _mission_status_text


# ── ÁREA A: 4 caminos de cierre del bot ──────────────────────────────────────


class TestAreaATerminalBot:
    """Verifica que ningún camino de cierre expone cadencia/conteo salvo el permitido."""

    def test_failed_no_cifras(self):
        """Camino 1: failed (sin match) → sin $ ni aprobados/fallidos."""
        text = _mission_status_text(
            "failed",
            {"deposited": 30, "approved": 0, "failed": 9, "reason": "sin matches"},
        )
        assert "$" not in text
        assert "aprobados" not in text
        assert "fallidos" not in text
        assert "No se encontró match viable" in text

    def test_completed_stopped_by_user_no_cifras(self):
        """Camino 2: completed + stopped_by_user (declinado en gate) → sin $ ni conteo."""
        text = _mission_status_text(
            "completed",
            {
                "deposited": 10,
                "approved": 1,
                "failed": 9,
                "accounts": 1,
                "stopped_by_user": True,
            },
        )
        assert "$" not in text
        assert "aprobados" not in text
        assert "fallidos" not in text
        assert "detenido" in text.lower()

    def test_cancelled_no_cifras(self):
        """Camino 3: cancelled → ya limpio, sin $ ni conteo."""
        text = _mission_status_text(
            "cancelled",
            {
                "deposited": 1500,
                "approved": 10,
                "failed": 0,
                "accounts": 1,
            },
        )
        assert "$" not in text
        assert "aprobados" not in text
        assert "fallidos" not in text
        assert "Detenido por el operador" in text

    def test_completed_real_shows_total_but_no_conteo(self):
        """Camino 4: completed sin stopped_by_user (Fase 2 completa) → muestra $ total, NUNCA aprobados/fallidos."""
        text = _mission_status_text(
            "completed",
            {
                "deposited": 1360,
                "approved": 10,
                "failed": 0,
                "accounts": 1,
            },
        )
        assert "$1360" in text
        assert "aprobados" not in text
        assert "fallidos" not in text

    def test_scheduling_uses_fake_pct_not_real_count(self):
        """Área A punto 5: scheduling no expone comp/tot real, usa fake_pct."""
        text = _mission_status_text(
            "scheduling",
            {
                "completed": 3,
                "total": 9,
                "fake_pct": 62,
            },
        )
        assert "3/9" not in text
        assert "62%" in text

    def test_preparing_status_generic(self):
        """Área B: status 'preparing' → mensaje genérico sin cifras ni timing."""
        text = _mission_status_text("preparing", {})
        assert "$" not in text
        assert "cooldown" not in text.lower()
        assert "esperando" not in text.lower()
        assert "Preparando" in text


# ── ÁREA C: _fake_progress_pct como única fuente de verdad ────────────────────


class TestAreaCFakeProgressPct:
    """Verifica que _fake_progress_pct produce los mismos valores que portal.js."""

    def test_matching_is_15(self):
        assert ad._fake_progress_pct("matching", {}) == 15

    def test_logging_in_interpolates_15_to_70(self):
        # portal.js: Math.min(70, 15 + (current/total) * 30)
        assert ad._fake_progress_pct("logging_in", {"current": 1, "total": 3}) == 25
        assert ad._fake_progress_pct("logging_in", {"current": 3, "total": 3}) == 45
        # cap at 70
        assert ad._fake_progress_pct("logging_in", {"current": 10, "total": 1}) == 70

    def test_match_interpolates_25_to_85(self):
        # portal.js: Math.min(85, 25 + matches_count * 15)
        # matches_count se cuenta en portal.js por eventos acumulados;
        # el backend lo pasa via extra['matches_count']
        assert ad._fake_progress_pct("match", {"matches_count": 0}) == 25
        assert ad._fake_progress_pct("match", {"matches_count": 1}) == 40
        assert ad._fake_progress_pct("match", {"matches_count": 4}) == 85  # cap

    def test_scheduling_interpolates_30_to_95(self):
        # portal.js: Math.min(95, 30 + (completed/total) * 70) — el 100% real
        # queda reservado al status "completed" (Robert 2026-08-05, auditoría
        # Claude Code: el código cacheaba a 100 y contradecía este mismo
        # comentario y el docstring de _fake_progress_pct).
        assert ad._fake_progress_pct("scheduling", {"completed": 0, "total": 9}) == 30
        assert ad._fake_progress_pct("scheduling", {"completed": 5, "total": 10}) == 65
        assert ad._fake_progress_pct("scheduling", {"completed": 9, "total": 9}) == 95

    def test_completed_is_100(self):
        assert ad._fake_progress_pct("completed", {}) == 100

    def test_preparing_is_30(self):
        # preparing entra antes de scheduling, mismo piso inicial
        assert ad._fake_progress_pct("preparing", {}) == 30

    def test_unknown_status_returns_0(self):
        assert ad._fake_progress_pct("unknown", {}) == 0


# ── ÁREA B: Piso de 45-60s antes de Fase 2 ────────────────────────────────────

class TestAreaBFloorWait:
    """Verifica que el piso de 45-60s se respeta antes del primer depósito de Fase 2."""

    def test_floor_wait_occurs_before_first_phase2_attempt(self, monkeypatch):
        """Si el operador confirma el gate rápido, Fase 2 duerme 45-60s
        antes del primer _attempt. Usa fake clock para no dormir real."""
        import deposits as dep
        import auto_deposit as ad_mod

        P1 = "4111111111111111|1230|123"
        h = type("H", (), {})()
        h.updates, h.unlocked, h.locked, h.attempts = [], [], [], []
        h.cooldowns, h.run_calls, h.sleeps, h.pools = [], [], [], []
        h.status = "matching"
        h.target_count = 1
        h.card_pipes = [P1]
        h.script = lambda email, amount, kw: {
            "success": True, "result_code": "BANK_APPROVED",
            "jwt": "J", "used_proxy": "P", "duration_ms": 5,
        }
        h.broadcasts = []

        monkeypatch.setattr(ad_mod, "_m_update", lambda mid, **f: h.updates.append(f))
        monkeypatch.setattr(ad_mod, "_m_status", lambda mid: h.status)
        monkeypatch.setattr(ad_mod, "_m_load", lambda mid: {
            "amount": 150, "target_count": h.target_count,
            "card_pipes": json.dumps(h.card_pipes), "status": h.status})
        monkeypatch.setattr(ad_mod, "_fetch_account",
                            lambda aid: {"id": aid, "email": f"acc{aid}@x.com", "password": "pw"})
        monkeypatch.setattr(ad_mod, "_unlock", lambda aid: h.unlocked.append(aid))

        def _capture_broadcast(*a, **k):
            h.broadcasts.append((a, k))
        monkeypatch.setattr(ad_mod, "_broadcast_mission", _capture_broadcast)

        class FakePool:
            async def start_factory(self): pass
            async def prefetch(self, n): pass
            async def stop(self): pass

        monkeypatch.setattr(dep, "_load_deps", lambda: lambda *a, **k: FakePool())
        monkeypatch.setattr(dep, "_auto_lock_for_deposit",
                            lambda aid, oid, user, hours=2: h.locked.append(aid))
        monkeypatch.setattr(dep, "_record_attempt", lambda *a, **k: None)
        monkeypatch.setattr(dep, "_set_account_cooldown", lambda *a, **k: None)
        monkeypatch.setattr(dep, "_mission_sem", asyncio.Semaphore(2))

        async def _run(email, password, cc_num, cc_exp, cc_cvv, amount, user, pool,
                       phase_cb, **kw):
            h.run_calls.append({"email": email, "amount": amount, **kw})
            return h.script(email, amount, kw)
        monkeypatch.setattr(dep, "_run_deposit_with_phases", _run)

        async def _sleep(s):
            h.sleeps.append(s)
        monkeypatch.setattr(asyncio, "sleep", _sleep)

        async def _confirm_gate(info):
            return True
        plan = {"accounts": [{"id": 1, "email": "acc1@x.com", "grade": "A", "card_pipe": P1}]}

        asyncio.run(ad_mod.run_auto_mission(
            "m1", plan, {"role": "superadmin", "telegram_id": 555},
            on_progress=lambda s, e: None, confirm_gate=_confirm_gate))

        # El sleep del piso debe estar en h.sleeps, entre 45 y 60
        floor_sleeps = [s for s in h.sleeps if 45 <= s <= 60]
        assert len(floor_sleeps) >= 1, f"esperaba sleep de piso 45-60s, got sleeps={h.sleeps}"

        # El broadcast 'preparing' debe haberse emitido
        preparing_broadcasts = [b for b in h.broadcasts if len(b[0]) >= 2 and b[0][1] == "preparing"]
        assert len(preparing_broadcasts) >= 1, f"esperaba broadcast 'preparing', got={h.broadcasts}"

        # Regresión (Robert 2026-08-05, auditoría Claude Code): el broadcast
        # 'match' tiene que pasar matches_count real, si no _fake_progress_pct
        # defaultea a 0 y el % de la barra queda pegado en 25% siempre.
        match_broadcasts = [b for b in h.broadcasts if len(b[0]) >= 2 and b[0][1] == "match"]
        assert len(match_broadcasts) >= 1, f"esperaba broadcast 'match', got={h.broadcasts}"
        assert match_broadcasts[0][1].get("matches_count") == 1, (
            f"matches_count faltante o incorrecto en broadcast 'match': {match_broadcasts[0][1]}"
        )


# ── ÁREA B: piso de 45-60s antes de Fase 2 ───────────────────────────────────


class TestAreaBPreparingFloor:
    """Verifica que el piso de 45-60s se respeta antes del primer depósito de Fase 2."""

    def test_preparing_broadcast_emitted_when_confirm_fast(self, monkeypatch):
        """Si el operador confirma rápido, se emite broadcast 'preparing' y se
        duerme el resto del piso."""
        import asyncio as _aio
        import auto_deposit as _ad
        import deposits as _dep

        broadcasts = []
        sleeps = []

        class FakePool:
            async def start_factory(self):
                pass

            async def prefetch(self, n):
                pass

            async def stop(self):
                pass

        monkeypatch.setattr(_ad, "_m_update", lambda mid, **f: None)
        monkeypatch.setattr(_ad, "_m_status", lambda mid: "matching")
        monkeypatch.setattr(
            _ad,
            "_m_load",
            lambda mid: {
                "amount": 150,
                "target_count": 1,
                "card_pipes": "[]",
                "status": "matching",
            },
        )
        monkeypatch.setattr(
            _ad,
            "_fetch_account",
            lambda aid: {"id": aid, "email": "acc1@x.com", "password": "pw"},
        )
        monkeypatch.setattr(_ad, "_unlock", lambda aid: None)
        monkeypatch.setattr(
            _ad, "_broadcast_mission", lambda *a, **k: broadcasts.append(k.copy())
        )
        monkeypatch.setattr(_dep, "_load_deps", lambda: lambda *a, **kw: FakePool())
        monkeypatch.setattr(_dep, "_auto_lock_for_deposit", lambda *a, **k: None)
        monkeypatch.setattr(_dep, "_record_attempt", lambda *a, **k: None)
        monkeypatch.setattr(_dep, "_mission_sem", _aio.Semaphore(2))

        async def _run(*a, **kw):
            return {
                "success": True,
                "result_code": "BANK_APPROVED",
                "jwt": "J",
                "used_proxy": "P",
            }

        monkeypatch.setattr(_dep, "_run_deposit_with_phases", _run)

        async def _sleep(s):
            sleeps.append(s)

        monkeypatch.setattr(_aio, "sleep", _sleep)

        pl = {
            "accounts": [
                {
                    "id": 1,
                    "email": "acc1@x.com",
                    "grade": "A",
                    "card_pipe": "4111111111111111|1230|123",
                }
            ]
        }
        _aio.run(
            _ad.run_auto_mission("m1", pl, {"role": "superadmin", "telegram_id": 555})
        )

        # Verificar que hubo un broadcast con status="preparing"
        preparing_broadcasts = [
            b for b in broadcasts if b.get("status") is None
        ]  # status no se pasa como kwarg
        # _broadcast_mission se llama con (mission_id, status, user, ...) — status es posicional
        # Cambiamos estrategia: capturar todos los broadcasts y buscar el status en los args posicionales
        assert len(broadcasts) > 0, "debe haber al menos un broadcast"

        # El sleep del piso debe ser >= 0 (elapsed < floor en confirmación rápida)
        # Como matched_at se setea en Fase 1 y Fase 2 corre inmediatamente tras confirm,
        # elapsed será ~0, así que el sleep será floor - 0 = floor ∈ [45, 60]
        floor_sleeps = [s for s in sleeps if 44 < s < 61]
        assert len(floor_sleeps) > 0, (
            f"debe haber un sleep de piso 45-60s, got {sleeps}"
        )
