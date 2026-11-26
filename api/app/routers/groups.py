import secrets
import string
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import and_, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import optional_user, require_user
from app.db import get_session
from app.errors import APIError, forbidden, not_found
from app.models import Game, Group, GroupMember, User, utcnow
from app.routers.games import PAGE_SIZE, page_query, to_page
from app.schemas.game import GamePage
from app.schemas.user import UserBrief
from app.services import stats
from app.services.visibility import sees_names

router = APIRouter(prefix="/api", tags=["groups"])

INVITE_ALPHABET = string.ascii_lowercase + string.digits
PERIOD_DAYS = {"week": 7, "month": 30, "all": None}
MANAGER_ROLES = ("owner", "admin")


def new_invite_code() -> str:
    return "".join(secrets.choice(INVITE_ALPHABET) for _ in range(10))


class GroupIn(BaseModel):
    name: str = Field(min_length=1, max_length=40)
    description: str | None = Field(default=None, max_length=280)

    @field_validator("name")
    @classmethod
    def _trim_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("name cannot be blank")
        return value

    @field_validator("description")
    @classmethod
    def _trim_description(cls, value: str | None) -> str | None:
        return (value or "").strip() or None


async def _membership(session: AsyncSession, group_id: str, user_id: str) -> GroupMember | None:
    return await session.get(GroupMember, (group_id, user_id))


async def _group_for_member(session: AsyncSession, group_id: str, user: User) -> tuple[Group, GroupMember]:
    """The group and the caller's membership. Non-members cannot tell it exists."""
    group = await session.get(Group, group_id)
    member = await _membership(session, group_id, user.id) if group else None
    if group is None or member is None:
        raise not_found("No such group")
    return group, member


async def _member_count(session: AsyncSession, group_id: str) -> int:
    query = select(func.count()).select_from(GroupMember).where(GroupMember.group_id == group_id)
    return (await session.execute(query)).scalar() or 0


async def _detail(session: AsyncSession, group: Group, me: GroupMember) -> dict:
    members = (
        (
            await session.execute(
                select(GroupMember).where(GroupMember.group_id == group.id).order_by(GroupMember.joined_at)
            )
        )
        .scalars()
        .all()
    )
    return {
        "id": group.id,
        "name": group.name,
        "description": group.description,
        "invite_code": group.invite_code,
        "my_role": me.role,
        "created_at": group.created_at,
        "members": [
            {
                "user": UserBrief.model_validate(m.user).model_dump(),
                "role": m.role,
                "joined_at": m.joined_at,
            }
            for m in members
        ],
    }


# --- CRUD -------------------------------------------------------------------------------------


@router.post("/groups")
async def create_group(body: GroupIn, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)):
    group = Group(name=body.name, description=body.description, owner_id=user.id, invite_code=new_invite_code())
    session.add(group)
    await session.flush()
    member = GroupMember(group_id=group.id, user_id=user.id, role="owner")
    session.add(member)
    await session.commit()
    member = await _membership(session, group.id, user.id)
    return await _detail(session, group, member)


@router.get("/groups")
async def my_groups(user: User = Depends(require_user), session: AsyncSession = Depends(get_session)):
    counts = select(GroupMember.group_id, func.count().label("members")).group_by(GroupMember.group_id).subquery()
    query = (
        select(Group, GroupMember.role, counts.c.members)
        .join(GroupMember, and_(GroupMember.group_id == Group.id, GroupMember.user_id == user.id))
        .join(counts, counts.c.group_id == Group.id)
        .order_by(Group.name)
    )
    return {
        "groups": [
            {
                "id": group.id,
                "name": group.name,
                "description": group.description,
                "my_role": role,
                "member_count": members,
            }
            for group, role, members in await session.execute(query)
        ]
    }


@router.get("/groups/{group_id}")
async def get_group(group_id: str, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)):
    group, me = await _group_for_member(session, group_id, user)
    return await _detail(session, group, me)


@router.delete("/groups/{group_id}", status_code=204)
async def delete_group(group_id: str, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)):
    group, me = await _group_for_member(session, group_id, user)
    if me.role != "owner":
        raise forbidden("Only the owner can delete a group")
    # Members go with it (ON DELETE CASCADE). Games are untouched: they belong to players.
    await session.execute(delete(Group).where(Group.id == group.id))
    await session.commit()
    return Response(status_code=204)


# --- invites ----------------------------------------------------------------------------------


async def _group_by_code(session: AsyncSession, code: str) -> Group:
    group = (await session.execute(select(Group).where(Group.invite_code == code))).scalar_one_or_none()
    if group is None:
        raise not_found("This invite link is not valid (it may have been regenerated)")
    return group


@router.get("/invites/{code}")
async def preview_invite(
    code: str,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    """What a group looks like before joining. Works signed out, so the link can be shared."""
    group = await _group_by_code(session, code)
    owner = await session.get(User, group.owner_id)
    return {
        "group": {
            "id": group.id,
            "name": group.name,
            "description": group.description,
            "member_count": await _member_count(session, group.id),
            "owner": UserBrief.of(owner, sees_names(user)).model_dump(),
        },
        "already_member": user is not None and await _membership(session, group.id, user.id) is not None,
    }


@router.post("/invites/{code}/join")
async def join_group(code: str, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)):
    group = await _group_by_code(session, code)
    if await _membership(session, group.id, user.id) is None:
        session.add(GroupMember(group_id=group.id, user_id=user.id, role="member"))
        await session.commit()
    return {"group_id": group.id}


