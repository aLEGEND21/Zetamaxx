"""Dev-only sample data, so charts and lists can be checked by eye.

    make seed          (or: cd api && uv run python -m app.seed)

Creates 4 users, 2 groups, friendships, and about 60 days of game history.
The seeded users cannot sign in (they do not exist in Clerk), so every real
account already in the database is made a friend of all four and added to both
groups; sign in once, then run `make seed` again to see their data. Safe to
re-run: existing seed users and games are left alone.
"""

import asyncio
import random
import sys
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select

from app.config import get_settings
from app.db import SessionLocal, engine, run_migrations
from app.game.generator import generate_sequence
from app.game.settings import STANDARD, STANDARD_HASH, settings_hash
from app.models import Friendship, Game, GameStart, Group, GroupMember, User, new_id
from app.services.localtime import local_fields
from app.services.validation import op_averages
from app.services.visibility import friendship_between

DAYS = 60
CUSTOM = {
    "duration": 60,
    "ops": {"add": False, "sub": False, "mul": True, "div": True},
    "add": {"a": [2, 100], "b": [2, 100]},
    "mul": {"a": [2, 20], "b": [2, 20]},
}

# username, display name, timezone, starting skill, gain over 60 days, favourite hour, play probability
PLAYERS = [
    ("ada", "Ada Lovelace", "America/New_York", 38, 14, 21, 0.85),
    ("grace", "Grace Hopper", "America/Los_Angeles", 52, 6, 7, 0.7),
    ("linus", "Linus T", "Europe/London", 27, 18, 13, 0.6),
    ("margaret", "Margaret H", "Asia/Tokyo", 44, 9, 23, 0.5),
]
# Relative solve time per operation, per player: everyone has a weak spot.
OP_WEIGHTS = {
    "ada": {"add": 0.8, "sub": 1.0, "mul": 1.1, "div": 1.3},
    "grace": {"add": 0.9, "sub": 0.9, "mul": 1.0, "div": 1.2},
    "linus": {"add": 0.7, "sub": 1.2, "mul": 1.4, "div": 1.0},
    "margaret": {"add": 1.0, "sub": 1.1, "mul": 0.8, "div": 1.2},
}


def _problems(rng: random.Random, seed: int, settings: dict, score: int, weights: dict) -> list[dict]:
    """`score` solved problems whose times add up to just under the duration."""
    raw = [(p, weights[p["op"]] * rng.uniform(0.6, 1.6)) for p in generate_sequence(seed, settings, score)]
    budget = settings["duration"] * 1000 * rng.uniform(0.95, 0.995)
    total = sum(weight for _, weight in raw) or 1
    return [
        {"op": p["op"], "a": p["a"], "b": p["b"], "ms": max(250, round(budget * weight / total))} for p, weight in raw
    ]


def _game_rows(rng: random.Random, user: User, settings: dict, score: int, finished_at: datetime, weights):
    seed = rng.getrandbits(32)
    problems = _problems(rng, seed, settings, score, weights)
    averages = op_averages(problems)
    is_ranked = settings_hash(settings) == STANDARD_HASH
    start = GameStart(
        id=new_id(),
        user_id=user.id,
        seed=seed,
        settings=settings,
        settings_hash=settings_hash(settings),
        is_ranked=is_ranked,
        started_at=finished_at - timedelta(seconds=settings["duration"]),
        consumed=True,
    )
    game = Game(
        user_id=user.id,
        start_id=start.id,
        score=score,
        duration_s=settings["duration"],
        is_ranked=is_ranked,
        settings_hash=start.settings_hash,
        settings=settings,
        problems=problems,
        avg_ms_add=averages["add"],
        avg_ms_sub=averages["sub"],
        avg_ms_mul=averages["mul"],
        avg_ms_div=averages["div"],
        finished_at=finished_at,
        **local_fields(finished_at, user.timezone),
    )
    return start, game


async def _seed_history(session, rng: random.Random, user: User, base: int, gain: int, hour: int, p_play: float):
    now = datetime.now(UTC)
    tz = ZoneInfo(user.timezone)
    today = now.astimezone(tz).date()
    weights = OP_WEIGHTS[user.username]
    created = 0
    for days_ago in range(DAYS - 1, -1, -1):
        if rng.random() > p_play:
            continue
        day = today - timedelta(days=days_ago)
        skill = base + gain * (DAYS - days_ago) / DAYS
        for n in range(rng.choice([1, 1, 2, 2, 3, 4])):
            local = datetime(day.year, day.month, day.day, tzinfo=tz) + timedelta(
                hours=(hour + rng.choice([-2, -1, 0, 0, 0, 1, 2])) % 24, minutes=rng.randrange(60) + n * 3
            )
            finished_at = local.astimezone(UTC)
            if finished_at > now:
                continue
            custom = rng.random() < 0.12
            score = max(3, round(rng.gauss(skill * (0.55 if custom else 1), 3.5)))
            start, game = _game_rows(rng, user, CUSTOM if custom else STANDARD, score, finished_at, weights)
            session.add(start)
            await session.flush()
            session.add(game)
            created += 1
    return created


