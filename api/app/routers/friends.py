from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import case, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_user
from app.db import get_session
from app.errors import APIError, not_found
from app.models import Friendship, Game, User, utcnow
from app.routers.games import PAGE_SIZE, page_query, to_page
from app.schemas.game import GamePage
from app.schemas.user import UserBrief
from app.services.visibility import friendship_between

router = APIRouter(prefix="/api/friends", tags=["friends"])


class FriendRequestIn(BaseModel):
    username: str


def _friend_ids(user_id: str):
    """Subquery: ids of everyone `user_id` is friends with (accepted, either direction)."""
    other = case((Friendship.requester_id == user_id, Friendship.addressee_id), else_=Friendship.requester_id)
    return select(other).where(
        or_(Friendship.requester_id == user_id, Friendship.addressee_id == user_id),
        Friendship.status == "accepted",
    )


async def _user_by_name(session: AsyncSession, username: str) -> User:
    user = (await session.execute(select(User).where(User.username == username.strip()))).scalar_one_or_none()
    if user is None:
        raise not_found(f"No player named '{username.strip()}'")
    return user


async def _between(session: AsyncSession, a_id: str, b_id: str) -> Friendship | None:
    return (await session.execute(select(Friendship).where(friendship_between(a_id, b_id)))).scalar_one_or_none()


@router.get("")
async def list_friends(user: User = Depends(require_user), session: AsyncSession = Depends(get_session)):
    rows = (
        await session.execute(
            select(Friendship).where(or_(Friendship.requester_id == user.id, Friendship.addressee_id == user.id))
        )
    ).scalars()
    other_of = {(f.addressee_id if f.requester_id == user.id else f.requester_id): f for f in rows}
    if not other_of:
        return {"friends": [], "incoming": [], "outgoing": []}

    users = {u.id: u for u in (await session.execute(select(User).where(User.id.in_(other_of)))).scalars()}
    # PB and last played (ranked games) for everyone in one query.
    best = {
        user_id: (pb, last)
        for user_id, pb, last in await session.execute(
            select(Game.user_id, func.max(Game.score), func.max(Game.local_finished_at))
            .where(Game.user_id.in_(other_of), Game.is_ranked.is_(True))
            .group_by(Game.user_id)
        )
    }

    friends, incoming, outgoing = [], [], []
    for other_id, friendship in other_of.items():
        brief = UserBrief.model_validate(users[other_id]).model_dump()
        if friendship.status == "accepted":
            pb, last = best.get(other_id, (None, None))
            friends.append({"user": brief, "pb": pb, "last_played": last})
        elif friendship.addressee_id == user.id:
            incoming.append({"user": brief})
        else:
            outgoing.append({"user": brief})
    by_name = lambda entry: entry["user"]["username"]  # noqa: E731
    return {
        "friends": sorted(friends, key=by_name),
        "incoming": sorted(incoming, key=by_name),
        "outgoing": sorted(outgoing, key=by_name),
    }


@router.post("/requests")
async def send_request(
    body: FriendRequestIn, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)
):
    target = await _user_by_name(session, body.username)
    if target.id == user.id:
        raise APIError(409, "self_request", "You can't add yourself")

    existing = await _between(session, user.id, target.id)
    if existing is not None:
        if existing.status == "accepted":
            raise APIError(409, "already_friends", f"You're already friends with {target.username}")
        if existing.requester_id == user.id:
            raise APIError(409, "already_requested", f"You already sent {target.username} a request")
        # They asked first: asking back accepts.
        existing.status = "accepted"
        existing.responded_at = utcnow()
        await session.commit()
        return {"status": "accepted", "user": UserBrief.model_validate(target).model_dump()}

    session.add(Friendship(requester_id=user.id, addressee_id=target.id))
    try:
        await session.commit()
    except IntegrityError as exc:
        # The other person sent a request at the same moment; the pair index refused a second row.
        await session.rollback()
        raise APIError(409, "already_requested", "A request between you two already exists") from exc
    return {"status": "pending", "user": UserBrief.model_validate(target).model_dump()}


@router.post("/requests/{username}/accept")
async def accept_request(
    username: str, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)
):
    other = await _user_by_name(session, username)
    friendship = await _between(session, user.id, other.id)
    if friendship is None or friendship.status != "pending" or friendship.addressee_id != user.id:
        raise not_found(f"No pending request from {other.username}")
    friendship.status = "accepted"
    friendship.responded_at = utcnow()
    await session.commit()
    return {"status": "accepted", "user": UserBrief.model_validate(other).model_dump()}


@router.delete("/{username}", status_code=204)
async def remove_friend(
    username: str, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)
):
    """Unfriend, decline an incoming request, or cancel an outgoing one."""
    other = await _user_by_name(session, username)
    friendship = await _between(session, user.id, other.id)
    if friendship is None:
        raise not_found(f"Nothing between you and {other.username}")
    await session.delete(friendship)
    await session.commit()
    return Response(status_code=204)


@router.get("/feed", response_model=GamePage)
async def friends_feed(
    cursor: str | None = None,
    limit: int = Query(PAGE_SIZE, ge=1, le=100),
    user: User = Depends(require_user),
    session: AsyncSession = Depends(get_session),
):
    """Recent ranked games from accepted friends, newest first."""
    query = select(Game).where(Game.user_id.in_(_friend_ids(user.id)), Game.is_ranked.is_(True))
    return to_page(list((await session.execute(page_query(query, cursor, limit))).scalars().all()), limit)
