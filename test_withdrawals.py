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
        return _json_response(200, {"accounts": [
            {"accountId": "a1", "account": "1670XXXX1215",
             "institutionName": "HEY BANCO", "accountStatus": 2,
             "accountStatusDescription": "Approved"},
        ]})
    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_bank_accounts("JWT", None, transport=transport))
    assert len(result) == 1
    assert result[0]["accountId"] == "a1"


def test_get_bank_accounts_filters_non_approved(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"accounts": [
            {"accountId": "a1", "account": "1", "institutionName": "X", "accountStatus": 2},
            {"accountId": "a2", "account": "2", "institutionName": "Y", "accountStatus": 1},
            {"accountId": "a3", "account": "3", "institutionName": "Z", "accountStatus": 0},
        ]})
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
        return _json_response(200, {"accounts": [
            {"accountId": "a1", "account": "1111111111111215",
             "institutionName": "HEY BANCO", "accountStatus": 2},
            {"accountId": "a2", "account": "2222222222220139",
             "institutionName": "BBVA", "accountStatus": 2},
        ]})
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
        return _json_response(200, {"accounts": [
            {"accountId": "a1", "account": "1", "institutionName": "X", "accountStatus": 2},
        ]})
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
    result = asyncio.run(wd.begin_withdrawal(
        "JWT", None, "a1", 100.0, "x@y.com", transport=transport
    ))
    assert result["transactionId"] == "273123"
    body = json.loads(reqs["calls"][0]["body"])
    assert body == {"accountId": "a1", "amount": 100.0, "email": "x@y.com"}


def test_begin_withdrawal_amount_is_float_not_string(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"transactionId": "273123"})
    transport, reqs = mock_bmx_transport(handler)
    asyncio.run(wd.begin_withdrawal("JWT", None, "a1", 100, "x@y.com", transport=transport))
    body = json.loads(reqs["calls"][0]["body"])
    assert isinstance(body["amount"], float)


def test_begin_withdrawal_400_concurrent_pending(mock_bmx_transport):
    def handler(request):
        return _json_response(400, {
            "message": "THE_TRANSACTION_DOES_NOT_COMPLY_WITH_THE_ESTABLISHED_CONFIGURATION"
        })
    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(wd.ConcurrentWithdrawalPending):
        asyncio.run(wd.begin_withdrawal("JWT", None, "a1", 100.0, "x@y.com", transport=transport))


def test_begin_withdrawal_401_jwt_dead(mock_bmx_transport):
    def handler(request):
        return httpx.Response(401, text="Unauthorized")
    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError, match="JWT inválido/expirado"):
        asyncio.run(wd.begin_withdrawal("JWT", None, "a1", 100.0, "x@y.com", transport=transport))


def test_begin_withdrawal_500_unexpected(mock_bmx_transport):
    def handler(request):
        return httpx.Response(500, text="Server error")
    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError):
        asyncio.run(wd.begin_withdrawal("JWT", None, "a1", 100.0, "x@y.com", transport=transport))


def test_begin_withdrawal_no_transaction_id_in_200(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {})
    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError):
        asyncio.run(wd.begin_withdrawal("JWT", None, "a1", 100.0, "x@y.com", transport=transport))


def test_begin_withdrawal_sends_canonical_headers(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"transactionId": "273123"})
    transport, reqs = mock_bmx_transport(handler)
    asyncio.run(wd.begin_withdrawal("JWT", None, "a1", 100.0, "x@y.com", transport=transport))
    headers = reqs["calls"][0]["headers"]
    assert headers["authorization"] == "Bearer JWT"
    assert headers["origin"] == "https://betmexico.mx"
    assert headers["referer"] == "https://betmexico.mx/"


def test_begin_withdrawal_does_not_retry_on_proxy_error(mock_bmx_transport):
    def handler(request):
        raise httpx.ConnectError("proxy down")
    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(Exception):
        asyncio.run(wd.begin_withdrawal("JWT", None, "a1", 100.0, "x@y.com", transport=transport))
    assert len(reqs["calls"]) == 1


# ── B4 — get_pending_withdrawal (PASO4) ───────────────────────────────────

