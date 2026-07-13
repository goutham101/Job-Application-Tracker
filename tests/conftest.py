import os

import psycopg
import pytest
from fastapi.testclient import TestClient

TEST_DATABASE_URL = "postgresql://localhost/jobtracker_test"
os.environ["DATABASE_URL"] = TEST_DATABASE_URL  # must be set before app import

from app.main import app  # noqa: E402
from db.migrate import migrate  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def test_schema():
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        conn.execute("DROP SCHEMA public CASCADE; CREATE SCHEMA public;")
        conn.commit()
    migrate(TEST_DATABASE_URL)


# Session-scoped: psycopg_pool cannot reopen a closed pool, so the app's
# lifespan (which opens/closes it) must run exactly once for the whole run.
@pytest.fixture(scope="session")
def _client(test_schema):
    with TestClient(app) as c:
        yield c


@pytest.fixture()
def client(_client):
    with psycopg.connect(TEST_DATABASE_URL) as conn:
        conn.execute(
            "TRUNCATE companies, applications, stage_events, questions, reviews "
            "RESTART IDENTITY CASCADE"
        )
        conn.commit()
    return _client


@pytest.fixture()
def make_app(client):
    def _make(company="Acme", role="SWE Intern", source="cold_apply", applied_at=None, **extra):
        body = {"company_name": company, "role_title": role, "source": source, **extra}
        if applied_at is not None:
            body["applied_at"] = applied_at
        response = client.post("/applications", json=body)
        assert response.status_code == 201, response.text
        return response.json()

    return _make
