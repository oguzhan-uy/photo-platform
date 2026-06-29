"""Milestone 6: compliance tests — verifiable deletion, retention, consent revocation log.

All tests run on in-memory SQLite (no Docker, no real R2).
R2 calls are monkeypatched at the app.routers.admin.storage / worker.jobs.expire.storage
boundaries so no real credentials are needed.

Coverage:
- Client hard-delete: returns correct counts, removes all DB rows, calls R2 delete,
  writes DeletionLog, returns 404 for unknown client
- Gallery expiry job: purges expired galleries (photos + faces + R2), skips active
  and no-expiry galleries, writes DeletionLog
- Deletion log endpoint: readable via GET /admin/deletion-log
- Expire trigger endpoint: POST /admin/expire-galleries enqueues the job
- Consent revocation: writes DeletionLog with face count (verifiable biometric purge)
"""
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import Client, DeletionLog, Face, Gallery, Photo, PhotoStatus
from app.security import hash_passcode

ADMIN = {"Authorization": "Bearer test-admin-token"}


# ---- helpers ----

def _make_client_with_gallery(
    db_session,
    n_photos: int = 0,
    n_faces: int = 0,
    expires_at=None,
    with_r2_keys: bool = True,
):
    cl = Client(display_name="Test", consent_biometric=n_faces > 0)
    db_session.add(cl)
    db_session.flush()
    g = Gallery(
        client_id=cl.id,
        title="G",
        passcode_hash=hash_passcode("pass1234"),
        expires_at=expires_at,
    )
    db_session.add(g)
    db_session.flush()
    photos = []
    for i in range(n_photos):
        p = Photo(
            gallery_id=g.id,
            r2_key_original=f"originals/{g.id}/{i}" if with_r2_keys else None,
            r2_key_web=f"web/{g.id}/{i}.jpg" if with_r2_keys else None,
            status=PhotoStatus.ready,
        )
        db_session.add(p)
        db_session.flush()
        for _ in range(n_faces):
            db_session.add(Face(photo_id=p.id, gallery_id=g.id))
        photos.append(p)
    db_session.commit()
    return cl, g, photos


# ---- client hard-delete ----

def test_delete_client_returns_counts(client, db_session, monkeypatch):
    cl, g, _ = _make_client_with_gallery(db_session, n_photos=2, n_faces=3)
    monkeypatch.setattr("app.routers.admin.storage.delete_objects", lambda keys: len(keys))

    r = client.delete(f"/admin/clients/{cl.id}", headers=ADMIN)

    assert r.status_code == 200
    body = r.json()
    assert body["purged_galleries"] == 1
    assert body["purged_photos"] == 2
    assert body["purged_faces"] == 6   # 2 photos × 3 faces each
    assert body["purged_r2_objects"] == 4  # 2 originals + 2 web keys


def test_delete_client_removes_all_db_rows(client, db_session, monkeypatch):
    cl, g, _ = _make_client_with_gallery(db_session, n_photos=1, n_faces=2)
    monkeypatch.setattr("app.routers.admin.storage.delete_objects", lambda keys: len(keys))

    client.delete(f"/admin/clients/{cl.id}", headers=ADMIN)

    assert db_session.get(Client, cl.id) is None
    assert db_session.get(Gallery, g.id) is None
    assert db_session.query(Photo).filter_by(gallery_id=g.id).count() == 0
    assert db_session.query(Face).filter_by(gallery_id=g.id).count() == 0


def test_delete_client_writes_deletion_log(client, db_session, monkeypatch):
    cl, _, _ = _make_client_with_gallery(db_session, n_photos=2)
    monkeypatch.setattr("app.routers.admin.storage.delete_objects", lambda keys: len(keys))

    client.delete(f"/admin/clients/{cl.id}", headers=ADMIN)

    entry = db_session.query(DeletionLog).filter_by(target_id=cl.id).one_or_none()
    assert entry is not None
    assert entry.event_type == "client_delete"
    assert entry.target_type == "client"
    assert entry.executed_by == "admin"
    assert entry.purged_photos == 2