def test_get_pending_withdrawal_happy(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"id": "273", "reference": "3347",
                                     "transactionStatus": 2, "gatewayType": 2})
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


# ── B5 — get_bank_transaction (PASO5) ─────────────────────────────────────

def test_get_bank_transaction_happy(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {
            "id": "273", "transactionStatus": 6,
            "lastModifiedUtc": "2026-07-24T18:18:35",
            "reference": "3347", "transactionTypeDescription": "Retiro",
            "amount": 100.0, "gateway": 2, "lastAccountDigits": "1215",
        })
    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_bank_transaction("JWT", None, "273", transport=transport))
    assert result["id"] == "273"
    assert result["lastModifiedUtc"] == "2026-07-24T18:18:35"


def test_get_bank_transaction_gateway2_spei_ok(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"id": "273", "gateway": 2, "lastAccountDigits": "1215"})
    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_bank_transaction("JWT", None, "273", transport=transport))
    assert result["gateway_spei"] is True
    assert result["gateway_mismatch"] is False


def test_get_bank_transaction_gateway1_card_alert_bug3(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"id": "273", "gateway": 1, "lastAccountDigits": "1215"})
    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_bank_transaction("JWT", None, "273", transport=transport))
    assert result["gateway_mismatch"] is True


def test_get_bank_transaction_digits_mismatch_alert_bug1(mock_bmx_transport):
    def handler(request):
        return _json_response(200, {"id": "273", "gateway": 2, "lastAccountDigits": "0139"})
    transport, reqs = mock_bmx_transport(handler)
    result = asyncio.run(wd.get_bank_transaction(
        "JWT", None, "273", expected_digits="1215", transport=transport
    ))
    assert result["digits_mismatch"] is True
    assert result["actual_digits"] == "0139"
    assert result["expected_digits"] == "1215"


def test_get_bank_transaction_non200_raises(mock_bmx_transport):
    def handler(request):
        return httpx.Response(404, text="Not found")
    transport, reqs = mock_bmx_transport(handler)
    with pytest.raises(RuntimeError):
        asyncio.run(wd.get_bank_transaction("JWT", None, "273", transport=transport))


# ── B6 — execute_withdrawal (orquestador PASO0-3) ─────────────────────────

def test_execute_withdrawal_full_flow_mocked(monkeypatch, seed_db):
    monkeypatch.setattr(
        wd, "_load_jwt_for_account",
        lambda db_path, account_id: ("JWT-VIGENTE", "x@y.com", "ok"),
    )
    monkeypatch.setattr(wd, "_get_admin_proxy_url", lambda: "http://proxy:8080")

    call_seq = {"n": 0}

    async def fake_get_bank_accounts(jwt, proxy_url, transport=None):
        call_seq["n"] += 1
        return [{"accountId": "a1", "account": "1670XXXX1215", "institutionName": "HEY BANCO"}]

    async def fake_get_real_balance(jwt, proxy_url, transport=None):
        call_seq["n"] += 1
        return {"Real": 200.0, "Bonos": 0.0}

    async def fake_begin_withdrawal(jwt, proxy_url, account_id_bmx, amount, email, transport=None):
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
        wd, "_load_jwt_for_account",
        lambda db_path, account_id: ("JWT-VIGENTE", "x@y.com", "ok"),
    )
    monkeypatch.setattr(wd, "_get_admin_proxy_url", lambda: "http://proxy:8080")

    async def fake_get_bank_accounts(jwt, proxy_url, transport=None):
        return [{"accountId": "a1", "account": "1670XXXX1215", "institutionName": "HEY BANCO"}]

    async def fake_get_real_balance(jwt, proxy_url, transport=None):
        return {"Real": 50.0, "Bonos": 0.0}

    monkeypatch.setattr(wd, "get_bank_accounts", fake_get_bank_accounts)
    monkeypatch.setattr(wd, "get_real_balance", fake_get_real_balance)

    with pytest.raises(wd.InsufficientBalance):
        asyncio.run(wd.execute_withdrawal(str(seed_db), 1, 100.0))


def test_execute_withdrawal_jwt_expired_no_api_call(monkeypatch, seed_db):
    monkeypatch.setattr(
        wd, "_load_jwt_for_account",
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
