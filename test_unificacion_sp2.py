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
    assert s["a@test.com"] == ("JWT1", "P1")


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
