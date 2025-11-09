import datetime
from pydantic import BaseModel, Field

class HealthCheckResponse(BaseModel):
    """
    Schema for the health check response.
    """
    status: str = "ok"
    message: str = "Service is healthy"
    timestamp: str = Field(default_factory=lambda: datetime.datetime.now(datetime.timezone.utc).isoformat())