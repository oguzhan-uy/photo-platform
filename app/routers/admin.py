"""Photographer (admin) endpoints. All require the admin bearer token."""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from fastapi.responses import Response
from rq import Retry
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app import storage
from app.context import request_id_var
from app.db import get_db
from app.models import Client, DeletionLog, Face, Gallery, Photo, PhotoStatus
from app.redis_client import task_queue
from app.schemas import (
    ClientCreate,
    ClientDeleteOut,
    ClientOut,
    ConsentUpdate,
    DeletionLogOut,
    GalleryCreate,
    GalleryOut,
    PhotoConfirmOut,
    PhotoOut,
    SetCoverIn,
)
from app.security import hash_passcode, require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/clients", response_model=ClientOut, status_code=201)
def create_client(payload: ClientCreate, db: Session = Depends(get_db)) -> Client:
    client = Client(display_name=payload.display_name, contact=payload.contact)
    db.add(client)
    db.commit()
    db.refresh(client)
    return client


@router.get("/clients", response_model=list[ClientOut])
def list_clients(db: Session = Depends(get_db)) -> list[Client]:
    return list(db.execute(select(Client).order_by(Client.created_at)).scalars())


@router.delete("/clients/{client_id}", response_model=ClientDeleteOut)
def delete_client(
    client_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> ClientDeleteOut:
    """Hard-delete a client and all their data (GDPR Article 17 right to erasure).

    Purges in order: R2 objects → Face rows → Photo rows → Gallery rows → Client row.
    Writes a DeletionLog entry and returns a deletion receipt with exact counts.
    """
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")

    gallery_ids = list(
        db.execute(select(Gallery.id).where(Gallery.client_id == client_id)).scalars()
    )

    photo_count = 0
    face_count = 0
    r2_keys: list[str] = []

    if gallery_ids:
        face_count = db.execute(
            select(func.count(Face.id)).where(Face.gallery_id.in_(gallery_ids))
        ).scalar_one()

        photos = list(
            db.execute(
                select(Photo.id, Photo.r2_key_original, Photo.r2_key_web)
                .where(Photo.gallery_id.in_(gallery_ids))
            ).all()
        )
        photo_count = len(photos)
        for _pid, orig_key, web_key in photos:
            if orig_key:
                r2_keys.append(orig_key)
            if web_key:
                r2_keys.append(web_key)

    r2_deleted = storage.delete_objects(r2_keys)

    # Delete in dependency order so this works on SQLite (no DB-level CASCADE in tests).
    if gallery_ids:
        db.execute(delete(Face).where(Face.gallery_id.in_(gallery_ids)))
        photo_ids = [row[0] for row in photos] if photo_count else []
        if photo_ids:
            db.execute(delete(Photo).where(Photo.id.in_(photo_ids)))
        db.execute(delete(Gallery).where(Gallery.client_id == client_id))
    db.execute(delete(Client).where(Client.id == client_id))

    db.add(DeletionLog(
        event_type="client_delete",
        target_type="client",
        target_id=client_id,
        purged_photos=photo_count,
        purged_faces=face_count,
        purged_r2_objects=r2_deleted,
        executed_by="admin",
    ))
    db.commit()

    return ClientDeleteOut(
        client_id=client_id,
        purged_galleries=len(gallery_ids),
        purged_photos=photo_count,
        purged_faces=face_count,
        purged_r2_objects=r2_deleted,
    )


@router.post("/galleries", response_model=GalleryOut, status_code=201)
def create_gallery(payload: GalleryCreate, db: Session = Depends(get_db)) -> Gallery:
    client = db.get(Client, payload.client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")
    gallery = Gallery(
        client_id=payload.client_id,
        title=payload.title,
        passcode_hash=hash_passcode(payload.passcode),
        published=payload.published,
        expires_at=payload.expires_at,
    )
    db.add(gallery)
    db.commit()
    db.refresh(gallery)
    return gallery


@router.get("/galleries", response_model=list[GalleryOut])
def list_galleries(db: Session = Depends(get_db)) -> list[Gallery]:
    return list(db.execute(select(Gallery).order_by(Gallery.created_at)).scalars())


@router.get("/galleries/{gallery_id}/photos", response_model=list[PhotoOut])
def list_gallery_photos(gallery_id: uuid.UUID, db: Session = Depends(get_db)) -> list[Photo]:
    gallery = db.get(Gallery, gallery_id)
    if gallery is None:
        raise HTTPException(status_code=404, detail="gallery not found")
    return list(db.execute(select(Photo).where(Photo.gallery_id == gallery_id).order_by(Photo.created_at)).scalars())



@router.delete("/galleries/{gallery_id}/photos", status_code=200)
def delete_all_photos(
    gallery_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Delete every photo in a gallery: R2 objects, Face rows, then Photo rows."""
    rows = db.execute(
        select(Photo.id, Photo.r2_key_original, Photo.r2_key_web)
        .where(Photo.gallery_id == gallery_id)
    ).all()

    keys = [k for r in rows for k in (r.r2_key_original, r.r2_key_web) if k]
    if keys:
        storage.delete_objects(keys)

    photo_ids = [r.id for r in rows]
    if photo_ids:
        db.execute(delete(Face).where(Face.photo_id.in_(photo_ids)))
        db.execute(delete(Photo).where(Photo.gallery_id == gallery_id))
        db.commit()

    return {"deleted": len(photo_ids)}


@router.delete("/photos/{photo_id}", status_code=204)
def delete_photo(
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> None:
    """Delete a single photo: remove R2 objects, Face rows, then the Photo row."""
    photo = db.get(Photo, photo_id)
    if photo is None:
        raise HTTPException(status_code=404, detail="photo not found")

    keys = [k for k in (photo.r2_key_original, photo.r2_key_web) if k]
    if keys:
        storage.delete_objects(keys)

    db.execute(delete(Face).where(Face.photo_id == photo_id))
    db.execute(delete(Photo).where(Photo.id == photo_id))
    db.commit()


@router.patch("/clients/{client_id}/consent", response_model=ClientOut)
def update_consent(
    client_id: uuid.UUID,
    payload: ConsentUpdate,
    db: Session = Depends(get_db),
) -> Client:
    """Grant or revoke biometric consent for a client.

    On revocation (consent_biometric=False), all Face rows for every gallery
    belonging to this client are hard-deleted immediately — embeddings are
    special-category biometric data under GDPR/KVKK and must be purged on
    withdrawal of consent, while the non-biometric gallery remains intact.
    A DeletionLog entry is written to provide a verifiable audit record.
    """
    client = db.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="client not found")

    was_consenting = client.consent_biometric
    client.consent_biometric = payload.consent_biometric
    client.consent_biometric_at = datetime.now(timezone.utc) if payload.consent_biometric else None

    face_count = 0
    if was_consenting and not payload.consent_biometric:
        gallery_ids = list(
            db.execute(select(Gallery.id).where(Gallery.client_id == client_id)).scalars()
        )
        if gallery_ids:
            face_count = db.execute(
                select(func.count(Face.id)).where(Face.gallery_id.in_(gallery_ids))
            ).scalar_one()
            db.execute(delete(Face).where(Face.gallery_id.in_(gallery_ids)))

        db.add(DeletionLog(
            event_type="consent_revoke",
            target_type="client",
            target_id=client_id,
            purged_photos=0,
            purged_faces=face_count,
            purged_r2_objects=0,
            executed_by="admin",
        ))

    db.commit()
    db.refresh(client)
    return client


@router.post(
    "/galleries/{gallery_id}/photos/upload",
    response_model=PhotoConfirmOut,
    status_code=201,
)
async def upload_photo(
    gallery_id: uuid.UUID,
    file: UploadFile,
    db: Session = Depends(get_db),
) -> PhotoConfirmOut:
    """Accept a file upload directly, push to storage, and enqueue ingest."""
    gallery = db.get(Gallery, gallery_id)
    if gallery is None:
        raise HTTPException(status_code=404, detail="gallery not found")

    photo_id = uuid.uuid4()
    r2_key = f"originals/{gallery_id}/{photo_id}"
    content_type = file.content_type or "image/jpeg"

    data = await file.read()
    storage.upload_bytes(r2_key, data, content_type)

    photo = Photo(
        id=photo_id,
        gallery_id=gallery_id,
        r2_key_original=r2_key,
        status=PhotoStatus.processing,
    )
    db.add(photo)
    db.commit()

    job = task_queue.enqueue(
        "worker.jobs.ingest.ingest_photo",
        str(photo_id),
        job_timeout=300,
        retry=Retry(max=3, interval=[10, 60, 300]),
        meta={"request_id": request_id_var.get("")},
    )
    return PhotoConfirmOut(photo_id=photo_id, status=photo.status, job_id=job.id)


@router.delete("/galleries/{gallery_id}/faces", status_code=200)
def reset_gallery_faces(
    gallery_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Delete all face rows for a gallery and re-enqueue embedding for every ready photo.

    Use this to start face detection from scratch (e.g. after consent changes or bad data).
    """
    gallery = db.get(Gallery, gallery_id)
    if gallery is None:
        raise HTTPException(status_code=404, detail="gallery not found")

    deleted = db.execute(
        delete(Face).where(Face.gallery_id == gallery_id)
    ).rowcount
    db.commit()

    photos = db.execute(
        select(Photo).where(
            Photo.gallery_id == gallery_id,
            Photo.status == PhotoStatus.ready,
        )
    ).scalars().all()

    for photo in photos:
        task_queue.enqueue(
            "worker.jobs.embed.embed_photo_faces",
            str(photo.id),
            job_id=f"embed-{photo.id}",
            job_timeout=600,
            retry=Retry(max=3, interval=[30, 120, 600]),
        )

    return {"deleted_faces": deleted, "embed_jobs_queued": len(photos)}


@router.post("/galleries/{gallery_id}/cluster", status_code=202)
def trigger_cluster(
    gallery_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> dict:
    """Enqueue HDBSCAN clustering for all face embeddings in a gallery.

    Run this once after bulk-ingesting and embedding a full shoot to build the
    cluster_id assignments that power the 'people row' on the client gallery.
    Safe to re-run; clustering is fully idempotent.
    """
    gallery = db.get(Gallery, gallery_id)
    if gallery is None:
        raise HTTPException(status_code=404, detail="gallery not found")

    job = task_queue.enqueue(
        "worker.jobs.cluster.cluster_gallery_faces",
        str(gallery_id),
        job_timeout=600,
        retry=Retry(max=2, interval=[60, 300]),
    )
    return {"job_id": job.id, "gallery_id": str(gallery_id)}



@router.post("/expire-galleries", status_code=202)
def trigger_expire_galleries() -> dict:
    """Enqueue the gallery expiry job.

    Safe to call multiple times — the job checks expiry timestamps at runtime,
    so re-enqueueing when no galleries have expired is a no-op.
    """
    job = task_queue.enqueue(
        "worker.jobs.expire.expire_galleries",
        job_timeout=600,
        retry=Retry(max=2, interval=[60, 300]),
    )
    return {"job_id": job.id}


@router.get("/deletion-log", response_model=list[DeletionLogOut])
def list_deletion_log(
    db: Session = Depends(get_db),
    limit: int = 100,
) -> list[DeletionLog]:
    """Return the compliance deletion audit log, most recent first."""
    return list(
        db.execute(
            select(DeletionLog).order_by(DeletionLog.created_at.desc()).limit(limit)
        ).scalars()
    )


@router.patch("/galleries/{gallery_id}/cover", status_code=200)
def set_gallery_cover(
    gallery_id: uuid.UUID,
    payload: SetCoverIn,
    db: Session = Depends(get_db),
) -> dict:
    """Set the cover photo for a gallery (shown blurred on the public landing page)."""
    gallery = db.get(Gallery, gallery_id)
    if gallery is None:
        raise HTTPException(status_code=404, detail="gallery not found")
    photo = db.get(Photo, payload.photo_id)
    if photo is None or photo.gallery_id != gallery_id or photo.status != PhotoStatus.ready:
        raise HTTPException(status_code=404, detail="photo not found in this gallery")
    gallery.cover_photo_id = payload.photo_id
    db.commit()
    return {"gallery_id": str(gallery_id), "cover_photo_id": str(payload.photo_id)}


@router.get("/galleries/{gallery_id}/photos/{photo_id}/data")
def admin_photo_data(
    gallery_id: uuid.UUID,
    photo_id: uuid.UUID,
    db: Session = Depends(get_db),
) -> Response:
    """Stream photo bytes for admin thumbnail preview (admin auth required)."""
    photo = db.get(Photo, photo_id)
    if photo is None or photo.gallery_id != gallery_id or photo.status != PhotoStatus.ready:
        raise HTTPException(status_code=404, detail="photo not found")
    if photo.r2_key_web is None:
        raise HTTPException(status_code=503, detail="photo not yet available")
    data = storage.download_bytes(photo.r2_key_web)
    return Response(
        content=data,
        media_type="image/jpeg",
        headers={"Cache-Control": "private, max-age=300"},
    )
