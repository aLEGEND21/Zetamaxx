from datetime import datetime

from sqlalchemy import Boolean, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, UTCDateTime, new_id, utcnow

DEFAULT_TIMEZONE = "America/New_York"


class User(Base):
    """Local mirror of the Clerk user. Every other table references `id`."""

    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    clerk_user_id: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    # 3 to 20 chars of [a-z0-9_]; unique regardless of case.
    username: Mapped[str] = mapped_column(String(20, collation="NOCASE"), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(Text)
    avatar_url: Mapped[str | None] = mapped_column(Text)
    timezone: Mapped[str] = mapped_column(Text, nullable=False, default=DEFAULT_TIMEZONE)
    timezone_set: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime, nullable=False, default=utcnow)
