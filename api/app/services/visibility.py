"""Who may see whose stats and games.

A user's details are visible to themselves, accepted friends, and anyone who
shares a group with them. Everyone else gets only the username and PB.
"""

from sqlalchemy import and_, exists, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.models import Friendship, GroupMember, User


def friendship_between(a_id: str, b_id: str):
    """SQL condition matching the friendship row of two users, whichever way it was requested."""
    return or_(
        and_(Friendship.requester_id == a_id, Friendship.addressee_id == b_id),
        and_(Friendship.requester_id == b_id, Friendship.addressee_id == a_id),
    )


async def are_friends(session: AsyncSession, a_id: str, b_id: str) -> bool:
    query = select(exists().where(friendship_between(a_id, b_id), Friendship.status == "accepted"))
    return bool((await session.execute(query)).scalar())


async def share_a_group(session: AsyncSession, a_id: str, b_id: str) -> bool:
    mine, theirs = aliased(GroupMember), aliased(GroupMember)
    query = select(exists().where(mine.user_id == a_id, theirs.user_id == b_id, mine.group_id == theirs.group_id))
    return bool((await session.execute(query)).scalar())


async def can_view(session: AsyncSession, viewer: User | None, target: User) -> bool:
    if viewer is None:
        return False
    if viewer.id == target.id:
        return True
    return await are_friends(session, viewer.id, target.id) or await share_a_group(session, viewer.id, target.id)