def test_delete_client_calls_r2_delete(client, db_session, monkeypatch):
    cl, _, _ = _make_client_with_gallery(db_session, n_photos=2, with_r2_keys=True)
    captured: list[str] = []

    def _fake_delete(keys: list[str]) -> int:
        captured.extend(keys)
        return len(keys)

    monkeypatch.setattr("app.routers.admin.storage.delete_objects", _fake_delete)

    client.delete(f"/admin/clients/{cl.id}", headers=ADMIN)

    assert any("originals" in k for k in captured)
    assert any("web" in k for k in captured)
    assert len(captured) == 4  # 2 originals + 2 web


def test_delete_client_no_r2_keys_when_no_photos(client, db_session, monkeypatch):
    """Client with no photos should not call delete_objects (avoids empty-batch edge case)."""
    cl, _, _ = _make_client_with_gallery(db_session, n_photos=0)
    called = []
    monkeypatch.setattr(
        "app.routers.admin.storage.delete_objects",
        lambda keys: (called.append(keys), 0)[1],
    )

    r = client.delete(f"/admin/clients/{cl.id}", headers=ADMIN)

    assert r.status_code == 200
    assert all(len(k) == 0 for k in called), "delete_objects called with non-empty batch unexpectedly"


def test_delete_nonexistent_client_returns_404(client, db_session):
    r = client.delete(f"/admin/clients/{uuid.uuid4()}", headers=ADMIN)
    assert r.status_code == 404


# ---- gallery expiry job ----

