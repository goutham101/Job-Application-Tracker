import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi.testclient import TestClient

from app.main import app
from app.database import Base, get_db

SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///./test.db"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(scope="function")
def client():
    Base.metadata.create_all(bind=engine)
    yield TestClient(app)
    Base.metadata.drop_all(bind=engine)
    
@pytest.fixture(scope="function")
def auth_client(client):
    client.post("/register", json={
        "email": "testuser@example.com",
        "password": "testpassword123"
    })
    login_response = client.post("/login", json={
        "email": "testuser@example.com",
        "password": "testpassword123"
    })
    token = login_response.json()["access_token"]

    client.headers.update({"Authorization": f"Bearer {token}"})
    return client