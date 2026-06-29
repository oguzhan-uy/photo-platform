"""client, gallery, photo tables

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-15
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

photo_status = sa.Enum(
    "uploaded", "processing", "ready", "failed", name="photo_status"
)


def upgrade() -> None:
    op.create_table(
        "client",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("contact", sa.String(length=320), nullable=True),
        sa.Column("consent_biometric", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("consent_biometric_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "gallery",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("client.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=300), nullable=False),
        sa.Column("passcode_hash", sa.String(length=200), nullable=False),
        sa.Column("published", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "photo",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("gallery_id", sa.Uuid(), sa.ForeignKey("gallery.id", ondelete="CASCADE"), nullable=False),
        sa.Column("r2_key_original", sa.String(length=500), nullable=True),
        sa.Column("r2_key_web", sa.String(length=500), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=True),
        sa.Column("status", photo_status, nullable=False, server_default="uploaded"),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_photo_content_hash", "photo", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_photo_content_hash", table_name="photo")
    op.drop_table("photo")
    op.drop_table("gallery")
    op.drop_table("client")
    photo_status.drop(op.get_bind(), checkfirst=True)
