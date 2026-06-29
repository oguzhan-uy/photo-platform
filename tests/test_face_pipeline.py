"""Milestone 5: face pipeline tests.

Tests run on in-memory SQLite (no Docker, no InsightFace, no pgvector).
The face_search.cosine_search helper is monkeypatched so the search endpoint
tests never exercise Postgres-specific SQL.

Coverage:
- Consent management: grant, revoke, purge-on-revoke
- Biometric gate: face endpoints return 403 without consent
- Embed enqueue: ingest job enqueues embed only when consent is True
- Face CRUD: photo_faces, clusters, by-cluster endpoints
- Search scoping: a client cannot reach another gallery's faces
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from app.models import Client, Face, Gallery, Photo, PhotoStatus
from app.security import hash_passcode

ADMIN = {"Authorization": "Bearer test-admin-token"}


# ---- helpers ----

def _make_consenting_gallery(db_session):
    """Create a client (consent=True) + gallery + one ready photo."""
    cl = Client(display_name="Consenting", consent_biometric=True)
    db_session.add(cl)
    db_session.flush()
    g = Gallery(
        client_id=cl.id,
        title="Shoot",
        passcode_hash=hash_passcode("pass1234"),
    )
    db_session.add(g)
    db_session.flush()
    p = Photo(gallery_id=g.id, status=PhotoStatus.ready)
    db_session.add(p)
    db_session.commit()
    return cl, g, p


def _client_token(client, gallery_id, passcode="pass1234"):
    r = client.post(f"/access/{gallery_id}", json={"passcode": passcode})
    assert r.status_code == 200
    return r.json()["token"]


def _auth(client, gallery_id):
    return {"Authorization": f"Bearer {_client_token(client, gallery_id)}"}


# ---- consent management ----

def test_grant_consent_sets_flag(client, db_session):
    cl = Client(display_name="A")
    db_session.add(cl)
    db_session.commit()

    r = client.patch(
        f"/admin/clients/{cl.id}/consent",
        json={"consent_biometric": True},
        headers=ADMIN,
    )
    assert r.status_code == 200
    db_session.refresh(cl)
    assert cl.consent_biometric is True
    assert cl.consent_biometric_at is not None


def test_revoke_consent_clears_flag_and_timestamp(client, db_session):
    cl, g, p = _make_consenting_gallery(db_session)

    r = client.patch(
        f"/admin/clients/{cl.id}/consent",
        json={"consent_biometric": False},
        headers=ADMIN,
    )
    assert r.status_code == 200
    db_session.refresh(cl)
    assert cl.consent_biometric is False
    assert cl.consent_biometric_at is None


def test_revocation_purges_face_rows(client, db_session):
    """Revoking consent must hard-delete all Face rows for the client's galleries."""
    cl, g, p = _make_consenting_gallery(db_session)

    # Insert two Face rows directly.
    f1 = Face(photo_id=p.id, gallery_id=g.id)
    f2 = Face(photo_id=p.id, gallery_id=g.id)
    db_session.add_all([f1, f2])
    db_session.commit()

    r = client.patch(
        f"/admin/clients/{cl.id}/consent",
        json={"consent_biometric": False},
        headers=ADMIN,
    )
    assert r.status_code == 200

    remaining = db_session.query(Face).filter_by(gallery_id=g.id).count()
    assert remaining == 0, "all Face rows must be purged on consent revocation"


def test_revocation_preserves_other_gallery_faces(client, db_session):
    """Revoking consent for client A must not delete faces for client B."""
    cl_a, g_a, p_a = _make_consenting_gallery(db_session)
    cl_b, g_b, p_b = _make_consenting_gallery(db_session)

    face_a = Face(photo_id=p_a.id, gallery_id=g_a.id)
    face_b = Face(photo_id=p_b.id, gallery_id=g_b.id)
    db_session.add_all([face_a, face_b])
    db_session.commit()

    client.patch(
        f"/admin/clients/{cl_a.id}/consent",
        json={"consent_biometric": False},
        headers=ADMIN,
    )

    assert db_session.query(Face).filter_by(gallery_id=g_b.id).count() == 1


# ---- biometric gate (403 without consent) ----

