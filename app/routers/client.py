"""Client-facing gallery endpoints.

Access flow: POST /access/{gallery_id} with the passcode -> a short-lived token
scoped to that gallery. Every /me/* read derives the gallery from the token, so
a client can only ever see their own gallery. The by-id photo read additionally
verifies ownership and returns 404 (not 403) for anything outside their gallery,
so it never reveals that another gallery's photo exists.

Face features (M5):
- GET /me/photos/{photo_id}/faces  — list detected faces + bounding boxes
- GET /me/clusters                  — "people row": one entry per identity cluster
- GET /me/photos/by-cluster/{id}   — all photos containing a given person
- POST /me/search/by-face/{face_id} — find photos similar to a stored face embedding
"""
import uuid
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import face_search as _face_search_mod
from app import storage
from app.config import get_settings
from app.db import get_db
from app.models import Client, Face, Gallery, Photo, PhotoStatus
from app.schemas import (
    ClusterOut,
    FaceOut,
    FaceSearchResult,
    GalleryAccessRequest,
    GalleryAccessResponse,
    GalleryOut,
    PhotoOut,
    PhotoURLOut,
    PublicGalleryOut,
)
from app.security import issue_gallery_token, require_gallery_access, verify_passcode

router = APIRouter(tags=["client"])


# ---- Public unauthenticated endpoints ----

@router.get("/galleries", response_model=list[PublicGalleryOut])
def list_public_galleries(db: Session = Depends(get_db)) -> list[PublicGalleryOut]:
    """Return all currently accessible (published, not expired) galleries for the landing page.

    No authentication required — only non-sensitive metadata is returned.
    """
    rows = db.execute(select(Gallery).where(Gallery.published.is_(True))).scalars().all()
    return [
        PublicGalleryOut(id=g.id, title=g.title, has_cover=g.cover_photo_id is not None)
        for g in rows
        if g.is_accessible()
    ]


@router.get("/galleries/{gallery_id}/cover")
def gallery_cover(gallery_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    """Serve the designated cover photo for a gallery, no authentication required.

    Only accessible when: gallery is published, not expired, and has a cover photo set.
    """
    gallery = db.get(Gallery, gallery_id)
    if gallery is None or not gallery.is_accessible() or gallery.cover_photo_id is None:
        raise HTTPException(status_code=404, detail="no cover photo")
    photo = db.get(Photo, gallery.cover_photo_id)
    if photo is None or photo.r2_key_web is None:
        raise HTTPException(status_code=404, detail="cover photo not available")
    data = storage.download_bytes(photo.r2_key_web)
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "public, max-age=300"},
    )


def _load_accessible_gallery(db: Session, gallery_id: uuid.UUID) -> Gallery:
    gallery = db.get(Gallery, gallery_id)
    if gallery is None or not gallery.is_accessible():
        # Unpublished/expired/missing all look identical to the client.
        raise HTTPException(status_code=404, detail="gallery not available")
    return gallery


@router.post("/access/{gallery_id}", response_model=GalleryAccessResponse)
def access_gallery(
    gallery_id: uuid.UUID,
    payload: GalleryAccessRequest,
    db: Session = Depends(get_db),
) -> GalleryAccessResponse:
    gallery = _load_accessible_gallery(db, gallery_id)
    if not verify_passcode(payload.passcode, gallery.passcode_hash):
        raise HTTPException(status_code=401, detail="invalid passcode")
    token, expires_in = issue_gallery_token(gallery.id)
    return GalleryAccessResponse(token=token, gallery_id=gallery.id, expires_in=expires_in)


@router.get("/me/gallery", response_model=GalleryOut)
def my_gallery(
    gallery_id: uuid.UUID = Depends(require_gallery_access),
    db: Session = Depends(get_db),
) -> Gallery:
    return _load_accessible_gallery(db, gallery_id)


@router.get("/me/photos", response_model=list[PhotoOut])
def my_photos(
    gallery_id: uuid.UUID = Depends(require_gallery_access),
    db: Session = Depends(get_db),
) -> list[Photo]:
    _load_accessible_gallery(db, gallery_id)  # re-check published/expiry each read
    stmt = (
        select(Photo)
        .where(Photo.gallery_id == gallery_id, Photo.status == PhotoStatus.ready)
        .order_by(Photo.created_at)
    )
    return list(db.execute(stmt).scalars())


@router.get("/me/photos/{photo_id}", response_model=PhotoOut)
def my_photo(
    photo_id: uuid.UUID,
    gallery_id: uuid.UUID = Depends(require_gallery_access),
    db: Session = Depends(get_db),
) -> Photo:
    _load_accessible_gallery(db, gallery_id)
    photo = db.get(Photo, photo_id)
    # Ownership check: anything not in *your* gallery is a 404, full stop.
    if photo is None or photo.gallery_id != gallery_id or photo.status != PhotoStatus.ready:
        raise HTTPException(status_code=404, detail="photo not found")
    return photo


@router.get("/me/photos/{photo_id}/url", response_model=PhotoURLOut)
def my_photo_url(
    photo_id: uuid.UUID,
    gallery_id: uuid.UUID = Depends(require_gallery_access),
    db: Session = Depends(get_db),
) -> PhotoURLOut:
    """Return a short-lived presigned GET URL for the web-res derivative.

    A new URL is generated on every call — no long-lived URLs are ever persisted.
    """
    _load_accessible_gallery(db, gallery_id)
    photo = db.get(Photo, photo_id)
    if photo is None or photo.gallery_id != gallery_id or photo.status != PhotoStatus.ready:
        raise HTTPException(status_code=404, detail="photo not found")
    if photo.r2_key_web is None:
        raise HTTPException(status_code=503, detail="photo not yet available")

    settings = get_settings()
    url = storage.presigned_get(photo.r2_key_web, settings.presigned_get_ttl)
    return PhotoURLOut(url=url, expires_in=settings.presigned_get_ttl)


