from fastapi import APIRouter, Depends
from psycopg import Connection

from app.db import get_conn
from app.schemas import StageCount

router = APIRouter(prefix="/stats")

BY_STAGE = """
    WITH current_status AS (
        SELECT DISTINCT ON (application_id) application_id, stage
        FROM stage_events
        ORDER BY application_id, occurred_at DESC, id DESC
    )
    SELECT stage, COUNT(*) AS count
    FROM current_status
    GROUP BY stage
    ORDER BY array_position(
        ARRAY['applied','oa','phone_screen','interview',
              'final_round','offer','rejected','withdrawn'],
        stage)
"""


@router.get("/by-stage", response_model=list[StageCount])
def stats_by_stage(conn: Connection = Depends(get_conn)):
    return conn.execute(BY_STAGE).fetchall()
