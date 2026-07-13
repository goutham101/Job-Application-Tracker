# Tier 2: SM-2, Gmail Ingestion, Discord Webhook Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build everything in Tier 2 of `job-tracker-build-plan.md` that doesn't require an interactive browser action: SM-2 spaced repetition, Gmail ingestion (idempotent polling, rule-based classification, human-confirmed review queue), and a fire-and-forget Discord webhook — leaving only the one-time Google OAuth consent step for the user to run themselves.

**Architecture:** SM-2 is a pure function (`app/sm2.py`) driven by two new tables (`questions`, `reviews`), mirroring the append-only philosophy of the rest of the app. Gmail ingestion separates concerns so most of it is unit-testable without real credentials: `app/gmail_classify.py` is pure (sender/subject → classification, company match), `app/gmail_poller.py` takes an injectable client (a `FakeGmailClient` in tests, `RealGmailClient` in production) and writes to two idempotency/review tables (`processed_emails`, `email_matches`), and `app/matches.py` exposes the human-confirmation endpoints that are the only path from a matched email to a real `stage_events` row. Discord notification is factored into a shared `insert_stage_event()` helper so both the manual API and the email-confirm path notify identically.

**Tech Stack:** FastAPI, psycopg 3 (existing), `google-api-python-client` + `google-auth-oauthlib` (Gmail API), `rapidfuzz` (company name fuzzy matching), `httpx` (already installed, used for the Discord webhook).

## Global Constraints

- **No auth, no users table** — unchanged from Tier 0/1.
- **Migrations:** numbered plain SQL files in `db/migrations/`, applied by the existing `db/migrate.py`. This plan adds `002_sm2.sql` and `003_email_ingestion.sql`.
- **Nothing writes to `stage_events` from an email without human confirmation** — `POST /matches/{id}/confirm` is the only path; the poller only ever inserts into `email_matches`.
- **SM-2 lapse rule (exact, per build plan):** quality < 3 → `repetitions = 0`, `interval_days = 1`, **easiness unchanged**. Do not update easiness on a lapse.
- **Discord webhook must never fail the request that triggered it** — wrap in try/except, swallow all errors.
- **Gmail OAuth tokens live in env vars only** (`GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`), never in the repo or the database.
- **Do not build a clever company resolver** — fuzzy-match against existing `companies.name`; below threshold or no companies, leave `application_id` null for the human to resolve in the review queue.
- Python: `./venv/bin/python` (3.13). Run tests as `./venv/bin/python -m pytest`.
- Test DB: `postgresql://localhost/jobtracker_test`. Dev DB: `postgresql://localhost/jobtracker`.

---

### Task 1: Discord notify function

**Files:**
- Create: `app/discord_notify.py`
- Test: `tests/test_discord_notify.py`

**Interfaces:**
- Produces: `notify(message: str) -> None` — reads `DISCORD_WEBHOOK_URL` from env at call time via the module's `WEBHOOK_URL` global; no-ops if unset; never raises.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_discord_notify.py
import httpx
import pytest

from app import discord_notify


def test_notify_posts_to_webhook(monkeypatch):
    monkeypatch.setattr(discord_notify, "WEBHOOK_URL", "https://discord.example/webhook")
    calls = []
    monkeypatch.setattr(
        discord_notify.httpx, "post", lambda url, json, timeout: calls.append((url, json))
    )

    discord_notify.notify("Stripe — SWE Intern moved to oa")

    assert calls == [("https://discord.example/webhook", {"content": "Stripe — SWE Intern moved to oa"})]


def test_notify_noop_when_unset(monkeypatch):
    monkeypatch.setattr(discord_notify, "WEBHOOK_URL", None)
    calls = []
    monkeypatch.setattr(discord_notify.httpx, "post", lambda *a, **k: calls.append(1))

    discord_notify.notify("should not send")

    assert calls == []


def test_notify_swallows_errors(monkeypatch):
    monkeypatch.setattr(discord_notify, "WEBHOOK_URL", "https://discord.example/webhook")

    def raise_error(*a, **k):
        raise httpx.ConnectError("boom")

    monkeypatch.setattr(discord_notify.httpx, "post", raise_error)

    discord_notify.notify("network is down")  # must not raise
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_discord_notify.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.discord_notify'`)

- [ ] **Step 3: Write the implementation**

```python
# app/discord_notify.py
import os

import httpx

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")


def notify(message: str) -> None:
    """Fire-and-forget Discord notification. A Discord outage must never
    fail the request that triggered it, so every error is swallowed."""
    if not WEBHOOK_URL:
        return
    try:
        httpx.post(WEBHOOK_URL, json={"content": message}, timeout=5)
    except httpx.HTTPError:
        pass
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_discord_notify.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add app/discord_notify.py tests/test_discord_notify.py
git commit -m "feat: add fire-and-forget Discord webhook notifier"
```

---

### Task 2: Wire Discord notification into stage events (shared helper)

**Files:**
- Modify: `app/applications.py`
- Test: `tests/test_events.py`

