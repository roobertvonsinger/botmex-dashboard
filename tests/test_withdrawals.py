# test_withdrawals.py — Task B: TDD de withdrawals.py (5 pasos API retiro BetMexico)
import asyncio
import json

import httpx
import pytest

import withdrawals as wd


def _json_response(status_code, payload):
    return httpx.Response(status_code, json=payload)


# ── B1 — get_bank_accounts (PASO1) ────────────────────────────────────────


def test_get_bank_accounts_happy_one_approved(mock_bmx_transport):
    def handler(request):
        return _json_response(
            200,
            {
                "accounts": [
                    {
                        "accountId": "a1",
                        "account": "1670XXXX1215",
                        "institutionName": "HEY BANCO",
                        "accountStatus": 2,
                        "accountStatusDescription": "Approved",
                    },
                ]
            },
        )

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_bank_accounts("JWT", None, transport=transport))
    assert len(result) == 1
    assert result[0]["accountId"] == "a1"


def test_get_bank_accounts_filters_non_approved(mock_bmx_transport):
    def handler(request):
        return _json_response(
            200,
            {
                "accounts": [
                    {
                        "accountId": "a1",
                        "account": "1",
                        "institutionName": "X",
                        "accountStatus": 2,
                    },
                    {
                        "accountId": "a2",
                        "account": "2",
                        "institutionName": "Y",
                        "accountStatus": 1,
                    },
                    {
                        "accountId": "a3",
                        "account": "3",
                        "institutionName": "Z",
                        "accountStatus": 0,
                    },
                ]
            },
        )

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_bank_accounts("JWT", None, transport=transport))
    assert len(result) == 1
    assert result[0]["accountId"] == "a1"


def test_get_bank_accounts_empty_aborts(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"accounts": []})

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(wd.NoApprovedWithdrawalAccount):
        asyncio.run(wd.get_bank_accounts("JWT", None, transport=transport))


def test_get_bank_accounts_multiple_approved_bug1(mock_bmx_transport):
    def handler(request):
        return _json_response(
            200,
            {
                "accounts": [
                    {
                        "accountId": "a1",
                        "account": "1111111111111215",
                        "institutionName": "HEY BANCO",
                        "accountStatus": 2,
                    },
                    {
                        "accountId": "a2",
                        "account": "2222222222220139",
                        "institutionName": "BBVA",
                        "accountStatus": 2,
                    },
                ]
            },
        )

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(wd.MultipleApprovedAccounts) as exc:
        asyncio.run(wd.get_bank_accounts("JWT", None, transport=transport))
    msg = str(exc.value)
    assert "HEY BANCO" in msg
    assert "BBVA" in msg
    assert "1215" in msg
    assert "0139" in msg


def test_get_bank_accounts_non200_raises(mock_bmx_transport):
    def handler(request):
        return httpx.Response(401, text="Unauthorized")

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError, match="BankAccounts HTTP 401"):
        asyncio.run(wd.get_bank_accounts("JWT", None, transport=transport))


def test_get_bank_accounts_uses_proxy_and_canonical_headers(mock_bmx_transport):
    def handler(request):
        return _json_response(
            200,
            {
                "accounts": [
                    {
                        "accountId": "a1",
                        "account": "1",
                        "institutionName": "X",
                        "accountStatus": 2,
                    },
                ]
            },
        )

    transport, reqs = mock_bmx_transport(handler)
    asyncio.run(wd.get_bank_accounts("JWT", None, transport=transport))
    headers = reqs["calls"][0]["headers"]
    assert headers["authorization"] == "Bearer JWT"
    assert headers["origin"] == "https://betmexico.mx"
    assert headers["referer"] == "https://betmexico.mx/"


def test_get_bank_accounts_timeout_raises(mock_bmx_transport):
    def handler(request):
        raise httpx.ConnectTimeout("timeout")

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError):
        asyncio.run(wd.get_bank_accounts("JWT", None, transport=transport))


# ── B2 — get_real_balance (PASO2) ─────────────────────────────────────────


def test_get_real_balance_happy(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"Real": 457.01, "Bonos": 0.0})

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_real_balance("JWT", None, transport=transport))
    assert result == {"Real": 457.01, "Bonos": 0.0}


