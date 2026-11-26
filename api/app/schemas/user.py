from datetime import datetime

from pydantic import BaseModel, ConfigDict


class UserBrief(BaseModel):
    """What other people see of a user."""

    model_config = ConfigDict(from_attributes=True)
    username: str
    display_name: str | None
    avatar_url: str | None

    @classmethod
    def of(cls, user, named: bool = True):
        """`named=False` leaves the full name out, for viewers who only get the username."""
        brief = cls.model_validate(user)
        if not named:
            brief.display_name = None
        return brief


class MeOut(UserBrief):
    id: str
    timezone: str
    timezone_set: bool
    created_at: datetime


class MePatch(BaseModel):
    timezone: str
