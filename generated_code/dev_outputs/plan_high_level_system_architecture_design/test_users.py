from fastapi.testclient import TestClient
from app.main import app
from app.core.config import settings

client = TestClient(app)

def test_create_user():
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        json={"email": "test@example.com", "full_name": "Test User"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test@example.com"
    assert "id" in data

def test_create_existing_user():
    # First creation should succeed
    client.post(
        f"{settings.API_V1_STR}/users/",
        json={"email": "test2@example.com", "full_name": "Test User 2"},
    )
    # Second attempt with same email should fail
    response = client.post(
        f"{settings.API_V1_STR}/users/",
        json={"email": "test2@example.com", "full_name": "Test User 2"},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "Email already registered"