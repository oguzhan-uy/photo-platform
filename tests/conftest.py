"""Test fixtures. Runs against in-memory SQLite (no Docker needed) by overriding
the get_db dependency. Auth secrets are set before app import."""
import os
import uuid

# Force-override so container env vars (from .env via docker-compose) don't win.
os.environ["ADMIN_TOKEN"] = "test-admin-token"
os.environ["SECRET_KEY"] = "test-secret-key"

# Clear the lru_cache so Settings re-reads the forced values above.
from app.config import get_settings  # noqa: E402
get_settings.cache_clear()

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import get_db
from app.main import app
from app.models import Base, Gallery, Photo, PhotoStatus
from app.security import hash_passcode

ADMIN = {"Authorization": "Bearer test-admin-token"}


@pytest.fixture()
def db_session():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    session = TestSession()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def client(db_session):
    def _override():
        yield db_session

    app.dependency_overrides[get_db] = _override
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture()
def make_gallery(db_session):
    """Factory: create a client + gallery (+ optional ready photos) directly in the DB."""
    def _make(passcode="secret123", published=True, expires_at=None, n_photos=0):
        from app.models import Client

        cl = Client(display_name="Test Client")
        db_session.add(cl)
        db_session.flush()
        g = Gallery(
            client_id=cl.id,
            title="Shoot",
            passcode_hash=hash_passcode(passcode),
            published=published,
            expires_at=expires_at,
        )
        db_session.add(g)
        db_session.flush()
        photos = []
        for _ in range(n_photos):
            p = Photo(gallery_id=g.id, status=PhotoStatus.ready)
            db_session.add(p)
            photos.append(p)
        db_session.commit()
        return g, photos

    return _make
