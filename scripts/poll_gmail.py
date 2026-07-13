"""Cron entrypoint — polls Gmail for new ATS emails and files matches for
review. Schedule every 2-6 hours (Render cron, or local crontab):

    python scripts/poll_gmail.py

Requires: DATABASE_URL, GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN.
"""

import psycopg
from psycopg.rows import dict_row

from app.db import DATABASE_URL
from app.gmail_client import RealGmailClient, build_gmail_service
from app.gmail_poller import poll_gmail


def main():
    service = build_gmail_service()
    client = RealGmailClient(service)
    with psycopg.connect(DATABASE_URL, row_factory=dict_row) as conn:
        stats = poll_gmail(conn, client)
    print(f"Gmail poll: {stats['seen']} seen, {stats['processed']} new, {stats['matched']} matched")


if __name__ == "__main__":
    main()
