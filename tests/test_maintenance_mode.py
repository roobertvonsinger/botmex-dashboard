import pytest
from fastapi.testclient import TestClient
import app as main_app

@pytest.fixture
def client():
    return TestClient(main_app.app)

def test_maintenance_mode_disabled_by_default(client, monkeypatch):
    monkeypatch.setenv("BMX_MAINTENANCE", "0")
    res = client.get("/login")
    assert res.status_code == 200

def test_maintenance_mode_redirects_unauth_user(client, monkeypatch):
    monkeypatch.setenv("BMX_MAINTENANCE", "1")
    res = client.get("/login", follow_redirects=False)
    assert res.status_code == 302
    assert res.headers["location"] == "/maintenance"

def test_maintenance_mode_blocks_api(client, monkeypatch):
    monkeypatch.setenv("BMX_MAINTENANCE", "1")
    res = client.get("/api/health")
    assert res.status_code == 530
    assert res.json() == {"error": "Sistema en mantenimiento", "maintenance": True}

def test_maintenance_mode_allows_static_assets(client, monkeypatch):
    monkeypatch.setenv("BMX_MAINTENANCE", "1")
    res = client.get("/maintenance")
    assert res.status_code == 200
    res_logo = client.get("/static/assets/botmexico_logo.png")
    assert res_logo.status_code == 200

def test_maintenance_mode_allows_superadmin(client, monkeypatch):
    monkeypatch.setenv("BMX_MAINTENANCE", "1")
    # Seteamos cookie con sesión mock de superadmin
    token = main_app._auth.create_session("robertvs")
    client.cookies.set("bmx_session", token)
    res = client.get("/api/health")
    assert res.status_code == 200