@router.get("/me/photos/{photo_id}/data")
def my_photo_data(
    photo_id: uuid.UUID,
    gallery_id: uuid.UUID = Depends(require_gallery_access),
    db: Session = Depends(get_db),
) -> Response:
    """Stream the web-res image bytes directly from storage.

    Simpler than presigned URLs for local dev and behind-proxy deployments —
    the browser never needs to reach storage directly.
    """
    _load_accessible_gallery(db, gallery_id)
    photo = db.get(Photo, photo_id)
    if photo is None or photo.gallery_id != gallery_id or photo.status != PhotoStatus.ready:
        raise HTTPException(status_code=404, detail="photo not found")
    if photo.r2_key_web is None:
        raise HTTPException(status_code=503, detail="photo not yet available")

    data = storage.download_bytes(photo.r2_key_web)
    return Response(content=data, media_type="image/jpeg", headers={
        "Cache-Control": "private, max-age=300",
    })


# ---- M5: face pipeline ----

def _require_consent(gallery_id: uuid.UUID, db: Session) -> None:
    """Raise 403 if the gallery's client has not given biometric consent."""
    gallery = db.get(Gallery, gallery_id)
    if gallery is None:
        raise HTTPException(status_code=404, detail="gallery not available")
    client = db.get(Client, gallery.client_id)
    if client is None or not client.consent_biometric:
        raise HTTPException(
            status_code=403,
            detail="face features require biometric consent",
        )


@router.get("/me/photos/{photo_id}/faces", response_model=list[FaceOut])
def photo_faces(
    photo_id: uuid.UUID,
    gallery_id: uuid.UUID = Depends(require_gallery_access),
    db: Session = Depends(get_db),
) -> list[Face]:
    """List detected face regions (bounding boxes + cluster assignment) for one photo."""
    _load_accessible_gallery(db, gallery_id)
    _require_consent(gallery_id, db)
    photo = db.get(Photo, photo_id)
    if photo is None or photo.gallery_id != gallery_id or photo.status != PhotoStatus.ready:
        raise HTTPException(status_code=404, detail="photo not found")
    return list(
        db.execute(select(Face).where(Face.photo_id == photo_id).order_by(Face.bbox_x)).scalars()
    )


@router.get("/me/clusters", response_model=list[ClusterOut])
def my_clusters(
    gallery_id: uuid.UUID = Depends(require_gallery_access),
    db: Session = Depends(get_db),
) -> list[ClusterOut]:
    """Return one entry per identity cluster in this gallery (the 'people row').

    Clusters are assembled from Face rows with a non-null, non-negative cluster_id.
    Run POST /admin/galleries/{id}/cluster first to populate cluster assignments.
    """
    _load_accessible_gallery(db, gallery_id)
    _require_consent(gallery_id, db)

    rows = db.execute(
        select(Face)
        .where(Face.gallery_id == gallery_id, Face.cluster_id >= 0)
        .order_by(Face.cluster_id, Face.created_at)
    ).scalars().all()

    grouped: dict[int, list[Face]] = defaultdict(list)
    for face in rows:
        grouped[face.cluster_id].append(face)

    return [
        ClusterOut(
            cluster_id=cid,
            face_count=len(faces),
            representative_photo_id=faces[0].photo_id,
        )
        for cid, faces in sorted(grouped.items())
    ]


@router.get("/me/photos/by-cluster/{cluster_id}", response_model=list[PhotoOut])
def photos_by_cluster(
    cluster_id: int,
    gallery_id: uuid.UUID = Depends(require_gallery_access),
    db: Session = Depends(get_db),
) -> list[Photo]:
    """Return all ready photos that contain at least one face in this cluster."""
    _load_accessible_gallery(db, gallery_id)
    _require_consent(gallery_id, db)

    photo_ids = db.execute(
        select(Face.photo_id)
        .where(Face.gallery_id == gallery_id, Face.cluster_id == cluster_id)
        .distinct()
    ).scalars().all()

    if not photo_ids:
        return []

    return list(
        db.execute(
            select(Photo)
            .where(
                Photo.id.in_(photo_ids),
                Photo.status == PhotoStatus.ready,
            )
            .order_by(Photo.created_at)
        ).scalars()
    )


@router.post("/me/search/by-face/{face_id}", response_model=list[FaceSearchResult])
def search_by_face(
    face_id: uuid.UUID,
    gallery_id: uuid.UUID = Depends(require_gallery_access),
    db: Session = Depends(get_db),
) -> list[FaceSearchResult]:
    """Find photos similar to a stored face embedding (cosine distance, pgvector).

    The query face must belong to the authenticated gallery — this is enforced
    by checking Face.gallery_id. The search itself is also scoped to the same
    gallery, so a client can never reach embeddings from another gallery.
    """
    _load_accessible_gallery(db, gallery_id)
    _require_consent(gallery_id, db)

    face = db.get(Face, face_id)
    if face is None or face.gallery_id != gallery_id:
        raise HTTPException(status_code=404, detail="face not found")
    if face.embedding is None:
        raise HTTPException(status_code=422, detail="face has no embedding yet")

    settings = get_settings()
    results = _face_search_mod.cosine_search(
        db=db,
        gallery_id=gallery_id,
        embedding=face.embedding,
        top_k=settings.face_search_top_k,
        threshold=settings.face_cosine_threshold,
    )
    return [FaceSearchResult(photo_id=photo_id, distance=distance) for photo_id, distance in results]