@router.post("/groups/{group_id}/invite/regenerate")
async def regenerate_invite(
    group_id: str, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)
):
    group, me = await _group_for_member(session, group_id, user)
    if me.role not in MANAGER_ROLES:
        raise forbidden("Only the owner or an admin can regenerate the invite link")
    group.invite_code = new_invite_code()
    await session.commit()
    return {"invite_code": group.invite_code}


@router.delete("/groups/{group_id}/members/{username}", status_code=204)
async def remove_member(
    group_id: str,
    username: str,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Leave a group (yourself) or remove someone (owner: anyone; admin: plain members)."""
    _, me = await _group_for_member(session, group_id, user)
    target_user = (await session.execute(select(User).where(User.username == username))).scalar_one_or_none()
    target = await _membership(session, group_id, target_user.id) if target_user else None
    if target is None:
        raise not_found("No such member")

    if target.user_id == user.id:
        if me.role == "owner":
            raise APIError(409, "owner_cannot_leave", "The owner can't leave; delete the group instead")
    elif me.role == "owner" or (me.role == "admin" and target.role == "member"):
        pass
    else:
        raise forbidden("You can't remove this member")

    await session.delete(target)
    await session.commit()
    return Response(status_code=204)


# --- stats: computed from games joined through group_members, never copied -----------------------


def _member_games(group_id: str, since_joining: bool):
    """Ranked games by members of the group (optionally only since each joined)."""
    join = and_(GroupMember.user_id == Game.user_id, GroupMember.group_id == group_id)
    if since_joining:
        join = and_(join, Game.finished_at >= GroupMember.joined_at)
    return select(Game).join(GroupMember, join).where(Game.is_ranked.is_(True))


@router.get("/groups/{group_id}/leaderboard")
async def leaderboard(
    group_id: str,
    period: Literal["week", "month", "all"] = "week",
    metric: Literal["best", "avg10"] = "best",
    since_joining: bool = False,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    await _group_for_member(session, group_id, user)
    games = _member_games(group_id, since_joining)
    if (days := PERIOD_DAYS[period]) is not None:
        games = games.where(Game.finished_at >= utcnow() - timedelta(days=days))

    if metric == "best":
        g = games.subquery()
        scores = select(g.c.user_id, func.max(g.c.score).label("value"), func.count().label("games"))
        scores = scores.group_by(g.c.user_id)
    else:
        # Mean of each member's last 10 games in the period.
        ranked = games.add_columns(
            func.row_number()
            .over(partition_by=Game.user_id, order_by=(Game.finished_at.desc(), Game.id.desc()))
            .label("position")
        ).subquery()
        scores = (
            select(ranked.c.user_id, func.avg(ranked.c.score).label("value"), func.count().label("games"))
            .where(ranked.c.position <= stats.RECENT_GAMES)
            .group_by(ranked.c.user_id)
        )
    by_user = {uid: (value, n) for uid, value, n in await session.execute(scores)}

    members = (await session.execute(select(GroupMember).where(GroupMember.group_id == group_id))).scalars().all()
    entries = [
        {
            "user": UserBrief.model_validate(m.user).model_dump(),
            "value": None if m.user_id not in by_user else round(float(by_user[m.user_id][0]), 2),
            "games": by_user.get(m.user_id, (None, 0))[1],
        }
        for m in members
    ]
    # Highest first; members with no games in the period go last, alphabetically.
    entries.sort(key=lambda e: (e["value"] is None, -(e["value"] or 0), e["user"]["username"]))
    rank = 0
    for position, entry in enumerate(entries, start=1):
        if entry["value"] is None:
            entry["rank"] = None
            continue
        if position == 1 or entry["value"] != entries[position - 2]["value"]:
            rank = position  # ties share a rank
        entry["rank"] = rank
    return {"period": period, "metric": metric, "since_joining": since_joining, "entries": entries}


@router.get("/groups/{group_id}/series")
async def group_series(
    group_id: str,
    range: Literal["30d", "90d", "1y", "all"] = "90d",
    since_joining: bool = False,
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Daily best per member, each by their own `local_date`, for the overlay chart."""
    await _group_for_member(session, group_id, user)
    g = _member_games(group_id, since_joining).subquery()
    query = select(g.c.user_id, g.c.local_date, func.max(g.c.score)).group_by(g.c.user_id, g.c.local_date)
    if (days := stats.RANGE_DAYS[range]) is not None:
        # A day of slack covers members who are ahead of UTC.
        cutoff = (utcnow() - timedelta(days=days)).date()
        query = query.where(g.c.local_date >= cutoff.isoformat())
    points: dict[str, list[dict]] = {}
    for user_id, local_date, best in await session.execute(query.order_by(g.c.local_date)):
        points.setdefault(user_id, []).append({"date": local_date, "best": best})

    members = (
        (
            await session.execute(
                select(GroupMember).where(GroupMember.group_id == group_id).order_by(GroupMember.joined_at)
            )
        )
        .scalars()
        .all()
    )
    return {
        "range": range,
        "members": [
            {"user": UserBrief.model_validate(m.user).model_dump(), "points": points.get(m.user_id, [])}
            for m in members
        ],
    }


@router.get("/groups/{group_id}/feed", response_model=GamePage)
async def group_feed(
    group_id: str,
    cursor: str | None = None,
    limit: int = Query(PAGE_SIZE, ge=1, le=100),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    await _group_for_member(session, group_id, user)
    query = page_query(_member_games(group_id, since_joining=False), cursor, limit)
    return to_page(list((await session.execute(query)).scalars().all()), limit)
