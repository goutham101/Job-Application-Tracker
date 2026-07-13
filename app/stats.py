from fastapi import APIRouter, Depends
from psycopg import Connection

from app.db import get_conn
from app.schemas import FunnelStage, SourceStats, StageCount, StageTransition

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


# Funnel methodology (documented in README):
# - rejected/withdrawn are terminal, outside the pipeline
# - skipped stages count as passed through (reached = max pipeline rank >= stage rank)
# - apps still sitting at a stage are excluded from that stage's conversion denominator
FUNNEL = """
    WITH pipeline(stage, rank) AS (
        VALUES ('applied',1),('oa',2),('phone_screen',3),
               ('interview',4),('final_round',5),('offer',6)
    ),
    app_progress AS (
        SELECT se.application_id, MAX(p.rank) AS max_rank
        FROM stage_events se
        JOIN pipeline p ON p.stage = se.stage
        GROUP BY se.application_id
    ),
    current_status AS (
        SELECT DISTINCT ON (application_id) application_id, stage
        FROM stage_events
        ORDER BY application_id, occurred_at DESC, id DESC
    )
    SELECT p.stage,
           COUNT(*) FILTER (WHERE x.max_rank >= p.rank) AS reached,
           COUNT(*) FILTER (WHERE x.max_rank = p.rank AND x.stage = p.stage)
               AS still_pending
    FROM pipeline p
    LEFT JOIN (
        SELECT ap.application_id, ap.max_rank, cs.stage
        FROM app_progress ap
        JOIN current_status cs USING (application_id)
    ) x ON true
    GROUP BY p.stage, p.rank
    ORDER BY p.rank
"""

TIME_IN_STAGE = """
    WITH transitions AS (
        SELECT stage,
               LAG(stage)       OVER w AS prev_stage,
               occurred_at,
               LAG(occurred_at) OVER w AS prev_at
        FROM stage_events
        WINDOW w AS (PARTITION BY application_id ORDER BY occurred_at, id)
    )
    SELECT prev_stage AS from_stage, stage AS to_stage,
           COUNT(*) AS transitions,
           AVG(EXTRACT(EPOCH FROM (occurred_at - prev_at)) / 86400.0)::float
               AS avg_days
    FROM transitions
    WHERE prev_stage IS NOT NULL
    GROUP BY prev_stage, stage
    ORDER BY from_stage, to_stage
"""

# "Responded" = the company did anything beyond the initial application,
# including rejecting it. Silence is the only non-response.
BY_SOURCE = """
    WITH responded AS (
        SELECT DISTINCT application_id FROM stage_events WHERE stage <> 'applied'
    )
    SELECT a.source,
           COUNT(*) AS total,
           COUNT(r.application_id) AS responded,
           (COUNT(r.application_id)::float / COUNT(*)) AS response_rate
    FROM applications a
    LEFT JOIN responded r ON r.application_id = a.id
    GROUP BY a.source
    ORDER BY response_rate DESC, a.source
"""


@router.get("/funnel", response_model=list[FunnelStage])
def stats_funnel(conn: Connection = Depends(get_conn)):
    rows = conn.execute(FUNNEL).fetchall()
    for i, row in enumerate(rows):
        row["conversion_to_next"] = None
        if i + 1 < len(rows):
            denominator = row["reached"] - row["still_pending"]
            if denominator > 0:
                row["conversion_to_next"] = rows[i + 1]["reached"] / denominator
    return rows


@router.get("/time-in-stage", response_model=list[StageTransition])
def stats_time_in_stage(conn: Connection = Depends(get_conn)):
    return conn.execute(TIME_IN_STAGE).fetchall()


@router.get("/by-source", response_model=list[SourceStats])
def stats_by_source(conn: Connection = Depends(get_conn)):
    return conn.execute(BY_SOURCE).fetchall()
