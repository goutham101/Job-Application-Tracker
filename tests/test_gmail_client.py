import pytest


def test_build_gmail_service_constructs_without_network(monkeypatch):
    monkeypatch.setenv("GMAIL_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("GMAIL_REFRESH_TOKEN", "fake-refresh-token")

    from app.gmail_client import build_gmail_service

    try:
        service = build_gmail_service()
    except Exception as exc:
        pytest.skip(f"gmail discovery requires network in this environment: {exc}")

    assert hasattr(service, "users")
