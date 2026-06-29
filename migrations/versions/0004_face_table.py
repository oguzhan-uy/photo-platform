"""face table with pgvector embedding + HNSW index

Revision ID: 0004
Revises: 0003
Create Date: 2026-06-16

Embedding column is added via raw SQL after table creation because pgvector's
`vector` type is not a standard SQLAlchemy type. The HNSW index uses cosine
distance ops, which matches the ArcFace embedding space (L2-normalised vectors).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "face",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "photo_id",
            sa.Uuid(),
            sa.ForeignKey("photo.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gallery_id", sa.Uuid(), nullable=False),
        sa.Column("bbox_x", sa.Integer(), nullable=True),
        sa.Column("bbox_y", sa.Integer(), nullable=True),
        sa.Column("bbox_w", sa.Integer(), nullable=True),
        sa.Column("bbox_h", sa.Integer(), nullable=True),
        sa.Column("det_score", sa.Float(), nullable=True),
        sa.Column("cluster_id", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    # pgvector column and HNSW index added via raw SQL (not a standard SA type).
    op.execute("ALTER TABLE face ADD COLUMN embedding vector(512)")
    op.create_index("ix_face_photo_id", "face", ["photo_id"])
    op.create_index("ix_face_gallery_id", "face", ["gallery_id"])
    op.create_index("ix_face_cluster_id", "face", ["cluster_id"])
    # HNSW with cosine ops — best recall/latency given 24 GB RAM and moderate
    # face counts. ArcFace embeddings are L2-normalised so cosine ≈ dot-product.
    op.execute(
        "CREATE INDEX ix_face_embedding_hnsw ON face "
        "USING hnsw (embedding vector_cosine_ops)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_face_embedding_hnsw")
    op.drop_index("ix_face_cluster_id", table_name="face")
    op.drop_index("ix_face_gallery_id", table_name="face")
    op.drop_index("ix_face_photo_id", table_name="face")
    op.drop_table("face")