def test_get_real_balance_non200_raises(mock_bmx_transport):
    def handler(request):
        return httpx.Response(500, text="Server error")

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError):
        asyncio.run(wd.get_real_balance("JWT", None, transport=transport))


def test_get_real_balance_missing_real_key(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"Bonos": 10})

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError, match="Real"):
        asyncio.run(wd.get_real_balance("JWT", None, transport=transport))


# ── B3 — begin_withdrawal (PASO3, SINGLE-SHOT) ────────────────────────────


def test_begin_withdrawal_happy_minimal_body(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"transactionId": "273123"})

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(
        wd.begin_withdrawal("JWT", None, "a1", 100.0, "x@y.com", transport=transport)
    )
    assert result["transactionId"] == "273123"
    body = json.loads(reqs["calls"][0]["body"])
    assert body == {"accountId": "a1", "amount": 100.0, "email": "x@y.com"}


def test_begin_withdrawal_amount_is_float_not_string(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"transactionId": "273123"})

    transport, reqs = mock_bmx_transport(handler)
    asyncio.run(
        wd.begin_withdrawal("JWT", None, "a1", 100, "x@y.com", transport=transport)
    )
    body = json.loads(reqs["calls"][0]["body"])
    assert isinstance(body["amount"], float)


def test_begin_withdrawal_400_concurrent_pending(mock_bmx_transport):
    def handler(request):
        return _json_response(
            400,
            {
                "message": "THE_TRANSACTION_DOES_NOT_COMPLY_WITH_THE_ESTABLISHED_CONFIGURATION"
            },
        )

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(wd.ConcurrentWithdrawalPending):
        asyncio.run(
            wd.begin_withdrawal(
                "JWT", None, "a1", 100.0, "x@y.com", transport=transport
            )
        )


def test_begin_withdrawal_401_jwt_dead(mock_bmx_transport):
    def handler(request):
        return httpx.Response(401, text="Unauthorized")

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError, match="JWT inválido/expirado"):
        asyncio.run(
            wd.begin_withdrawal(
                "JWT", None, "a1", 100.0, "x@y.com", transport=transport
            )
        )


def test_begin_withdrawal_500_unexpected(mock_bmx_transport):
    def handler(request):
        return httpx.Response(500, text="Server error")

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError):
        asyncio.run(
            wd.begin_withdrawal(
                "JWT", None, "a1", 100.0, "x@y.com", transport=transport
            )
        )


def test_begin_withdrawal_no_transaction_id_in_200(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {})

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError):
        asyncio.run(
            wd.begin_withdrawal(
                "JWT", None, "a1", 100.0, "x@y.com", transport=transport
            )
        )


def test_begin_withdrawal_sends_canonical_headers(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"transactionId": "273123"})

    transport, reqs = mock_bmx_transport(handler)
    asyncio.run(
        wd.begin_withdrawal("JWT", None, "a1", 100.0, "x@y.com", transport=transport)
    )
    headers = reqs["calls"][0]["headers"]
    assert headers["authorization"] == "Bearer JWT"
    assert headers["origin"] == "https://betmexico.mx"
    assert headers["referer"] == "https://betmexico.mx/"


def test_begin_withdrawal_does_not_retry_on_proxy_error(mock_bmx_transport):
    def handler(request):
        raise httpx.ConnectError("proxy down")

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(Exception):
        asyncio.run(
            wd.begin_withdrawal(
                "JWT", None, "a1", 100.0, "x@y.com", transport=transport
            )
        )
    assert len(reqs["calls"]) == 1


# ── B4 — get_pending_withdrawal (PASO4) ───────────────────────────────────


def test_get_pending_withdrawal_happy(mock_bmx_transport):
    def handler(request):
        return _json_response(
            200,
            {
                "id": "273",
                "reference": "3347",
                "transactionStatus": 2,
                "gatewayType": 2,
            },
        )

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_pending_withdrawal("JWT", None, transport=transport))
    assert result["id"] == "273"


def test_get_pending_withdrawal_none_when_no_pending(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"id": None})

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_pending_withdrawal("JWT", None, transport=transport))
    assert result is None


def test_get_pending_withdrawal_status6_returns_dict(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"id": "273", "transactionStatus": 6})

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_pending_withdrawal("JWT", None, transport=transport))
    assert result is not None
    assert result["transactionStatus"] == 6


