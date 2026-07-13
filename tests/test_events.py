def get_app(client, app_id):
    return next(a for a in client.get("/applications").json() if a["id"] == app_id)


def test_add_event_advances_stage(client, make_app):
    created = make_app()
    response = client.post(
        f"/applications/{created['id']}/events", json={"stage": "oa"}
    )
    assert response.status_code == 201
    data = response.json()
    assert data["stage"] == "oa"
    assert data["application_id"] == created["id"]

    assert get_app(client, created["id"])["current_stage"] == "oa"


def test_add_event_unknown_application(client):
    response = client.post("/applications/9999/events", json={"stage": "oa"})
    assert response.status_code == 404


def test_add_event_invalid_stage(client, make_app):
    created = make_app()
    response = client.post(
        f"/applications/{created['id']}/events", json={"stage": "ghosted"}
    )
    assert response.status_code == 422


def test_out_of_order_event_rejected(client, make_app):
    created = make_app(applied_at="2026-07-10T12:00:00Z")
    response = client.post(
        f"/applications/{created['id']}/events",
        json={"stage": "oa", "occurred_at": "2026-07-08T12:00:00Z"},
    )
    assert response.status_code == 409


def test_backfill_flag_allows_out_of_order(client, make_app):
    created = make_app(applied_at="2026-07-10T12:00:00Z")
    response = client.post(
        f"/applications/{created['id']}/events?backfill=true",
        json={"stage": "oa", "occurred_at": "2026-07-08T12:00:00Z"},
    )
    assert response.status_code == 201

    # Latest event by occurred_at is still the original 'applied' one.
    assert get_app(client, created["id"])["current_stage"] == "applied"


def test_stage_event_triggers_discord_notify(client, make_app, monkeypatch):
    from app import applications

    calls = []
    monkeypatch.setattr(applications, "notify", lambda msg: calls.append(msg))

    created = make_app(company="Acme", role="SWE Intern")
    client.post(f"/applications/{created['id']}/events", json={"stage": "oa"})

    assert calls == ["Acme — SWE Intern moved to oa"]