async def _ensure_friends(session, a: User, b: User, status: str = "accepted") -> None:
    existing = (await session.execute(select(Friendship).where(friendship_between(a.id, b.id)))).scalar_one_or_none()
    if existing is None:
        now = datetime.now(UTC)
        session.add(
            Friendship(
                requester_id=a.id,
                addressee_id=b.id,
                status=status,
                created_at=now - timedelta(days=20),
                responded_at=now - timedelta(days=19) if status == "accepted" else None,
            )
        )


async def _ensure_member(session, group: Group, user: User, role: str = "member", days_ago: int = 0) -> None:
    if await session.get(GroupMember, (group.id, user.id)) is None:
        joined = datetime.now(UTC) - timedelta(days=days_ago)
        session.add(GroupMember(group_id=group.id, user_id=user.id, role=role, joined_at=joined))


async def _ensure_group(session, name: str, description: str, owner: User, code: str) -> Group:
    group = (await session.execute(select(Group).where(Group.invite_code == code))).scalar_one_or_none()
    if group is None:
        group = Group(name=name, description=description, owner_id=owner.id, invite_code=code)
        session.add(group)
        await session.flush()
    return group


async def seed() -> None:
    rng = random.Random(42)
    async with SessionLocal() as session:
        players: dict[str, User] = {}
        games_created = 0
        for username, display_name, timezone, base, gain, hour, p_play in PLAYERS:
            user = (
                await session.execute(select(User).where(User.clerk_user_id == f"seed_{username}"))
            ).scalar_one_or_none()
            if user is None:
                user = User(
                    clerk_user_id=f"seed_{username}",
                    username=username,
                    display_name=display_name,
                    timezone=timezone,
                    timezone_set=True,
                    # Seed rows never refresh from Clerk: nobody can sign in as them.
                    created_at=datetime.now(UTC) - timedelta(days=DAYS + 5),
                )
                session.add(user)
                await session.flush()
                games_created += await _seed_history(session, rng, user, base, gain, hour, p_play)
            players[username] = user

        ada, grace, linus, margaret = (players[name] for name in ("ada", "grace", "linus", "margaret"))
        await _ensure_friends(session, ada, grace)
        await _ensure_friends(session, ada, linus)
        await _ensure_friends(session, grace, linus)
        await _ensure_friends(session, margaret, ada, status="pending")

        mathletes = await _ensure_group(session, "Mathletes", "Everyone. Weekly bragging rights.", ada, "mathletes0")
        owls = await _ensure_group(session, "Night Owls", "Late sessions only.", grace, "nightowls0")
        await _ensure_member(session, mathletes, ada, "owner", days_ago=DAYS)
        await _ensure_member(session, mathletes, grace, "admin", days_ago=50)
        await _ensure_member(session, mathletes, linus, days_ago=30)
        await _ensure_member(session, mathletes, margaret, days_ago=12)
        await _ensure_member(session, owls, grace, "owner", days_ago=40)
        await _ensure_member(session, owls, linus, days_ago=25)

        # Let real accounts see the sample data.
        real_users = (
            (await session.execute(select(User).where(User.clerk_user_id.not_like("seed\\_%", escape="\\"))))
            .scalars()
            .all()
        )
        for user in real_users:
            for player in players.values():
                await _ensure_friends(session, player, user)
            await _ensure_member(session, mathletes, user)
            await _ensure_member(session, owls, user)

        await session.commit()

    print(f"seeded: {len(PLAYERS)} users, 2 groups, {games_created} new games")
    if real_users:
        print("linked your account(s): " + ", ".join(u.username for u in real_users))
    else:
        print("no real accounts yet: sign in once, then run `make seed` again to see this data")
    print("join links: /join/mathletes0  /join/nightowls0")


def main() -> None:
    settings = get_settings()
    if settings.clerk_secret_key.startswith("sk_live_") and "--force" not in sys.argv:
        sys.exit("Refusing to seed: this looks like production (sk_live_ key). Pass --force to override.")
    run_migrations()

    async def run():
        try:
            await seed()
        finally:
            await engine.dispose()

    asyncio.run(run())


if __name__ == "__main__":
    main()
