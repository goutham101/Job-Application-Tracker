from datetime import datetime, timezone
from email.header import Header
from email.message import EmailMessage

from app.gmail_client import parse_message


def make_raw_email(sender, subject, date_str, encode_subject=False):
    msg = EmailMessage()
    msg["From"] = sender
    msg["Subject"] = Header(subject, "utf-8").encode() if encode_subject else subject
    msg["Date"] = date_str
    msg.set_content("Body text here.")
    return msg.as_bytes()


def test_parse_plain_message():
    raw = make_raw_email(
        "no-reply@greenhouse.io",
        "Let's schedule your interview",
        "Wed, 1 Jul 2026 09:00:00 -0400",
    )
    result = parse_message(raw)
    assert result["sender"] == "no-reply@greenhouse.io"
    assert result["subject"] == "Let's schedule your interview"
    assert result["received_at"] == datetime(2026, 7, 1, 13, 0, 0, tzinfo=timezone.utc)


def test_parse_encoded_subject():
    raw = make_raw_email(
        '"Stripe via Greenhouse" <no-reply@greenhouse.io>',
        "Thank you for applying",
        "Wed, 1 Jul 2026 09:00:00 +0000",
        encode_subject=True,
    )
    result = parse_message(raw)
    assert result["sender"] == '"Stripe via Greenhouse" <no-reply@greenhouse.io>'
    assert result["subject"] == "Thank you for applying"


def test_parse_missing_date_defaults_to_now():
    raw = b"From: x@y.com\r\nSubject: hi\r\n\r\nBody\r\n"
    result = parse_message(raw)
    assert result["sender"] == "x@y.com"
    assert result["subject"] == "hi"
    assert result["received_at"].tzinfo is not None
