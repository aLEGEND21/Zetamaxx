import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.types import TypeDecorator

ISO_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"  # fixed width, so text order == time order


class Base(DeclarativeBase):
    pass


class UTCDateTime(TypeDecorator):
    """A UTC timestamp that is always timezone-aware in Python.

    SQLite has no timestamp type, so the value is stored as ISO 8601 text
    (`2026-11-25T03:30:00.000000Z`). Naive datetimes are rejected on write and
    values always come back with tzinfo=UTC. On Postgres this maps to a real
    TIMESTAMPTZ column.
    """

    impl = String(27)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(DateTime(timezone=True))
        return dialect.type_descriptor(String(27))

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UTCDateTime requires a timezone-aware datetime")
        value = value.astimezone(UTC)
        return value if dialect.name == "postgresql" else value.strftime(ISO_FORMAT)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.astimezone(UTC) if value.tzinfo else value.replace(tzinfo=UTC)
        return datetime.strptime(value, ISO_FORMAT).replace(tzinfo=UTC)


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id() -> str:
    """UUIDv7 as a 36-char string: unique and sortable by creation time."""
    return str(uuid.uuid7())
