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

**One-time setup — IMAP with an App Password, no Google Cloud project, no OAuth, no billing account anywhere near it:**

1. Turn on 2-Step Verification on your Google account, if it isn't already: [myaccount.google.com/security](https://myaccount.google.com/security)
2. Generate an App Password: [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) — app "Mail", generate, copy the 16-character password.
3. Set two environment variables wherever the poller runs: `GMAIL_ADDRESS` (your Gmail address) and `GMAIL_APP_PASSWORD` (the password from step 2). Never commit them.

**Running the poller automatically — free, via GitHub Actions:** `.github/workflows/poll-gmail.yml` runs it every 4 hours (plus a manual "Run workflow" button on the Actions tab). Add three repo secrets — Settings → Secrets and variables → Actions → New repository secret:

| Secret | Value |
|---|---|
| `DATABASE_URL` | your Neon connection string |
| `GMAIL_ADDRESS` | your Gmail address |
| `GMAIL_APP_PASSWORD` | the App Password from step 2 above |

That's it — no server of your own needs to stay running for polling to happen. You can also run it manually any time: `./venv/bin/python scripts/poll_gmail.py`.

**Review queue:** in the dashboard, the **Review Queue** tab lists pending matches, lets you confirm (linking to an application first if the sender didn't auto-match) or dismiss each one. Same thing via the API directly: `GET /matches`, `POST /matches/{id}/confirm` (optionally `{"application_id": N}`), `POST /matches/{id}/dismiss`.

## Spaced repetition (Tier 2)

`POST /questions` to add an interview-prep question, `GET /questions/due` for today's queue, `POST /questions/{id}/review` with `{"quality": 0-5}` to grade yourself — standard SM-2, exactly as in `app/sm2.py`.

## Migrations

Numbered plain SQL files in `db/migrations/` (`001_init.sql`, `002_...sql`), applied in order by `db/migrate.py`, which records each file in `schema_migrations` and skips ones already applied. Add a migration by dropping the next-numbered file in the directory and re-running the script. No Alembic — deliberately.

## Tests

```bash
./venv/bin/python -m pytest -v
```

Runs against `jobtracker_test` (schema rebuilt per session, tables truncated per test). The funnel/time-in-stage tests assert exact numbers from a hand-verified six-application fixture — see `tests/test_stats.py`.

## Deploying (Render + Neon, both free)

Two Render services from this one repo — a Python web service for the API, a static site for the frontend — plus a Neon Postgres database. No credit card required for either.

**1. Neon (database):**
1. Sign up at [neon.tech](https://neon.tech), create a project.
2. Copy the connection string it gives you (starts `postgresql://...`, includes `?sslmode=require`).
3. Run migrations against it once, from your machine: `DATABASE_URL="<neon-connection-string>" ./venv/bin/python db/migrate.py`.

**2. Render — API (web service):**
1. Sign up at [render.com](https://render.com), connect your GitHub account, select this repo.
2. New > Web Service. Root directory: leave as repo root.
3. Build command: `pip install -r requirements.txt`
4. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Environment variables: `DATABASE_URL` (the Neon string from step 1). Optional: `GMAIL_ADDRESS`, `GMAIL_APP_PASSWORD`, `FRONTEND_ORIGIN` (see step 3).
6. Deploy. Render gives you a URL like `https://job-tracker-api-xxxx.onrender.com` — copy it.

**3. Render — frontend (static site):**
1. New > Static Site, same repo.
2. Root directory: `frontend`
3. Build command: `npm install && npm run build`
4. Publish directory: `dist`
5. Environment variable: `VITE_API_URL` set to the API URL from step 2 (no trailing slash) — Vite bakes this into the build, so set it *before* the first deploy.
6. Deploy. You'll get a second URL, e.g. `https://job-tracker-xxxx.onrender.com` — that's the site you actually visit.
7. Optional but recommended: go back to the API service's env vars and set `FRONTEND_ORIGIN` to this frontend URL, then redeploy the API — this locks CORS down to just your frontend instead of allowing any origin.

**Free-tier note:** Render's free web service sleeps after 15 minutes idle; the first request after that takes ~30 seconds to wake up. Fine for a personal tracker, not for a demo you're timing.
