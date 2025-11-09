from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.
    """
    PROJECT_NAME: str = "FastAPI React Project"
    API_V1_STR: str = "/api/v1"

    DATABASE_URL: str = "postgresql://user:password@localhost:5432/mydatabase"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @model_validator(mode='after')
    def validate_settings(self) -> 'Settings':
        if not self.SECRET_KEY:
            raise ValueError("SECRET_KEY cannot be empty.")
        return self

@lru_cache()
def get_settings() -> Settings:
    """
    Get cached settings instance.
    """
    return Settings()