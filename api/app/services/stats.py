"""Personal stats, computed in SQL.

Everything is for ranked games unless a `settings_hash` is given. Anything
per-day groups by the stored `local_date`, so no timezone math happens here;
the only timezone-dependent input is "today" for the streak and date ranges,
which the caller derives from the profile owner's timezone.
"""

from datetime import date, datetime, timedelta

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.game.settings import OPS
from app.models import Game

RECENT_GAMES = 10
ROLLING_WINDOW = 7
ACTIVITY_DAYS = 365
IMPROVEMENT_DAYS = 30
RANGE_DAYS = {"30d": 30, "90d": 90, "1y": 365, "all": None}
TIME_BUCKETS = ("morning", "afternoon", "evening", "late_night")

_AVG_COLUMNS = {
    "add": Game.avg_ms_add,
    "sub": Game.avg_ms_sub,
    "mul": Game.avg_ms_mul,
    "div": Game.avg_ms_div,
}


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


async def op_speed(session: AsyncSession, filters: list, last_n: int | None = None) -> dict[str, int | None]:
    """Mean solve time (ms) per operation: the mean of each game's per-op average."""
    columns = [column.label(op) for op, column in _AVG_COLUMNS.items()]
    query = select(*columns).where(*filters)
    if last_n is not None:
        query = query.order_by(Game.finished_at.desc(), Game.id.desc()).limit(last_n)
    games = query.subquery()
    row = (await session.execute(select(*[func.avg(games.c[op]) for op in OPS]))).one()
    return {op: None if value is None else round(float(value)) for op, value in zip(OPS, row, strict=True)}


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


async def time_of_day(session: AsyncSession, filters: list) -> list[dict]:
    """Games and mean score by part of the day, from the stored `local_hour`."""
    hour = Game.local_hour
    bucket = case(
        (and_(hour >= 5, hour < 12), "morning"),
        (and_(hour >= 12, hour < 17), "afternoon"),
        (and_(hour >= 17, hour < 22), "evening"),
        else_="late_night",
    ).label("bucket")
    query = select(bucket, func.count(), func.avg(Game.score)).where(*filters).group_by(bucket)
    found = {name: (games, avg) for name, games, avg in await session.execute(query)}
    return [
        {
            "bucket": name,
            "games": found.get(name, (0, None))[0],
            "avg_score": None if name not in found else round(float(found[name][1]), 2),
        }
        for name in TIME_BUCKETS
    ]


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
