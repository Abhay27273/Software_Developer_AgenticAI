from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.exc import SQLAlchemyError

from src.config.settings import get_settings

settings = get_settings()

try:
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True)
except SQLAlchemyError as e:
    raise RuntimeError(f"Failed to initialize database engine: {e}") from e

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = None
    try:
        db = SessionLocal()
        yield db
    except SQLAlchemyError as e:
        raise RuntimeError(f"Failed to get database session: {e}") from e
    finally:
        if db:
            db.close()

def dispose_engine():
    if engine:
        engine.dispose()