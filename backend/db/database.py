"""
Database Configuration — SQLite (zero-cost local storage)
=========================================================
Provides SQLAlchemy engine, session, and Base for ORM models.
Uses SQLite by default; can be swapped to PostgreSQL via DATABASE_URL env var.
"""

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from backend.config import DATABASE_URL

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """
    FastAPI dependency that yields a database session.
    Ensures the session is closed after the request completes.

    Yields:
        Session: SQLAlchemy database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create all tables defined by ORM models.
    Called on application startup.
    """
    from backend.db import models as _  # noqa: F401 — ensure models are registered
    Base.metadata.create_all(bind=engine)
