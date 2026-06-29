"""Add cover_photo_id to gallery table

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-16

Allows the photographer to designate one photo per gallery as the public
cover image shown on the landing page (blurred, unauthenticated).
SET NULL on delete so removing the cover photo just clears the pointer.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("gallery", sa.Column("cover_photo_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_gallery_cover_photo",
        "gallery",
        "photo",
        ["cover_photo_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_gallery_cover_photo", "gallery", type_="foreignkey")
    op.drop_column("gallery", "cover_photo_id")
