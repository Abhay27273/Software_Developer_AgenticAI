import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException
from fastapi.responses import JSONResponse

from src.config.settings import get_settings
from src.api.v1 import health
from src.core.exceptions import CustomException

# Configure logging
# Ensure basicConfig is only called once, which is important in test environments or when reloading
if not logging.root.handlers:
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

settings = get_settings()

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for application startup and shutdown events.
    Handles potential unhandled exceptions during the application's active phase.
    """
    logger.info(f"{settings.PROJECT_NAME} starting up...")
    try:
        # Initialize database connections, cache, etc. here
        # from src.db.database import engine, Base
        # Base.metadata.create_all(bind=engine) # For initial setup, consider Alembic for migrations
        yield
    except Exception as e:
        logger.critical(f"Unhandled exception during application lifespan: {e}", exc_info=True)
        # Re-raise the exception to ensure the application doesn't silently fail or hang
        raise
    finally:
        logger.info(f"{settings.PROJECT_NAME} shutting down...")
        # Clean up resources here

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust this to specific origins in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom Exception Handler for CustomException
@app.exception_handler(CustomException)
async def custom_exception_handler(request, exc: CustomException):
    """
    Handles custom exceptions and returns a structured JSON response.
    Logs the full traceback for better debugging.
    """
    logger.error(f"CustomException caught: {exc.detail} (Status: {exc.status_code})", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=exc.headers
    )

# Generic HTTP Exception Handler for FastAPI's HTTPException
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    """
    Handles FastAPI's HTTPException and returns a structured JSON response.
    Logs the full traceback for better debugging.
    """
    logger.error(f"HTTPException caught: {exc.detail} (Status: {exc.status_code})", exc_info=True)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# Include API routers
app.include_router(health.router, prefix=settings.API_V1_STR, tags=["Health"])

@app.get("/", include_in_schema=False)
async def root():
    """
    Root endpoint redirecting to API documentation.
    """
    return {"message": f"Welcome to {settings.PROJECT_NAME}! Visit {settings.API_V1_STR}/docs for API documentation."}