"""Shared helpers for tests that need games."""

from datetime import UTC, datetime, timedelta

from app.db import SessionLocal
from app.game.generator import generate_sequence
from app.game.settings import STANDARD, is_standard, settings_hash
from app.models import Game, GameStart, User, new_id
from app.services.localtime import local_fields
from app.services.validation import op_averages
from tests.conftest import auth


def utc(year, month, day, hour=0, minute=0, second=0) -> datetime:
    return datetime(year, month, day, hour, minute, second, tzinfo=UTC)


def solved(seed: int, settings: dict, count: int, ms: int = 2000) -> list[dict]:
    """The first `count` problems of a game, each 'solved' in `ms` milliseconds."""
    return [{"op": p["op"], "a": p["a"], "b": p["b"], "ms": ms} for p in generate_sequence(seed, settings, count)]


async def start(client, user: User | None = None, settings: dict | None = None) -> dict:
    body = {"settings": settings} if settings else {}
    r = await client.post("/api/games/start", json=body, headers=auth(user) if user else {})
    assert r.status_code == 200, r.text
    return r.json()


async def finish(client, started: dict, problems: list[dict], user: User | None = None, **extra):
    return await client.post(
        "/api/games/finish",
        json={"start_id": started["start_id"], "problems": problems, **extra},
        headers=auth(user) if user else {},
    )


async def play(client, clock, user: User | None = None, *, count=10, ms=2000, settings=None, late_s=0):
    """Start a game, 'play' it for its full duration, and submit it. Returns the finish response."""
    started = await start(client, user, settings)
    clock.shift(timedelta(seconds=started["settings"]["duration"] + late_s))
    return await finish(client, started, solved(started["seed"], started["settings"], count, ms), user)


async def add_game(
    user: User,
    score: int,
    finished_at: datetime,
    *,
    settings: dict | None = None,
    avg_ms: dict | None = None,
    timezone: str | None = None,
) -> Game:
    """Insert a finished game directly (for stats tests that need many games on exact dates)."""
    settings = settings or STANDARD
    problems = solved(1, settings, score, ms=1000)
    averages = {**op_averages(problems), **(avg_ms or {})}
    async with SessionLocal() as session:
        game_start = GameStart(
            id=new_id(),
            user_id=user.id,
            seed=1,
            settings=settings,
            settings_hash=settings_hash(settings),
            is_ranked=is_standard(settings),
            started_at=finished_at - timedelta(seconds=settings["duration"]),
            consumed=True,
        )
        session.add(game_start)
        await session.flush()  # the game row references the start
        game = Game(
            user_id=user.id,
            start_id=game_start.id,
            score=score,
            duration_s=settings["duration"],
            is_ranked=game_start.is_ranked,
            settings_hash=game_start.settings_hash,
            settings=settings,
            problems=problems,
            avg_ms_add=averages["add"],
            avg_ms_sub=averages["sub"],
            avg_ms_mul=averages["mul"],
            avg_ms_div=averages["div"],
            finished_at=finished_at,
            **local_fields(finished_at, timezone or user.timezone),
        )
        session.add(game)
        await session.commit()
        return game
