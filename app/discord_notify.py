import os

import httpx

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def notify(message: str) -> None:
    """Fire-and-forget Discord notification. A Discord outage must never
    fail the request that triggered it, so every error is swallowed."""
    if not WEBHOOK_URL:
        return
    try:
        httpx.post(WEBHOOK_URL, json={"content": message}, timeout=5)
    except httpx.HTTPError:
        pass
