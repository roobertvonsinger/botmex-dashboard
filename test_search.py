"""Tests del buscador inteligente (_build_search_clause) — multi-campo, multi-término,
normalización de tarjetas. Criterio de dominio: un operador busca una cuenta por
email, nombre del titular, CURP, teléfono, combo (password), o por su tarjeta
(número completo / BIN / terminación, con o sin separadores), o por una nota.
"""
import importlib


def _app(seed_db):
    import app
    importlib.reload(app)
    return app


def test_search_empty(seed_db):
    app = _app(seed_db)
    assert app._build_search_clause("") == ("", [])
    assert app._build_search_clause("   ") == ("", [])
    assert app._build_search_clause(None) == ("", [])


def test_search_single_term_covers_all_domain_fields(seed_db):
    app = _app(seed_db)
    sql, params = app._build_search_clause("andrea")
    for field in ("a.email", "a.fullname", "a.curp", "a.phone", "a.password", "a.address"):
        assert f"{field} LIKE ?" in sql, f"falta {field}"
    assert "account_cards" in sql and "account_notes" in sql
    assert "%andrea%" in params


def test_search_numeric_normalizes_card(seed_db):
    app = _app(seed_db)
    # tarjeta pegada con separadores → debe matchear el card_number sin separadores
    sql, params = app._build_search_clause("4189-2810")
    assert "%41892810%" in params      # versión limpia para card_number
    assert "%4189-2810%" in params     # versión textual para los demás campos


def test_search_multiterm_is_and(seed_db):
    app = _app(seed_db)
    # "Andrea García" → cada palabra debe aparecer (AND entre términos)
    sql, params = app._build_search_clause("andrea garcia")
    assert " AND " in sql
    assert "%andrea%" in params and "%garcia%" in params


def test_search_bin_matches_card(seed_db):
    app = _app(seed_db)
    # un BIN (6 dígitos) debe poder matchear card_number
    sql, params = app._build_search_clause("418928")
    assert "%418928%" in params
    assert "account_cards" in sql
