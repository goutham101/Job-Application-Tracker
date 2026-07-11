# Job Application Tracker — Build Plan

Target: Tier 0 + Tier 1 demoable by **mid-August 2026**. This deadline matters more than you think — see "Timeline reality check" at the bottom.

---

## 1. Tier 0 Postgres Schema

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

### Justification per decision

| Decision | Why |
|---|---|
| `companies` as its own table | One row per company even with 5 applications to it; lets you later query "response rate per company" without string-matching names. |
| `UNIQUE` on company name | Prevents "Google" and "google " duplicates; forces you to handle the insert-or-get pattern (`ON CONFLICT`), a real SQL skill. |
| `source` on `applications` **now, not Tier 1** | It's one column and costs nothing today; retrofitting it in Tier 1 means backfilling data you didn't capture. Capture it from day one even though the analytics come later. |
| `CHECK` constraint instead of Postgres `ENUM` type | Same integrity guarantee, but `ALTER TABLE ... DROP CONSTRAINT / ADD CONSTRAINT` is far easier than altering an ENUM when you inevitably add a stage. Defensible in an interview. |
| `stage_events` append-only, no `status` column on `applications` | Your core design thesis: status is derived, not stored. No update anomalies, full history, enables all Tier 1 analytics. |
| `occurred_at` separate from insertion time | You'll log events late ("the OA email came Tuesday, I'm logging it Thursday"). Default `now()` but overridable. |
| Index on `(application_id, occurred_at DESC)` | "Current status" = latest event per application; this index makes that lookup cheap. Know why it exists. |
| No `ghosted` stage | Ghosting is the *absence* of events, not an event. Derive it in queries: no event in N days after `applied`/`oa` → stale. Excellent interview talking point. |
| `SERIAL` ints, not UUIDs | Single-user app, no distributed writes, no ID-guessing threat model. Simpler. Know the tradeoff. |
| No `users` table | Single-user by design. This one decision saves you 2+ weeks of auth work. Do not add multi-user. |

### The "current status" query (your first hard SQL)

```sql
SELECT DISTINCT ON (application_id)
       application_id, stage, occurred_at
FROM stage_events
ORDER BY application_id, occurred_at DESC;
```

`DISTINCT ON` is Postgres-specific. Also learn the portable window-function version (`ROW_NUMBER() OVER (PARTITION BY ...)`) — interviewers may ask for it.

### Tier 0 endpoints

- `POST /companies` (or fold into application creation with get-or-create)
- `POST /applications`
- `POST /applications/{id}/events` — validate stage value; reject events earlier than the latest existing event unless a `backfill=true` flag is set
- `GET /applications` — with current status joined in
- `GET /stats/by-stage` — count of applications currently in each stage

**DB access layer: use raw SQL via `psycopg` (v3), not the SQLAlchemy ORM.** The ORM would write your SQL for you, which defeats the stated purpose of this project. SQLAlchemy *Core* is an acceptable middle ground later; start with raw parameterized queries so every JOIN is yours.

**Migrations:** numbered plain SQL files (`001_init.sql`, `002_add_x.sql`) applied by a tiny Python script. Do NOT learn Alembic in week 1 — it's a rabbit hole. Adopt it in week 5 if you want, as a "here's why migration tools exist" lesson.

---

## 2. Week-by-Week Timeline (Tier 0 + Tier 1)

Assumes ~10–12 focused hours/week alongside your internship. Today is July 6.

### Week 1 (Jul 6–12): SQL fundamentals + schema, no Python
- Install Postgres locally (or Docker). Live in `psql` all week.
- **SQL to learn:** `CREATE TABLE`, types, `PRIMARY KEY`, `FOREIGN KEY`, `CHECK`, `INSERT`, `SELECT`, `WHERE`, `ORDER BY`, inner `JOIN`.
- Create the schema above by hand. Insert your *real* applications so far, by hand, in SQL.
- Milestone: you can write, from memory, a JOIN listing every application with its company name and every event.