def test_photo_faces_requires_consent(client, make_gallery):
    # make_gallery creates a client with consent_biometric=False and passcode "secret123"
    g, photos = make_gallery(n_photos=1)
    token = _client_token(client, str(g.id), passcode="secret123")
    r = client.get(
        f"/me/photos/{photos[0].id}/faces",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_clusters_requires_consent(client, make_gallery):
    g, _ = make_gallery()
    token = _client_token(client, str(g.id), passcode="secret123")
    r = client.get("/me/clusters", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 403


def test_by_cluster_requires_consent(client, make_gallery):
    g, _ = make_gallery()
    token = _client_token(client, str(g.id), passcode="secret123")
    r = client.get(
        "/me/photos/by-cluster/0",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


def test_search_by_face_requires_consent(client, make_gallery):
    g, _ = make_gallery()
    token = _client_token(client, str(g.id), passcode="secret123")
    r = client.post(
        f"/me/search/by-face/{uuid.uuid4()}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert r.status_code == 403


# ---- face listing ----

def test_photo_faces_returns_faces(client, db_session):
    cl, g, p = _make_consenting_gallery(db_session)

    f = Face(photo_id=p.id, gallery_id=g.id, bbox_x=10, bbox_y=20, bbox_w=50, bbox_h=60, det_score=0.99)
    db_session.add(f)
    db_session.commit()

    r = client.get(
        f"/me/photos/{p.id}/faces",
        headers=_auth(client, str(g.id)),
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["bbox_x"] == 10
    assert body[0]["det_score"] == pytest.approx(0.99)
    assert body[0]["photo_id"] == str(p.id)


def test_photo_faces_scoped_to_gallery(client, db_session):
    """Faces from another gallery's photo are never returned."""
    cl_a, g_a, p_a = _make_consenting_gallery(db_session)
    cl_b, g_b, p_b = _make_consenting_gallery(db_session)

    # Face belongs to gallery_b's photo.
    f_b = Face(photo_id=p_b.id, gallery_id=g_b.id)
    db_session.add(f_b)
    db_session.commit()

    # Client A tries to fetch faces for gallery B's photo.
    r = client.get(
        f"/me/photos/{p_b.id}/faces",
        headers=_auth(client, str(g_a.id)),
    )
    # p_b does not belong to g_a → 404 (photo not found in this gallery)
    assert r.status_code == 404


# ---- clusters ----

def test_clusters_returns_people_row(client, db_session):
    cl, g, p = _make_consenting_gallery(db_session)

    for i in range(3):
        db_session.add(Face(photo_id=p.id, gallery_id=g.id, cluster_id=0))
    db_session.add(Face(photo_id=p.id, gallery_id=g.id, cluster_id=1))
    db_session.add(Face(photo_id=p.id, gallery_id=g.id, cluster_id=-1))  # noise — excluded
    db_session.commit()

    r = client.get("/me/clusters", headers=_auth(client, str(g.id)))
    assert r.status_code == 200
    clusters = r.json()
    assert len(clusters) == 2  # noise excluded
    ids = {c["cluster_id"] for c in clusters}
    assert ids == {0, 1}
    counts = {c["cluster_id"]: c["face_count"] for c in clusters}
    assert counts[0] == 3
    assert counts[1] == 1


def test_photos_by_cluster(client, db_session):
    cl, g, p = _make_consenting_gallery(db_session)

    p2 = Photo(gallery_id=g.id, status=PhotoStatus.ready)
    db_session.add(p2)
    db_session.flush()

    db_session.add(Face(photo_id=p.id, gallery_id=g.id, cluster_id=0))
    db_session.add(Face(photo_id=p2.id, gallery_id=g.id, cluster_id=1))
    db_session.commit()

    r = client.get("/me/photos/by-cluster/0", headers=_auth(client, str(g.id)))
    assert r.status_code == 200
    photo_ids = {item["id"] for item in r.json()}
    assert str(p.id) in photo_ids
    assert str(p2.id) not in photo_ids


# ---- face similarity search ----

def test_search_by_face_returns_results(client, db_session, monkeypatch):
    cl, g, p = _make_consenting_gallery(db_session)

    # Face row with a stub embedding (no real InsightFace needed).
    import json
    stub_embedding = json.dumps([0.0] * 512)
    f = Face(photo_id=p.id, gallery_id=g.id, embedding=stub_embedding)
    db_session.add(f)
    db_session.commit()

    # Mock the pgvector search so it doesn't need Postgres.
    monkeypatch.setattr(
        "app.routers.client._face_search_mod.cosine_search",
        lambda db, gallery_id, embedding, top_k, threshold: [(p.id, 0.1)],
    )

    r = client.post(
        f"/me/search/by-face/{f.id}",
        headers=_auth(client, str(g.id)),
    )
    assert r.status_code == 200
    results = r.json()
    assert len(results) == 1
    assert results[0]["photo_id"] == str(p.id)
    assert results[0]["distance"] == pytest.approx(0.1)


def test_search_by_face_scoped_to_gallery(client, db_session, monkeypatch):
    """A client cannot use a face from another gallery as a search query."""
    cl_a, g_a, p_a = _make_consenting_gallery(db_session)
    cl_b, g_b, p_b = _make_consenting_gallery(db_session)

    import json
    f_b = Face(photo_id=p_b.id, gallery_id=g_b.id, embedding=json.dumps([0.0] * 512))
    db_session.add(f_b)
    db_session.commit()

    # Client A tries to search using gallery B's face ID.
    r = client.post(
        f"/me/search/by-face/{f_b.id}",
        headers=_auth(client, str(g_a.id)),
    )
    # face belongs to g_b, not g_a → 404
    assert r.status_code == 404


def test_search_by_face_requires_embedding(client, db_session, monkeypatch):
    """A face row with no embedding yet returns 422."""
    cl, g, p = _make_consenting_gallery(db_session)
    f = Face(photo_id=p.id, gallery_id=g.id, embedding=None)
    db_session.add(f)
    db_session.commit()

    r = client.post(
        f"/me/search/by-face/{f.id}",
        headers=_auth(client, str(g.id)),
    )
    assert r.status_code == 422


# ---- ingest → embed enqueue ----

def test_ingest_enqueues_embed_when_consent_granted(db_session, monkeypatch):
    """embed_photo_faces is enqueued by ingest_photo when consent_biometric=True."""
    import io
    from PIL import Image

    img = Image.new("RGB", (100, 80), (128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg = buf.getvalue()

    # Client with consent granted.
    cl = Client(display_name="Consenter", consent_biometric=True)
    db_session.add(cl)
    db_session.flush()
    g = Gallery(client_id=cl.id, title="S", passcode_hash=hash_passcode("x1234"))
    db_session.add(g)
    db_session.flush()
    p = Photo(gallery_id=g.id, r2_key_original="originals/x/1", status=PhotoStatus.processing)
    db_session.add(p)
    db_session.commit()

    enqueued_args = []

    def fake_enqueue(func_path, *args, **kwargs):
        enqueued_args.append(func_path)
        return MagicMock(id="fake-embed-job")

    monkeypatch.setattr("worker.jobs.ingest.storage.download_bytes", lambda key: jpeg)
    monkeypatch.setattr("worker.jobs.ingest.storage.upload_bytes", lambda *a, **kw: None)

    with patch("worker.jobs.ingest.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        with patch("worker.jobs.ingest.task_queue") as mock_q:
            mock_q.enqueue.side_effect = fake_enqueue
            from worker.jobs.ingest import ingest_photo
            ingest_photo(str(p.id))

    assert any("embed_photo_faces" in a for a in enqueued_args), (
        "embed job must be enqueued when consent_biometric is True"
    )


def test_ingest_does_not_enqueue_embed_without_consent(db_session, monkeypatch):
    """embed_photo_faces is NOT enqueued when consent_biometric=False."""
    import io
    from PIL import Image

    img = Image.new("RGB", (100, 80), (128, 64, 32))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    jpeg = buf.getvalue()

    cl = Client(display_name="No consent", consent_biometric=False)
    db_session.add(cl)
    db_session.flush()
    g = Gallery(client_id=cl.id, title="S", passcode_hash=hash_passcode("x1234"))
    db_session.add(g)
    db_session.flush()
    p = Photo(gallery_id=g.id, r2_key_original="originals/x/2", status=PhotoStatus.processing)
    db_session.add(p)
    db_session.commit()

    monkeypatch.setattr("worker.jobs.ingest.storage.download_bytes", lambda key: jpeg)
    monkeypatch.setattr("worker.jobs.ingest.storage.upload_bytes", lambda *a, **kw: None)

    with patch("worker.jobs.ingest.SessionLocal") as mock_sl:
        mock_sl.return_value.__enter__ = lambda s: db_session
        mock_sl.return_value.__exit__ = lambda s, *a: False
        # task_queue must NOT be called — if it is, the real Redis call would fail.
        with patch("worker.jobs.ingest.task_queue") as mock_q:
            from worker.jobs.ingest import ingest_photo
            ingest_photo(str(p.id))
            mock_q.enqueue.assert_not_called()
