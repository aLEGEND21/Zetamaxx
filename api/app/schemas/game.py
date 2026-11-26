from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.game.settings import GameSettings
from app.models.game import Game
from app.schemas.user import UserBrief


class StartIn(BaseModel):
    settings: GameSettings | None = None  # omitted = standard (ranked)


class StartOut(BaseModel):
    start_id: str
    seed: int
    settings: dict
    is_ranked: bool
    server_time: datetime


class ProblemIn(BaseModel):
    op: Literal["add", "sub", "mul", "div"]
    a: int
    b: int
    ms: int = Field(ge=0)


class FinishIn(BaseModel):
    """Anything else the client sends (a score, for instance) is ignored."""

    start_id: str
    problems: list[ProblemIn]


class ClaimIn(BaseModel):
    start_id: str


class GameSummary(BaseModel):
    id: str
    user: UserBrief
    score: int
    duration_s: int
    is_ranked: bool
    settings_hash: str
    settings: dict
    avg_ms: dict[str, int | None]
    local_finished_at: str
    local_date: str

    @classmethod
    def of(cls, game: Game, named: bool = True):
        return cls(**_summary_fields(game, named))


class GameDetail(GameSummary):
    problems: list[dict]

    @classmethod
    def of(cls, game: Game, named: bool = True):
        return cls(**_summary_fields(game, named), problems=game.problems)


def _summary_fields(game: Game, named: bool) -> dict:
    return {
        "id": game.id,
        "user": UserBrief.of(game.user, named),
        "score": game.score,
        "duration_s": game.duration_s,
        "is_ranked": game.is_ranked,
        "settings_hash": game.settings_hash,
        "settings": game.settings,
        "avg_ms": {
            "add": game.avg_ms_add,
            "sub": game.avg_ms_sub,
            "mul": game.avg_ms_mul,
            "div": game.avg_ms_div,
        },
        "local_finished_at": game.local_finished_at,
        "local_date": game.local_date,
    }


class FinishOut(BaseModel):
    saved: bool  # false for a guest game that is waiting to be claimed
    score: int
    game: GameDetail | None = None
    is_pb: bool = False
    previous_best: int | None = None


class GamePage(BaseModel):
    items: list[GameSummary]
    next_cursor: str | None