def test_get_pending_withdrawal_non200_raises(mock_bmx_transport):
    def handler(request):
        return httpx.Response(500, text="Server error")

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError):
        asyncio.run(wd.get_pending_withdrawal("JWT", None, transport=transport))


# ── B5 — get_bank_transaction (PASO5, vía Transactions/ByUser) ────────────
# Root cause (2026-08-08, verificado en vivo con tx real bb4a346c...):
# /api/wallet/bankTransaction/{tx_id} NUNCA trae gateway/lastAccountDigits
# para retiros (solo transactionStatus/reference/amount). El endpoint que SÍ
# trae esos campos es /api/Wallet/Transactions/ByUser (verificado en vivo,
# misma tx: gateway:2, account:"5646", lastAccountDigits:"5646"). Sin esto,
# gateway_mismatch/digits_mismatch quedaban SIEMPRE False — guardarrail ciego.


def _txlist_response(items, page=1, page_size=50):
    return _json_response(200, {"data": {"results": items}})


def test_get_bank_transaction_happy(mock_bmx_transport):
    def handler(request):
        return _txlist_response(
            [
                {
                    "id": "273",
                    "status": 6,
                    "date": "2026-07-24T18:18:35",
                    "reference": "3347",
                    "type": 2,
                    "amount": 100.0,
                    "gateway": 2,
                    "lastAccountDigits": "1215",
                    "account": "1215",
                }
            ]
        )

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(
        wd.get_bank_transaction("JWT", None, "273", transport=transport)
    )
    assert result["id"] == "273"
    assert result["lastModifiedUtc"] == "2026-07-24T18:18:35"
    assert result["transactionStatus"] == 6


def test_get_bank_transaction_gateway2_spei_ok(mock_bmx_transport):
    def handler(request):
        return _txlist_response(
            [{"id": "273", "gateway": 2, "lastAccountDigits": "1215", "status": 6}]
        )

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(
        wd.get_bank_transaction("JWT", None, "273", transport=transport)
    )
    assert result["gateway_spei"] is True
    assert result["gateway_mismatch"] is False


def test_get_bank_transaction_gateway1_card_alert_bug3(mock_bmx_transport):
    def handler(request):
        return _txlist_response(
            [{"id": "273", "gateway": 1, "lastAccountDigits": "1215", "status": 6}]
        )

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(
        wd.get_bank_transaction("JWT", None, "273", transport=transport)
    )
    assert result["gateway_mismatch"] is True


def test_get_bank_transaction_digits_mismatch_alert_bug1(mock_bmx_transport):
    def handler(request):
        return _txlist_response(
            [{"id": "273", "gateway": 2, "lastAccountDigits": "0139", "status": 6}]
        )

    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(
        wd.get_bank_transaction(
            "JWT", None, "273", expected_digits="1215", transport=transport
        )
    )
    assert result["digits_mismatch"] is True
    assert result["actual_digits"] == "0139"
    assert result["expected_digits"] == "1215"


def test_get_bank_transaction_non200_raises(mock_bmx_transport):
    def handler(request):
        return httpx.Response(404, text="Not found")

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError):
        asyncio.run(wd.get_bank_transaction("JWT", None, "273", transport=transport))


def test_get_bank_transaction_not_found_in_history_raises(mock_bmx_transport):
    """La tx no aparece en la primera página del historial → error explícito,
    no un dict silencioso con flags en False (eso era exactamente el bug)."""

    def handler(request):
        return _txlist_response(
            [{"id": "OTRA-TX", "gateway": 2, "lastAccountDigits": "1215", "status": 6}]
        )

    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError, match="273"):
        asyncio.run(wd.get_bank_transaction("JWT", None, "273", transport=transport))


def test_get_bank_transaction_hits_transactions_by_user_endpoint(mock_bmx_transport):
    """Fija el endpoint correcto — regresión directa del bug: antes pegaba a
    /api/wallet/bankTransaction/{id} (siempre vacío de gateway/digits para
    retiros)."""

    def handler(request):
        return _txlist_response(
            [{"id": "273", "gateway": 2, "lastAccountDigits": "1215", "status": 6}]
        )

    transport, reqs = mock_bmx_transport(handler)
    asyncio.run(wd.get_bank_transaction("JWT", None, "273", transport=transport))
    url = reqs["calls"][0]["url"]
    assert "/api/Wallet/Transactions/ByUser" in url
    assert "bankTransaction" not in url


