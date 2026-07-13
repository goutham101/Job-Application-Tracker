from datetime import date, timedelta


def test_create_and_list_due(client):
    response = client.post("/questions", json={"prompt": "Explain DISTINCT ON"})
    assert response.status_code == 201
    question = response.json()
    assert question["due_date"] == date.today().isoformat()
    assert question["easiness"] == 2.5

    due = client.get("/questions/due").json()
    assert any(q["id"] == question["id"] for q in due)


def test_review_updates_state_and_due_date(client):
    question = client.post("/questions", json={"prompt": "What is a window function?"}).json()

    response = client.post(f"/questions/{question['id']}/review", json={"quality": 5})
    assert response.status_code == 200
    updated = response.json()
    assert updated["repetitions"] == 1
    assert updated["interval_days"] == 1
    assert updated["due_date"] == (date.today() + timedelta(days=1)).isoformat()


def test_lapse_removes_question_from_due_tomorrow(client):
    question = client.post("/questions", json={"prompt": "What is MVCC?"}).json()
    client.post(f"/questions/{question['id']}/review", json={"quality": 5})  # due_date -> +1

    due_today = client.get("/questions/due").json()
    assert all(q["id"] != question["id"] for q in due_today)


def test_review_unknown_question_404(client):
    response = client.post("/questions/9999/review", json={"quality": 4})
    assert response.status_code == 404


def test_review_quality_out_of_range_422(client):
    question = client.post("/questions", json={"prompt": "..."}).json()
    response = client.post(f"/questions/{question['id']}/review", json={"quality": 9})
    assert response.status_code == 422
