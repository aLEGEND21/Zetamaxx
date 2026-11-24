"""Personal stats, computed in SQL.

Everything is for ranked games unless a `settings_hash` is given. Anything
per-day groups by the stored `local_date`, so no timezone math happens here;
the only timezone-dependent input is "today" for the streak and date ranges,
which the caller derives from the profile owner's timezone.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Game

RECENT_GAMES = 10
ROLLING_WINDOW = 7
ACTIVITY_DAYS = 365
IMPROVEMENT_DAYS = 30
RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90, "1y": 365, "all": None}


def game_filters(user_id: str, settings_hash: str | None = None) -> list:
    which = Game.settings_hash == settings_hash if settings_hash else Game.is_ranked.is_(True)
    return [Game.user_id == user_id, which]


def date_range(end: date, days: int) -> list[date]:
    """`days` consecutive dates ending on `end`. Steps whole dates, never 24-hour
    blocks, so daylight-saving days (23 or 25 hours long) cannot skip or repeat."""
    return [end - timedelta(days=offset) for offset in range(days - 1, -1, -1)]


async def personal_best(session: AsyncSession, filters: list) -> int | None:
    return (await session.execute(select(func.max(Game.score)).where(*filters))).scalar()


async def games_count(session: AsyncSession, filters: list) -> int:
    return (await session.execute(select(func.count()).select_from(Game).where(*filters))).scalar() or 0


async def recent_average(session: AsyncSession, filters: list, before: datetime | None = None) -> float | None:
    """Mean score of the last 10 games (optionally: the last 10 as of `before`)."""
    query = select(Game.score).where(*filters)
    if before is not None:
        query = query.where(Game.finished_at <= before)
    recent = query.order_by(Game.finished_at.desc(), Game.id.desc()).limit(RECENT_GAMES).subquery()
    value = (await session.execute(select(func.avg(recent.c.score)))).scalar()
    return None if value is None else round(float(value), 2)


async def improvement(session: AsyncSession, filters: list, now: datetime) -> float | None:
    """Recent average now minus the recent average as it stood 30 days ago."""
    current = await recent_average(session, filters)
    earlier = await recent_average(session, filters, before=now - timedelta(days=IMPROVEMENT_DAYS))
    if current is None or earlier is None:
        return None
    return round(current - earlier, 2)


async def last_played(session: AsyncSession, filters: list) -> str | None:
    query = select(Game.local_finished_at).where(*filters)
    return (await session.execute(query.order_by(Game.finished_at.desc()).limit(1))).scalar()


async def streak(session: AsyncSession, filters: list, today: date) -> int:
    """Consecutive days with at least one game, ending today or yesterday."""
    query = select(Game.local_date).where(*filters).distinct().order_by(Game.local_date.desc())
    played = [date.fromisoformat(d) for d in (await session.execute(query.limit(3660))).scalars()]
    if not played or played[0] < today - timedelta(days=1):
        return 0
    count, expected = 0, played[0]
    for day in played:
        if day != expected:
            break
        count += 1
        expected -= timedelta(days=1)
    return count


async def daily_series(session: AsyncSession, filters: list, since: date | None = None) -> list[dict]:
    """Per local day: best and mean score, plus the 7-game rolling mean as it
    stood after that day's last game. Days without games are omitted."""
    daily = (
        select(Game.local_date, func.max(Game.score), func.avg(Game.score), func.count())
        .where(*filters)
        .group_by(Game.local_date)
        .order_by(Game.local_date)
    )
    # The rolling mean runs over the whole game sequence (so the first day in
    # range still averages over the games before it), then one value per day.
    rolled = (
        select(
            Game.local_date.label("local_date"),
            func.avg(Game.score)
            .over(order_by=(Game.finished_at, Game.id), rows=(-(ROLLING_WINDOW - 1), 0))
            .label("rolling"),
            func.row_number()
            .over(partition_by=Game.local_date, order_by=(Game.finished_at.desc(), Game.id.desc()))
            .label("position"),
        )
        .where(*filters)
        .subquery()
    )
    rolling = select(rolled.c.local_date, rolled.c.rolling).where(rolled.c.position == 1)
    if since is not None:
        daily = daily.where(Game.local_date >= since.isoformat())
        rolling = rolling.where(rolled.c.local_date >= since.isoformat())

    rolling_by_date = dict((await session.execute(rolling)).all())
    return [
        {
            "date": local_date,
            "best": best,
            "avg": round(float(avg), 2),
            "games": games,
            "rolling_avg": round(float(rolling_by_date[local_date]), 2),
        }
        for local_date, best, avg, games in await session.execute(daily)
    ]


async def game_series(session: AsyncSession, filters: list, since: date) -> list[dict]:
    """One point per game since `since`: when it was played (the player's local
    time), its score, and the 7-game rolling mean as it stood after that game."""
    # As in `daily_series`, the rolling mean runs over the whole game sequence
    # before the date filter, so the first games in range average over earlier ones.
    rolled = (
        select(
            Game.local_finished_at.label("at"),
            Game.local_date.label("local_date"),
            Game.score.label("score"),
            func.avg(Game.score)
            .over(order_by=(Game.finished_at, Game.id), rows=(-(ROLLING_WINDOW - 1), 0))
            .label("rolling"),
            Game.finished_at.label("finished_at"),
            Game.id.label("id"),
        )
        .where(*filters)
        .subquery()
    )
    query = (
        select(rolled.c.at, rolled.c.score, rolled.c.rolling)
        .where(rolled.c.local_date >= since.isoformat())
        .order_by(rolled.c.finished_at, rolled.c.id)
    )
    return [
        {"at": at, "score": score, "rolling_avg": round(float(rolling), 2)}
        for at, score, rolling in await session.execute(query)
    ]


async def activity(session: AsyncSession, filters: list, today: date) -> list[dict]:
    """Games per day for the 365 days ending today (every day present, zeros included)."""
    days = date_range(today, ACTIVITY_DAYS)
    query = (
        select(Game.local_date, func.count())
        .where(*filters, Game.local_date >= days[0].isoformat(), Game.local_date <= days[-1].isoformat())
        .group_by(Game.local_date)
    )
    counts = dict((await session.execute(query)).all())
    return [{"date": day.isoformat(), "games": counts.get(day.isoformat(), 0)} for day in days]


async def custom_configs(session: AsyncSession, user_id: str) -> list[dict]:
    """The user's custom (unranked) configurations, most recently played first."""
    last = func.max(Game.finished_at)
    query = (
        select(
            Game.settings_hash,
            func.count(),
            func.max(Game.score),
            func.avg(Game.score),
            func.max(Game.local_date),
        )
        .where(Game.user_id == user_id, Game.is_ranked.is_(False))
        .group_by(Game.settings_hash)
        .order_by(last.desc())
    )
    rows = (await session.execute(query)).all()
    if not rows:
        return []
    # One representative settings object per hash (identical by definition).
    settings_query = (
        select(Game.settings_hash, Game.settings)
        .where(Game.user_id == user_id, Game.is_ranked.is_(False))
        .group_by(Game.settings_hash)
    )
    settings_by_hash = dict((await session.execute(settings_query)).all())
    return [
        {
            "settings_hash": settings_hash,
            "settings": settings_by_hash[settings_hash],
            "games": games,
            "best": best,
            "avg": round(float(avg), 2),
            "last_played": last_date,
        }
        for settings_hash, games, best, avg, last_date in rows
    ]