# ── B6 — execute_withdrawal (orquestador PASO0-3) ─────────────────────────


def test_execute_withdrawal_full_flow_mocked(monkeypatch, seed_db):
    monkeypatch.setattr(
        wd,
        "_load_jwt_for_account",
        lambda db_path, account_id: ("JWT-VIGENTE", "x@y.com", "ok"),
    )
    monkeypatch.setattr(wd, "_get_admin_proxy_url", lambda: "http://proxy:8080")

    call_seq = {"n": 0}

    async def fake_get_bank_accounts(jwt, proxy_url, transport=None):
        call_seq["n"] += 1
        return [
            {
                "accountId": "a1",
                "account": "1670XXXX1215",
                "institutionName": "HEY BANCO",
            }
        ]

    async def fake_get_real_balance(jwt, proxy_url, transport=None):
        call_seq["n"] += 1
        return {"Real": 200.0, "Bonos": 0.0}

    async def fake_begin_withdrawal(
        jwt, proxy_url, account_id_bmx, amount, email, transport=None
    ):
        call_seq["n"] += 1
        return {"transactionId": "273123"}

    monkeypatch.setattr(wd, "get_bank_accounts", fake_get_bank_accounts)
    monkeypatch.setattr(wd, "get_real_balance", fake_get_real_balance)
    monkeypatch.setattr(wd, "begin_withdrawal", fake_begin_withdrawal)

    result = asyncio.run(wd.execute_withdrawal(str(seed_db), 1, 100.0))
    assert result["transactionId"] == "273123"
    assert result["accountId"] == "a1"
    assert result["accountDigits"] == "1215"
    assert result["amount"] == 100.0
    assert result["warnings"] == []
    assert call_seq["n"] == 3


def test_execute_withdrawal_insufficient_balance(monkeypatch, seed_db):
    monkeypatch.setattr(
        wd,
        "_load_jwt_for_account",
        lambda db_path, account_id: ("JWT-VIGENTE", "x@y.com", "ok"),
    )
    monkeypatch.setattr(wd, "_get_admin_proxy_url", lambda: "http://proxy:8080")

    async def fake_get_bank_accounts(jwt, proxy_url, transport=None):
        return [
            {
                "accountId": "a1",
                "account": "1670XXXX1215",
                "institutionName": "HEY BANCO",
            }
        ]

    async def fake_get_real_balance(jwt, proxy_url, transport=None):
        return {"Real": 50.0, "Bonos": 0.0}

    monkeypatch.setattr(wd, "get_bank_accounts", fake_get_bank_accounts)
    monkeypatch.setattr(wd, "get_real_balance", fake_get_real_balance)

    with pytest.raises(wd.InsufficientBalance):
        asyncio.run(wd.execute_withdrawal(str(seed_db), 1, 100.0))


def test_execute_withdrawal_jwt_expired_no_api_call(monkeypatch, seed_db):
    monkeypatch.setattr(
        wd,
        "_load_jwt_for_account",
        lambda db_path, account_id: (None, "x@y.com", "jwt EXPIRADO"),
    )
    called = {"n": 0}

    async def fake_get_bank_accounts(jwt, proxy_url, transport=None):
        called["n"] += 1
        return []

    monkeypatch.setattr(wd, "get_bank_accounts", fake_get_bank_accounts)

    with pytest.raises(wd.JwtExpired):
        asyncio.run(wd.execute_withdrawal(str(seed_db), 1, 100.0))
    assert called["n"] == 0


# ── B7 — resolve_withdrawal_status (función compartida PASO4+PASO5) ─────────
# Extraída de app.py::withdraw_status para que el endpoint HTTP y el bg-loop
# server-side (account_refresh._withdrawal_resolution_loop) llamen la MISMA
# función. Lógica idéntica, no duplicada.


