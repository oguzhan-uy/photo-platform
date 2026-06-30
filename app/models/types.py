"""SQLAlchemy column types that work on both Postgres (pgvector) and SQLite (tests)."""
import json

import numpy as np
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

EMBEDDING_DIMS = 512


class EmbeddingType(TypeDecorator):
    """Vector(512) on Postgres via pgvector; JSON-serialised Text on SQLite.

    Using a TypeDecorator lets us swap the underlying storage per dialect at
    runtime, so tests run on SQLite without needing pgvector installed while
    production uses the native pgvector type (and its HNSW index).
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector
            return dialect.type_descriptor(Vector(EMBEDDING_DIMS))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            # pgvector accepts numpy arrays and lists natively.
            return value
        # SQLite: serialise to JSON string.
        if isinstance(value, np.ndarray):
            return json.dumps(value.tolist())
        if isinstance(value, (list, tuple)):
            return json.dumps(list(value))
        return value  # already a string (round-trip from SQLite)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value  # pgvector returns numpy array
        # SQLite: deserialise from JSON string.
        if isinstance(value, str):
            return np.array(json.loads(value), dtype=np.float32)
        return value


EMBEDDING_TYPE = EmbeddingType()
