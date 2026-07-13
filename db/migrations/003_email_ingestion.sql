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
