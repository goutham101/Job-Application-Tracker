import email
import imaplib
import os
from datetime import datetime, timezone
from email.header import decode_header
from email.utils import parsedate_to_datetime

IMAP_HOST = "imap.gmail.com"

# Any ATS senders + subject keywords match; parenthesized OR-of-OR is the
# safe, widely-supported form for chaining more than two IMAP FROM criteria.
DEFAULT_QUERY = '(OR (OR (FROM "greenhouse.io") (FROM "lever.co")) (FROM "myworkday.com"))'


def connect_imap():
    """Log into Gmail via IMAP using an App Password — no Google Cloud
    project or OAuth consent screen required. Generate one at
    myaccount.google.com/apppasswords (needs 2-Step Verification enabled)."""
    conn = imaplib.IMAP4_SSL(IMAP_HOST)
    conn.login(os.environ["GMAIL_ADDRESS"], os.environ["GMAIL_APP_PASSWORD"])
    return conn


def _decode(value: str) -> str:
    parts = decode_header(value)
    decoded = []
    for text, charset in parts:
        if isinstance(text, bytes):
            decoded.append(text.decode(charset or "utf-8", errors="replace"))
        else:
            decoded.append(text)
    return "".join(decoded)


def parse_message(raw_bytes: bytes) -> dict:
    msg = email.message_from_bytes(raw_bytes)
    sender = _decode(msg.get("From", ""))
    subject = _decode(msg.get("Subject", ""))
    date_header = msg.get("Date")
    received_at = parsedate_to_datetime(date_header) if date_header else datetime.now(timezone.utc)
    if received_at.tzinfo is None:
        received_at = received_at.replace(tzinfo=timezone.utc)
    return {"sender": sender, "subject": subject, "received_at": received_at}


class RealGmailClient:
    def __init__(self, conn):
        self.conn = conn
        self.conn.select("INBOX")

    def list_messages(self, query: str) -> list[dict]:
        status, data = self.conn.uid("search", None, query)
        if status != "OK" or not data or not data[0]:
            return []
        return [{"id": uid.decode()} for uid in data[0].split()]

    def get_message(self, message_id: str) -> dict:
        status, data = self.conn.uid("fetch", message_id, "(RFC822)")
        if status != "OK" or not data or data[0] is None:
            raise ValueError(f"Could not fetch message {message_id}")
        return parse_message(data[0][1])
