"""Authentication dependencies.

`current_user` turns the request's Clerk session token into a local `User`
(creating the row on first sight). Routes depend on `optional_user` (guests
allowed) or `require_user` (401 for guests). Tests override `current_user`.
"""

import logging
from datetime import timedelta

import httpx
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.errors import APIError
from app.models import utcnow
from app.models.user import User
from app.services.clerk import ClerkProfile, InvalidToken, clerk, normalize_username

log = logging.getLogger(__name__)

PROFILE_MAX_AGE = timedelta(minutes=10)


def _candidate_tokens(request: Request) -> list[str]:
    """The `__session` cookie first, then `Authorization: Bearer` as a fallback."""
    tokens = []
    if cookie := request.cookies.get("__session"):
        tokens.append(cookie)
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer ") and (bearer := header[7:].strip()):
        if bearer not in tokens:
            tokens.append(bearer)
    return tokens


async def _unique_username(session: AsyncSession, wanted: str, own_id: str | None = None) -> str:
    candidate, n = wanted, 1
    while True:
        owner = (await session.execute(select(User.id).where(User.username == candidate))).scalar()
        if owner is None or owner == own_id:
            return candidate
        n += 1
        candidate = f"{wanted[: 20 - len(str(n)) - 1]}_{n}"


async def _apply_profile(session: AsyncSession, user: User, profile: ClerkProfile) -> None:
    wanted = normalize_username(profile.username, user.clerk_user_id)
    if wanted != user.username:
        user.username = await _unique_username(session, wanted, user.id)
    user.display_name = profile.display_name
    user.avatar_url = profile.avatar_url
    user.updated_at = utcnow()


async def get_or_create_user(session: AsyncSession, clerk_user_id: str) -> User:
    user = (await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))).scalar_one_or_none()

    if user is None:
        # Lazy provisioning: first request from this Clerk user.
        try:
            profile = await clerk.fetch_user(clerk_user_id)
        except httpx.HTTPError as exc:
            raise APIError(503, "auth_unavailable", "Could not load your account from Clerk") from exc
        user = User(clerk_user_id=clerk_user_id, username="pending")
        await _apply_profile(session, user, profile)
        session.add(user)
        try:
            await session.commit()
        except IntegrityError:
            # Two first requests raced; the other one created the row.
            await session.rollback()
            user = (await session.execute(select(User).where(User.clerk_user_id == clerk_user_id))).scalar_one()
        return user

    if utcnow() - user.updated_at > PROFILE_MAX_AGE:
        try:
            await _apply_profile(session, user, await clerk.fetch_user(clerk_user_id))
            await session.commit()
        except httpx.HTTPError as exc:
            log.warning("could not refresh profile for %s: %s", clerk_user_id, exc)
            await session.rollback()
    return user


async def current_user(request: Request, session: AsyncSession = Depends(get_session)) -> User | None:
    for token in _candidate_tokens(request):
        try:
            claims = await clerk.verify_token(token)
        except InvalidToken:
            continue
        return await get_or_create_user(session, claims["sub"])
    return None


async def optional_user(user: User | None = Depends(current_user)) -> User | None:
    return user


async def require_user(user: User | None = Depends(current_user)) -> User:
    if user is None:
        raise APIError(401, "unauthorized", "Sign in to do this")
    return user
