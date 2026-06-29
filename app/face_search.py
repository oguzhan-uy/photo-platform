"""pgvector cosine-distance face search, isolated for easy mocking in tests.

All callers import and call `cosine_search` directly; tests monkeypatch this
module-level function so they never exercise Postgres-specific SQL on SQLite.

The query finds, per photo, the closest face to the query embedding within the
gallery. It deduplicates by photo_id (a photo with multiple faces returns only
the best-matching face distance), which is what the client UX wants.

The HNSW index (created in migration 0004) makes this query fast even for
galleries with thousands of faces.
"""
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def cosine_search(
    db: "Session",
    gallery_id: uuid.UUID,
    embedding,
    top_k: int,
    threshold: float,
) -> list[tuple[uuid.UUID, float]]:
    """Return [(photo_id, distance), ...] sorted by distance ascending.

    Args:
        db: SQLAlchemy session (must be connected to Postgres with pgvector).
        gallery_id: Scope search to this gallery only.
        embedding: Query embedding — numpy array, list of floats, or any
                   value accepted by pgvector's vector cast.
        top_k: Maximum number of distinct photos to return.
        threshold: Maximum cosine distance to include (0–2, smaller = more similar).

    Postgres-only. Do not call on SQLite — tests mock this function instead.
    """
    from sqlalchemy import text  # noqa: PLC0415

    if hasattr(embedding, "tolist"):
        embedding = embedding.tolist()
    vec_str = "[" + ",".join(str(v) for v in embedding) + "]"

    rows = db.execute(
        text("""
            SELECT photo_id::text, MIN(embedding <=> :vec::vector) AS distance
            FROM face
            WHERE gallery_id = :gid::uuid
            GROUP BY photo_id
            HAVING MIN(embedding <=> :vec::vector) <= :threshold
            ORDER BY distance
            LIMIT :top_k
        """),
        {
            "vec": vec_str,
            "gid": str(gallery_id),
            "threshold": threshold,
            "top_k": top_k,
        },
    ).fetchall()

    return [(uuid.UUID(row.photo_id), float(row.distance)) for row in rows]
