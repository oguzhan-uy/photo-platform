"""deletion_log table for verifiable compliance deletions

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-16

Records every hard-deletion driven by compliance requirements:
  - client_delete  : GDPR Article 17 right to erasure
  - gallery_expire : automated retention expiry
  - consent_revoke : biometric consent withdrawal (faces only)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: Union[str, None] = "0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "deletion_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("event_type", sa.String(50), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.Uuid(), nullable=False),
        sa.Column("purged_photos", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purged_faces", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("purged_r2_objects", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executed_by", sa.String(50), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_deletion_log_target_id", "deletion_log", ["target_id"])


def downgrade() -> None:
    op.drop_index("ix_deletion_log_target_id", table_name="deletion_log")
    op.drop_table("deletion_log")
