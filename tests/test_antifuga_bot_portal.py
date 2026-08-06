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
        text = _mission_status_text("failed", {"deposited": 30, "approved": 0, "failed": 9, "reason": "sin matches"})
        assert "$" not in text
        assert "aprobados" not in text
        assert "fallidos" not in text
        assert "No se encontró match viable" in text

    def test_completed_stopped_by_user_no_cifras(self):
        """Camino 2: completed + stopped_by_user (declinado en gate) → sin $ ni conteo."""
        text = _mission_status_text("completed", {
            "deposited": 10, "approved": 1, "failed": 9,
            "accounts": 1, "stopped_by_user": True,
        })
        assert "$" not in text
        assert "aprobados" not in text
        assert "fallidos" not in text
        assert "detenido" in text.lower()

    def test_cancelled_no_cifras(self):
        """Camino 3: cancelled → ya limpio, sin $ ni conteo."""
        text = _mission_status_text("cancelled", {
            "deposited": 1500, "approved": 10, "failed": 0, "accounts": 1,
        })
        assert "$" not in text
        assert "aprobados" not in text
        assert "fallidos" not in text
        assert "Detenido por el operador" in text

    def test_completed_real_shows_total_but_no_conteo(self):
        """Camino 4: completed sin stopped_by_user (Fase 2 completa) → muestra $ total, NUNCA aprobados/fallidos."""
        text = _mission_status_text("completed", {
            "deposited": 1360, "approved": 10, "failed": 0, "accounts": 1,
        })
        assert "$1360" in text
        assert "aprobados" not in text
        assert "fallidos" not in text

    def test_scheduling_uses_fake_pct_not_real_count(self):
        """Área A punto 5: scheduling no expone comp/tot real, usa fake_pct."""
        text = _mission_status_text("scheduling", {
            "completed": 3, "total": 9, "fake_pct": 62,
        })
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
        # portal.js: Math.min(95, 30 + (completed/total) * 70)
        assert ad._fake_progress_pct("scheduling", {"completed": 0, "total": 9}) == 30
        assert ad._fake_progress_pct("scheduling", {"completed": 5, "total": 10}) == 65
        assert ad._fake_progress_pct("scheduling", {"completed": 9, "total": 9}) == 100

    def test_completed_is_100(self):
        assert ad._fake_progress_pct("completed", {}) == 100

    def test_preparing_is_30(self):
        # preparing entra antes de scheduling, mismo piso inicial
        assert ad._fake_progress_pct("preparing", {}) == 30

    def test_unknown_status_returns_0(self):
        assert ad._fake_progress_pct("unknown", {}) == 0
