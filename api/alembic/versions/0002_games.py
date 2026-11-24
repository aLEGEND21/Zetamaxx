"""game_starts and games

Revision ID: 0002
Revises: 0001
"""

import sqlalchemy as sa
from alembic import op

from app.models.base import UTCDateTime

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_starts",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id")),
        sa.Column("seed", sa.BigInteger, nullable=False),
        sa.Column("settings", sa.JSON, nullable=False),
        sa.Column("settings_hash", sa.Text, nullable=False),
        sa.Column("is_ranked", sa.Boolean, nullable=False),
        sa.Column("started_at", UTCDateTime, nullable=False),
        sa.Column("consumed", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("guest_problems", sa.JSON),
        sa.Column("guest_finished_at", UTCDateTime),
    )
    op.create_table(
        "games",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("start_id", sa.String(36), sa.ForeignKey("game_starts.id"), nullable=False, unique=True),
        sa.Column("score", sa.Integer, nullable=False),
        sa.Column("duration_s", sa.Integer, nullable=False),
        sa.Column("is_ranked", sa.Boolean, nullable=False),
        sa.Column("settings_hash", sa.Text, nullable=False),
        sa.Column("settings", sa.JSON, nullable=False),
        sa.Column("problems", sa.JSON, nullable=False),
        sa.Column("avg_ms_add", sa.Integer),
        sa.Column("avg_ms_sub", sa.Integer),
        sa.Column("avg_ms_mul", sa.Integer),
        sa.Column("avg_ms_div", sa.Integer),
        sa.Column("flagged", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("finished_at", UTCDateTime, nullable=False),
        sa.Column("timezone", sa.Text, nullable=False),
        sa.Column("utc_offset_min", sa.Integer, nullable=False),
        sa.Column("local_finished_at", sa.String(19), nullable=False),
        sa.Column("local_date", sa.String(10), nullable=False),
        sa.Column("local_hour", sa.Integer, nullable=False),
    )
    op.create_index("ix_games_user_finished", "games", ["user_id", sa.text("finished_at DESC")])
    op.create_index("ix_games_user_local_date", "games", ["user_id", "local_date"])
    op.create_index("ix_games_ranked_finished", "games", ["is_ranked", sa.text("finished_at DESC")])


def downgrade() -> None:
    op.drop_table("games")
    op.drop_table("game_starts")
