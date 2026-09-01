import deposits


def test_session_get_empty():
    assert deposits._mm_session_get({}, "a@test.com") == (None, None)


def test_session_get_returns_cached():
    s = {"a@test.com": ("JWT1", "P1")}
    assert deposits._mm_session_get(s, "a@test.com") == ("JWT1", "P1")


def test_update_caches_on_first_success():
    s = {}
    deposits._mm_session_update(s, "a@test.com",
        {"success": True, "jwt": "JWT1", "used_proxy": "P1"})
    assert s["a@test.com"] == ("JWT1", "P1")


def test_update_does_not_overwrite_existing():
    s = {"a@test.com": ("JWT1", "P1")}
    deposits._mm_session_update(s, "a@test.com",
        {"success": True, "jwt": "JWT2", "used_proxy": "P2"})
    assert s["a@test.com"] == ("JWT1", "P1")  # primera sesión manda


def test_update_invalidates_on_401():
    s = {"a@test.com": ("JWT1", "P1")}
    deposits._mm_session_update(s, "a@test.com",
        {"success": False, "result_code": "LOGIN_FAILED",
         "error": "begin_deposit: sesión rechazada (401 redirectLogin)"})
    assert "a@test.com" not in s


def test_update_keeps_session_on_normal_rejection():
    """Un rechazo de tarjeta (BANK_REJECTED) NO invalida la sesión de login."""
    s = {"a@test.com": ("JWT1", "P1")}
    deposits._mm_session_update(s, "a@test.com",
        {"success": False, "result_code": "BANK_REJECTED",
         "error": "Tarjeta rechazada por el banco"})


def test_check_caps_sa_bypass():
    """SA ignora el cap 24h ($1499), pero mantiene la regla de $499 por txn para evitar 3DS."""
    # Para operador normal sin is_sa, cap de >$499 o ventana llena debe fallar si excede
    err_txn = deposits._check_caps("test@email.com", 500.0, is_sa=False)
    assert err_txn is not None
    assert "dispara 3DS" in err_txn

    # Para SA con $500, viola por-txn ($499 max por 3DS)
    err_sa_txn = deposits._check_caps("test@email.com", 500.0, is_sa=True)
    assert err_sa_txn is not None
    assert "dispara 3DS" in err_sa_txn

    # Para SA con $490 (válido per-txn), no retorna error aun si is_sa=True (se omite check 24h)
    err_sa_ok = deposits._check_caps("test@email.com", 490.0, is_sa=True)
    assert err_sa_ok is None


def test_update_invalidates_on_bare_401():
    s = {"a@test.com": ("JWT1", "P1")}
    deposits._mm_session_update(s, "a@test.com",
        {"success": False, "error": "gateway devolvió 401"})
    assert "a@test.com" not in s


def test_update_invalidates_on_redirectlogin():
    s = {"a@test.com": ("JWT1", "P1")}
    deposits._mm_session_update(s, "a@test.com",
        {"success": False, "error": "respuesta: redirectLogin true"})
    assert "a@test.com" not in s
