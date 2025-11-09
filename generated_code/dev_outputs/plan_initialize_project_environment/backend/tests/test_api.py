import pytest
from httpx import AsyncClient
from datetime import datetime

from src.main import app

@pytest.mark.asyncio
async def test_health_check():
    """
    Test the health check endpoint.
    """
    async with AsyncClient(app=app, base_url="http://test") as ac:
        # Add a timeout to the request to prevent test execution timeout
        # A health check should respond quickly, so a short timeout is appropriate.
        response = await ac.get("/api/v1/health", timeout=5.0)

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["message"] == "Service is healthy"
    assert "timestamp" in response.json()
    # Optionally, check if timestamp is a valid ISO format date
    try:
        datetime.fromisoformat(response.json()["timestamp"])
    except ValueError:
        pytest.fail("Timestamp is not in valid ISO format")