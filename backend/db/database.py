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
    _add_missing_columns()


def _add_missing_columns():
    """
    Add columns introduced after a table was first created. `create_all` never
    alters existing tables, so older local databases would otherwise fail on
    the new ledger fields. Additive only: nothing is dropped or rewritten.
    """
    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue
            existing = {c["name"] for c in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                col_type = col.type.compile(dialect=engine.dialect)
                conn.execute(text(f'ALTER TABLE {table.name} ADD COLUMN {col.name} {col_type}'))
