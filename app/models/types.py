"""SQLAlchemy column types that work on both Postgres (pgvector) and SQLite (tests)."""


def _embedding_type():
    """Return Vector(512) on Postgres or Text on SQLite/test environments."""
    try:
        from pgvector.sqlalchemy import Vector
        return Vector(512)
    except ImportError:
        from sqlalchemy import Text
        return Text()


EMBEDDING_TYPE = _embedding_type()
EMBEDDING_DIMS = 512
