from fastapi import FastAPI
from app.core.config import settings
from app.api.v1.endpoints import users
from app.db.session import engine
from app.models.user import Base

# Create DB tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Include routers
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])

@app.get("/")
def read_root():
    return {"message": "Welcome to the User Service"}