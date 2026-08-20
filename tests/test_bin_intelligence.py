"""Unit tests para el Motor de Inteligencia y Recomendación de BINes."""

import pytest
import sqlite3
from bin_intelligence import (
    lookup_bin_metadata,
    classify_bin_tier,
    get_bin_intelligence_summary,
    format_telegram_start_banner,
    format_telegram_bet_warning,
    format_telegram_radar_full,
    get_single_card_bin_badge,
    MEXICAN_BIN_CATALOG,
)


def test_lookup_bin_metadata_known():
    """Verifica resolución de bancos mexicanos conocidos."""
    santander = lookup_bin_metadata("491566")
    assert santander["bank"] == "Santander"
    assert santander["type"] == "DEBIT"
    assert santander["flag"] == "🇲🇽"

    bbva = lookup_bin_metadata("526424")
    assert "BBVA" in bbva["bank"]
    assert bbva["scheme"] == "MASTERCARD"
    assert bbva["flag"] == "🇲🇽"

    banorte = lookup_bin_metadata("544548")
    assert banorte["bank"] == "Banorte"
    assert banorte["type"] == "CREDIT"

    citibanamex = lookup_bin_metadata("511916")
    assert citibanamex["bank"] == "Citibanamex"
    assert citibanamex["level"] == "PLATINUM"


def test_lookup_bin_metadata_unknown_fallback():
    """Verifica que un BIN no catalogado reciba un fallback seguro."""
    res = lookup_bin_metadata("499999")
    assert res["flag"] == "🇲🇽"
    assert res["scheme"] == "VISA"

    res_mc = lookup_bin_metadata("599999")
    assert res_mc["scheme"] == "MASTERCARD"


def test_classify_bin_tier_corona():
    """Al menos 1 aprobado y tasa >= 10% clasifica como 'corona'."""
    tier, title, badge, slang = classify_bin_tier(attempts=10, approved=5, threeds=1, rejected=4)
    assert tier == "corona"
    assert "CORONA" in badge
    assert "50.0%" in slang


def test_classify_bin_tier_threeds():
    """Dispara 3DS sin aprobación clasifica como 'threeds'."""
    tier, title, badge, slang = classify_bin_tier(attempts=5, approved=0, threeds=2, rejected=3)
    assert tier == "threeds"
    assert "3DS" in badge
    assert "2 retos 3DS" in slang


def test_classify_bin_tier_dead():
    """Rechazo ultra consistente (>=4 y 0 aprobados ni 3ds) clasifica como 'dead'."""
    tier, title, badge, slang = classify_bin_tier(attempts=15, approved=0, threeds=0, rejected=15)
    assert tier == "dead"
    assert "QUEMADA" in badge
    assert "al día de hoy nadie ha coronado" in slang


def test_classify_bin_tier_testing():
    """Pocos intentos (<=3) sin 3DS ni aprobación clasifica como 'testing'."""
    tier, title, badge, slang = classify_bin_tier(attempts=2, approved=0, threeds=0, rejected=2)
    assert tier == "testing"
    assert "TEST" in badge
    assert "seguir intentando" in slang


def test_format_telegram_start_banner():
    """Verifica que el banner de /start contenga formato HTML y emojis cuando hay datos."""
    mock_summary = {
        "top_5": [{"bin": "491566", "bank": "Santander", "type": "DEBIT", "flag": "🇲🇽", "approval_rate": 75.0}]
    }
    banner = format_telegram_start_banner(mock_summary)
    assert "TOP BINES" in banner
    assert "👑" in banner
    assert "🇲🇽" in banner
    # Si no hay datos, retorna vacío
    assert format_telegram_start_banner({"top_5": []}) == ""


def test_format_telegram_bet_warning():
    """Verifica que el aviso comercial de /bet contenga recomendaciones y advertencias."""
    mock_summary = {
        "top_5": [{"bin": "491566", "bank": "Santander", "type": "DEBIT", "flag": "🇲🇽", "approval_rate": 75.0}],
        "threeds": [{"bin": "551238"}],
        "dead": [{"bin": "525343"}],
    }
    warning = format_telegram_bet_warning(mock_summary)
    assert "RADAR DE INTELIGENCIA DE PASARELA" in warning
    assert "BINES CON MAYOR TASA DE ÉXITO" in warning
    assert "3DS" in warning
    assert "Decline" in warning


def test_format_telegram_radar_full():
    """Verifica que el radar completo presente las 4 categorías."""
    mock_summary = {
        "corona": [{"bin": "491566", "bank": "Santander", "type": "DEBIT", "flag": "🇲🇽", "approval_rate": 75.0, "approved": 10}],
        "threeds": [{"bin": "551238", "bank": "HSBC", "threeds": 3}],
        "testing": [{"bin": "510125", "bank": "Banorte", "attempts": 2}],
        "dead": [{"bin": "525343", "bank": "Scotiabank", "rejected": 5}],
    }
    radar = format_telegram_radar_full(mock_summary)
    assert "TOP CORONA" in radar
    assert "3DS / ANTIFRAUD" in radar
    assert "EN PRUEBAS" in radar
    assert "QUEMADAS" in radar


def test_get_single_card_bin_badge():
    """Verifica que una tarjeta individual reciba su badge correspondiente."""
    mock_summary = {
        "corona": [{"bin": "491566", "tier": "corona", "tier_badge": "👑 CORONA"}]
    }
    # Santander debito con summary
    res = get_single_card_bin_badge("4915661234567890|12|28|123", summary=mock_summary)
    assert "Santander" in res["bank"]
    assert res["flag"] == "🇲🇽"
    assert res["tier"] == "corona"


def test_api_bin_recommendations_endpoint(client):
    """Endpoint /api/deposits/bin-recommendations devuelve los 4 tiers."""
    resp = client.get("/api/deposits/bin-recommendations")
    assert resp.status_code == 200
    data = resp.json()
    assert "totals" in data
    assert "corona" in data
    assert "threeds" in data
    assert "testing" in data
    assert "dead" in data
    assert "top_5" in data


def test_api_bin_check_enriched_endpoint(client):
    """Endpoint /api/deposits/bin-check/{bin6} devuelve inteligencia y metadata."""
    resp = client.get("/api/deposits/bin-check/491566")
    assert resp.status_code == 200
    data = resp.json()
    assert "is_3ds_prone" in data
    assert "metadata" in data
    assert "intelligence" in data
    assert data["metadata"]["bank"] == "Santander"


def test_api_operator_recent_ticker_endpoint(client):
    """Endpoint /api/operator/recent-ticker devuelve stats_1h, marquesinas, tips y trending."""
    resp = client.get("/api/operator/recent-ticker")
    assert resp.status_code == 200
    data = resp.json()
    assert data["ok"] is True
    assert "stats_1h" in data
    assert "recent_deposits" in data
    assert "recent_withdrawals" in data
    assert "tips" in data
    assert "trending" in data
    assert len(data["tips"]) > 0
    assert "rising" in data["trending"]
    assert "falling" in data["trending"]
