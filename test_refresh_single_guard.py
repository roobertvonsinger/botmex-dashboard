"""Reproduce el bug: refresh-stream de UNA sola cuenta con JWT expirado,
disparado por un operador no-SA, cae en el guard bulk `no_jwt` y nunca
intenta login fresco. El guard (agregado en 4c42517, prewarm.py:729-742)
debe aplicar solo a refresh MASIVO (>1 cuenta), no al clic individual.

Sigue el patrón de fixtures de conftest.py / test_anti_rate_limit.py:
seed_db (BD sqlite temporal) + make_client (TestClient con rol inyectado).
"""
import json
import time

import pytest


@pytest.fixture
def seed_account_expired_jwt(seed_db):
    """Cuenta LIVE (a@test.com, id conocido) con JWT vencido hace 1h y password seteado."""
    import sqlite3
    con = sqlite3.connect(seed_db)
    try:
        # _migrate() (corrido por make_client vía importlib.reload(app_mod)) agrega
        # la columna jwt_expires_at — pero el fixture corre ANTES de esa reload en
        # algunos ordenamientos, así que la agregamos aquí de forma defensiva.
        try:
            con.execute("ALTER TABLE accounts ADD COLUMN jwt_expires_at INTEGER")
        except sqlite3.OperationalError:
            pass  # ya existe
        expired = int(time.time()) - 3600
        con.execute(
            "UPDATE accounts SET jwt_expires_at=?, password='x', status='LIVE' WHERE email='a@test.com'",
            (expired,),
        )
        con.commit()
        row = con.execute("SELECT id FROM accounts WHERE email='a@test.com'").fetchone()
    finally:
        con.close()
    return {"id": row[0]}


def test_single_row_refresh_bypasses_no_jwt_guard(make_client, seed_account_expired_jwt, monkeypatch):
    """Un operador (no-SA) que refresca UNA sola cuenta manualmente debe
    poder disparar login fresco aunque el JWT cacheado esté expirado —
    el guard anti-bulk solo debe aplicar a refresh masivo (>1 cuenta)."""
    client = make_client(role="operator", telegram_id=555, username="op555")

    import prewarm as pw

    # El endpoint corta con 503 si _HAS_BOT_DEPS es False (deps del bot no
    # instaladas en el entorno de test) — no es lo que este test cubre.
    monkeypatch.setattr(pw, "_HAS_BOT_DEPS", True)

    # Evita que el test dependa del login real (captcha/proxies/BetMexico) —
    # solo nos interesa si el guard no_jwt deja pasar o bloquea el intento.
    called = {"ran": False}

    async def _fake_run_prewarm(operator_id, email, password):
        called["ran"] = True
        return {"ok": False, "error": "login simulado no ejecutado en test"}

    monkeypatch.setattr(pw, "_run_prewarm", _fake_run_prewarm)

    acc_id = seed_account_expired_jwt["id"]
    resp = client.post(
        "/api/prewarm/refresh-stream",
        json={"account_ids": [acc_id], "force": True},
    )
    assert resp.status_code == 200
    body = resp.text

    events = [json.loads(l[len("data: "):]) for l in body.splitlines() if l.startswith("data: ")]
    skip_no_jwt = [e for e in events if e.get("type") == "skip" and e.get("reason") == "no_jwt"]

    assert not skip_no_jwt, (
        "el refresh de 1 sola cuenta no debe caer en el guard bulk no_jwt "
        f"(eventos: {events})"
    )
    assert called["ran"], "con el guard eximido, debio intentarse un login fresco via _run_prewarm"
