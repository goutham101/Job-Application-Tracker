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

-- "Current status" = latest event per application; this index makes that lookup cheap.
CREATE INDEX idx_stage_events_app_time
    ON stage_events (application_id, occurred_at DESC);
