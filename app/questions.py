from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from psycopg import Connection

from app.db import get_conn
from app.schemas import QuestionCreate, QuestionResponse, ReviewCreate
from app.sm2 import sm2_update

router = APIRouter()


@router.post("/questions", response_model=QuestionResponse, status_code=201)
def create_question(question: QuestionCreate, conn: Connection = Depends(get_conn)):
    return conn.execute(
        """
        INSERT INTO questions (prompt, source_application_id)
        VALUES (%s, %s)
        RETURNING id, prompt, source_application_id, easiness, interval_days, repetitions, due_date
        """,
        (question.prompt, question.source_application_id),
    ).fetchone()


@router.get("/questions/due", response_model=list[QuestionResponse])
def list_due_questions(conn: Connection = Depends(get_conn)):
    return conn.execute(
        "SELECT * FROM questions WHERE due_date <= CURRENT_DATE ORDER BY due_date"
    ).fetchall()


@router.post("/questions/{question_id}/review", response_model=QuestionResponse)
def review_question(
    question_id: int, review: ReviewCreate, conn: Connection = Depends(get_conn)
):
    question = conn.execute(
        "SELECT * FROM questions WHERE id = %s", (question_id,)
    ).fetchone()
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")

    new_state = sm2_update(
        question["easiness"], question["interval_days"], question["repetitions"], review.quality
    )
    due_date = date.today() + timedelta(days=new_state.interval_days)

    conn.execute(
        "INSERT INTO reviews (question_id, quality) VALUES (%s, %s)",
        (question_id, review.quality),
    )
    return conn.execute(
        """
        UPDATE questions
        SET easiness = %s, interval_days = %s, repetitions = %s, due_date = %s
        WHERE id = %s
        RETURNING id, prompt, source_application_id, easiness, interval_days, repetitions, due_date
        """,
        (new_state.easiness, new_state.interval_days, new_state.repetitions, due_date, question_id),
    ).fetchone()
