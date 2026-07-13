# Postgres Event-Log Rebuild Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the SQLAlchemy/SQLite/JWT backend with the build plan's design: raw psycopg on Postgres, append-only `stage_events`, Tier 0 endpoints + Tier 1 analytics, tested and documented.

**Architecture:** Status is derived, never stored — an append-only `stage_events` table is the source of truth; "current status" is the latest event per application (`DISTINCT ON` + covering index). Raw parameterized SQL via psycopg v3 with a connection pool; numbered plain-SQL migrations applied by a tiny runner. No users table, no auth (per build plan §4.4).

**Tech Stack:** FastAPI, psycopg 3 + psycopg_pool, PostgreSQL 18 (Postgres.app), pytest + httpx TestClient.

## Global Constraints

- **No SQLAlchemy, no ORM** — every query is raw parameterized SQL (build plan: "use raw SQL via psycopg (v3)").
- **No auth, no users table** (build plan: "Auth/multi-user. Never.").
- **Stages (exact):** `applied, oa, phone_screen, interview, final_round, offer, rejected, withdrawn` — CHECK constraint, not ENUM type.
- **Sources (exact):** `cold_apply, referral, career_fair, recruiter, other`, default `cold_apply`.
- **No `ghosted` stage** — ghosting is absence of events.
- **Migrations:** numbered plain SQL files under `db/migrations/`, applied by `db/migrate.py`. No Alembic.
- Dev DB: `postgresql://localhost/jobtracker`; test DB: `postgresql://localhost/jobtracker_test` (both exist, server running via Postgres.app binaries).
- Python: `./venv/bin/python` (3.13). Run tests as `./venv/bin/python -m pytest`.
- Frontend directory `frontend/` is out of scope — leave untouched.

---

### Task 1: Remove legacy code

**Files:**
- Delete: `app/auth.py`, `app/models.py`, `app/database.py`, `ApplicationCreate.py`, `ApplicationResponse.py`, `create_tables.py`, `data_mode.txt`, `applications.db`, `test.db`, old `tests/test_applications.py`, old `tests/conftest.py`
- Empty out (rewritten in later tasks): `app/main.py`, `app/schemas.py`

- [x] **Step 1:** `git rm` tracked legacy files; `rm` untracked db files. Commit: `refactor: remove ORM/auth backend ahead of event-log rebuild`

### Task 2: Migrations

**Files:**
- Create: `db/migrations/001_init.sql` — exact schema from build plan §1 (companies, applications, stage_events, index)
- Create: `db/migrate.py`

**Interfaces:**
- Produces: `python db/migrate.py [--database-url URL]` (default `$DATABASE_URL`, then `postgresql://localhost/jobtracker`). Tracks applied files in `schema_migrations(filename TEXT PRIMARY KEY, applied_at TIMESTAMPTZ)`. Each migration runs in one transaction; already-applied files are skipped.

`001_init.sql`:

```sql
CREATE TABLE companies (
    id          SERIAL PRIMARY KEY,
    name        TEXT NOT NULL UNIQUE,
    website     TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE applications (
    id          SERIAL PRIMARY KEY,
    company_id  INTEGER NOT NULL REFERENCES companies(id),
    role_title  TEXT NOT NULL,
    source      TEXT NOT NULL DEFAULT 'cold_apply'
                CHECK (source IN ('cold_apply','referral','career_fair','recruiter','other')),
    job_url     TEXT,
    notes       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE stage_events (
    id             SERIAL PRIMARY KEY,
    application_id INTEGER NOT NULL REFERENCES applications(id) ON DELETE CASCADE,
    stage          TEXT NOT NULL
                   CHECK (stage IN ('applied','oa','phone_screen','interview',
                                    'final_round','offer','rejected','withdrawn')),
    occurred_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    notes          TEXT
);

CREATE INDEX idx_stage_events_app_time
    ON stage_events (application_id, occurred_at DESC);
```

- [x] **Step 1:** Write both files.
- [x] **Step 2:** Run against `jobtracker` and `jobtracker_test`; verify `\dt` shows 4 tables (3 + schema_migrations); re-run is a no-op.
- [x] **Step 3:** Commit: `feat: add Postgres schema migrations and runner`

### Task 3: App skeleton (db pool, schemas, lifespan)

**Files:**
- Create: `app/db.py`
- Rewrite: `app/schemas.py`, `app/main.py`

