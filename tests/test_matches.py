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
