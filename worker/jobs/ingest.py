"""Photo ingest job: hash → dedup → thumbnail → mark ready → (optionally) embed faces.

Called by RQ after the admin confirms an upload. Designed to be:
- Idempotent: re-running on an already-ready photo is a no-op.
- Deduplicating: two uploads with the same content hash in one gallery → the
  second is marked failed with a clear reason rather than silently duplicated.
- Dead-lettered on error: any unhandled exception sets status=failed with a
  failure_reason and writes a JobAudit row so the photographer can see exactly
  what went wrong.

After a photo is marked ready, the job checks whether the gallery's client has
given biometric consent (consent_biometric=True). If so, it enqueues the
embed_photo_faces job. This check keeps existing tests working without change:
the test helper creates clients with consent_biometric=False (the default), so
no Redis call is made and no mocking is required in the existing test suite.

Observability:
- Picks up the request_id from RQ job.meta so worker log lines share the same
  correlation ID as the originating HTTP request.
- Records photo_job_total{status} and photo_job_duration_seconds counters for
  Prometheus.
"""
import hashlib
import io
import logging
import time
import uuid

from PIL import Image
from sqlalchemy import select

from app import storage
from app.context import request_id_var
from app.db import SessionLocal
from app.metrics import job_duration_seconds, job_total
from app.models import Client, Gallery, JobAudit, Photo, PhotoStatus
from app.redis_client import task_queue

log = logging.getLogger("worker.ingest")

WEB_MAX_PX = 2000       # longest side of the web-resolution derivative
WEB_JPEG_QUALITY = 85


def ingest_photo(photo_id: str) -> None:
    """RQ entry point. Accepts photo_id as a string (RQ serialises args as JSON)."""
    # Propagate the correlation ID from the enqueueing HTTP request into this job.
    try:
        from rq import get_current_job
        job = get_current_job()
        if job and job.meta.get("request_id"):
            request_id_var.set(job.meta["request_id"])
    except Exception:
        pass

    pid = uuid.UUID(photo_id)
    start = time.perf_counter()

    with SessionLocal() as db:
        photo = db.get(Photo, pid)
        if photo is None:
            log.error("ingest called for unknown photo", extra={"extra_fields": {"photo_id": photo_id}})
            return

        if photo.status == PhotoStatus.ready:
            log.info("photo already ready, skipping", extra={"extra_fields": {"photo_id": photo_id}})
            return

        try:
            _process(photo, db)
            elapsed = time.perf_counter() - start
            job_total.labels("ingest", "success").inc()
            job_duration_seconds.labels("ingest").observe(elapsed)
            _write_audit(db, pid, "ingest", "success", None)
            _maybe_enqueue_embed(photo, db)
        except Exception as exc:
            elapsed = time.perf_counter() - start
            reason = f"{type(exc).__name__}: {exc}"
            log.exception(
                "ingest failed",
                extra={"extra_fields": {"photo_id": photo_id, "reason": reason}},
            )
            photo.status = PhotoStatus.failed
            photo.failure_reason = reason
            db.commit()
            job_total.labels("ingest", "failed").inc()
            job_duration_seconds.labels("ingest").observe(elapsed)
            _write_audit(db, pid, "ingest", "failed", reason)
            raise   # re-raise so RQ can apply retry policy


def _process(photo: Photo, db) -> None:
    raw = storage.download_bytes(photo.r2_key_original)
    content_hash = hashlib.sha256(raw).hexdigest()

    # Dedup: if another *ready* photo in the same gallery already has this hash,
    # mark this one as a duplicate rather than storing identical bytes twice.
    existing = db.execute(
        select(Photo).where(
            Photo.gallery_id == photo.gallery_id,
            Photo.content_hash == content_hash,
            Photo.status == PhotoStatus.ready,
            Photo.id != photo.id,
        )
    ).scalar_one_or_none()
    if existing is not None:
        photo.status = PhotoStatus.failed
        photo.failure_reason = f"duplicate of photo {existing.id}"
        photo.content_hash = content_hash
        db.commit()
        log.warning(
            "duplicate photo detected",
            extra={"extra_fields": {"photo_id": str(photo.id), "existing_id": str(existing.id)}},
        )
        return

    img = Image.open(io.BytesIO(raw))
    width, height = img.size
    web_img = _resize(img)
    web_bytes = _encode_jpeg(web_img)

    web_key = f"web/{photo.gallery_id}/{photo.id}.jpg"
    storage.upload_bytes(web_key, web_bytes, "image/jpeg")

    photo.content_hash = content_hash
    photo.r2_key_web = web_key
    photo.width = width
    photo.height = height
    photo.status = PhotoStatus.ready
    photo.failure_reason = None
    db.commit()

    log.info(
        "ingest complete",
        extra={
            "extra_fields": {
                "photo_id": str(photo.id),
                "content_hash": content_hash,
                "dimensions": f"{width}x{height}",
            }
        },
    )


def _resize(img: Image.Image) -> Image.Image:
    w, h = img.size
    if max(w, h) <= WEB_MAX_PX:
        return img
    scale = WEB_MAX_PX / max(w, h)
    return img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)


def _encode_jpeg(img: Image.Image) -> bytes:
    if img.mode not in ("RGB", "L"):
        img = img.convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=WEB_JPEG_QUALITY, optimize=True)
    return buf.getvalue()


def _maybe_enqueue_embed(photo: Photo, db) -> None:
    """Enqueue the face-embedding job if the gallery's client has biometric consent.

    Only called after a successful ingest. If consent is absent (the default),
    this is a no-op and does not touch Redis — so the existing test suite passes
    without any additional mocking.
    """
    gallery = db.get(Gallery, photo.gallery_id)
    if gallery is None:
        return
    client = db.get(Client, gallery.client_id)
    if client is None or not client.consent_biometric:
        return

    from rq import Retry  # noqa: PLC0415

    task_queue.enqueue(
        "worker.jobs.embed.embed_photo_faces",
        str(photo.id),
        job_id=f"embed-{photo.id}",  # deduplicate: same photo → same job ID
        job_timeout=600,
        retry=Retry(max=3, interval=[30, 120, 600]),
    )
    log.info("embed job enqueued", extra={"extra_fields": {"photo_id": str(photo.id)}})


def _write_audit(db, photo_id: uuid.UUID, job_type: str, status: str, error: str | None) -> None:
    db.add(JobAudit(job_type=job_type, target_id=photo_id, status=status, last_error=error))
    db.commit()