def test_resolve_pending_to_successful_two_phase(mock_bmx_transport, monkeypatch):
    """PASO4 retorna status=6 → confirma con PASO5 → out.status=successful."""
    monkeypatch.setattr(wd, "_persist_wd_status", lambda *a, **kw: None)

    def handler(request):
        url = str(request.url)
        if "PendingWithdrawal" in url:
            return _json_response(200, {"id": "273", "transactionStatus": 6})
        if "Transactions/ByUser" in url:
            return _txlist_response(
                [
                    {
                        "id": "273",
                        "gateway": 2,
                        "lastAccountDigits": "1215",
                        "date": "2026-07-24T18:18:35",
                        "status": 6,
                    }
                ]
            )
        return httpx.Response(404, text="not found")

    transport, reqs = mock_bmx_transport(handler)
    out = asyncio.run(
        wd.resolve_withdrawal_status(
            jwt="JWT",
            proxy_url=None,
            tx_id="273",
            expected_digits="1215",
            prev_status_api=2,
            transport=transport,
        )
    )
    assert out["status"] == "successful"
    assert out["phase"] == "executed"
    assert out["transactionStatus"] == 6
    assert out["lastModifiedUtc"] == "2026-07-24T18:18:35"
    assert out["gateway"] == 2
    assert out["alerts"]["gatewayMismatch"] is False
    assert out["alerts"]["digitsMismatch"] is False


def test_resolve_still_pending_status_not_6(mock_bmx_transport, monkeypatch):
    """PASO4 retorna status=2 (no terminal) → out.status=pending."""
    monkeypatch.setattr(wd, "_persist_wd_status", lambda *a, **kw: None)

    def handler(request):
        return _json_response(
            200,
            {
                "id": "273",
                "transactionStatus": 2,
                "transactionStatusDescription": "En proceso",
            },
        )

    transport, reqs = mock_bmx_transport(handler)
    out = asyncio.run(
        wd.resolve_withdrawal_status(
            jwt="JWT",
            proxy_url=None,
            tx_id="273",
            expected_digits="1215",
            prev_status_api=2,
            transport=transport,
        )
    )
    assert out["status"] == "pending"
    assert out["phase"] == "pending"
    assert out["transactionStatus"] == 2


def test_resolve_no_pending_bank_tx_confirms_6(mock_bmx_transport, monkeypatch):
    """PASO4 retorna None (ya no pendiente) → PASO5 confirma status=6 →
    out.status=successful (el caso del Bug 1: el retiro resolvió pero PASO4
    ya no lo lista)."""
    monkeypatch.setattr(wd, "_persist_wd_status", lambda *a, **kw: None)

    def handler(request):
        url = str(request.url)
        if "PendingWithdrawal" in url:
            return _json_response(200, {"id": None})
        if "Transactions/ByUser" in url:
            return _txlist_response(
                [
                    {
                        "id": "273",
                        "status": 6,
                        "gateway": 2,
                        "lastAccountDigits": "1215",
                        "date": "2026-07-24T18:18:35",
                    }
                ]
            )
        return httpx.Response(404, text="not found")

    transport, reqs = mock_bmx_transport(handler)
    out = asyncio.run(
        wd.resolve_withdrawal_status(
            jwt="JWT",
            proxy_url=None,
            tx_id="273",
            expected_digits="1215",
            prev_status_api=2,
            transport=transport,
        )
    )
    assert out["status"] == "successful"
    assert out["transactionStatus"] == 6


def test_resolve_no_jwt_returns_idle(mock_bmx_transport, monkeypatch):
    """Sin JWT no hay forma de consultar la API → idle (próximo ciclo)."""
    monkeypatch.setattr(wd, "_persist_wd_status", lambda *a, **kw: None)

    def handler(request):
        return httpx.Response(404, text="not found")

    transport, reqs = mock_bmx_transport(handler)
    out = asyncio.run(
        wd.resolve_withdrawal_status(
            jwt=None,
            proxy_url=None,
            tx_id="273",
            expected_digits="1215",
            prev_status_api=2,
            transport=transport,
        )
    )
    assert out["status"] == "idle"
    assert out["transactionStatus"] == 2


