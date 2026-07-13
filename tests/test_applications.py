def test_create_application(client):
    response = client.post(
        "/applications",
        json={"company_name": "Acme", "role_title": "SWE Intern"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["company_name"] == "Acme"
    assert data["role_title"] == "SWE Intern"
    assert data["source"] == "cold_apply"
    assert data["current_stage"] == "applied"
    assert data["current_stage_at"] is not None


def test_company_get_or_create(client, make_app):
    first = make_app(company="Acme", role="SWE Intern")
    second = make_app(company="Acme", role="Data Intern")
    assert first["company_id"] == second["company_id"]

    r1 = client.post("/companies", json={"name": "Globex"})
    r2 = client.post("/companies", json={"name": "Globex"})
    assert r1.status_code == 201 and r2.status_code == 201
    assert r1.json()["id"] == r2.json()["id"]


def test_create_application_invalid_source(client):
    response = client.post(
        "/applications",
        json={"company_name": "Acme", "role_title": "SWE", "source": "spam"},
    )
    assert response.status_code == 422


def test_applied_at_override(make_app):
    from datetime import datetime

    data = make_app(applied_at="2026-07-01T09:00:00Z")
    assert datetime.fromisoformat(data["current_stage_at"]) == datetime.fromisoformat(
        "2026-07-01T09:00:00+00:00"
    )


def test_delete_application(client, make_app):
    created = make_app()
    response = client.delete(f"/applications/{created['id']}")
    assert response.status_code == 204

    listing = client.get("/applications")
    assert all(a["id"] != created["id"] for a in listing.json())

    response = client.delete(f"/applications/{created['id']}")
    assert response.status_code == 404