**Interfaces:**
- Produces: `insert_stage_event(conn, application_id: int, stage: str, occurred_at=None, notes=None) -> dict` — inserts the event row, looks up company/role for the message, calls `discord_notify.notify(...)`, returns the inserted row (same shape `StageEventResponse` expects). Used by both `add_stage_event` (this task) and the Gmail confirm endpoint (Task 9).

Current `add_stage_event` (from the Tier 0/1 build) ends with this insert, which is being extracted:

```python
    return conn.execute(
        """
        INSERT INTO stage_events (application_id, stage, occurred_at, notes)
        VALUES (%s, %s, COALESCE(%s, now()), %s)
        RETURNING id, application_id, stage, occurred_at, notes
        """,
        (application_id, event.stage.value, event.occurred_at, event.notes),
    ).fetchone()
```

- [ ] **Step 1: Write the failing test**

```python
# tests/test_events.py — add to the existing file
def test_stage_event_triggers_discord_notify(client, make_app, monkeypatch):
    from app import applications

    calls = []
    monkeypatch.setattr(applications, "notify", lambda msg: calls.append(msg))

    created = make_app(company="Acme", role="SWE Intern")
    client.post(f"/applications/{created['id']}/events", json={"stage": "oa"})

    assert calls == ["Acme — SWE Intern moved to oa"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `./venv/bin/python -m pytest tests/test_events.py::test_stage_event_triggers_discord_notify -v`
Expected: FAIL (`AttributeError: module 'app.applications' has no attribute 'notify'`)

- [ ] **Step 3: Extract the shared helper and wire it in**

Add the import at the top of `app/applications.py`:

```python
from app.discord_notify import notify
```

Add this function (near the top, after the module-level SQL constants):

```python
def insert_stage_event(conn, application_id: int, stage: str, occurred_at=None, notes=None):
    row = conn.execute(
        """
        INSERT INTO stage_events (application_id, stage, occurred_at, notes)
        VALUES (%s, %s, COALESCE(%s, now()), %s)
        RETURNING id, application_id, stage, occurred_at, notes
        """,
        (application_id, stage, occurred_at, notes),
    ).fetchone()

    app_info = conn.execute(
        """
        SELECT a.role_title, c.name AS company_name
        FROM applications a JOIN companies c ON c.id = a.company_id
        WHERE a.id = %s
        """,
        (application_id,),
    ).fetchone()
    notify(f"{app_info['company_name']} — {app_info['role_title']} moved to {stage}")

    return row