def test_resolve_prev_completed_stays_completed(mock_bmx_transport, monkeypatch):
    """prev_status_api=6 (ya terminal) y PASO4 retorna None (ya no pendiente)
    → no necesita PASO5, retorna completed sin persistir nada nuevo."""
    monkeypatch.setattr(wd, "_persist_wd_status", lambda *a, **kw: None)

    def handler(request):
        url = str(request.url)
        if "PendingWithdrawal" in url:
            # PASO4 retorna "no pendiente" → pending=None
            return _json_response(200, {"id": None})
        return httpx.Response(404, text="not found")

    transport, reqs = mock_bmx_transport(handler)
    out = asyncio.run(
        wd.resolve_withdrawal_status(
            jwt="JWT",
            proxy_url=None,
            tx_id="273",
            expected_digits="1215",
            prev_status_api=6,
            prev_gateway=2,
            prev_last_modified="2026-07-24T18:18:35",
            transport=transport,
        )
    )
    assert out["status"] == "completed"
    assert out["transactionStatus"] == 6
    assert out["lastModifiedUtc"] == "2026-07-24T18:18:35"
    assert out["gateway"] == 2


# ── B8 — execute_withdrawal persiste withdrawal_institution (Bug 2) ────────


def test_execute_withdrawal_persists_institution_bug2(monkeypatch, seed_db):
    """Bug 2 fix: execute_withdrawal exitoso debe dejar
    accounts.withdrawal_institution igual a la institución de la cuenta
    bancaria REALMENTE usada (resultado de SU get_bank_accounts), no la de un
    chequeo viejo de account_refresh.py (hasta 20 min después)."""
    import sqlite3 as _sqlite3

    # Asegurar que las columnas existen (las añade _migrate() en prod, pero
    # seed_db no reload app — las añadimos a mano como hace _migrate).
    con = _sqlite3.connect(str(seed_db))
    for col, ddl in [
        (
            "withdrawal_ready",
            "ALTER TABLE accounts ADD COLUMN withdrawal_ready INTEGER DEFAULT 0",
        ),
        (
            "withdrawal_institution",
            "ALTER TABLE accounts ADD COLUMN withdrawal_institution TEXT",
        ),
        ("jwt_token", "ALTER TABLE accounts ADD COLUMN jwt_token TEXT"),
    ]:
        try:
            con.execute(ddl)
        except _sqlite3.OperationalError:
            pass
    # Stale institution — la que habría dejado un chequeo viejo de
    # account_refresh.py
    con.execute(
        "UPDATE accounts SET withdrawal_institution='BANAMEX', withdrawal_ready=1 "
        "WHERE email='a@test.com'"
    )
    con.commit()
    con.close()

    monkeypatch.setattr(
        wd,
        "_load_jwt_for_account",
        lambda db_path, account_id: ("JWT-VIGENTE", "a@test.com", "ok"),
    )
    monkeypatch.setattr(wd, "_get_admin_proxy_url", lambda: "http://proxy:8080")

    async def fake_get_bank_accounts(jwt, proxy_url, transport=None):
        # La cuenta REALMENTE usada es INBURSA, no BANAMEX (stale)
        return [
            {"accountId": "a1", "account": "1670XXXX1215", "institutionName": "INBURSA"}
        ]

    async def fake_get_real_balance(jwt, proxy_url, transport=None):
        return {"Real": 200.0, "Bonos": 0.0}

    async def fake_begin_withdrawal(
        jwt, proxy_url, account_id_bmx, amount, email, transport=None
    ):
        return {"transactionId": "273123"}

    monkeypatch.setattr(wd, "get_bank_accounts", fake_get_bank_accounts)
    monkeypatch.setattr(wd, "get_real_balance", fake_get_real_balance)
    monkeypatch.setattr(wd, "begin_withdrawal", fake_begin_withdrawal)

    result = asyncio.run(wd.execute_withdrawal(str(seed_db), 1, 100.0))
    assert result["institutionName"] == "INBURSA"

    con = _sqlite3.connect(str(seed_db))
    row = con.execute(
        "SELECT withdrawal_institution, withdrawal_ready FROM accounts WHERE email='a@test.com'"
    ).fetchone()
    con.close()
    assert row[0] == "INBURSA"
    assert row[1] == 1


