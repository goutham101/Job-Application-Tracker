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
