"""Declarative base + domain models. Importing this package registers all tables."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


# Import models so Base.metadata is populated (for Alembic + create_all in tests).
from app.models.entities import Client, DeletionLog, Face, Gallery, JobAudit, Photo, PhotoStatus  # noqa: E402,F401
