# Job Application Tracker

A FastAPI + PostgreSQL API for tracking job applications as an **append-only event log**. Status is derived, never stored. Raw parameterized SQL via psycopg 3 — no ORM, by design.

## Schema

```
companies                 applications                    stage_events (append-only)
─────────                 ────────────                    ──────────────────────────
id           ◄──────┐     id            ◄──────────┐      id
name UNIQUE         └──── company_id                └──── application_id  (ON DELETE CASCADE)
website                   role_title                      stage        CHECK (8 values)
created_at                source        CHECK (5 values)  occurred_at  (overridable, default now())
                          job_url                         notes
                          notes
                          created_at

INDEX idx_stage_events_app_time ON stage_events (application_id, occurred_at DESC)
```

Stages: `applied, oa, phone_screen, interview, final_round, offer, rejected, withdrawn`.
Sources: `cold_apply, referral, career_fair, recruiter, other`.

### Why `stage_events` is append-only

An application's status is a *derived fact*, not a stored one. There is no `status` column to update, so there are no update anomalies: the history can never disagree with the current state, because the current state **is** the latest history row (`DISTINCT ON (application_id) ... ORDER BY occurred_at DESC`, made cheap by the index above). The full timeline comes for free, which is exactly what the funnel and time-in-stage analytics consume. The cost is that every status read is a query over events — acceptable at this scale, and a materialized `current_stage` cache could be added later *if measurement demanded it*. There is deliberately no `ghosted` stage: ghosting is the absence of events, derived in queries, not an event someone sends you.

## Endpoints

| Method | Path | Notes |
|---|---|---|
| POST | `/companies` | Get-or-create by unique name (`ON CONFLICT`) |
| POST | `/applications` | Get-or-creates the company, logs the initial `applied` event (`applied_at` overridable) |
| GET | `/applications` | Each row joined with its current stage |
| DELETE | `/applications/{id}` | Cascades to its events |
| POST | `/applications/{id}/events` | Rejects `occurred_at` earlier than the latest event (409) unless `?backfill=true` |
| GET | `/stats/by-stage` | Applications currently in each stage |
| GET | `/stats/funnel` | Reached / still-pending / conversion per pipeline stage |
| GET | `/stats/time-in-stage` | Avg days per stage transition (`LAG` window function) |
| GET | `/stats/by-source` | Response rate per application source |

### Funnel methodology (explicit choices)

- Pipeline order: `applied → oa → phone_screen → interview → final_round → offer`. `rejected`/`withdrawn` are terminal and outside the pipeline.
- **Skipped stages count as passed through.** An interview with no OA event still counts as having "reached" OA (reached = max pipeline rank ≥ stage rank). Some companies skip stages; that's their pipeline shape, not missing data.
- **In-flight applications are excluded from conversion denominators.** An app currently sitting at stage *s* hasn't answered "did it convert?" yet: `conversion(s→s+1) = reached(s+1) / (reached(s) − still_pending(s))`. Counting pending apps as failures would understate conversion rates.
- `/stats/by-source`: "responded" = any event beyond the initial `applied`, including a rejection. Silence is the only non-response.

## Running locally

Requires PostgreSQL (Postgres.app on this machine) with databases `jobtracker` and `jobtracker_test`.

```bash
# start Postgres if it isn't running (or just open Postgres.app)
/Applications/Postgres.app/Contents/Versions/latest/bin/pg_ctl \
    -D "$HOME/Library/Application Support/Postgres/var-18" start

python -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python db/migrate.py                # apply migrations (dev DB)
./venv/bin/uvicorn app.main:app --reload       # http://127.0.0.1:8000/docs
```

Configuration is one env var: `DATABASE_URL` (default `postgresql://localhost/jobtracker`).

### Frontend

A Vite + React dashboard in `frontend/` — an applications table (filters, search, add/delete, stage-event logging with backfill support) and an analytics page (funnel, time-in-stage, response-by-source, current-stage-mix charts with an accessible table fallback for each). No routing library — view switching is a plain `location.hash` listener.

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /applications, /companies, /stats to :8000
```

Run the API (`uvicorn app.main:app --reload`) alongside it — the dev server proxies API paths to `http://127.0.0.1:8000` (see `frontend/vite.config.js`).

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

## Migrations

Numbered plain SQL files in `db/migrations/` (`001_init.sql`, `002_...sql`), applied in order by `db/migrate.py`, which records each file in `schema_migrations` and skips ones already applied. Add a migration by dropping the next-numbered file in the directory and re-running the script. No Alembic — deliberately.

## Tests

```bash
./venv/bin/python -m pytest -v
```

Runs against `jobtracker_test` (schema rebuilt per session, tables truncated per test). The funnel/time-in-stage tests assert exact numbers from a hand-verified six-application fixture — see `tests/test_stats.py`.
