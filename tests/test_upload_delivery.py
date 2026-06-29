"""Upload pipeline, ingest job, and presigned delivery tests.

All tests run on in-memory SQLite (no Docker, no real R2).
Storage functions are monkeypatched at the app.storage boundary.
RQ enqueueing is patched so no real Redis is needed for API-level tests.
"""
import io
import uuid
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app.models import JobAudit, Photo, PhotoStatus

ADMIN = {"Authorization": "Bearer test-admin-token"}


# ---- helpers ----

def _make_jpeg(width: int = 100, height: int = 80) -> bytes:
    img = Image.new("RGB", (width, height), color=(128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def _gallery(client, db_session):
    """Create a client + gallery via the admin API, return gallery_id."""
    c = client.post("/admin/clients", json={"display_name": "Tester"}, headers=ADMIN)
    assert c.status_code == 201
    g = client.post(
        "/admin/galleries",
        json={"client_id": c.json()["id"], "title": "Shoot", "passcode": "pass1234"},
        headers=ADMIN,
    )
    assert g.status_code == 201
    return g.json()["id"]


# ---- ingest job ----

def _setup_photo(db_session, status=PhotoStatus.processing) -> Photo:
    """Insert a Photo row directly, bypassing the API."""
    from app.models import Client, Gallery
    from app.security import hash_passcode

    cl = Client(display_name="T")
    db_session.add(cl)
    db_session.flush()
    g = Gallery(client_id=cl.id, title="S", passcode_hash=hash_passcode("x1234"))
    db_session.add(g)
    db_session.flush()
    p = Photo(
        gallery_id=g.id,
        r2_key_original=f"originals/{g.id}/{uuid.uuid4()}",
        status=status,
    )
    db_session.add(p)
    db_session.commit()
    return p


def test_ingest_marks_photo_ready(db_session, monkeypatch):
    jpeg = _make_jpeg(200, 150)
    photo = _setup_photo(db_session)

    monkeypatch.setattr("worker.jobs.ingest.storage.download_bytes", lambda key: jpeg)
    monkeypatch.setattr("worker.jobs.ingest.storage.upload_bytes", lambda key, data, ct: None)

    # Run the job synchronously using a real DB session
    with patch("worker.jobs.ingest.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.ingest import ingest_photo
        ingest_photo(str(photo.id))

    db_session.refresh(photo)
    assert photo.status == PhotoStatus.ready
    assert photo.content_hash is not None
    assert photo.r2_key_web is not None
    assert photo.width == 200
    assert photo.height == 150


def test_ingest_is_idempotent_on_already_ready(db_session, monkeypatch):
    """Re-running ingest on a ready photo is a no-op and does not call R2."""
    photo = _setup_photo(db_session, status=PhotoStatus.ready)
    download_called = []
    monkeypatch.setattr("worker.jobs.ingest.storage.download_bytes", lambda k: download_called.append(k) or b"")

    with patch("worker.jobs.ingest.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.ingest import ingest_photo
        ingest_photo(str(photo.id))

    assert len(download_called) == 0, "R2 download must not happen for already-ready photo"


def test_ingest_deduplicates_same_content_hash(db_session, monkeypatch):
    """A second photo with identical bytes in the same gallery is marked failed."""
    jpeg = _make_jpeg()
    import hashlib
    h = hashlib.sha256(jpeg).hexdigest()

    from app.models import Client, Gallery
    from app.security import hash_passcode

    cl = Client(display_name="T")
    db_session.add(cl)
    db_session.flush()
    g = Gallery(client_id=cl.id, title="S", passcode_hash=hash_passcode("x1234"))
    db_session.add(g)
    db_session.flush()

    # First photo already ready with the same hash
    p1 = Photo(
        gallery_id=g.id,
        r2_key_original="originals/x/1",
        status=PhotoStatus.ready,
        content_hash=h,
    )
    db_session.add(p1)
    # Second photo (the one being ingested)
    p2 = Photo(
        gallery_id=g.id,
        r2_key_original="originals/x/2",
        status=PhotoStatus.processing,
    )
    db_session.add(p2)
    db_session.commit()

    monkeypatch.setattr("worker.jobs.ingest.storage.download_bytes", lambda key: jpeg)
    monkeypatch.setattr("worker.jobs.ingest.storage.upload_bytes", lambda *a, **kw: None)

    with patch("worker.jobs.ingest.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.ingest import ingest_photo
        ingest_photo(str(p2.id))

    db_session.refresh(p2)
    assert p2.status == PhotoStatus.failed
    assert "duplicate" in p2.failure_reason


def test_ingest_records_failure_reason_on_error(db_session, monkeypatch):
    photo = _setup_photo(db_session)
    monkeypatch.setattr(
        "worker.jobs.ingest.storage.download_bytes",
        lambda key: (_ for _ in ()).throw(RuntimeError("bucket gone")),
    )

    with patch("worker.jobs.ingest.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.ingest import ingest_photo
        with pytest.raises(RuntimeError):
            ingest_photo(str(photo.id))

    db_session.refresh(photo)
    assert photo.status == PhotoStatus.failed
    assert "bucket gone" in photo.failure_reason


def test_ingest_writes_audit_row_on_success(db_session, monkeypatch):
    jpeg = _make_jpeg()
    photo = _setup_photo(db_session)

    monkeypatch.setattr("worker.jobs.ingest.storage.download_bytes", lambda key: jpeg)
    monkeypatch.setattr("worker.jobs.ingest.storage.upload_bytes", lambda *a, **kw: None)

    with patch("worker.jobs.ingest.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.ingest import ingest_photo
        ingest_photo(str(photo.id))

    audits = db_session.query(JobAudit).filter_by(target_id=photo.id).all()
    assert len(audits) == 1
    assert audits[0].status == "success"
    assert audits[0].job_type == "ingest"


def test_ingest_writes_audit_row_on_failure(db_session, monkeypatch):
    photo = _setup_photo(db_session)
    monkeypatch.setattr(
        "worker.jobs.ingest.storage.download_bytes",
        lambda key: (_ for _ in ()).throw(OSError("network error")),
    )

    with patch("worker.jobs.ingest.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        from worker.jobs.ingest import ingest_photo
        with pytest.raises(OSError):
            ingest_photo(str(photo.id))

    audits = db_session.query(JobAudit).filter_by(target_id=photo.id).all()
    assert len(audits) == 1
    assert audits[0].status == "failed"
    assert "network error" in audits[0].last_error


# ---- delivery URL ----

def _client_token(client, gallery_id, passcode="pass1234"):
    r = client.post(f"/access/{gallery_id}", json={"passcode": passcode})
    assert r.status_code == 200
    return r.json()["token"]


def test_client_gets_presigned_url_for_ready_photo(client, db_session, monkeypatch):
    monkeypatch.setattr("app.storage.presigned_get", lambda key, ttl: f"https://r2.test/{key}?sig=abc")

    gid = _gallery(client, db_session)
    # Add a ready photo directly
    from app.models import Gallery
    g = db_session.get(Gallery, uuid.UUID(gid))
    p = Photo(gallery_id=g.id, status=PhotoStatus.ready, r2_key_web=f"web/{gid}/img.jpg")
    db_session.add(p)
    db_session.commit()

    token = _client_token(client, gid)
    r = client.get(f"/me/photos/{p.id}/url", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert "r2.test" in body["url"]
    assert body["expires_in"] > 0


def test_client_cannot_get_url_for_non_ready_photo(client, db_session, monkeypatch):
    monkeypatch.setattr("app.storage.presigned_get", lambda key, ttl: "https://r2.test/x")
    gid = _gallery(client, db_session)
    from app.models import Gallery
    g = db_session.get(Gallery, uuid.UUID(gid))
    p = Photo(gallery_id=g.id, status=PhotoStatus.processing)
    db_session.add(p)
    db_session.commit()

    token = _client_token(client, gid)
    r = client.get(f"/me/photos/{p.id}/url", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 404


def test_client_cannot_get_url_for_another_gallerys_photo(client, db_session, monkeypatch):
    monkeypatch.setattr("app.storage.presigned_get", lambda key, ttl: "https://r2.test/x")

    # Gallery A
    gid_a = _gallery(client, db_session)
    # Gallery B with its own photo
    from app.models import Client, Gallery
    from app.security import hash_passcode
    cl_b = Client(display_name="B")
    db_session.add(cl_b)
    db_session.flush()
    g_b = Gallery(client_id=cl_b.id, title="B Shoot", passcode_hash=hash_passcode("bbbb1234"))
    db_session.add(g_b)
    db_session.flush()
    photo_b = Photo(gallery_id=g_b.id, status=PhotoStatus.ready, r2_key_web="web/b/img.jpg")
    db_session.add(photo_b)
    db_session.commit()

    token_a = _client_token(client, gid_a)
    r = client.get(f"/me/photos/{photo_b.id}/url", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 404
