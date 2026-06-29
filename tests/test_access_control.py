"""The security spine: prove a client can only ever reach their own gallery."""
import uuid
from datetime import datetime, timedelta, timezone

ADMIN = {"Authorization": "Bearer test-admin-token"}


def _token_for(client, gallery_id, passcode="secret123"):
    r = client.post(f"/access/{gallery_id}", json={"passcode": passcode})
    assert r.status_code == 200, r.text
    return r.json()["token"]


# ---- admin auth ----
def test_admin_endpoints_reject_missing_token(client):
    assert client.get("/admin/clients").status_code == 401


def test_admin_endpoints_reject_wrong_token(client):
    r = client.get("/admin/clients", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_admin_can_create_client_and_gallery(client):
    c = client.post("/admin/clients", json={"display_name": "Alice"}, headers=ADMIN)
    assert c.status_code == 201
    cid = c.json()["id"]
    g = client.post(
        "/admin/galleries",
        json={"client_id": cid, "title": "Wedding", "passcode": "hunter2x"},
        headers=ADMIN,
    )
    assert g.status_code == 201
    # passcode must never be echoed back
    assert "passcode" not in g.json() and "passcode_hash" not in g.json()


# ---- passcode gate ----
def test_wrong_passcode_is_rejected(client, make_gallery):
    g, _ = make_gallery(passcode="correct-horse")
    r = client.post(f"/access/{g.id}", json={"passcode": "wrong"})
    assert r.status_code == 401


def test_correct_passcode_issues_token(client, make_gallery):
    g, _ = make_gallery(passcode="correct-horse")
    r = client.post(f"/access/{g.id}", json={"passcode": "correct-horse"})
    assert r.status_code == 200
    assert r.json()["gallery_id"] == str(g.id)


# ---- the core isolation guarantee ----
def test_token_scopes_photo_listing_to_own_gallery(client, make_gallery):
    g_a, photos_a = make_gallery(passcode="aaa111", n_photos=3)
    g_b, _ = make_gallery(passcode="bbb222", n_photos=2)
    token_a = _token_for(client, g_a.id, "aaa111")

    r = client.get("/me/photos", headers={"Authorization": f"Bearer {token_a}"})
    assert r.status_code == 200
    ids = {p["id"] for p in r.json()}
    assert ids == {str(p.id) for p in photos_a}      # exactly gallery A's photos
    assert len(r.json()) == 3                          # never gallery B's


def test_client_cannot_read_another_gallerys_photo_by_id(client, make_gallery):
    g_a, _ = make_gallery(passcode="aaa111", n_photos=1)
    g_b, photos_b = make_gallery(passcode="bbb222", n_photos=1)
    token_a = _token_for(client, g_a.id, "aaa111")

    # Try to fetch gallery B's photo using gallery A's token -> 404, not 403
    foreign_photo_id = photos_b[0].id
    r = client.get(
        f"/me/photos/{foreign_photo_id}",
        headers={"Authorization": f"Bearer {token_a}"},
    )
    assert r.status_code == 404


def test_me_endpoints_reject_missing_or_bad_token(client, make_gallery):
    make_gallery()
    assert client.get("/me/photos").status_code == 401
    assert client.get(
        "/me/photos", headers={"Authorization": "Bearer garbage.token.here"}
    ).status_code == 401


# ---- published / expiry enforcement ----
def test_unpublished_gallery_is_not_accessible(client, make_gallery):
    g, _ = make_gallery(passcode="aaa111", published=False)
    assert client.post(f"/access/{g.id}", json={"passcode": "aaa111"}).status_code == 404


def test_expired_gallery_is_not_accessible(client, make_gallery):
    past = datetime.now(timezone.utc) - timedelta(days=1)
    g, _ = make_gallery(passcode="aaa111", expires_at=past)
    assert client.post(f"/access/{g.id}", json={"passcode": "aaa111"}).status_code == 404


def test_unknown_gallery_id_is_404(client):
    assert client.post(f"/access/{uuid.uuid4()}", json={"passcode": "x"}).status_code == 404


# ---- only 'ready' photos are visible ----
def test_non_ready_photos_are_hidden(client, make_gallery, db_session):
    from app.models import Photo, PhotoStatus

    g, _ = make_gallery(passcode="aaa111")
    db_session.add(Photo(gallery_id=g.id, status=PhotoStatus.processing))
    db_session.commit()
    token = _token_for(client, g.id, "aaa111")
    r = client.get("/me/photos", headers={"Authorization": f"Bearer {token}"})
    assert r.json() == []  # processing photo not shown