**Interfaces (produced):**
- `app.db.pool: ConnectionPool` created from `DATABASE_URL` env (default `postgresql://localhost/jobtracker`), opened/closed in FastAPI lifespan (`open=False` at import so tests can point elsewhere before startup).
- `app.db.get_conn()` — FastAPI dependency yielding a pooled connection with `row_factory=dict_row`; commits on success, rolls back on exception.
- `app/schemas.py`: `Stage(str, Enum)` (8 values), `Source(str, Enum)` (5 values); `ApplicationCreate {company_name, company_website?, role_title, source=cold_apply, job_url?, notes?, applied_at?: datetime}`; `ApplicationResponse {id, company_id, company_name, role_title, source, job_url, notes, created_at, current_stage: Stage|None, current_stage_at: datetime|None}`; `CompanyCreate {name, website?}` / `CompanyResponse {id, name, website, created_at}`; `StageEventCreate {stage: Stage, occurred_at?: datetime, notes?}` / `StageEventResponse {id, application_id, stage, occurred_at, notes}`; stats rows: `StageCount {stage, count}`, `FunnelStage {stage, reached, still_pending, conversion_to_next: float|None}`, `StageTransition {from_stage, to_stage, transitions, avg_days: float}`, `SourceStats {source, total, responded, response_rate: float}`.
- `app/main.py`: FastAPI app with lifespan opening/closing the pool; routers from Tasks 5–8 registered here.

- [x] **Step 1:** Write files; verify `TestClient(app)` context-manager startup works against dev DB.
- [x] **Step 2:** Commit: `feat: psycopg pool, lifespan, and API schemas`

### Task 4: Test harness

**Files:**
- Create: `tests/conftest.py`

Behavior: set `DATABASE_URL=postgresql://localhost/jobtracker_test` **before** importing `app.main`; session fixture drops/recreates `public` schema and runs `db/migrate.py` machinery against the test DB; function-scoped `client` fixture truncates `companies, applications, stage_events RESTART IDENTITY CASCADE` then yields `TestClient(app)` (context-managed). Helper fixture `make_app(client, company="Acme", role="SWE", source="cold_apply", applied_at=None)` returning the created application dict.

- [x] **Step 1:** Write conftest; `pytest` collects 0 tests, no errors.
- [x] **Step 2:** Commit with Task 5 (harness has no observable behavior alone).

### Task 5: POST /companies and POST /applications (TDD)

**Files:**
- Create: `app/applications.py` (router: companies + applications endpoints)
- Test: `tests/test_applications.py`

**Interfaces (produced):**
- `POST /companies` → 201 `CompanyResponse`. Get-or-create: `INSERT ... ON CONFLICT (name) DO UPDATE SET name = EXCLUDED.name RETURNING *` (DO UPDATE so RETURNING yields the existing row).
- `POST /applications` → 201 `ApplicationResponse`. Get-or-create company by `company_name`, insert application, insert initial `applied` stage event at `applied_at` (or now). All in one transaction.
- `DELETE /applications/{id}` → 204; 404 if missing; cascade removes events.

Tests (exact):
- `test_create_application` — 201; response has `company_name == "Acme"`, `current_stage == "applied"`, `source` default `cold_apply`.
- `test_company_get_or_create` — two applications with the same `company_name` share `company_id`; `POST /companies` twice with same name returns same `id`.
- `test_create_application_invalid_source` — 422.
- `test_applied_at_override` — passing `applied_at: "2026-07-01T09:00:00Z"` makes `current_stage_at` equal it.
- `test_delete_application` — 204 then GET list no longer contains it; deleting again → 404.

- [x] **Steps:** failing tests → run (fail: 404/import error) → implement → run (pass) → commit `feat: Tier 0 create endpoints with company get-or-create`

### Task 6: POST /applications/{id}/events (TDD)

**Files:**
- Modify: `app/applications.py`
- Test: `tests/test_events.py`

**Interfaces (produced):**
- `POST /applications/{id}/events?backfill=false` → 201 `StageEventResponse`. 404 unknown application. If `occurred_at` earlier than the application's latest event and `backfill` is false → 409 with detail naming the latest timestamp. Stage validated by Pydantic enum (422 on garbage).

Latest-event guard SQL: `SELECT MAX(occurred_at) AS latest FROM stage_events WHERE application_id = %s`.

Tests: advance to `oa` → 201 and list shows `current_stage == "oa"`; unknown app → 404; bad stage → 422; earlier `occurred_at` without backfill → 409; same with `backfill=true` → 201.

- [x] **Steps:** failing tests → implement → pass → commit `feat: stage event logging with backfill guard`

### Task 7: GET /applications + GET /stats/by-stage (TDD)

**Files:**
- Modify: `app/applications.py` (list endpoint)
- Create: `app/stats.py` (stats router)
- Test: extend `tests/test_applications.py`, create `tests/test_stats.py`

