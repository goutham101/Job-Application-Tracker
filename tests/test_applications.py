def test_create_application(auth_client):
    response = auth_client.post("/applications", json={
        "company": "Google",
        "role": "Software Engineering Intern",
        "job_type": "internship",
        "date_applied": "2026-07-12",
        "source": "linkedin",
        "is_referral": False
    })

    assert response.status_code == 200

    data = response.json()
    assert data["company"] == "Google"
    assert data["current_status"] == "applied"
    assert len(data["history"]) == 1
    assert data["history"][0]["status"] == "applied"


def test_list_applications(auth_client):
    auth_client.post("/applications", json={
        "company": "Google",
        "role": "Software Engineering Intern",
        "job_type": "internship",
        "date_applied": "2026-07-12",
        "source": "linkedin",
        "is_referral": False
    })
    auth_client.post("/applications", json={
        "company": "Stripe",
        "role": "Backend Intern",
        "job_type": "internship",
        "date_applied": "2026-07-12",
        "source": "company_site",
        "is_referral": False
    })

    response = auth_client.get("/applications")

    assert response.status_code == 200

    data = response.json()
    assert len(data) == 2
    companies = [app["company"] for app in data]
    assert "Google" in companies
    assert "Stripe" in companies


def test_update_status(auth_client):
    created = auth_client.post("/applications", json={
        "company": "Google",
        "role": "Software Engineering Intern",
        "job_type": "internship",
        "date_applied": "2026-07-12",
        "source": "linkedin",
        "is_referral": False
    }).json()

    response = auth_client.patch(f"/applications/{created['id']}", json={
        "current_status": "interviewing"
    })

    assert response.status_code == 200

    data = response.json()
    assert data["current_status"] == "interviewing"
    assert len(data["history"]) == 2
    assert data["history"][0]["status"] == "applied"
    assert data["history"][1]["status"] == "interviewing"


def test_update_status_not_found(auth_client):
    response = auth_client.patch("/applications/9999", json={
        "current_status": "interviewing"
    })

    assert response.status_code == 404


def test_delete_application(auth_client):
    created = auth_client.post("/applications", json={
        "company": "Google",
        "role": "Software Engineering Intern",
        "job_type": "internship",
        "date_applied": "2026-07-12",
        "source": "linkedin",
        "is_referral": False
    }).json()

    response = auth_client.delete(f"/applications/{created['id']}")

    assert response.status_code == 204

    remaining = auth_client.get("/applications").json()
    remaining_ids = [app["id"] for app in remaining]
    assert created["id"] not in remaining_ids


def test_delete_application_not_found(auth_client):
    response = auth_client.delete("/applications/9999")

    assert response.status_code == 404
