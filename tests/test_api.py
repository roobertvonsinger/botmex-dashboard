def test_health_returns_db_path_and_count(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["accounts"] == 3
    assert body["db"].endswith("test.db")
