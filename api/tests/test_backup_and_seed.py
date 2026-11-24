import sqlite3

from sqlalchemy import func, select

from app.backup import KEEP, backup
from app.config import get_settings
from app.db import SessionLocal
from app.models import Friendship, Game, Group, GroupMember, User
from app.seed import seed
from tests.conftest import auth


async def test_backup_is_a_consistent_readable_copy(make_user, tmp_path):
    await make_user("alice")
    target = backup(get_settings().database_path, tmp_path, today="20261124")
    assert target.name == "zetamaxx-20261124.db"
    with sqlite3.connect(target) as conn:
        assert conn.execute("SELECT username FROM users").fetchall() == [("alice",)]
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not list(tmp_path.glob("*.partial"))


def test_backup_keeps_only_the_newest_files(tmp_path):
    source = tmp_path / "live.db"
    sqlite3.connect(source).execute("CREATE TABLE t (x)").connection.close()
    out = tmp_path / "backups"
    for day in range(1, KEEP + 4):
        backup(source, out, today=f"202611{day:02d}")
    names = sorted(p.name for p in out.glob("zetamaxx-*.db"))
    assert len(names) == KEEP and names[0] == "zetamaxx-20261104.db" and names[-1] == "zetamaxx-20261117.db"


async def test_seed_creates_sample_data_and_is_idempotent(client, make_user):
    me = await make_user("realme")
    await seed()

    async def counts():
        async with SessionLocal() as session:
            return [
                (await session.execute(select(func.count()).select_from(model))).scalar()
                for model in (User, Group, GroupMember, Friendship, Game)
            ]

    users, groups, members, friendships, games = await counts()
    assert users == 5 and groups == 2
    assert members == 6 + 2  # seeded memberships + the real account in both groups
    assert friendships == 4 + 4  # seeded friendships + the real account with all four
    assert 150 < games < 700

    await seed()  # running it again changes nothing
    assert await counts() == [users, groups, members, friendships, games]

    # The real account can see a seeded player's full profile and both leaderboards.
    stats = (await client.get("/api/users/ada/stats", headers=auth(me))).json()
    assert stats["visible"] is True and stats["pb"] > 30 and stats["streak"] >= 0
    series = (await client.get("/api/users/ada/series", params={"range": "90d"}, headers=auth(me))).json()
    assert len(series["points"]) > 30
    mine = (await client.get("/api/groups", headers=auth(me))).json()["groups"]
    assert sorted(g["name"] for g in mine) == ["Mathletes", "Night Owls"]

    # Every seeded game would pass the real validation rules.
    async with SessionLocal() as session:
        for game in (await session.execute(select(Game).limit(200))).scalars():
            assert sum(p["ms"] for p in game.problems) <= game.duration_s * 1000 + 2000
            assert len(game.problems) == game.score and min(p["ms"] for p in game.problems) >= 150
