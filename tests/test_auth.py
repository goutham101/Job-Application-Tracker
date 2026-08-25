import os


def test_open_when_api_key_unset(client):
    assert "API_KEY" not in os.environ
    response = client.get("/applications")
    assert response.status_code == 200


def test_rejects_missing_key_when_api_key_set(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret123")
    response = client.get("/applications")
    assert response.status_code == 401


def test_rejects_wrong_key_when_api_key_set(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret123")
    response = client.get("/applications", headers={"X-API-Key": "wrong"})
    assert response.status_code == 401


def test_accepts_correct_key_when_api_key_set(client, monkeypatch):
    monkeypatch.setenv("API_KEY", "secret123")
    response = client.get("/applications", headers={"X-API-Key": "secret123"})
    assert response.status_code == 200
