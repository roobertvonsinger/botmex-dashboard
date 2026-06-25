# Tests SP-1: /execute borrado, modernos intactos, app importa sin BOT_RUN_DEPOSIT.
PIPE = "4111111111111111|12|30|123"

def test_execute_endpoint_removed(client):
    """La ruta legacy /api/deposits/execute ya no existe → 404."""
    r = client.post("/api/deposits/execute",
                    json={"account_id": 1, "card_pipe": PIPE, "amount": 50})
    assert r.status_code == 404

def test_execute_stream_still_registered(client):
    """El single moderno sigue registrado (no 404; sin deps del bot da 503, no 404)."""
    r = client.post("/api/deposits/execute-stream",
                    json={"account_id": 1, "card_pipe": PIPE, "amount": 50})
    assert r.status_code != 404

def test_multi_and_scheduled_still_registered(client):
    r1 = client.post("/api/deposits/multi/stream", json={})
    r2 = client.post("/api/deposits/scheduled/create", json={})
    assert r1.status_code != 404
    assert r2.status_code != 404

def test_load_deps_returns_pool_without_bot_run_deposit():
    """_load_deps ya no depende de BOT_RUN_DEPOSIT; retorna make_pool (o None)."""
    import deposits
    res = deposits._load_deps()
    # En el entorno de test las deps del bot no están → None. Lo clave: NO crashea
    # y NO es una tupla de 2 (contrato nuevo: un solo valor).
    assert res is None or callable(res)

import os

def test_legacy_modules_archived():
    """Los 7 módulos muertos están en _legacy/, no en la raíz."""
    for m in ("web_routes_deposits.py", "web_routes_missions.py",
              "web_routes_prewarm.py", "web_watchdog.py",
              "web_routes_cards.py", "web_routes_logs.py",
              "web_routes_notifications.py"):
        assert not os.path.exists(m), f"{m} sigue en raíz"
        assert os.path.exists(os.path.join("_legacy", m)), f"{m} no está en _legacy/"

def test_no_live_import_of_legacy():
    """Ningún módulo vivo (en raíz) importa los legacy."""
    import glob, re
    pat = re.compile(r"^\s*(from|import)\s+(web_routes_deposits|web_routes_missions|"
                     r"web_routes_prewarm|web_watchdog|web_routes_cards|web_routes_logs|"
                     r"web_routes_notifications)\b", re.M)
    for f in glob.glob("*.py"):
        txt = open(f, encoding="utf-8").read()
        assert not pat.search(txt), f"{f} aún importa un módulo legacy"