**Interfaces (produced):** `GET /applications` → `list[ApplicationResponse]` newest-first; `GET /stats/by-stage` → `list[StageCount]` in pipeline order.

Core query (build plan's `DISTINCT ON`, tie-broken by `id`):

```sql
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
ORDER BY a.created_at DESC, a.id DESC;
```

By-stage:

```sql
WITH current_status AS (
    SELECT DISTINCT ON (application_id) application_id, stage
    FROM stage_events
    ORDER BY application_id, occurred_at DESC, id DESC
)
SELECT stage, COUNT(*) AS count
FROM current_status
GROUP BY stage
ORDER BY array_position(
    ARRAY['applied','oa','phone_screen','interview','final_round','offer','rejected','withdrawn'],
    stage);
```

Tests: three apps advanced to different stages → list shows correct `current_stage` per app; by-stage returns exact counts; empty DB → empty lists.

- [x] **Steps:** failing tests → implement → pass → commit `feat: current-status listing and by-stage stats`

### Task 8: Tier 1 analytics (TDD)

**Files:**
- Modify: `app/stats.py`
- Test: extend `tests/test_stats.py`

**Documented funnel choices (also go in README):**
- Pipeline order: `applied → oa → phone_screen → interview → final_round → offer`; `rejected`/`withdrawn` are terminal, outside the pipeline.
- **Skipped stages count as passed through**: reaching `interview` with no `oa` event counts as having reached `oa` (reached = max pipeline rank ≥ stage rank).
- **In-flight apps excluded from conversion denominators**: an app whose *current* stage is exactly pipeline stage s (not terminal, not advanced) hasn't answered "did it convert?" yet. `conversion_to_next(s) = reached(s+1) / (reached(s) − still_pending(s))`, `None` when the denominator is 0.

Funnel SQL:

```sql
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
       COUNT(*) FILTER (WHERE ap.max_rank >= p.rank) AS reached,
       COUNT(*) FILTER (WHERE ap.max_rank = p.rank AND cs.stage = p.stage) AS still_pending
FROM pipeline p
CROSS JOIN app_progress ap
JOIN current_status cs USING (application_id)
GROUP BY p.stage, p.rank
ORDER BY p.rank;
```

Conversion arithmetic in Python from `reached`/`still_pending`.

Time-in-stage (`LAG`, per build plan):

```sql
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
       AVG(EXTRACT(EPOCH FROM (occurred_at - prev_at)) / 86400.0)::float AS avg_days
FROM transitions
WHERE prev_stage IS NOT NULL
GROUP BY prev_stage, stage
ORDER BY from_stage, to_stage;
```

By-source ("responded" = any event beyond `applied`, including `rejected`):

```sql
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
ORDER BY response_rate DESC, a.source;
```

Tests — hand-verified fixture: 6 apps: A applied only (cold_apply); B applied→rejected (referral); C applied→oa→interview (cold_apply, skipped phone_screen); D applied→oa→rejected (referral); E applied→interview→offer (recruiter, skipped oa+phone_screen); F applied→oa (cold_apply, pending at oa).
Expected funnel: applied reached=6 pending=1; oa reached=4 pending=1; phone_screen reached=2 pending=0; interview reached=2 pending=1; final_round reached=1 pending=0; offer reached=1 pending=0. Conversions: applied→oa 4/(6−1)=0.8; oa→phone_screen 2/(4−1)≈0.667; phone_screen→interview 2/2=1.0; interview→final_round 1/(2−1)=1.0; final_round→offer 1/1=1.0; offer None.
Time-in-stage: apps with controlled `occurred_at` gaps (e.g. applied→oa at 2 and 4 days for two apps → avg 3.0 days).
By-source: cold_apply total=3 responded=2 rate≈0.667; referral 2/2=1.0; recruiter 1/1=1.0.

- [x] **Steps:** failing tests (exact numbers above) → implement → pass → commit `feat: Tier 1 funnel, time-in-stage, and source analytics`

### Task 9: README, requirements, verification

**Files:**
- Create: `README.md` — schema + why append-only (build plan requirement), setup/run/test instructions, migration how-to, documented funnel choices, endpoint list.
- Rewrite: `requirements.txt` — fastapi, uvicorn, psycopg[binary], psycopg-pool, pydantic, pytest, httpx (pinned to installed versions). Drop SQLAlchemy/jose/passlib/bcrypt.
- Modify: `.gitignore` — drop the now-deleted sqlite entries.

- [x] **Step 1:** Full `pytest -v` green; boot server against dev DB and exercise POST/GET/stats over HTTP once (verify skill).
- [x] **Step 2:** Commit: `docs: README with schema rationale; trim requirements`
