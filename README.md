# Job Application Tracker

FastAPI + Postgres, tracking job applications as an append-only event log. Status isn't stored anywhere. It's derived from history. Raw SQL through psycopg 3, no ORM.

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

### Why stage_events is append-only

An application's status shouldn't be something you update. It should be something you derive. There's no `status` column, so nothing can drift out of sync. Whatever the latest event says, that's the current state (`DISTINCT ON (application_id) ... ORDER BY occurred_at DESC`, cheap thanks to the index above). You also get the full timeline for free, which is exactly what the funnel and time-in-stage stats run on.

The tradeoff is that every status read means querying events instead of reading a column. That's fine at this scale. If it ever wasn't, a materialized `current_stage` would be easy to add later. There's also no `ghosted` stage, on purpose. Ghosting is just silence, not something that actually happened, so it gets derived in queries instead of faked as an event.

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

### How the funnel numbers work

Pipeline order is `applied → oa → phone_screen → interview → final_round → offer`. `rejected` and `withdrawn` sit outside that, as dead ends rather than pipeline stages.

Skipped stages still count as reached. An interview with no OA event still counts as having passed OA. Reached just means your furthest stage is at or past this one. Some companies skip stages in their process. That's not missing data, it's just their pipeline.

Apps still sitting at a stage don't count against its conversion rate. If you're still waiting to hear back after an OA, you haven't failed to convert, you just haven't converted yet. So `conversion(s → s+1) = reached(s+1) / (reached(s) − still_pending(s))`.

For by-source stats, "responded" means anything beyond the initial `applied` event. A rejection counts as a response. Silence is the only thing that doesn't.

## Running it locally

Needs PostgreSQL (Postgres.app on this machine) with `jobtracker` and `jobtracker_test` databases.

```bash
# start Postgres if it isn't running (or just open Postgres.app)
/Applications/Postgres.app/Contents/Versions/latest/bin/pg_ctl \
    -D "$HOME/Library/Application Support/Postgres/var-18" start

python -m venv venv && ./venv/bin/pip install -r requirements.txt
./venv/bin/python db/migrate.py                # apply migrations (dev DB)
./venv/bin/uvicorn app.main:app --reload       # http://127.0.0.1:8000/docs
```

One env var to configure: `DATABASE_URL` (defaults to `postgresql://localhost/jobtracker`).

### Frontend

Vite + React dashboard in `frontend/`. An applications table (filters, search, add/delete, stage-event logging with backfill support), an analytics page (funnel, time-in-stage, response-by-source, current-stage-mix, each chart with an accessible table fallback), and a review queue for Gmail matches. No routing library, just a `location.hash` listener switching views.

```bash
cd frontend
npm install
npm run dev   # http://localhost:5173, proxies /applications, /companies, /stats, /matches, /questions to :8000
```

Run the API alongside it (`uvicorn app.main:app --reload`). The dev server proxies API paths to `http://127.0.0.1:8000`, see `frontend/vite.config.js`.

## Gmail ingestion

Polls Gmail for ATS emails (Greenhouse/Lever/Workday sender patterns), classifies them with plain keyword rules, no ML, and queues the actionable ones (rejections, interview requests) for you to confirm before anything touches `stage_events`. Nothing gets written automatically, ever.

**One-time setup.** This uses IMAP with an App Password, so there's no Google Cloud project, no OAuth screen, no billing account involved anywhere:

1. Turn on 2-Step Verification if you haven't already: [myaccount.google.com/security](https://myaccount.google.com/security)
2. Generate an App Password: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords). Pick "Mail", generate, copy the 16-character password.
3. Set two env vars wherever the poller runs: `GMAIL_ADDRESS` (your Gmail address) and `GMAIL_APP_PASSWORD` (from step 2). Don't commit them anywhere.

**Running the poller automatically, for free, via GitHub Actions.** `.github/workflows/poll-gmail.yml` runs it every 4 hours, plus you can trigger it manually from the Actions tab. Add these as repo secrets (Settings, Secrets and variables, Actions, New repository secret):

| Secret | Value |
|---|---|
| `DATABASE_URL` | your Neon connection string |
| `GMAIL_ADDRESS` | your Gmail address |
| `GMAIL_APP_PASSWORD` | the App Password from step 2 |

No server of your own has to stay running for this to work. You can also just run it manually whenever: `./venv/bin/python scripts/poll_gmail.py`.

**Review queue.** The dashboard has a Review Queue tab listing pending matches. Confirm one (linking it to an application first if it didn't auto-match) or dismiss it. Same thing works directly through the API: `GET /matches`, `POST /matches/{id}/confirm` (optionally `{"application_id": N}`), `POST /matches/{id}/dismiss`.

## Spaced repetition

`POST /questions` adds an interview-prep question, `GET /questions/due` gets today's queue, `POST /questions/{id}/review` with `{"quality": 0-5}` grades yourself. Standard SM-2, implemented straight from the spec in `app/sm2.py`.

## Migrations

Numbered plain SQL files in `db/migrations/` (`001_init.sql`, `002_...sql`), applied in order by `db/migrate.py`, which tracks what's already run in a `schema_migrations` table. To add one, drop the next-numbered file in and re-run the script. No Alembic, on purpose.

## Tests

```bash
./venv/bin/python -m pytest -v
```

Runs against `jobtracker_test` (schema rebuilt per session, tables truncated between tests). The funnel and time-in-stage tests check exact numbers against a hand-verified six-application fixture. See `tests/test_stats.py` if you want to see the math worked out.

## Deploying (Render + Neon, both free)

Two Render services off this one repo: a Python web service for the API, a static site for the frontend. Plus a Neon Postgres database. Neither needs a credit card.

**1. Neon (database):**
1. Sign up at [neon.tech](https://neon.tech), create a project.
2. Copy the connection string it gives you (starts `postgresql://...`, ends with `?sslmode=require`).
3. Run migrations against it once, from your machine: `DATABASE_URL="<neon-connection-string>" ./venv/bin/python db/migrate.py`.

**2. Render, API (web service):**
1. Sign up at [render.com](https://render.com), connect your GitHub account, pick this repo.
2. New > Web Service. Root directory: repo root.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Environment variables: `DATABASE_URL` (from step 1). Optional: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `FRONTEND_ORIGIN` (see step 3).
6. Deploy. You'll get a URL like `https://job-tracker-api-xxxx.onrender.com`. Hang onto it.

**3. Render, frontend (static site):**
1. New > Static Site, same repo.
2. Root directory: `frontend`
3. Build command: `npm install && npm run build`
4. Publish directory: `dist`
5. Environment variable: `VITE_API_URL` set to the API URL from step 2, no trailing slash. Vite bakes this in at build time, so it has to be set before the first deploy, not after.
6. Deploy. This second URL is the actual site you visit.
7. Worth doing: go back to the API service, set `FRONTEND_ORIGIN` to this frontend URL, redeploy. Locks CORS down to just your frontend instead of allowing any origin.
