"""Cron entrypoint — polls Gmail for new ATS emails and files matches for
review. Schedule every 2-6 hours (Render cron, or local crontab):

    python scripts/poll_gmail.py

Requires: DATABASE_URL, GMAIL_ADDRESS, GMAIL_APP_PASSWORD.
Generate an App Password at myaccount.google.com/apppasswords — no Google
Cloud project needed.
"""

import sys
from pathlib import Path

# Running this file directly only puts scripts/ on sys.path, not the repo
# root — add it so `app.*` imports resolve regardless of invocation method.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import psycopg
from psycopg.rows import dict_row

from app.db import DATABASE_URL
from app.gmail_client import RealGmailClient, connect_imap
from app.gmail_poller import poll_gmail


def main():
    imap_conn = connect_imap()
    client = RealGmailClient(imap_conn)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        stats = poll_gmail(conn, client)
    imap_conn.logout()
    print(f"Gmail poll: {stats['seen']} seen, {stats['processed']} new, {stats['matched']} matched")


if __name__ == "__main__":
    main()
