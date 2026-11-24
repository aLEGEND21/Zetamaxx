"""users

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from alembic import op

from app.models.base import UTCDateTime

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("clerk_user_id", sa.Text, nullable=False, unique=True),
        sa.Column("username", sa.String(20, collation="NOCASE"), nullable=False, unique=True),
        sa.Column("display_name", sa.Text),
        sa.Column("avatar_url", sa.Text),
        sa.Column("timezone", sa.Text, nullable=False, server_default="America/New_York"),
        sa.Column("timezone_set", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.Column("updated_at", UTCDateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table("users")
