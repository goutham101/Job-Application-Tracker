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


def funnel_fixture(client, make_app):
    """Six apps, hand-verified in the plan doc:
    A applied only (cold_apply); B applied->rejected (referral);
    C applied->oa->interview (cold_apply, skipped phone_screen);
    D applied->oa->rejected (referral);
    E applied->interview->offer (recruiter, skipped oa+phone_screen);
    F applied->oa (cold_apply, pending at oa).
    """
    a = make_app(company="A")
    b = make_app(company="B", source="referral")
    c = make_app(company="C")
    d = make_app(company="D", source="referral")
    e = make_app(company="E", source="recruiter")
    f = make_app(company="F")
    advance(client, b["id"], "rejected")
    advance(client, c["id"], "oa")
    advance(client, c["id"], "interview")
    advance(client, d["id"], "oa")
    advance(client, d["id"], "rejected")
    advance(client, e["id"], "interview")
    advance(client, e["id"], "offer")
    advance(client, f["id"], "oa")


def test_funnel(client, make_app):
    funnel_fixture(client, make_app)
    response = client.get("/stats/funnel")
    assert response.status_code == 200
    rows = {r["stage"]: r for r in response.json()}
    assert [r["stage"] for r in response.json()] == [
        "applied", "oa", "phone_screen", "interview", "final_round", "offer",
    ]

    assert (rows["applied"]["reached"], rows["applied"]["still_pending"]) == (6, 1)
    assert (rows["oa"]["reached"], rows["oa"]["still_pending"]) == (4, 1)
    assert (rows["phone_screen"]["reached"], rows["phone_screen"]["still_pending"]) == (2, 0)
    assert (rows["interview"]["reached"], rows["interview"]["still_pending"]) == (2, 1)
    assert (rows["final_round"]["reached"], rows["final_round"]["still_pending"]) == (1, 0)
    assert (rows["offer"]["reached"], rows["offer"]["still_pending"]) == (1, 1)

    assert rows["applied"]["conversion_to_next"] == 0.8          # 4 / (6-1)
    assert round(rows["oa"]["conversion_to_next"], 3) == 0.667   # 2 / (4-1)
    assert rows["phone_screen"]["conversion_to_next"] == 1.0     # 2 / 2
    assert rows["interview"]["conversion_to_next"] == 1.0        # 1 / (2-1)
    assert rows["final_round"]["conversion_to_next"] == 1.0      # 1 / 1
    assert rows["offer"]["conversion_to_next"] is None


def test_funnel_empty(client):
    response = client.get("/stats/funnel")
    assert response.status_code == 200
    assert len(response.json()) == 6
    assert all(r["reached"] == 0 and r["conversion_to_next"] is None for r in response.json())


def test_time_in_stage(client, make_app):
    g = make_app(company="G", applied_at="2026-06-01T00:00:00Z")
    h = make_app(company="H", applied_at="2026-06-01T00:00:00Z")
    advance(client, g["id"], "oa", "2026-06-03T00:00:00Z")   # 2 days
    advance(client, h["id"], "oa", "2026-06-05T00:00:00Z")   # 4 days
    advance(client, g["id"], "interview", "2026-06-06T00:00:00Z")  # 3 days

    response = client.get("/stats/time-in-stage")
    assert response.status_code == 200
    rows = {(r["from_stage"], r["to_stage"]): r for r in response.json()}
    assert rows[("applied", "oa")]["transitions"] == 2
    assert rows[("applied", "oa")]["avg_days"] == 3.0
    assert rows[("oa", "interview")]["transitions"] == 1
    assert rows[("oa", "interview")]["avg_days"] == 3.0


def test_stats_by_source(client, make_app):
    funnel_fixture(client, make_app)
    response = client.get("/stats/by-source")
    assert response.status_code == 200
    rows = {r["source"]: r for r in response.json()}
    assert (rows["cold_apply"]["total"], rows["cold_apply"]["responded"]) == (3, 2)
    assert round(rows["cold_apply"]["response_rate"], 3) == 0.667
    assert (rows["referral"]["total"], rows["referral"]["responded"]) == (2, 2)
    assert rows["referral"]["response_rate"] == 1.0
    assert (rows["recruiter"]["total"], rows["recruiter"]["responded"]) == (1, 1)
