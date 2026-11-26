"""Who may see what of another player.

Everyone, signed in or not, sees every player's stats and games. A player's
full name is shown to signed-in viewers only: guests get just the username.
"""

from sqlalchemy import and_, or_

from app.models import Friendship, User


def sees_names(viewer: User | None) -> bool:
    return viewer is not None


def friendship_between(a_id: str, b_id: str):
    """SQL condition matching the friendship row of two users, whichever way it was requested."""
    return or_(
        and_(Friendship.requester_id == a_id, Friendship.addressee_id == b_id),
        and_(Friendship.requester_id == b_id, Friendship.addressee_id == a_id),
    )
