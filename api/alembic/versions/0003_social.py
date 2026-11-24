"""friendships, groups, group_members

Revision ID: 0003
Revises: 0002
"""

import sqlalchemy as sa
from alembic import op

from app.models.base import UTCDateTime

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "friendships",
        sa.Column("requester_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("addressee_id", sa.String(36), sa.ForeignKey("users.id"), primary_key=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="pending"),
        sa.Column("created_at", UTCDateTime, nullable=False),
        sa.Column("responded_at", UTCDateTime),
        sa.CheckConstraint("status IN ('pending', 'accepted')", name="ck_friendships_status"),
        sa.CheckConstraint("requester_id <> addressee_id", name="ck_friendships_not_self"),
    )
    # No duplicate pair in either direction: (a, b) and (b, a) share one key.
    # On Postgres the two-argument min/max become LEAST/GREATEST.
    op.create_index(
        "uq_friendships_pair",
        "friendships",
        [sa.text("min(requester_id, addressee_id)"), sa.text("max(requester_id, addressee_id)")],
        unique=True,
    )
    op.create_index("ix_friendships_addressee", "friendships", ["addressee_id"])

    op.create_table(
        "groups",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(40), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("invite_code", sa.String(10), nullable=False, unique=True),
        sa.Column("created_at", UTCDateTime, nullable=False),
    )
    op.create_table(
        "group_members",
        sa.Column("group_id", sa.String(36), sa.ForeignKey("groups.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", sa.String(10), nullable=False, server_default="member"),
        sa.Column("joined_at", UTCDateTime, nullable=False),
        sa.CheckConstraint("role IN ('owner', 'admin', 'member')", name="ck_group_members_role"),
    )
    op.create_index("ix_group_members_user", "group_members", ["user_id"])


def downgrade() -> None:
    op.drop_table("group_members")
    op.drop_table("groups")
    op.drop_table("friendships")
