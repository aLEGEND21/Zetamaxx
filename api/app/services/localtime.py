"""Local-time snapshots. Each game stores the player's wall-clock time when it
finished, so per-day stats never need timezone math at read time."""

from datetime import date, datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from app.models.user import DEFAULT_TIMEZONE


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError, ValueError:
        return ZoneInfo(DEFAULT_TIMEZONE)


def local_fields(finished_at: datetime, timezone: str) -> dict:
    """The five snapshot columns for a game that finished at `finished_at` (aware)."""
    if finished_at.tzinfo is None:
        raise ValueError("finished_at must be timezone-aware")
    tz = zone(timezone)
    local = finished_at.astimezone(tz)
    return {
        "timezone": tz.key,
        "utc_offset_min": int(local.utcoffset().total_seconds() // 60),
        "local_finished_at": local.strftime("%Y-%m-%dT%H:%M:%S"),
        "local_date": local.strftime("%Y-%m-%d"),
        "local_hour": local.hour,
    }


def today_in(timezone: str) -> date:
    """Today's date where the user lives. Never the server's date."""
    return datetime.now(zone(timezone)).date()
