from datetime import datetime, timezone

from app.gmail_poller import poll_gmail


class FakeGmailClient:
    def __init__(self, messages):
        self._messages = messages  # dict: id -> {"sender", "subject", "received_at"}

    def list_messages(self, query):
        return [{"id": mid} for mid in self._messages]

    def get_message(self, message_id):
        return self._messages[message_id]


def make_email(sender, subject, received_at=None):
    return {
        "sender": sender,
        "subject": subject,
        "received_at": received_at or datetime(2026, 7, 1, tzinfo=timezone.utc),
    }


def test_poll_creates_match_for_actionable_email(client, make_app):
    make_app(company="Stripe")
    fake = FakeGmailClient(
        {"msg-1": make_email('"Stripe via Greenhouse" <no-reply@greenhouse.io>', "Let's schedule your interview")}
    )

    from app.db import pool

    with pool.connection() as conn:
        stats = poll_gmail(conn, fake, query="irrelevant")

    assert stats == {"seen": 1, "processed": 1, "matched": 1}

    matches = client.get("/matches").json()
    assert len(matches) == 1
    assert matches[0]["suggested_stage"] == "interview"
    assert matches[0]["status"] == "pending"


def test_poll_is_idempotent(client, make_app):
    make_app(company="Stripe")
    fake = FakeGmailClient(
        {"msg-1": make_email('"Stripe via Greenhouse" <no-reply@greenhouse.io>', "Let's schedule your interview")}
    )

    from app.db import pool

    with pool.connection() as conn:
        poll_gmail(conn, fake, query="irrelevant")
        second = poll_gmail(conn, fake, query="irrelevant")

    assert second == {"seen": 1, "processed": 0, "matched": 0}
    assert len(client.get("/matches").json()) == 1


def test_poll_skips_confirmation_and_unclassified(client, make_app):
    make_app(company="Stripe")
    fake = FakeGmailClient(
        {
            "msg-1": make_email("no-reply@stripe.com", "Thank you for applying"),
            "msg-2": make_email("friend@gmail.com", "lunch?"),
        }
    )

    from app.db import pool

    with pool.connection() as conn:
        stats = poll_gmail(conn, fake, query="irrelevant")

    assert stats == {"seen": 2, "processed": 2, "matched": 0}
    assert client.get("/matches").json() == []


def test_poll_leaves_application_null_when_no_company_matches(client):
    fake = FakeGmailClient(
        {"msg-1": make_email("no-reply@totallyunknown.io", "Unfortunately, we have decided not to proceed")}
    )

    from app.db import pool

    with pool.connection() as conn:
        poll_gmail(conn, fake, query="irrelevant")

    matches = client.get("/matches").json()
    assert len(matches) == 1
    assert matches[0]["application_id"] is None
    assert matches[0]["suggested_stage"] == "rejected"
