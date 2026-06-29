"""Gallery expiry job: hard-delete galleries past their expires_at deadline.

Called by RQ (enqueued via POST /admin/expire-galleries or a nightly cron entry
in docker-compose). Designed to be idempotent: re-running when no galleries have
expired is a no-op that takes milliseconds.

For each expired gallery the job:
  1. Collects R2 object keys for all photos (originals + web derivatives).
  2. Batch-deletes the R2 objects via S3 DeleteObjects.
  3. Hard-deletes Face, Photo, Gallery rows in dependency order (SQLite-safe).
  4. Writes a DeletionLog entry — verifiable receipt of what was purged and when.

GDPR/KVKK note: face embeddings are special-category biometric data subject to
retention limits. Deleting the gallery in step 3 purges all associated Face rows
before the gallery row itself, ensuring embeddings are erased on schedule.
"""
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import delete, func, select

from app import storage
from app.db import SessionLocal
from app.metrics import job_duration_seconds, job_total
from app.models import DeletionLog, Face, Gallery, Photo

log = logging.getLogger("worker.expire")


def expire_galleries() -> dict:
    """RQ entry point. Finds and purges all galleries whose expires_at has passed."""
    start = time.perf_counter()
    purged = 0

    with SessionLocal() as db:
        now = datetime.now(timezone.utc)
        expired = list(
            db.execute(
                select(Gallery).where(
                    Gallery.expires_at.is_not(None),
                    Gallery.expires_at <= now,
                )
            ).scalars()
        )

        for gallery in expired:
            try:
                _purge_gallery(gallery, db)
                purged += 1
            except Exception:
                log.exception(
                    "failed to purge gallery",
                    extra={"extra_fields": {"gallery_id": str(gallery.id)}},
                )

    elapsed = time.perf_counter() - start
    job_total.labels("expire_galleries", "success").inc()
    job_duration_seconds.labels("expire_galleries").observe(elapsed)
    log.info(
        "expiry run complete",
        extra={"extra_fields": {"purged": purged, "elapsed_s": round(elapsed, 3)}},
    )
    return {"purged": purged}


def _purge_gallery(gallery: Gallery, db) -> None:
    gid = gallery.id

    face_count = db.execute(
        select(func.count(Face.id)).where(Face.gallery_id == gid)
    ).scalar_one()

    photos = list(
        db.execute(
            select(Photo.id, Photo.r2_key_original, Photo.r2_key_web)
            .where(Photo.gallery_id == gid)
        ).all()
    )
    photo_count = len(photos)
    r2_keys = [k for _pid, orig, web in photos for k in (orig, web) if k]

    r2_deleted = storage.delete_objects(r2_keys)

    # Delete in dependency order for SQLite compatibility (no DB-level CASCADE in tests).
    db.execute(delete(Face).where(Face.gallery_id == gid))
    photo_ids = [row[0] for row in photos]
    if photo_ids:
        db.execute(delete(Photo).where(Photo.id.in_(photo_ids)))
    db.execute(delete(Gallery).where(Gallery.id == gid))

    db.add(DeletionLog(
        event_type="gallery_expire",
        target_type="gallery",
        target_id=gid,
        purged_photos=photo_count,
        purged_faces=face_count,
        purged_r2_objects=r2_deleted,
        executed_by="expiry_worker",
    ))
    db.commit()

    log.info(
        "gallery expired",
        extra={
            "extra_fields": {
                "gallery_id": str(gid),
                "photos": photo_count,
                "faces": face_count,
                "r2_objects": r2_deleted,
            }
        },
    )