### Week 2 (Jul 13–19): FastAPI + psycopg, Tier 0 endpoints
- **SQL to learn:** `INSERT ... RETURNING`, `ON CONFLICT` (upsert), parameterized queries, LEFT JOIN, why SQL injection happens and how parameters prevent it.
- Wire up connection pooling (`psycopg_pool`), Pydantic request/response models.
- Milestone: all Tier 0 endpoints working locally against real data.

### Week 3 (Jul 20–26): Current-status query, deploy, start real usage
- **SQL to learn:** `DISTINCT ON`, `GROUP BY` + aggregates, subqueries.
- Build `GET /applications` with joined current status and `GET /stats/by-stage`.
- Deploy: Render for the API (you know this), **Neon or Supabase free tier for Postgres** (Render's free Postgres expires after 90 days — avoid).
- Milestone: **deployed; you log every real application through the API from now on.** Tier 0 done.

### Week 4 (Jul 27–Aug 2): Tier 1 — funnel + time-in-stage
- **SQL to learn:** window functions — `LAG`, `LEAD`, `ROW_NUMBER`, `PARTITION BY`. This is the intellectual core of the project.
- Time-in-stage: `LAG(occurred_at) OVER (PARTITION BY application_id ORDER BY occurred_at)` → diff → average per stage-pair.
- Funnel: per stage, count distinct applications that ever reached it; conversion = reached(next) ÷ reached(current). Decide explicitly how to handle skipped stages (e.g., interview with no OA — count it as passing through, or as a separate path? Document your choice).
- Milestone: `GET /stats/funnel` and `GET /stats/time-in-stage` return correct numbers you've verified by hand on paper.

### Week 5 (Aug 3–9): Response-rate by source, tests, polish
- `GET /stats/by-source` (you captured `source` from day one — this is now a single GROUP BY).
- pytest suite against a separate test database with fixture data; test the funnel math on a known dataset.
- README with schema diagram and a paragraph on *why* stage_events is append-only.
- Milestone: **Tier 0 + Tier 1 complete, tested, deployed, documented. This is the resume-ready checkpoint.**

### Week 6 (Aug 10–16): Buffer
You will need it. If somehow not: minimal HTML frontend (server-rendered Jinja2 or a single static page hitting the API — do not start a React project).

---

## 3. Tier 2 Plan (start only after Week 5 milestone)

### 3a. Gmail integration (realistically 2.5–3 weeks — the biggest item in the whole project)

**Architecture: polling, not push.** Google Pub/Sub push notifications require a public webhook, topic setup, and renewal logic — massive complexity for one user. A cron job (Render cron or APScheduler) polling every 2–6 hours is entirely sufficient and much more defensible than half-working push.

Build order:
1. **OAuth (3–5 days, the annoying part):** Google Cloud project → enable Gmail API → OAuth consent screen ("External" + add yourself as test user — you do NOT need app verification for personal use, do not go down that path) → request only `gmail.readonly` scope → one-time local auth flow → store the **refresh token** and use it server-side thereafter. Store tokens encrypted or in env vars, never in the repo.
2. **Ingestion + idempotency (2–3 days):** poll `messages.list` with a query like `newer_than:7d from:(no-reply@greenhouse.io OR *@lever.co OR *@myworkday.com)`. Create a table `processed_emails(gmail_message_id TEXT PRIMARY KEY, ...)` — insert with `ON CONFLICT DO NOTHING` so re-polling never double-creates events. This idempotency table is an interview gold mine.
3. **Classification (3–5 days):** simple rule-based matching on sender domain + subject keywords ("thank you for applying" → confirmation; "unfortunately" / "not moving forward" → rejection; "schedule" / "interview" → interview). No ML — rules are more debuggable and you can explain every decision.
4. **Review queue (2–3 days):** `email_matches` table with `status IN ('pending','confirmed','dismissed')`; matched emails create *pending* rows; a `POST /matches/{id}/confirm` endpoint creates the real stage_event. **Nothing writes to `stage_events` without your confirmation** — this eliminates the accuracy pressure entirely.
5. Company-name matching from email → existing application: fuzzy match, and when ambiguous, leave it for the review queue. Do not build a clever resolver.

**Good-enough cutoff:** Greenhouse + Lever + Workday sender patterns, polling, human-confirmed queue. Anything past that (arbitrary ATS coverage, auto-confirm, real-time push) is ballooning — stop.

### 3b. SM-2 spaced repetition (3–5 days — small, contained, do it as a palate cleanser)

Schema:
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

Standard SM-2, exactly:
- quality < 3 → `repetitions = 0`, `interval = 1` day (easiness unchanged on lapse in canonical SM-2 — many implementations get this wrong; check the original spec).
- quality ≥ 3 → interval: 1st rep = 1 day, 2nd = 6 days, then `previous_interval × easiness`, rounded up.
- Easiness update: `EF' = EF + (0.1 − (5−q) × (0.08 + (5−q) × 0.02))`, floor at 1.3.
- Endpoints: `GET /questions/due`, `POST /questions/{id}/review`.
- Keep the `reviews` log table (SM-2 only needs current state, but the log fits your append-only theme and lets you replay/verify).

### 3c. Discord webhook (half a day, hard cap 1 day)
`httpx.post(WEBHOOK_URL, json={"content": ...})` after a stage_event insert. Fire-and-forget with a try/except — a Discord outage must never fail the API request. Done. Resist making it configurable.

---

## 4. Where scope will balloon — and the cutoffs

1. **Gmail OAuth + parsing** — the #1 risk. Cutoffs are in §3a. If OAuth alone takes more than a week, timebox it: the project is complete and impressive without Tier 2.
2. **Frontend creep.** You said secondary; hold yourself to it. Cutoff: one page, table of applications + a form. No React, no build tooling. If you catch yourself installing npm, stop.
3. **Migration tooling.** Numbered SQL files. Alembic only as an optional Week-6+ upgrade.
4. **Auth/multi-user.** Never. One `API_KEY` header check for your deployed instance is the ceiling.
5. **Stage taxonomy debates.** You'll be tempted to model recruiter chats, take-homes, team-matching... Eight stages max. `notes` absorbs the rest.
6. **Tier 3.** Honest take: skip both. The resume-matcher reuses old skills (you said so yourself), and for salary data, the clean free options (BLS OEWS, H-1B disclosure data) are coarse — real but low payoff. Only touch if Tier 2 is done and apps are submitted.

---

## 5. Interview-defense cheat sheet

| Feature | The question you'll get | What your answer hinges on |
|---|---|---|
| `stage_events` design | "Why an event log instead of a status column? What did it cost you?" | Immutability, auditability, derived state; cost = every status read needs a query (mitigated by the index; mention you could add a materialized `current_stage` as a cache **if** reads demanded it — you measured, they didn't). |
| Current-status query | "Get each application's latest status — write it, then make it fast." | `DISTINCT ON` + the `(application_id, occurred_at DESC)` index; portable `ROW_NUMBER()` variant. |
| Funnel analytics | "How do you handle applications that skip a stage, and in-flight ones that haven't reached it *yet*?" | Explicit documented choice; conversion denominators exclude still-pending applications or you're understating rates. |
| Time-in-stage | "Why a window function instead of a self-join?" | `LAG` reads each row's neighbor in one pass; self-join is O(n²)-ish and uglier. Be able to sketch both. |
| Gmail ingestion | "What happens if your poller runs twice on the same email?" | Idempotency via `processed_emails` PK + `ON CONFLICT DO NOTHING`; nothing hits `stage_events` without human confirmation. |
| SM-2 | "Why do intervals grow multiplicatively, and what happens on a lapse?" | Spacing effect; multiplicative growth matches the forgetting curve; lapse resets repetitions, not easiness (canonical spec). |
| Overall | "What would you change for 10k users?" | users table + row scoping, connection pooling limits, move poller to a queue, indexes revisited. Knowing what you *deliberately didn't build* is senior-sounding. |
