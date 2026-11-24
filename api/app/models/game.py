from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, UTCDateTime, new_id
from app.models.user import User


class GameStart(Base):
    """Issued when a game begins. Holds the seed the server will replay to
    validate the result. Rows that never turn into a game are pruned."""

    __tablename__ = "game_starts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(ForeignKey("users.id"))  # null for guests
    seed: Mapped[int] = mapped_column(BigInteger, nullable=False)  # 32-bit unsigned
    settings: Mapped[dict] = mapped_column(JSON, nullable=False)
    settings_hash: Mapped[str] = mapped_column(Text, nullable=False)
    is_ranked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    started_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)
    consumed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # A finished guest game, already validated, waiting for the guest to sign in and claim it.
    guest_problems: Mapped[list | None] = mapped_column(JSON(none_as_null=True))
    guest_finished_at: Mapped[datetime | None] = mapped_column(UTCDateTime)


class Game(Base):
    """One row per finished, validated game."""

    __tablename__ = "games"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), nullable=False)
    start_id: Mapped[str] = mapped_column(ForeignKey("game_starts.id"), unique=True, nullable=False)
    score: Mapped[int] = mapped_column(Integer, nullable=False)
    duration_s: Mapped[int] = mapped_column(Integer, nullable=False)
    is_ranked: Mapped[bool] = mapped_column(Boolean, nullable=False)
    settings_hash: Mapped[str] = mapped_column(Text, nullable=False)
    settings: Mapped[dict] = mapped_column(JSON, nullable=False)
    problems: Mapped[list] = mapped_column(JSON, nullable=False)  # [{op, a, b, ms}]
    # Denormalized mean solve time per operation; null when the op never came up.
    avg_ms_add: Mapped[int | None] = mapped_column(Integer)
    avg_ms_sub: Mapped[int | None] = mapped_column(Integer)
    avg_ms_mul: Mapped[int | None] = mapped_column(Integer)
    avg_ms_div: Mapped[int | None] = mapped_column(Integer)
    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    finished_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False)  # UTC; orders everything
    # Snapshot of the player's local time when the game finished. Never recomputed.
    timezone: Mapped[str] = mapped_column(Text, nullable=False)
    utc_offset_min: Mapped[int] = mapped_column(Integer, nullable=False)
    local_finished_at: Mapped[str] = mapped_column(String(19), nullable=False)  # YYYY-MM-DDTHH:MM:SS
    local_date: Mapped[str] = mapped_column(String(10), nullable=False)  # YYYY-MM-DD
    local_hour: Mapped[int] = mapped_column(Integer, nullable=False)  # 0 to 23

    user: Mapped[User] = relationship(lazy="joined")

    __table_args__ = (
        Index("ix_games_user_finished", "user_id", finished_at.desc()),
        Index("ix_games_user_local_date", "user_id", "local_date"),
        Index("ix_games_ranked_finished", "is_ranked", finished_at.desc()),
    )