def test_resolve_status_processing_5_persists_full(mock_bmx_transport, monkeypatch):
    """PASO4 retorna None → PASO5 retorna status=5 (En proceso) → out.status=pending, persiste status_api=5."""
    persisted = []
    monkeypatch.setattr(
        wd,
        "_persist_wd_status",
        lambda tx_id, status_api, gateway=None, last_mod=None, full=False: persisted.append(
            {"tx_id": tx_id, "status_api": status_api, "gateway": gateway, "full": full}
        ),
    )

    def handler(request):
        url = str(request.url)
        if "PendingWithdrawal" in url:
            return _json_response(200, {"id": None})
        if "Transactions/ByUser" in url:
            return _txlist_response(
                [
                    {
                        "id": "tx-proc-5",
                        "status": 5,
                        "gateway": 2,
                        "lastAccountDigits": "5646",
                        "date": "2026-08-19T03:30:04",
                    }
                ]
            )
        return httpx.Response(404, text="not found")

    transport, _ = mock_bmx_transport(handler)
    out = asyncio.run(
        wd.resolve_withdrawal_status(
            jwt="JWT",
            proxy_url=None,
            tx_id="tx-proc-5",
            expected_digits="5646",
            prev_status_api=None,
            transport=transport,
        )
    )
    assert out["status"] == "pending"
    assert out["phase"] == "processing"
    assert out["transactionStatus"] == 5
    assert len(persisted) == 1
    assert persisted[0]["status_api"] == 5
    assert persisted[0]["gateway"] == 2
    assert persisted[0]["full"] is True


def test_resolve_status_failed_negative_persists_full(mock_bmx_transport, monkeypatch):
    """PASO4 retorna None → PASO5 retorna status=-4 (Rechazado) → out.status=failed, out.phase=failed."""
    persisted = []
    monkeypatch.setattr(
        wd,
        "_persist_wd_status",
        lambda tx_id, status_api, gateway=None, last_mod=None, full=False: persisted.append(
            {"tx_id": tx_id, "status_api": status_api, "gateway": gateway, "full": full}
        ),
    )

    def handler(request):
        url = str(request.url)
        if "PendingWithdrawal" in url:
            return _json_response(200, {"id": None})
        if "Transactions/ByUser" in url:
            return _txlist_response(
                [
                    {
                        "id": "tx-fail-4",
                        "status": -4,
                        "gateway": 2,
                        "lastAccountDigits": "5646",
                        "date": "2026-08-19T04:00:00",
                    }
                ]
            )
        return httpx.Response(404, text="not found")

    transport, _ = mock_bmx_transport(handler)
    out = asyncio.run(
        wd.resolve_withdrawal_status(
            jwt="JWT",
            proxy_url=None,
            tx_id="tx-fail-4",
            expected_digits="5646",
            prev_status_api=None,
            transport=transport,
        )
    )
    assert out["status"] == "failed"
    assert out["phase"] == "failed"
    assert out["transactionStatus"] == -4
    assert len(persisted) == 1
    assert persisted[0]["status_api"] == -4
    assert persisted[0]["full"] is True


def test_resolve_card_refund_gateway_1(mock_bmx_transport, monkeypatch):
    """PASO5 retorna gateway=1 (Tarjeta) → out.alerts.gatewayMismatch=True y descripción de reembolso."""
    persisted = []
    monkeypatch.setattr(
        wd,
        "_persist_wd_status",
        lambda tx_id, status_api, gateway=None, last_mod=None, full=False: persisted.append(
            {"tx_id": tx_id, "status_api": status_api, "gateway": gateway, "full": full}
        ),
    )

    def handler(request):
        url = str(request.url)
        if "PendingWithdrawal" in url:
            return _json_response(200, {"id": None})
        if "Transactions/ByUser" in url:
            return _txlist_response(
                [
                    {
                        "id": "tx-card-refund",
                        "status": 6,
                        "gateway": 1,
                        "lastAccountDigits": "",
                        "date": "2026-08-19T03:30:00",
                    }
                ]
            )
        return httpx.Response(404, text="not found")

    transport, _ = mock_bmx_transport(handler)
    out = asyncio.run(
        wd.resolve_withdrawal_status(
            jwt="JWT",
            proxy_url=None,
            tx_id="tx-card-refund",
            expected_digits="5646",
            prev_status_api=None,
            transport=transport,
        )
    )
    assert out["status"] == "successful"
    assert out["alerts"]["gatewayMismatch"] is True
    assert "reembolso a tarjeta" in out["description"].lower()
    assert len(persisted) == 1
    assert persisted[0]["gateway"] == 1
