"""HDBSCAN clustering job for face identities within a gallery.

Run this after embedding all photos in a gallery (triggered explicitly by the
admin via POST /admin/galleries/{id}/cluster — not auto-triggered per embed, to
avoid thundering-herd when batch-ingesting a large shoot).

HDBSCAN groups faces by identity, assigning each Face a cluster_id (-1 = noise).
Cluster IDs power the "show all photos of this person" feature on the client UI.
Re-running is safe and fully idempotent — cluster IDs are simply overwritten.

ArcFace embeddings are L2-normalised, so Euclidean distance in embedding space
is proportional to cosine distance. HDBSCAN with metric="euclidean" is therefore
correct and avoids an extra normalisation step.
"""
import logging
import time
import uuid

import numpy as np
from sqlalchemy import select, update

from app.config import get_settings
from app.db import SessionLocal
from app.metrics import job_duration_seconds, job_total
from app.models import Face, Gallery, JobAudit

log = logging.getLogger("worker.cluster")


def cluster_gallery_faces(gallery_id: str) -> None:
    """RQ entry point. Re-cluster all faces in a gallery."""
    gid = uuid.UUID(gallery_id)
    start = time.perf_counter()

    with SessionLocal() as db:
        gallery = db.get(Gallery, gid)
        if gallery is None:
            log.error("cluster called for unknown gallery", extra={"extra_fields": {"gallery_id": gallery_id}})
            return

        try:
            n_faces, n_clusters = _cluster(gid, db)
            elapsed = time.perf_counter() - start
            job_total.labels("cluster", "success").inc()
            job_duration_seconds.labels("cluster").observe(elapsed)
            _write_audit(db, gid, "cluster", "success", None)
            log.info(
                "clustering complete",
                extra={
                    "extra_fields": {
                        "gallery_id": gallery_id,
                        "faces": n_faces,
                        "clusters": n_clusters,
                    }
                },
            )
        except Exception as exc:
            elapsed = time.perf_counter() - start
            reason = f"{type(exc).__name__}: {exc}"
            log.exception("clustering failed", extra={"extra_fields": {"gallery_id": gallery_id}})
            job_total.labels("cluster", "failed").inc()
            job_duration_seconds.labels("cluster").observe(elapsed)
            _write_audit(db, gid, "cluster", "failed", reason)
            raise


def _cluster(gallery_id: uuid.UUID, db) -> tuple[int, int]:
    """Load embeddings, run HDBSCAN, write cluster_id back. Returns (n_faces, n_clusters)."""
    from sklearn.cluster import HDBSCAN  # noqa: PLC0415

    rows = db.execute(
        select(Face.id, Face.embedding)
        .where(Face.gallery_id == gallery_id, Face.embedding.isnot(None))
    ).all()

    if not rows:
        return 0, 0

    face_ids = [r.id for r in rows]
    embeddings = np.stack([_to_array(r.embedding) for r in rows])

    settings = get_settings()
    min_size = max(2, settings.face_min_cluster_size)

    if len(embeddings) < min_size:
        labels = np.full(len(embeddings), -1, dtype=int)
    else:
        clusterer = HDBSCAN(min_cluster_size=min_size, metric="euclidean", store_centers="centroid")
        labels = clusterer.fit_predict(embeddings)

    # Promote noise faces (label -1) to solo clusters so they appear in the
    # people row instead of being silently dropped. Assign IDs above the
    # highest HDBSCAN cluster ID so they don't collide.
    next_id = int(labels.max()) + 1 if (labels >= 0).any() else 0
    for i, label in enumerate(labels):
        if label == -1:
            labels[i] = next_id
            next_id += 1

    # Write labels back.
    for face_id, label in zip(face_ids, labels):
        db.execute(
            update(Face).where(Face.id == face_id).values(cluster_id=int(label))
        )
    db.commit()

    n_clusters = len(set(l for l in labels if l >= 0))
    return len(face_ids), n_clusters


def _to_array(embedding) -> np.ndarray:
    """Accept numpy array, list, or JSON string (SQLite fallback)."""
    if isinstance(embedding, np.ndarray):
        return embedding.astype(np.float32)
    if isinstance(embedding, (list, tuple)):
        return np.array(embedding, dtype=np.float32)
    # JSON string stored by the SQLite Text fallback in tests.
    import json  # noqa: PLC0415
    return np.array(json.loads(embedding), dtype=np.float32)


def _write_audit(db, gallery_id: uuid.UUID, job_type: str, status: str, error: str | None) -> None:
    db.add(JobAudit(job_type=job_type, target_id=gallery_id, status=status, last_error=error))
    db.commit()
