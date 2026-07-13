def advance(client, app_id, stage, occurred_at=None):
    body = {"stage": stage}
    if occurred_at is not None:
        body["occurred_at"] = occurred_at
    response = client.post(f"/applications/{app_id}/events", json=body)
    assert response.status_code == 201, response.text


def test_list_shows_current_stage_per_app(client, make_app):
    a = make_app(company="Acme")
    b = make_app(company="Globex")
    c = make_app(company="Initech")
    advance(client, b["id"], "oa")
    advance(client, c["id"], "oa")
    advance(client, c["id"], "rejected")

    stages = {app["id"]: app["current_stage"] for app in client.get("/applications").json()}
    assert stages == {a["id"]: "applied", b["id"]: "oa", c["id"]: "rejected"}


def test_stats_by_stage(client, make_app):
    a = make_app(company="Acme")
    b = make_app(company="Globex")
    c = make_app(company="Initech")
    d = make_app(company="Umbrella")
    advance(client, b["id"], "oa")
    advance(client, c["id"], "oa")
    advance(client, d["id"], "interview")

    response = client.get("/stats/by-stage")
    assert response.status_code == 200
    rows = {row["stage"]: row["count"] for row in response.json()}
    assert rows == {"applied": 1, "oa": 2, "interview": 1}


def test_stats_by_stage_empty(client):
    response = client.get("/stats/by-stage")
    assert response.status_code == 200
    assert response.json() == []
