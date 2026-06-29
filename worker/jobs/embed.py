"""Face detection and embedding job.

Enqueued by the ingest job after a photo is marked ready, but ONLY when the
gallery's client has biometric consent (consent_biometric=True). Consent is
re-checked at job execution time to handle revocation between enqueue and run.

Design decisions:
- InsightFace is loaded once per worker process (module-level singleton) — the
  model is ~300 MB and takes ~5 s to load; subsequent calls are fast (~50 ms).
- The embedding column stores ArcFace 512-d float32 vectors (L2-normalised).
- If no faces are detected, no Face rows are written — the job succeeds silently.
- Idempotent: re-running on a photo that already has faces clears and re-inserts
  them so ingest retries are safe.
"""
import logging
import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import storage
from app.context import request_id_var
from app.db import SessionLocal
from app.metrics import job_duration_seconds, job_total
from app.models import Client, Face, Gallery, JobAudit, Photo, PhotoStatus

log = logging.getLogger("worker.embed")

# Module-level InsightFace singleton; loaded lazily on first job execution.
_face_app = None


def _get_face_app():
    """Return the InsightFace analysis app, loading it on first call."""
    global _face_app
    if _face_app is not None:
        return _face_app

    # Lazy import so the module can be imported without insightface installed
    # (e.g. in the test environment).
    import insightface  # noqa: PLC0415
    from app.config import get_settings  # noqa: PLC0415

    s = get_settings()
    log.info("loading InsightFace model", extra={"extra_fields": {"model": s.face_model}})
    app = insightface.app.FaceAnalysis(
        name=s.face_model,
        root=s.face_model_cache_dir,
        providers=["CPUExecutionProvider"],
    )
    app.prepare(ctx_id=-1)  # -1 = CPU
    _face_app = app
    log.info("InsightFace model ready")
    return _face_app


def embed_photo_faces(photo_id: str) -> None:
    """RQ entry point. Detect and embed all faces in one photo."""
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
            log.error("embed called for unknown photo", extra={"extra_fields": {"photo_id": photo_id}})
            return
        if photo.status != PhotoStatus.ready:
            log.warning(
                "embed called for non-ready photo, skipping",
                extra={"extra_fields": {"photo_id": photo_id, "status": photo.status}},
            )
            return

        # Re-check consent — it may have been revoked between enqueue and now.
        gallery = db.get(Gallery, photo.gallery_id)
        if gallery is None:
            return
        client = db.get(Client, gallery.client_id)
        if client is None or not client.consent_biometric:
            log.info(
                "biometric consent absent, skipping embed",
                extra={"extra_fields": {"photo_id": photo_id}},
            )
            return

        try:
            n_faces = _process(photo, db)
            elapsed = time.perf_counter() - start
            job_total.labels("embed", "success").inc()
            job_duration_seconds.labels("embed").observe(elapsed)
            _write_audit(db, pid, "embed", "success", None)
            log.info(
                "embed complete",
                extra={"extra_fields": {"photo_id": photo_id, "faces_detected": n_faces}},
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start
            reason = f"{type(exc).__name__}: {exc}"
            log.exception("embed failed", extra={"extra_fields": {"photo_id": photo_id}})
            job_total.labels("embed", "failed").inc()
            job_duration_seconds.labels("embed").observe(elapsed)
            _write_audit(db, pid, "embed", "failed", reason)
            raise


def _process(photo: Photo, db: Session) -> int:
    """Detect faces, write Face rows. Returns the number of faces detected."""
    import cv2  # noqa: PLC0415
    import numpy as np  # noqa: PLC0415

    # Download the web-res derivative (smaller, faster to process than original).
    key = photo.r2_key_web or photo.r2_key_original
    raw = storage.download_bytes(key)

    nparr = np.frombuffer(raw, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
    if img is None:
        log.warning("could not decode image", extra={"extra_fields": {"photo_id": str(photo.id)}})
        return 0

    face_app = _get_face_app()
    detected = face_app.get(img)

    # Idempotent: clear any existing Face rows before re-inserting.
    existing = db.execute(select(Face).where(Face.photo_id == photo.id)).scalars().all()
    for f in existing:
        db.delete(f)
    db.flush()

    for face in detected:
        x1, y1, x2, y2 = face.bbox.astype(int)
        row = Face(
            photo_id=photo.id,
            gallery_id=photo.gallery_id,
            bbox_x=int(x1),
            bbox_y=int(y1),
            bbox_w=int(x2 - x1),
            bbox_h=int(y2 - y1),
            det_score=float(face.det_score),
            embedding=face.embedding,  # ndarray(512,), L2-normalised
        )
        db.add(row)

    db.commit()
    return len(detected)


def _write_audit(db: Session, photo_id: uuid.UUID, job_type: str, status: str, error: str | None) -> None:
    db.add(JobAudit(job_type=job_type, target_id=photo_id, status=status, last_error=error))
    db.commit()
