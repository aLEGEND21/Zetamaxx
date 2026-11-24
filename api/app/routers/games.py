import secrets
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import optional_user, require_user
from app.db import get_session
from app.errors import APIError, forbidden, not_found
from app.game.settings import STANDARD, is_standard, settings_hash
from app.models import Game, GameStart, User, utcnow
from app.models.base import ISO_FORMAT
from app.schemas.game import (
    ClaimIn,
    FinishIn,
    FinishOut,
    GameDetail,
    GamePage,
    GameSummary,
    StartIn,
    StartOut,
)
from app.services.localtime import local_fields
from app.services.validation import MIN_HUMAN_MS, Rejected, Validated, op_averages, validate_submission
from app.services.visibility import can_view

router = APIRouter(prefix="/api/games", tags=["games"])

CLAIM_WINDOW = timedelta(minutes=15)  # a guest has this long to sign in and claim a game
# Past this age an unused start can be neither finished nor claimed.
STALE_START_AGE = CLAIM_WINDOW + timedelta(minutes=1)
PAGE_SIZE = 20


async def prune_stale_starts(session: AsyncSession, now: datetime) -> None:
    """Delete starts that never became a game: restarted or abandoned games,
    unused prefetches, and guest games nobody claimed. They leave no trace."""
    await session.execute(
        delete(GameStart).where(GameStart.consumed.is_(False), GameStart.started_at < now - STALE_START_AGE)
    )


