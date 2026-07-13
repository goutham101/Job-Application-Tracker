from app.gmail_classify import classify_email, match_company

DEFAULT_QUERY = (
    "newer_than:14d from:(no-reply@greenhouse.io OR *@lever.co OR *@myworkday.com)"
)

ACTIONABLE_STAGES = {"rejection": "rejected", "interview": "interview"}


def poll_gmail(conn, client, query: str = DEFAULT_QUERY) -> dict:
    stats = {"seen": 0, "processed": 0, "matched": 0}

    for ref in client.list_messages(query):
        stats["seen"] += 1
        message_id = ref["id"]

        already_seen = conn.execute(
            "SELECT 1 FROM processed_emails WHERE gmail_message_id = %s", (message_id,)
        ).fetchone()
        if already_seen:
            continue

        msg = client.get_message(message_id)
        classification = classify_email(msg["sender"], msg["subject"])

        conn.execute(
            """
            INSERT INTO processed_emails
                (gmail_message_id, received_at, sender, subject, classification)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (gmail_message_id) DO NOTHING
            """,
            (message_id, msg["received_at"], msg["sender"], msg["subject"], classification),
        )
        stats["processed"] += 1

        suggested_stage = ACTIONABLE_STAGES.get(classification)
        if suggested_stage:
            companies = conn.execute("SELECT id, name FROM companies").fetchall()
            application_id = match_company(msg["sender"], msg["subject"], companies)
            conn.execute(
                """
                INSERT INTO email_matches (gmail_message_id, application_id, suggested_stage)
                VALUES (%s, %s, %s)
                """,
                (message_id, application_id, suggested_stage),
            )
            stats["matched"] += 1

    conn.commit()
    return stats
