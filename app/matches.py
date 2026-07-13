from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.applications import insert_stage_event
from app.db import get_conn
from app.schemas import EmailMatchResponse, MatchConfirm

router = APIRouter(prefix="/matches")

LIST_MATCHES = """
    SELECT m.id, m.gmail_message_id, m.application_id, m.suggested_stage, m.status,
           m.created_at, pe.sender, pe.subject, pe.received_at
    FROM email_matches m
    JOIN processed_emails pe ON pe.gmail_message_id = m.gmail_message_id
    WHERE m.status = %s
    ORDER BY pe.received_at DESC
"""


@router.get("", response_model=list[EmailMatchResponse])
def list_matches(
    status: Literal["pending", "confirmed", "dismissed"] = "pending",
    conn: Connection = Depends(get_conn),
):
    return conn.execute(LIST_MATCHES, (status,)).fetchall()


@router.post("/{match_id}/confirm", response_model=EmailMatchResponse)
def confirm_match(match_id: int, body: MatchConfirm, conn: Connection = Depends(get_conn)):
    match = conn.execute(
        "SELECT * FROM email_matches WHERE id = %s", (match_id,)
    ).fetchone()
    if match is None:
        raise HTTPException(status_code=404, detail="Match not found")
    if match["status"] != "pending":
        raise HTTPException(status_code=409, detail=f"Match already {match['status']}")

    application_id = body.application_id or match["application_id"]
    if application_id is None:
        raise HTTPException(
            status_code=422, detail="No application linked to this email; provide application_id"
        )

    insert_stage_event(
        conn,
        application_id,
        match["suggested_stage"],
        notes=f"Confirmed from email: {match['gmail_message_id']}",
    )

    updated = conn.execute(
        """
        UPDATE email_matches SET status = 'confirmed', application_id = %s
        WHERE id = %s
        RETURNING id, gmail_message_id, application_id, suggested_stage, status, created_at
        """,
        (application_id, match_id),
    ).fetchone()
    pe = conn.execute(
        "SELECT sender, subject, received_at FROM processed_emails WHERE gmail_message_id = %s",
        (updated["gmail_message_id"],),
    ).fetchone()
    return {**updated, **pe}


@router.post("/{match_id}/dismiss", response_model=EmailMatchResponse)
def dismiss_match(match_id: int, conn: Connection = Depends(get_conn)):
    updated = conn.execute(
        """
        UPDATE email_matches SET status = 'dismissed'
        WHERE id = %s AND status = 'pending'
        RETURNING id, gmail_message_id, application_id, suggested_stage, status, created_at
        """,
        (match_id,),
    ).fetchone()
    if updated is None:
        raise HTTPException(status_code=404, detail="Match not found or already resolved")
    pe = conn.execute(
        "SELECT sender, subject, received_at FROM processed_emails WHERE gmail_message_id = %s",
        (updated["gmail_message_id"],),
    ).fetchone()
    return {**updated, **pe}
