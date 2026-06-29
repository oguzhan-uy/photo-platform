"""enable pgvector extension

Revision ID: 0001
Revises:
Create Date: 2026-06-15

Milestone 1: prove the pgvector-enabled Postgres image works and the migration
chain runs. Domain tables arrive in milestone 2.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")


def downgrade() -> None:
    op.execute("DROP EXTENSION IF EXISTS vector")
