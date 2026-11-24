from zoneinfo import available_timezones

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import require_user
from app.db import get_session
from app.errors import APIError
from app.models import utcnow
from app.models.user import User
from app.schemas.user import MeOut, MePatch

router = APIRouter(prefix="/api/me", tags=["me"])

VALID_TIMEZONES = available_timezones()


@router.get("", response_model=MeOut)
async def get_me(user: User = Depends(require_user)):
    """The local user row. `require_user` creates it on the first call."""
    return user


@router.patch("", response_model=MeOut)
async def patch_me(body: MePatch, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)):
    if body.timezone not in VALID_TIMEZONES:
        raise APIError(422, "invalid_timezone", f"'{body.timezone}' is not a known IANA timezone")
    user = await session.merge(user)
    user.timezone = body.timezone
    user.timezone_set = True
    user.updated_at = utcnow()
    await session.commit()
    return user
