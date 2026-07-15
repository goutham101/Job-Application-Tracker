from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.db import get_conn
from app.schemas import (
    ApplicationCreate,
    ApplicationResponse,
    CompanyCreate,
    CompanyResponse,
    StageEventCreate,
    StageEventResponse,
)

router = APIRouter()

# DO UPDATE instead of DO NOTHING so RETURNING yields the existing row on conflict.
GET_OR_CREATE_COMPANY = """
    INSERT INTO companies (name, website)
    VALUES (%(name)s, %(website)s)
    ON CONFLICT (name) DO UPDATE
        SET website = COALESCE(EXCLUDED.website, companies.website)
    RETURNING id, name, website, created_at
"""

LIST_APPLICATIONS = """
    WITH current_status AS (
        SELECT DISTINCT ON (application_id)
               application_id, stage, occurred_at
        FROM stage_events
        ORDER BY application_id, occurred_at DESC, id DESC
    )
    SELECT a.id, a.company_id, c.name AS company_name, a.role_title, a.source,
           a.job_url, a.notes, a.created_at,
           cs.stage AS current_stage, cs.occurred_at AS current_stage_at
    FROM applications a
    JOIN companies c ON c.id = a.company_id
    LEFT JOIN current_status cs ON cs.application_id = a.id
"""


def insert_stage_event(conn, application_id: int, stage: str, occurred_at=None, notes=None):
    return conn.execute(
        """
        INSERT INTO stage_events (application_id, stage, occurred_at, notes)
        VALUES (%s, %s, COALESCE(%s, now()), %s)
        RETURNING id, application_id, stage, occurred_at, notes
        """,
        (application_id, stage, occurred_at, notes),
    ).fetchone()


@router.post("/companies", response_model=CompanyResponse, status_code=201)
def create_company(company: CompanyCreate, conn: Connection = Depends(get_conn)):
    return conn.execute(
        GET_OR_CREATE_COMPANY, {"name": company.name, "website": company.website}
    ).fetchone()


@router.post("/applications", response_model=ApplicationResponse, status_code=201)
def create_application(
    application: ApplicationCreate, conn: Connection = Depends(get_conn)
):
    company = conn.execute(
        GET_OR_CREATE_COMPANY,
        {"name": application.company_name, "website": application.company_website},
    ).fetchone()

    row = conn.execute(
        """
        INSERT INTO applications (company_id, role_title, source, job_url, notes)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id, company_id, role_title, source, job_url, notes, created_at
        """,
        (
            company["id"],
            application.role_title,
            application.source.value,
            application.job_url,
            application.notes,
        ),
    ).fetchone()

    event = conn.execute(
        """
        INSERT INTO stage_events (application_id, stage, occurred_at)
        VALUES (%s, 'applied', COALESCE(%s, now()))
        RETURNING stage, occurred_at
        """,
        (row["id"], application.applied_at),
    ).fetchone()

    return {
        **row,
        "company_name": company["name"],
        "current_stage": event["stage"],
        "current_stage_at": event["occurred_at"],
    }


@router.get("/applications", response_model=list[ApplicationResponse])
def list_applications(conn: Connection = Depends(get_conn)):
    return conn.execute(
        LIST_APPLICATIONS + " ORDER BY a.created_at DESC, a.id DESC"
    ).fetchall()


@router.post(
    "/applications/{application_id}/events",
    response_model=StageEventResponse,
    status_code=201,
)
def add_stage_event(
    application_id: int,
    event: StageEventCreate,
    backfill: bool = False,
    conn: Connection = Depends(get_conn),
):
    exists = conn.execute(
        "SELECT id FROM applications WHERE id = %s", (application_id,)
    ).fetchone()
    if exists is None:
        raise HTTPException(status_code=404, detail="Application not found")

    if event.occurred_at is not None and not backfill:
        latest = conn.execute(
            "SELECT MAX(occurred_at) AS latest FROM stage_events WHERE application_id = %s",
            (application_id,),
        ).fetchone()["latest"]
        if latest is not None and event.occurred_at < latest:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"occurred_at is earlier than the latest event ({latest.isoformat()}); "
                    "pass ?backfill=true to log it anyway"
                ),
            )

    return insert_stage_event(
        conn, application_id, event.stage.value, event.occurred_at, event.notes
    )


@router.delete("/applications/{application_id}", status_code=204)
def delete_application(application_id: int, conn: Connection = Depends(get_conn)):
    deleted = conn.execute(
        "DELETE FROM applications WHERE id = %s RETURNING id", (application_id,)
    ).fetchone()
    if deleted is None:
        raise HTTPException(status_code=404, detail="Application not found")
