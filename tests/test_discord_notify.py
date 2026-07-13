import httpx

from app import discord_notify


def test_notify_posts_to_webhook(monkeypatch):
    monkeypatch.setattr(discord_notify, "WEBHOOK_URL", "https://discord.example/webhook")
    calls = []
    monkeypatch.setattr(
        discord_notify.httpx, "post", lambda url, json, timeout: calls.append((url, json))
    )

    discord_notify.notify("Stripe — SWE Intern moved to oa")

    assert calls == [("https://discord.example/webhook", {"content": "Stripe — SWE Intern moved to oa"})]


def test_notify_noop_when_unset(monkeypatch):
    monkeypatch.setattr(discord_notify, "WEBHOOK_URL", None)
    calls = []
    monkeypatch.setattr(discord_notify.httpx, "post", lambda *a, **k: calls.append(1))

    discord_notify.notify("should not send")

    assert calls == []


def test_notify_swallows_errors(monkeypatch):
    monkeypatch.setattr(discord_notify, "WEBHOOK_URL", "https://discord.example/webhook")

    def raise_error(*a, **k):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(discord_notify.httpx, "post", raise_error)

    discord_notify.notify("network is down")  # must not raise
