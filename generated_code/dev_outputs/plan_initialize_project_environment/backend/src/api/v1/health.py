from datetime import datetime, timezone
from fastapi import APIRouter, status

from src.schemas.health import HealthCheckResponse

router = APIRouter()

@router.get("/health", response_model=HealthCheckResponse, status_code=status.HTTP_200_OK)
async def health_check():
    """
    Performs a health check on the API.
    Returns a simple status indicating if the service is running.
    """
    # Use UTC for consistency and to avoid timezone-related issues in a production environment.
    return HealthCheckResponse(timestamp=datetime.now(timezone.utc).isoformat())