def _run_expire(db_session, monkeypatch):
    """Helper: run expire_galleries() with SessionLocal patched to use db_session."""
    monkeypatch.setattr("worker.jobs.expire.storage.delete_objects", lambda keys: len(keys))
    with patch("worker.jobs.expire.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs import expire as expire_mod
        import importlib
        importlib.reload(expire_mod)
        return expire_mod.expire_galleries()


def test_expire_job_deletes_expired_gallery(db_session, monkeypatch):
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    cl, g, _ = _make_client_with_gallery(db_session, n_photos=2, n_faces=1, expires_at=past)

    monkeypatch.setattr("worker.jobs.expire.storage.delete_objects", lambda keys: len(keys))
    with patch("worker.jobs.expire.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.expire import expire_galleries
        result = expire_galleries()

    assert result["purged"] == 1
    assert db_session.get(Gallery, g.id) is None
    assert db_session.query(Photo).filter_by(gallery_id=g.id).count() == 0
    assert db_session.query(Face).filter_by(gallery_id=g.id).count() == 0


def test_expire_job_skips_future_gallery(db_session, monkeypatch):
    future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    cl, g, _ = _make_client_with_gallery(db_session, expires_at=future)

    monkeypatch.setattr("worker.jobs.expire.storage.delete_objects", lambda keys: len(keys))
    with patch("worker.jobs.expire.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.expire import expire_galleries
        result = expire_galleries()

    assert result["purged"] == 0
    assert db_session.get(Gallery, g.id) is not None


def test_expire_job_skips_gallery_without_expiry(db_session, monkeypatch):
    cl, g, _ = _make_client_with_gallery(db_session, expires_at=None)

    monkeypatch.setattr("worker.jobs.expire.storage.delete_objects", lambda keys: len(keys))
    with patch("worker.jobs.expire.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.expire import expire_galleries
        result = expire_galleries()

    assert result["purged"] == 0
    assert db_session.get(Gallery, g.id) is not None


def test_expire_job_writes_deletion_log(db_session, monkeypatch):
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    cl, g, _ = _make_client_with_gallery(db_session, n_photos=3, expires_at=past)

    monkeypatch.setattr("worker.jobs.expire.storage.delete_objects", lambda keys: len(keys))
    with patch("worker.jobs.expire.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.expire import expire_galleries
        expire_galleries()

    entry = db_session.query(DeletionLog).filter_by(target_id=g.id).one_or_none()
    assert entry is not None
    assert entry.event_type == "gallery_expire"
    assert entry.target_type == "gallery"
    assert entry.executed_by == "expiry_worker"
    assert entry.purged_photos == 3


def test_expire_job_purges_multiple_galleries(db_session, monkeypatch):
    past = datetime(2000, 1, 1, tzinfo=timezone.utc)
    future = datetime(2099, 1, 1, tzinfo=timezone.utc)
    cl1, g1, _ = _make_client_with_gallery(db_session, n_photos=1, expires_at=past)
    cl2, g2, _ = _make_client_with_gallery(db_session, n_photos=1, expires_at=past)
    cl3, g3, _ = _make_client_with_gallery(db_session, n_photos=1, expires_at=future)

    monkeypatch.setattr("worker.jobs.expire.storage.delete_objects", lambda keys: len(keys))
    with patch("worker.jobs.expire.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.expire import expire_galleries
        result = expire_galleries()

    assert result["purged"] == 2
    assert db_session.get(Gallery, g1.id) is None
    assert db_session.get(Gallery, g2.id) is None
    assert db_session.get(Gallery, g3.id) is not None  # active — untouched


# ---- deletion log endpoint ----

def test_deletion_log_endpoint_returns_entries(client, db_session):
    entry = DeletionLog(
        event_type="client_delete",
        target_type="client",
        target_id=uuid.uuid4(),
        purged_photos=5,
        purged_faces=10,
        purged_r2_objects=10,
        executed_by="admin",
    )
    db_session.add(entry)
    db_session.commit()

    r = client.get("/admin/deletion-log", headers=ADMIN)

    assert r.status_code == 200
    body = r.json()
    assert len(body) >= 1
    assert any(e["event_type"] == "client_delete" for e in body)


def test_deletion_log_requires_admin_token(client, db_session):
    r = client.get("/admin/deletion-log", headers={"Authorization": "Bearer wrong"})
    assert r.status_code == 401


# ---- expire trigger endpoint ----

def test_expire_endpoint_enqueues_job(client, monkeypatch):
    fake_job = MagicMock()
    fake_job.id = "fake-expire-job-id"
    monkeypatch.setattr("app.routers.admin.task_queue.enqueue", lambda *a, **kw: fake_job)

    r = client.post("/admin/expire-galleries", headers=ADMIN)

    assert r.status_code == 202
    assert r.json()["job_id"] == "fake-expire-job-id"


# ---- consent revocation writes deletion log ----

def test_consent_revocation_writes_deletion_log(client, db_session):
    """Biometric consent revocation must write a DeletionLog entry with the face count."""
    cl = Client(display_name="Bio", consent_biometric=True)
    db_session.add(cl)
    db_session.flush()
    g = Gallery(client_id=cl.id, title="G", passcode_hash=hash_passcode("x1234"))
    db_session.add(g)
    db_session.flush()
    p = Photo(gallery_id=g.id, status=PhotoStatus.ready)
    db_session.add(p)
    db_session.flush()
    db_session.add(Face(photo_id=p.id, gallery_id=g.id))
    db_session.add(Face(photo_id=p.id, gallery_id=g.id))
    db_session.commit()

    r = client.patch(
        f"/admin/clients/{cl.id}/consent",
        json={"consent_biometric": False},
        headers=ADMIN,
    )
    assert r.status_code == 200

    entry = db_session.query(DeletionLog).filter_by(target_id=cl.id).one_or_none()
    assert entry is not None
    assert entry.event_type == "consent_revoke"
    assert entry.purged_faces == 2
    assert entry.purged_photos == 0
    assert entry.purged_r2_objects == 0
    assert entry.executed_by == "admin"


def test_consent_grant_does_not_write_deletion_log(client, db_session):
    """Granting consent must NOT write a DeletionLog — only revocation does."""
    cl = Client(display_name="New", consent_biometric=False)
    db_session.add(cl)
    db_session.commit()

    client.patch(
        f"/admin/clients/{cl.id}/consent",
        json={"consent_biometric": True},
        headers=ADMIN,
    )

    count = db_session.query(DeletionLog).filter_by(target_id=cl.id).count()
    assert count == 0