```

Replace the tail of `add_stage_event` (everything from the 409 check's closing brace down to the final `return conn.execute(...)`) with:

```python
    return insert_stage_event(
        conn, application_id, event.stage.value, event.occurred_at, event.notes
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_events.py tests/test_applications.py tests/test_stats.py -v`
Expected: all pass (existing behavior unchanged, new test passes)

- [ ] **Step 5: Commit**

```bash
git add app/applications.py tests/test_events.py
git commit -m "refactor: extract insert_stage_event helper, notify Discord on stage change"
```

---

### Task 3: SM-2 migration + schemas

**Files:**
- Create: `db/migrations/002_sm2.sql`
- Modify: `app/schemas.py`
- Modify: `tests/conftest.py`

**Interfaces:**
- Produces: `questions`, `reviews` tables. `QuestionCreate`, `QuestionResponse`, `ReviewCreate` Pydantic models.

`002_sm2.sql` (exact schema from the build plan):

```sql
CREATE TABLE questions (
    id SERIAL PRIMARY KEY,
    prompt TEXT NOT NULL,
    source_application_id INTEGER REFERENCES applications(id),
    easiness REAL NOT NULL DEFAULT 2.5,
    interval_days INTEGER NOT NULL DEFAULT 0,
    repetitions INTEGER NOT NULL DEFAULT 0,
    due_date DATE NOT NULL DEFAULT CURRENT_DATE
);

CREATE TABLE reviews (
    id SERIAL PRIMARY KEY,
    question_id INTEGER NOT NULL REFERENCES questions(id),
    quality SMALLINT NOT NULL CHECK (quality BETWEEN 0 AND 5),
    reviewed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- [ ] **Step 1: Write the migration file** (exact content above)

- [ ] **Step 2: Apply to dev and test databases**

```bash
./venv/bin/python db/migrate.py
DATABASE_URL=postgresql://localhost/jobtracker_test ./venv/bin/python db/migrate.py
```
Expected: `Applied: 002_sm2.sql` both times

- [ ] **Step 3: Update the test truncate list**

In `tests/conftest.py`, change:

```python
        conn.execute(
            "TRUNCATE companies, applications, stage_events RESTART IDENTITY CASCADE"
        )
```

to:

```python
        conn.execute(
            "TRUNCATE companies, applications, stage_events, questions, reviews "
            "RESTART IDENTITY CASCADE"
        )
```

- [ ] **Step 4: Add schemas**

In `app/schemas.py`, add `date` to the datetime import:

```python
from datetime import date, datetime
```

Add at the end of the file:

```python
class QuestionCreate(BaseModel):
    prompt: str
    source_application_id: Optional[int] = None


class QuestionResponse(BaseModel):
    id: int
    prompt: str
    source_application_id: Optional[int] = None
    easiness: float
    interval_days: int
    repetitions: int
    due_date: date


class ReviewCreate(BaseModel):
    quality: int = Field(ge=0, le=5)
```

Add `Field` to the pydantic import at the top of the file:

```python
from pydantic import BaseModel, Field
```

- [ ] **Step 5: Run full suite to confirm nothing broke**

Run: `./venv/bin/python -m pytest -q`
Expected: all existing tests still pass (no new tests yet — this task is schema-only)

- [ ] **Step 6: Commit**

```bash
git add db/migrations/002_sm2.sql tests/conftest.py app/schemas.py
git commit -m "feat: add SM-2 questions/reviews schema"
```

---

### Task 4: SM-2 pure algorithm

**Files:**
- Create: `app/sm2.py`
- Test: `tests/test_sm2.py`

**Interfaces:**
- Produces: `SM2State(easiness: float, interval_days: int, repetitions: int)` dataclass; `sm2_update(easiness: float, interval_days: int, repetitions: int, quality: int) -> SM2State`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_sm2.py
import pytest

from app.sm2 import sm2_update


def test_lapse_resets_interval_and_repetitions_but_not_easiness():
    result = sm2_update(easiness=2.5, interval_days=10, repetitions=3, quality=2)
    assert result.interval_days == 1
    assert result.repetitions == 0
    assert result.easiness == 2.5  # unchanged on lapse — the plan's explicit rule


def test_first_successful_review():
    result = sm2_update(easiness=2.5, interval_days=0, repetitions=0, quality=5)
    assert result.interval_days == 1
    assert result.repetitions == 1
    assert result.easiness == pytest.approx(2.6)


def test_second_successful_review_uses_six_days():
    result = sm2_update(easiness=2.36, interval_days=1, repetitions=1, quality=4)
    assert result.interval_days == 6
    assert result.repetitions == 2
    assert result.easiness == pytest.approx(2.36)


def test_third_plus_review_multiplies_by_easiness_rounded_up():
    result = sm2_update(easiness=2.0, interval_days=6, repetitions=2, quality=4)
    assert result.interval_days == 12  # ceil(6 * 2.0)
    assert result.repetitions == 3


def test_easiness_floors_at_one_point_three():
    result = sm2_update(easiness=1.3, interval_days=10, repetitions=5, quality=3)
    assert result.easiness == 1.3
    assert result.interval_days == 13  # ceil(10 * 1.3)


def test_quality_out_of_range_rejected():
    with pytest.raises(ValueError):
        sm2_update(easiness=2.5, interval_days=1, repetitions=0, quality=6)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_sm2.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.sm2'`)

- [ ] **Step 3: Write the implementation**

```python
# app/sm2.py
import math
from dataclasses import dataclass


@dataclass
class SM2State:
    easiness: float
    interval_days: int
    repetitions: int


def sm2_update(easiness: float, interval_days: int, repetitions: int, quality: int) -> SM2State:
    """Canonical SM-2. On a lapse (quality < 3), easiness is left unchanged —
    many implementations get this wrong; the spec only updates it on a pass."""
    if not 0 <= quality <= 5:
        raise ValueError("quality must be between 0 and 5")

    if quality < 3:
        return SM2State(easiness=easiness, interval_days=1, repetitions=0)

    if repetitions == 0:
        new_interval = 1
    elif repetitions == 1:
        new_interval = 6
    else:
        new_interval = math.ceil(interval_days * easiness)

    new_easiness = easiness + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
    new_easiness = max(1.3, new_easiness)

    return SM2State(easiness=new_easiness, interval_days=new_interval, repetitions=repetitions + 1)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_sm2.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add app/sm2.py tests/test_sm2.py
git commit -m "feat: add pure SM-2 spaced repetition algorithm"
```

---

### Task 5: SM-2 endpoints

**Files:**
- Create: `app/questions.py`
- Modify: `app/main.py`
- Test: `tests/test_questions.py`

**Interfaces:**
- Consumes: `sm2_update` (Task 4), `QuestionCreate`/`QuestionResponse`/`ReviewCreate` (Task 3).
- Produces: `POST /questions`, `GET /questions/due`, `POST /questions/{id}/review`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_questions.py
from datetime import date, timedelta


def test_create_and_list_due(client):
    response = client.post("/questions", json={"prompt": "Explain DISTINCT ON"})
    assert response.status_code == 201
    question = response.json()
    assert question["due_date"] == date.today().isoformat()
    assert question["easiness"] == 2.5

    due = client.get("/questions/due").json()
    assert any(q["id"] == question["id"] for q in due)


def test_review_updates_state_and_due_date(client):
    question = client.post("/questions", json={"prompt": "What is a window function?"}).json()

    response = client.post(f"/questions/{question['id']}/review", json={"quality": 5})
    assert response.status_code == 200
    updated = response.json()
    assert updated["repetitions"] == 1
    assert updated["interval_days"] == 1
    assert updated["due_date"] == (date.today() + timedelta(days=1)).isoformat()


def test_lapse_removes_question_from_due_tomorrow(client):
    question = client.post("/questions", json={"prompt": "What is MVCC?"}).json()
    client.post(f"/questions/{question['id']}/review", json={"quality": 5})  # due_date -> +1

    due_today = client.get("/questions/due").json()
    assert all(q["id"] != question["id"] for q in due_today)


def test_review_unknown_question_404(client):
    response = client.post("/questions/9999/review", json={"quality": 4})
    assert response.status_code == 404


def test_review_quality_out_of_range_422(client):
    question = client.post("/questions", json={"prompt": "..."}).json()
    response = client.post(f"/questions/{question['id']}/review", json={"quality": 9})
    assert response.status_code == 422
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_questions.py -v`
Expected: FAIL (404s — no routes registered yet)

- [ ] **Step 3: Write the implementation**

```python
# app/questions.py
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
```

Register the router in `app/main.py` — add the import alongside the others:

```python
from app.questions import router as questions_router
```

and after `app.include_router(stats_router)`:

```python
app.include_router(questions_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_questions.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add app/questions.py app/main.py tests/test_questions.py
git commit -m "feat: add SM-2 spaced repetition endpoints"
```

---

### Task 6: Gmail ingestion migration

**Files:**
- Create: `db/migrations/003_email_ingestion.sql`
- Modify: `tests/conftest.py`

**Interfaces:**
- Produces: `processed_emails`, `email_matches` tables.

```sql
CREATE TABLE processed_emails (
    gmail_message_id TEXT PRIMARY KEY,
    received_at      TIMESTAMPTZ NOT NULL,
    sender           TEXT NOT NULL,
    subject          TEXT NOT NULL,
    classification   TEXT NOT NULL
                     CHECK (classification IN ('confirmation','rejection','interview','unclassified')),
    processed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE email_matches (
    id               SERIAL PRIMARY KEY,
    gmail_message_id TEXT NOT NULL REFERENCES processed_emails(gmail_message_id),
    application_id   INTEGER REFERENCES applications(id),
    suggested_stage  TEXT NOT NULL
                     CHECK (suggested_stage IN ('applied','oa','phone_screen','interview',
                                                 'final_round','offer','rejected','withdrawn')),
    status           TEXT NOT NULL DEFAULT 'pending'
                     CHECK (status IN ('pending','confirmed','dismissed')),
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

- [ ] **Step 1: Write the migration file** (exact content above)

- [ ] **Step 2: Apply to dev and test databases**

```bash
./venv/bin/python db/migrate.py
DATABASE_URL=postgresql://localhost/jobtracker_test ./venv/bin/python db/migrate.py
```
Expected: `Applied: 003_email_ingestion.sql` both times

- [ ] **Step 3: Update the test truncate list**

In `tests/conftest.py`, change the truncate statement to:

```python
        conn.execute(
            "TRUNCATE companies, applications, stage_events, questions, reviews, "
            "processed_emails, email_matches RESTART IDENTITY CASCADE"
        )
```

- [ ] **Step 4: Run full suite to confirm nothing broke**

Run: `./venv/bin/python -m pytest -q`
Expected: all existing tests still pass

- [ ] **Step 5: Commit**

```bash
git add db/migrations/003_email_ingestion.sql tests/conftest.py
git commit -m "feat: add Gmail ingestion idempotency and review-queue schema"
```

---

### Task 7: Gmail classification (pure functions)

**Files:**
- Create: `app/gmail_classify.py`
- Test: `tests/test_gmail_classify.py`

**Interfaces:**
- Produces: `classify_email(sender: str, subject: str) -> str` (one of `"confirmation"`, `"rejection"`, `"interview"`, `"unclassified"`); `guess_company_name(sender: str, subject: str) -> str`; `match_company(sender: str, subject: str, companies: list[dict], threshold: int = 85) -> int | None` where each `companies` dict has `"id"` and `"name"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gmail_classify.py
from app.gmail_classify import classify_email, guess_company_name, match_company


def test_classify_rejection():
    assert classify_email(
        "no-reply@greenhouse.io", "Update on your application: we've decided not to proceed"
    ) == "rejection"


def test_classify_interview():
    assert classify_email(
        "recruiting@lever.co", "Let's schedule your interview"
    ) == "interview"


def test_classify_confirmation():
    assert classify_email(
        "no-reply@myworkday.com", "Thank you for applying to Acme Corp"
    ) == "confirmation"


def test_classify_unclassified():
    assert classify_email("friend@gmail.com", "lunch tomorrow?") == "unclassified"


def test_guess_company_name_from_display_name():
    assert guess_company_name('"Stripe via Greenhouse" <no-reply@greenhouse.io>', "") == "Stripe"


def test_guess_company_name_falls_back_to_domain():
    assert guess_company_name("jobs@stripe.com", "") == "stripe"


def test_match_company_above_threshold():
    companies = [{"id": 1, "name": "Stripe"}, {"id": 2, "name": "Ramp"}]
    sender = '"Stripe via Greenhouse" <no-reply@greenhouse.io>'
    assert match_company(sender, "", companies) == 1


def test_match_company_no_match_returns_none():
    companies = [{"id": 1, "name": "Stripe"}]
    assert match_company("jobs@totallydifferentco.com", "", companies) is None


def test_match_company_empty_list_returns_none():
    assert match_company("jobs@stripe.com", "", []) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_gmail_classify.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.gmail_classify'`)

- [ ] **Step 3: Install rapidfuzz**

```bash
./venv/bin/pip install rapidfuzz
./venv/bin/pip freeze | grep -i rapidfuzz
```

- [ ] **Step 4: Write the implementation**

```python
# app/gmail_classify.py
import re

from rapidfuzz import fuzz, process

REJECTION_KEYWORDS = (
    "unfortunately",
    "not moving forward",
    "not be moving forward",
    "decided not to proceed",
    "other candidates",
)
INTERVIEW_KEYWORDS = ("schedule", "interview")
CONFIRMATION_KEYWORDS = (
    "thank you for applying",
    "received your application",
    "application received",
)

_NOISE_WORDS = re.compile(r"\b(via|careers|recruiting|talent|hiring)\b", re.IGNORECASE)
_DISPLAY_NAME = re.compile(r'^"?([^"<]+?)"?\s*<')
_DOMAIN = re.compile(r"@([\w.-]+)")


def classify_email(sender: str, subject: str) -> str:
    text = subject.lower()
    if any(k in text for k in REJECTION_KEYWORDS):
        return "rejection"
    if any(k in text for k in INTERVIEW_KEYWORDS):
        return "interview"
    if any(k in text for k in CONFIRMATION_KEYWORDS):
        return "confirmation"
    return "unclassified"


def guess_company_name(sender: str, subject: str) -> str:
    """Best-effort company name guess. Deliberately simple — ambiguous
    cases are left for the human review queue, not resolved here."""
    display_match = _DISPLAY_NAME.match(sender)
    if display_match:
        name = _NOISE_WORDS.sub("", display_match.group(1)).strip()
        if name:
            return name
    domain_match = _DOMAIN.search(sender)
    if domain_match:
        return domain_match.group(1).split(".")[0]
    return subject


def match_company(
    sender: str, subject: str, companies: list[dict], threshold: int = 85
) -> int | None:
    if not companies:
        return None
    candidate = guess_company_name(sender, subject)
    names = [c["name"] for c in companies]
    result = process.extractOne(candidate, names, scorer=fuzz.WRatio)
    if result and result[1] >= threshold:
        matched_name = result[0]
        return next(c["id"] for c in companies if c["name"] == matched_name)
    return None
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_gmail_classify.py -v`
Expected: 9 passed

- [ ] **Step 6: Commit**

```bash
git add app/gmail_classify.py tests/test_gmail_classify.py requirements.txt
git commit -m "feat: add rule-based email classification and company matching"
```

---

### Task 8: Gmail poller

**Files:**
- Create: `app/gmail_poller.py`
- Test: `tests/test_gmail_poller.py`

**Interfaces:**
- Consumes: `classify_email`, `match_company` (Task 7).
- Produces: `poll_gmail(conn, client, query: str = DEFAULT_QUERY) -> dict` returning `{"seen": int, "processed": int, "matched": int}`. `client` is any object with `list_messages(query: str) -> list[{"id": str}]` and `get_message(message_id: str) -> {"sender": str, "subject": str, "received_at": datetime}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_gmail_poller.py
from datetime import datetime, timezone

from app.gmail_poller import poll_gmail


class FakeGmailClient:
    def __init__(self, messages):
        self._messages = messages  # dict: id -> {"sender", "subject", "received_at"}

    def list_messages(self, query):
        return [{"id": mid} for mid in self._messages]

    def get_message(self, message_id):
        return self._messages[message_id]


def make_email(sender, subject, received_at=None):
    return {
        "sender": sender,
        "subject": subject,
        "received_at": received_at or datetime(2026, 7, 1, tzinfo=timezone.utc),
    }


def test_poll_creates_match_for_actionable_email(client, make_app):
    make_app(company="Stripe")
    fake = FakeGmailClient(
        {"msg-1": make_email('"Stripe via Greenhouse" <no-reply@greenhouse.io>', "Let's schedule your interview")}
    )

    from app.db import pool

    with pool.connection() as conn:
        stats = poll_gmail(conn, fake, query="irrelevant")

    assert stats == {"seen": 1, "processed": 1, "matched": 1}

    matches = client.get("/matches").json()
    assert len(matches) == 1
    assert matches[0]["suggested_stage"] == "interview"
    assert matches[0]["status"] == "pending"


def test_poll_is_idempotent(client, make_app):
    make_app(company="Stripe")
    fake = FakeGmailClient(
        {"msg-1": make_email('"Stripe via Greenhouse" <no-reply@greenhouse.io>', "Let's schedule your interview")}
    )

    from app.db import pool

    with pool.connection() as conn:
        poll_gmail(conn, fake, query="irrelevant")
        second = poll_gmail(conn, fake, query="irrelevant")

    assert second == {"seen": 1, "processed": 0, "matched": 0}
    assert len(client.get("/matches").json()) == 1


def test_poll_skips_confirmation_and_unclassified(client, make_app):
    make_app(company="Stripe")
    fake = FakeGmailClient(
        {
            "msg-1": make_email("no-reply@stripe.com", "Thank you for applying"),
            "msg-2": make_email("friend@gmail.com", "lunch?"),
        }
    )

    from app.db import pool

    with pool.connection() as conn:
        stats = poll_gmail(conn, fake, query="irrelevant")

    assert stats == {"seen": 2, "processed": 2, "matched": 0}
    assert client.get("/matches").json() == []


def test_poll_leaves_application_null_when_no_company_matches(client):
    fake = FakeGmailClient(
        {"msg-1": make_email("no-reply@totallyunknown.io", "Unfortunately, we have decided not to proceed")}
    )

    from app.db import pool

    with pool.connection() as conn:
        poll_gmail(conn, fake, query="irrelevant")

    matches = client.get("/matches").json()
    assert len(matches) == 1
    assert matches[0]["application_id"] is None
    assert matches[0]["suggested_stage"] == "rejected"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_gmail_poller.py -v`
Expected: FAIL (`ModuleNotFoundError` for `app.gmail_poller`, then 404s for `/matches` until Task 9 lands — that's expected; this task's own assertions about `poll_gmail`'s return value and DB rows are what matter here. Re-run after Task 9 to see the `/matches` assertions pass too.)

- [ ] **Step 3: Write the implementation**

```python
# app/gmail_poller.py
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
```

- [ ] **Step 4: Run tests to verify they pass** (after Task 9 registers `/matches` — see note in Step 2)

Run: `./venv/bin/python -m pytest tests/test_gmail_poller.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add app/gmail_poller.py tests/test_gmail_poller.py
git commit -m "feat: add idempotent Gmail poller with injectable client"
```

---

### Task 9: Review-queue endpoints

**Files:**
- Create: `app/matches.py`
- Modify: `app/main.py`, `app/schemas.py`
- Test: `tests/test_matches.py`

**Interfaces:**
- Consumes: `insert_stage_event` (Task 2).
- Produces: `GET /matches?status=pending|confirmed|dismissed`, `POST /matches/{id}/confirm` (body: `{"application_id": int | null}`), `POST /matches/{id}/dismiss`.

Add to `app/schemas.py`:

```python
class EmailMatchResponse(BaseModel):
    id: int
    gmail_message_id: str
    application_id: Optional[int] = None
    suggested_stage: Stage
    status: str
    created_at: datetime
    sender: str
    subject: str
    received_at: datetime


class MatchConfirm(BaseModel):
    application_id: Optional[int] = None
```

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_matches.py
import psycopg

TEST_DATABASE_URL = "postgresql://localhost/jobtracker_test"


def seed_match(application_id=None, suggested_stage="interview", status="pending"):
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        conn.execute(
            """INSERT INTO processed_emails
                   (gmail_message_id, received_at, sender, subject, classification)
               VALUES ('msg-1', now(), 'no-reply@greenhouse.io', 'Interview time', 'interview')"""
        )
        row = conn.execute(
            """INSERT INTO email_matches (gmail_message_id, application_id, suggested_stage, status)
               VALUES ('msg-1', %s, %s, %s) RETURNING id""",
            (application_id, suggested_stage, status),
        ).fetchone()
        conn.commit()
        return row[0]


def test_list_pending_matches(client, make_app):
    app = make_app(company="Stripe")
    match_id = seed_match(application_id=app["id"])

    response = client.get("/matches")
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == match_id
    assert body[0]["sender"] == "no-reply@greenhouse.io"


def test_confirm_creates_stage_event(client, make_app):
    app = make_app(company="Stripe")
    match_id = seed_match(application_id=app["id"], suggested_stage="interview")

    response = client.post(f"/matches/{match_id}/confirm", json={})
    assert response.status_code == 200
    assert response.json()["status"] == "confirmed"

    listing = client.get("/applications").json()
    updated = next(a for a in listing if a["id"] == app["id"])
    assert updated["current_stage"] == "interview"


def test_confirm_with_null_application_requires_override(client):
    match_id = seed_match(application_id=None, suggested_stage="rejected")

    response = client.post(f"/matches/{match_id}/confirm", json={})
    assert response.status_code == 422


def test_confirm_with_override_application_id(client, make_app):
    app = make_app(company="Ramp")
    match_id = seed_match(application_id=None, suggested_stage="rejected")

    response = client.post(f"/matches/{match_id}/confirm", json={"application_id": app["id"]})
    assert response.status_code == 200

    listing = client.get("/applications").json()
    updated = next(a for a in listing if a["id"] == app["id"])
    assert updated["current_stage"] == "rejected"


def test_dismiss_match(client):
    match_id = seed_match(application_id=None, suggested_stage="rejected")

    response = client.post(f"/matches/{match_id}/dismiss")
    assert response.status_code == 200
    assert response.json()["status"] == "dismissed"

    assert client.get("/matches").json() == []


def test_confirm_unknown_match_404(client):
    response = client.post("/matches/9999/confirm", json={})
    assert response.status_code == 404


def test_confirm_already_resolved_409(client):
    match_id = seed_match(application_id=None, suggested_stage="rejected", status="dismissed")

    response = client.post(f"/matches/{match_id}/confirm", json={"application_id": 1})
    assert response.status_code == 409
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `./venv/bin/python -m pytest tests/test_matches.py -v`
Expected: FAIL (404s — no routes registered yet)

- [ ] **Step 3: Write the implementation**

```python
# app/matches.py
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
```

Register in `app/main.py` — add the import:

```python
from app.matches import router as matches_router
```

and after `app.include_router(questions_router)`:

```python
app.include_router(matches_router)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `./venv/bin/python -m pytest tests/test_matches.py tests/test_gmail_poller.py -v`
Expected: all pass (this also completes the Task 8 tests that depend on `/matches`)

- [ ] **Step 5: Commit**

```bash
git add app/matches.py app/main.py app/schemas.py tests/test_matches.py
git commit -m "feat: add human-confirmed email review queue endpoints"
```

---

### Task 10: Real Gmail API client adapter

**Files:**
- Create: `app/gmail_client.py`
- Test: `tests/test_gmail_client.py`

**Interfaces:**
- Produces: `build_gmail_service()`, `RealGmailClient` implementing the same `list_messages`/`get_message` interface `poll_gmail` expects.

- [ ] **Step 1: Install Gmail API dependencies**

```bash
./venv/bin/pip install google-api-python-client google-auth-oauthlib google-auth-httplib2
./venv/bin/pip freeze | grep -iE "google|httplib2"
```

- [ ] **Step 2: Write the implementation**

```python
# app/gmail_client.py
import os
from datetime import datetime, timezone

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def build_gmail_service():
    creds = Credentials(
        token=None,
        refresh_token=os.environ["GMAIL_REFRESH_TOKEN"],
        client_id=os.environ["GMAIL_CLIENT_ID"],
        client_secret=os.environ["GMAIL_CLIENT_SECRET"],
        token_uri="https://oauth2.googleapis.com/token",
        scopes=SCOPES,
    )
    return build("gmail", "v1", credentials=creds)


class RealGmailClient:
    def __init__(self, service):
        self.service = service

    def list_messages(self, query: str) -> list[dict]:
        results = []
        req = self.service.users().messages().list(userId="me", q=query)
        while req is not None:
            resp = req.execute()
            results.extend(resp.get("messages", []))
            req = self.service.users().messages().list_next(req, resp)
        return results

    def get_message(self, message_id: str) -> dict:
        msg = (
            self.service.users()
            .messages()
            .get(
                userId="me",
                id=message_id,
                format="metadata",
                metadataHeaders=["From", "Subject"],
            )
            .execute()
        )
        headers = {h["name"]: h["value"] for h in msg["payload"]["headers"]}
        return {
            "sender": headers.get("From", ""),
            "subject": headers.get("Subject", ""),
            "received_at": datetime.fromtimestamp(
                int(msg["internalDate"]) / 1000, tz=timezone.utc
            ),
        }
```

- [ ] **Step 3: Write a construction-only smoke test**

This cannot exercise `list_messages`/`get_message` without real Gmail credentials and network access — that's expected and fine; those two methods are integration-only and get their logic coverage from `poll_gmail`'s tests against `FakeGmailClient` (Task 8). This test only confirms the module imports and builds a service object without error.

```python
# tests/test_gmail_client.py
import pytest


def test_build_gmail_service_constructs_without_network(monkeypatch):
    monkeypatch.setenv("GMAIL_CLIENT_ID", "fake-client-id")
    monkeypatch.setenv("GMAIL_CLIENT_SECRET", "fake-client-secret")
    monkeypatch.setenv("GMAIL_REFRESH_TOKEN", "fake-refresh-token")

    from app.gmail_client import build_gmail_service

    try:
        service = build_gmail_service()
    except Exception as exc:
        pytest.skip(f"gmail discovery requires network in this environment: {exc}")

    assert hasattr(service, "users")
```

- [ ] **Step 4: Run test**

Run: `./venv/bin/python -m pytest tests/test_gmail_client.py -v`
Expected: PASS, or SKIP with a network-related reason (either is acceptable — this file's only job is to catch import/signature errors, not to validate real Gmail connectivity)

- [ ] **Step 5: Commit**

```bash
git add app/gmail_client.py tests/test_gmail_client.py requirements.txt
git commit -m "feat: add real Gmail API client adapter"
```

---

### Task 11: One-time OAuth script and cron entrypoint (manual setup, documented)

**Files:**
- Create: `scripts/gmail_auth.py`, `scripts/poll_gmail.py`
- Modify: `README.md`

**Interfaces:**
- Produces: two CLI scripts. Neither is unit-tested — `gmail_auth.py` opens a real browser for the user's own Google login (cannot run non-interactively), and `poll_gmail.py` requires the credentials that script produces.

- [ ] **Step 1: Write the one-time auth script**

```python
# scripts/gmail_auth.py
"""One-time interactive Gmail OAuth flow — run this yourself, once, locally:

    GMAIL_CLIENT_ID=... GMAIL_CLIENT_SECRET=... python scripts/gmail_auth.py

It opens a browser for you to sign in and grant read-only Gmail access, then
prints a refresh token. Save that as the GMAIL_REFRESH_TOKEN environment
variable wherever the API runs — never commit it to the repo.

GMAIL_CLIENT_ID / GMAIL_CLIENT_SECRET come from Google Cloud Console:
APIs & Services > Credentials > Create Credentials > OAuth client ID > Desktop app.
"""

import os

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def main():
    client_config = {
        "installed": {
            "client_id": os.environ["GMAIL_CLIENT_ID"],
            "client_secret": os.environ["GMAIL_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    creds = flow.run_local_server(port=0)
    print("\nSave this as the GMAIL_REFRESH_TOKEN environment variable:\n")
    print(creds.refresh_token)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Write the poller cron entrypoint**

```python
# scripts/poll_gmail.py
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
```

- [ ] **Step 3: Document the manual setup in README.md**

Add a new section after the "Frontend" section:

```markdown
## Gmail ingestion (Tier 2)

Polls Gmail for ATS emails (Greenhouse/Lever/Workday sender patterns), classifies
them with plain keyword rules (no ML), and queues actionable ones — rejections and
interview requests — for you to confirm before anything touches `stage_events`.
Nothing is ever written automatically.

**One-time setup (you have to do this part — it's an interactive OAuth consent):**

1. Create a project at [console.cloud.google.com](https://console.cloud.google.com), enable the Gmail API.
2. APIs & Services > OAuth consent screen: choose "External," add yourself as a test user. No verification needed for personal use.
3. APIs & Services > Credentials > Create Credentials > OAuth client ID > **Desktop app**. Note the client ID and secret.
4. Run the one-time auth script locally:
   ```bash
   GMAIL_CLIENT_ID=<your-client-id> GMAIL_CLIENT_SECRET=<your-client-secret> \
       ./venv/bin/python scripts/gmail_auth.py
   ```
   A browser opens; sign in and grant read-only Gmail access. The script prints a refresh token.
5. Set all three as environment variables wherever the API and poller run: `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`. Never commit them.

**Running the poller:** `./venv/bin/python scripts/poll_gmail.py`, on a schedule (cron, Render cron, APScheduler) every 2-6 hours.

**Review queue:** `GET /matches` lists pending matches; `POST /matches/{id}/confirm` (optionally `{"application_id": N}` to link an unmatched email) logs the real stage event; `POST /matches/{id}/dismiss` discards it.

## Discord notifications (Tier 2)

Set `DISCORD_WEBHOOK_URL` (a Discord channel's webhook URL) to get a message on every stage change — manual or confirmed-from-email. Unset by default; a Discord outage never fails the underlying request.

## Spaced repetition (Tier 2)

`POST /questions` to add an interview-prep question, `GET /questions/due` for today's queue, `POST /questions/{id}/review` with `{"quality": 0-5}` to grade yourself — standard SM-2, exactly as in `app/sm2.py`.
```

- [ ] **Step 4: Commit**

```bash
git add scripts/gmail_auth.py scripts/poll_gmail.py README.md
git commit -m "docs: document manual Gmail OAuth setup; add poller cron entrypoint"
```

---

### Task 12: Final requirements pin and full verification

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Pin exact installed versions**

```bash
./venv/bin/pip freeze | grep -iE "rapidfuzz|google-api-python-client|google-auth-oauthlib|google-auth-httplib2|google-auth\b|httplib2|uritemplate|cachetools|pyasn1-modules|rsa"
```

Add each to `requirements.txt` at the versions printed (append below the existing entries, don't reorder existing ones).

- [ ] **Step 2: Run the full backend suite**

Run: `./venv/bin/python -m pytest -v`
Expected: all tests pass (Tier 0/1 tests unaffected, all new Tier 2 tests green)

- [ ] **Step 3: Manual smoke test against the dev DB**

```bash
./venv/bin/uvicorn app.main:app --port 8000 &
sleep 2
curl -s -X POST http://127.0.0.1:8000/questions -H 'content-type: application/json' \
    -d '{"prompt": "Why DISTINCT ON instead of a self-join?"}'
curl -s http://127.0.0.1:8000/questions/due
curl -s http://127.0.0.1:8000/matches
kill %1
```
Expected: 201 with `due_date` today, the due list includes it, `/matches` returns `[]` (no emails polled against dev DB).

- [ ] **Step 4: Commit**

```bash
git add requirements.txt
git commit -m "chore: pin Tier 2 dependency versions"
```
