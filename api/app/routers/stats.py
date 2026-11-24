from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import optional_user
from app.db import get_session
from app.errors import forbidden, not_found
from app.models import User, utcnow
from app.schemas.user import UserBrief
from app.services import stats
from app.services.localtime import today_in
from app.services.visibility import can_view

router = APIRouter(prefix="/api/users", tags=["stats"])


async def get_target(session: AsyncSession, username: str) -> User:
    target = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
    if target is None:
        raise not_found("No such user")
    return target


async def visible_target(session: AsyncSession, viewer: User | None, username: str) -> User:
    target = await get_target(session, username)
    if not await can_view(session, viewer, target):
        raise forbidden("You can't see this player's stats")
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
    pb = await stats.personal_best(session, filters)

    if not await can_view(session, viewer, target):
        # Strangers get the username and PB only.
        return {
            "user": {"username": target.username, "display_name": None, "avatar_url": None},
            "visible": False,
            "is_self": False,
            "pb": pb,
        }

    return {
        "user": UserBrief.model_validate(target).model_dump(),
        "visible": True,
        "is_self": viewer is not None and viewer.id == target.id,
        "pb": pb,
        "games": await stats.games_count(session, filters),
        "recent_avg": await stats.recent_average(session, filters),
        "improvement": await stats.improvement(session, filters, utcnow()),
        "streak": await stats.streak(session, filters, today_in(target.timezone)),
        "last_played": await stats.last_played(session, filters),
        "op_speed": {
            "last10": await stats.op_speed(session, filters, last_n=stats.RECENT_GAMES),
            "all": await stats.op_speed(session, filters),
        },
        "time_of_day": await stats.time_of_day(session, filters),
    }


@router.get("/{username}/series")
async def user_series(
    username: str,
    range: Literal["30d", "90d", "1y", "all"] = "90d",
    settings_hash: str | None = None,
    viewer: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    target = await visible_target(session, viewer, username)
    days = stats.RANGE_DAYS[range]
    today = today_in(target.timezone)
    since = None if days is None else today - timedelta(days=days - 1)
    points = await stats.daily_series(session, stats.game_filters(target.id, settings_hash), since)
    return {
        "range": range,
        "from": since.isoformat() if since else (points[0]["date"] if points else today.isoformat()),
        "to": today.isoformat(),
        "points": points,
    }


@router.get("/{username}/activity")
async def user_activity(
    username: str,
    settings_hash: str | None = None,
    viewer: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    target = await visible_target(session, viewer, username)
    filters = stats.game_filters(target.id, settings_hash)
    days = await stats.activity(session, filters, today_in(target.timezone))
    return {"days": days, "total": sum(day["games"] for day in days)}


@router.get("/{username}/configs")
async def user_configs(
    username: str,
    viewer: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    """Custom (unranked) configurations this user has played, for grouping history."""
    target = await visible_target(session, viewer, username)
    return {"configs": await stats.custom_configs(session, target.id)}
