import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.core.config import settings

logger = logging.getLogger("eventdhara.database")

db_url = settings.DATABASE_URL

# Explicitly use the installed psycopg2 driver
if db_url.startswith("postgresql+psycopg://"):
    db_url = db_url.replace(
        "postgresql+psycopg://",
        "postgresql+psycopg2://",
        1
    )
elif db_url.startswith("postgresql://"):
    db_url = db_url.replace(
        "postgresql://",
        "postgresql+psycopg2://",
        1
    )
elif db_url.startswith("postgres://"):
    db_url = db_url.replace(
        "postgres://",
        "postgresql+psycopg2://",
        1
    )


try:
    # Test PostgreSQL connection
    test_engine = create_engine(db_url, echo=settings.SQL_ECHO, pool_pre_ping=True)
    with test_engine.connect() as conn:
        logger.info("Successfully connected to PostgreSQL database at %s", db_url.split("@")[-1])
    engine = test_engine
except Exception as e:
    logger.warning("PostgreSQL connection error: %s. Falling back to SQLite database for resilience.", e)
    fallback_url = "sqlite:///./eventdhara_fallback.db"
    engine = create_engine(fallback_url, connect_args={"check_same_thread": False}, echo=settings.SQL_ECHO)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