@router.post("/start", response_model=StartOut)
async def start_game(
    body: StartIn | None = None,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    settings = body.settings.as_dict() if body and body.settings else STANDARD
    now = utcnow()
    await prune_stale_starts(session, now)
    start = GameStart(
        user_id=user.id if user else None,
        seed=secrets.randbits(32),
        settings=settings,
        settings_hash=settings_hash(settings),
        is_ranked=is_standard(settings),
        started_at=now,
    )
    session.add(start)
    await session.commit()
    return StartOut(start_id=start.id, seed=start.seed, settings=settings, is_ranked=start.is_ranked, server_time=now)


async def _discard(session: AsyncSession, start: GameStart) -> None:
    """A rejected submission burns its start: it can't be retried and leaves no row."""
    await session.delete(start)
    await session.commit()


async def _save_game(
    session: AsyncSession, start: GameStart, user: User, result: Validated, finished_at: datetime
) -> FinishOut:
    previous_best = (
        await session.execute(
            select(func.max(Game.score)).where(Game.user_id == user.id, Game.settings_hash == start.settings_hash)
        )
    ).scalar()
    game = Game(
        user_id=user.id,
        start_id=start.id,
        score=result.score,
        duration_s=start.settings["duration"],
        is_ranked=start.is_ranked,
        settings_hash=start.settings_hash,
        settings=start.settings,
        problems=result.problems,
        avg_ms_add=result.avg_ms["add"],
        avg_ms_sub=result.avg_ms["sub"],
        avg_ms_mul=result.avg_ms["mul"],
        avg_ms_div=result.avg_ms["div"],
        flagged=result.flagged,
        finished_at=finished_at,
        **local_fields(finished_at, user.timezone),
    )
    start.consumed = True
    start.guest_problems = None
    start.guest_finished_at = None
    session.add(game)
    try:
        await session.commit()
    except IntegrityError as exc:
        # Two identical submissions raced; the other one won.
        await session.rollback()
        raise APIError(409, "start_consumed", "This game was already submitted") from exc
    game = (await session.execute(select(Game).where(Game.id == game.id))).scalar_one()
    return FinishOut(
        saved=True,
        score=game.score,
        game=GameDetail.of(game),
        is_pb=game.score > (previous_best or 0),
        previous_best=previous_best,
    )


@router.post("/finish", response_model=FinishOut)
async def finish_game(
    body: FinishIn,
    user: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    now = utcnow()
    start = await session.get(GameStart, body.start_id)
    if start is None:
        raise APIError(404, "start_not_found", "Unknown game")
    if start.consumed or start.guest_problems is not None:
        raise APIError(409, "start_consumed", "This game was already submitted")
    if start.user_id is not None and (user is None or user.id != start.user_id):
        # Someone else's game (or the session expired mid-game).
        raise APIError(403 if user else 401, "not_your_start", "This game belongs to another account")

    try:
        result = validate_submission(
            seed=start.seed,
            settings=start.settings,
            started_at=start.started_at,
            received_at=now,
            problems=[p.model_dump() for p in body.problems],
        )
    except Rejected as exc:
        await _discard(session, start)
        raise APIError(422, exc.code, exc.message) from exc

    if user is None:
        # Guest: validated in time, held on the start row until claimed.
        start.guest_problems = result.problems
        start.guest_finished_at = now
        await session.commit()
        return FinishOut(saved=False, score=result.score)

    user = await session.merge(user)
    return await _save_game(session, start, user, result, finished_at=now)


@router.post("/claim", response_model=FinishOut)
async def claim_game(body: ClaimIn, user: User = Depends(require_user), session: AsyncSession = Depends(get_session)):
    """Attach a finished guest game to the account the guest just signed in to."""
    now = utcnow()
    start = await session.get(GameStart, body.start_id)
    if start is None:
        raise APIError(404, "start_not_found", "Unknown game")
    if start.consumed:
        raise APIError(409, "start_consumed", "This game was already saved")
    if start.user_id is not None or start.guest_problems is None:
        raise APIError(409, "not_claimable", "This game cannot be claimed")
    if now - start.started_at >= CLAIM_WINDOW:
        raise APIError(410, "claim_expired", "This game is too old to claim")

    # Validated when it was submitted; re-derive the summary from the stored problems.
    problems = start.guest_problems
    result = Validated(
        problems=problems,
        score=len(problems),
        flagged=any(p["ms"] < MIN_HUMAN_MS for p in problems),
        avg_ms=op_averages(problems),
    )
    user = await session.merge(user)
    # The game happened when the guest finished it; local fields use the claimer's timezone.
    return await _save_game(session, start, user, result, finished_at=start.guest_finished_at)


def _encode_cursor(game: Game) -> str:
    return f"{game.finished_at.strftime(ISO_FORMAT)}~{game.id}"


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        stamp, game_id = cursor.split("~", 1)
        return datetime.strptime(stamp, ISO_FORMAT).replace(tzinfo=UTC), game_id
    except ValueError as exc:
        raise APIError(422, "invalid_cursor", "Invalid cursor") from exc


def page_query(query, cursor: str | None, limit: int):
    """Newest first, keyset-paginated on (finished_at, id)."""
    if cursor:
        stamp, game_id = _decode_cursor(cursor)
        query = query.where(or_(Game.finished_at < stamp, and_(Game.finished_at == stamp, Game.id < game_id)))
    return query.order_by(Game.finished_at.desc(), Game.id.desc()).limit(limit + 1)


def to_page(games: list[Game], limit: int) -> GamePage:
    has_more = len(games) > limit
    games = games[:limit]
    return GamePage(
        items=[GameSummary.of(g) for g in games],
        next_cursor=_encode_cursor(games[-1]) if has_more else None,
    )


@router.get("", response_model=GamePage)
async def list_games(
    user: str | None = Query(None, description="username; defaults to the signed-in user"),
    ranked: bool | None = None,
    settings_hash: str | None = None,
    cursor: str | None = None,
    limit: int = Query(PAGE_SIZE, ge=1, le=100),
    viewer: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    if user is None:
        if viewer is None:
            raise APIError(401, "unauthorized", "Sign in to see your games")
        target = viewer
    else:
        target = (await session.execute(select(User).where(User.username == user))).scalar_one_or_none()
        if target is None:
            raise not_found("No such user")
    if not await can_view(session, viewer, target):
        raise forbidden("You can't see this player's games")

    query = select(Game).where(Game.user_id == target.id)
    if ranked is not None:
        query = query.where(Game.is_ranked.is_(ranked))
    if settings_hash is not None:
        query = query.where(Game.settings_hash == settings_hash)
    games = (await session.execute(page_query(query, cursor, limit))).scalars().all()
    return to_page(list(games), limit)


@router.get("/{game_id}", response_model=GameDetail)
async def get_game(
    game_id: str,
    viewer: User | None = Depends(optional_user),
    session: AsyncSession = Depends(get_session),
):
    game = await session.get(Game, game_id)
    if game is None:
        raise not_found("No such game")
    if not await can_view(session, viewer, game.user):
        raise forbidden("You can't see this game")
    return GameDetail.of(game)
