from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import optional_user
from app.db import get_session
from app.errors import not_found
from app.models import User, utcnow
from app.schemas.user import UserBrief
from app.services import stats
from app.services.localtime import today_in
from app.services.visibility import sees_names

router = APIRouter(prefix="/api/users", tags=["stats"])


async def get_target(session: AsyncSession, username: str) -> User:
    target = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if target is None:
        raise not_found("No such user")
    return target


@router.get("/{username}/stats")
async def user_stats(
    username: str,
    settings_hash: str | None = None,
    viewer: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    target = await get_target(session, username)
    filters = stats.game_filters(target.id, settings_hash)
    return {
        "user": UserBrief.of(target, sees_names(viewer)).model_dump(),
        "is_self": viewer is not None and viewer.id == target.id,
        "pb": await stats.personal_best(session, filters),
        "games": await stats.games_count(session, filters),
        "recent_avg": await stats.recent_average(session, filters),
        "improvement": await stats.improvement(session, filters, utcnow()),
        "streak": await stats.streak(session, filters, today_in(target.timezone)),
        "last_played": await stats.last_played(session, filters),
    }


@router.get("/{username}/series")
async def user_series(
    username: str,
    range: Literal["7d", "30d", "90d", "1y"] = "7d",
    settings_hash: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    """Progress over the last N days. The 7-day range has one point per game, at
    the time it was played; longer ranges have one point per day."""
    target = await get_target(session, username)
    today = today_in(target.timezone)
    since = today - timedelta(days=stats.RANGE_DAYS[range] - 1)
    filters = stats.game_filters(target.id, settings_hash)
    per_game = range == "7d"
    points = await (stats.game_series if per_game else stats.daily_series)(session, filters, since)
    return {
        "range": range,
        "from": since.isoformat(),
        "to": today.isoformat(),
        "per": "game" if per_game else "day",
        "points": points,
    }


@router.get("/{username}/activity")
async def user_activity(
    username: str,
    settings_hash: str | None = None,
    session: AsyncSession = Depends(get_session),
):
    target = await get_target(session, username)
    filters = stats.game_filters(target.id, settings_hash)
    days = await stats.activity(session, filters, today_in(target.timezone))
    return {"days": days, "total": sum(day["games"] for day in days)}


@router.get("/{username}/configs")
async def user_configs(
    username: str,
    session: AsyncSession = Depends(get_session),
):
    """Custom (unranked) configurations this user has played, for grouping history."""
    target = await get_target(session, username)
    return {"configs": await stats.custom_configs(session, target.id)}
