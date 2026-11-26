"""Groups: CRUD, invites, roles, leaderboard, overlay series, and the feed."""

from datetime import timedelta

from sqlalchemy import func, select, update

from app.db import SessionLocal
from app.models import Game, Group, GroupMember
from tests.conftest import auth
from tests.helpers import add_game, utc

NOW = utc(2026, 6, 15, 16)  # the frozen clock


async def create_group(client, owner, name="Mathletes", description=None) -> dict:
    r = await client.post("/api/groups", json={"name": name, "description": description}, headers=auth(owner))
    assert r.status_code == 200, r.text
    return r.json()


async def join(client, group: dict, user):
    r = await client.post(f"/api/invites/{group['invite_code']}/join", headers=auth(user))
    assert r.status_code == 200, r.text


async def set_role(group_id: str, user, role: str):
    async with SessionLocal() as session:
        await session.execute(
            update(GroupMember)
            .where(GroupMember.group_id == group_id, GroupMember.user_id == user.id)
            .values(role=role)
        )
        await session.commit()


# --- CRUD and invites -----------------------------------------------------------------------------


async def test_create_and_list_groups(client, make_user, clock):
    alice, bob = await make_user("alice"), await make_user("bob")
    group = await create_group(client, alice, "  Mathletes  ", "Friday drills")
    assert group["name"] == "Mathletes" and group["description"] == "Friday drills"
    assert group["my_role"] == "owner" and len(group["invite_code"]) == 10
    assert [(m["user"]["username"], m["role"]) for m in group["members"]] == [("alice", "owner")]

    mine = (await client.get("/api/groups", headers=auth(alice))).json()["groups"]
    assert [(g["name"], g["my_role"], g["member_count"]) for g in mine] == [("Mathletes", "owner", 1)]
    assert (await client.get("/api/groups", headers=auth(bob))).json() == {"groups": []}
    assert (await client.get("/api/groups")).status_code == 401


async def test_group_name_validation(client, make_user):
    alice = await make_user("alice")
    for bad in ("", "   ", "x" * 41):
        r = await client.post("/api/groups", json={"name": bad}, headers=auth(alice))
        assert r.status_code == 422, bad
    assert (await client.post("/api/groups", json={"name": "x" * 40}, headers=auth(alice))).status_code == 200


async def test_invite_preview_and_join(client, make_user, clock):
    alice, bob = await make_user("alice", display_name="Alice A"), await make_user("bob")
    group = await create_group(client, alice, description="Friday drills")
    code = group["invite_code"]

    # Anyone with the link can preview, signed in or not.
    preview = (await client.get(f"/api/invites/{code}")).json()
    assert preview["group"]["name"] == "Mathletes" and preview["group"]["member_count"] == 1
    assert preview["already_member"] is False
    # Signed out, the owner is shown by username only.
    assert preview["group"]["owner"]["username"] == "alice" and preview["group"]["owner"]["display_name"] is None
    as_bob = (await client.get(f"/api/invites/{code}", headers=auth(bob))).json()
    assert as_bob["group"]["owner"]["display_name"] == "Alice A"
    assert (await client.get(f"/api/invites/{code}", headers=auth(alice))).json()["already_member"] is True

    # Joining needs an account.
    assert (await client.post(f"/api/invites/{code}/join")).status_code == 401
    joined = await client.post(f"/api/invites/{code}/join", headers=auth(bob))
    assert joined.json() == {"group_id": group["id"]}
    # Joining twice is harmless.
    await join(client, group, bob)
    detail = (await client.get(f"/api/groups/{group['id']}", headers=auth(bob))).json()
    assert [(m["user"]["username"], m["role"]) for m in detail["members"]] == [
        ("alice", "owner"),
        ("bob", "member"),
    ]
    assert detail["my_role"] == "member"
    assert (await client.get("/api/invites/doesnotexist")).status_code == 404


async def test_regenerating_the_invite_kills_the_old_link(client, make_user, clock):
    alice, bob, carol = await make_user("alice"), await make_user("bob"), await make_user("carol")
    group = await create_group(client, alice)
    await join(client, group, bob)

    # A plain member cannot regenerate; an admin can.
    url = f"/api/groups/{group['id']}/invite/regenerate"
    assert (await client.post(url, headers=auth(bob))).status_code == 403
    await set_role(group["id"], bob, "admin")
    new_code = (await client.post(url, headers=auth(bob))).json()["invite_code"]
    assert new_code != group["invite_code"] and len(new_code) == 10

    assert (await client.post(f"/api/invites/{group['invite_code']}/join", headers=auth(carol))).status_code == 404
    assert (await client.post(f"/api/invites/{new_code}/join", headers=auth(carol))).status_code == 200


async def test_non_members_cannot_see_a_group(client, make_user, clock):
    alice, mallory = await make_user("alice"), await make_user("mallory")
    group = await create_group(client, alice)
    gid = group["id"]
    for path in ("", "/leaderboard", "/series", "/feed"):
        r = await client.get(f"/api/groups/{gid}{path}", headers=auth(mallory))
        assert r.status_code == 404, path
        assert (await client.get(f"/api/groups/{gid}{path}")).status_code == 401
    assert (await client.post(f"/api/groups/{gid}/invite/regenerate", headers=auth(mallory))).status_code == 404
    assert (await client.delete(f"/api/groups/{gid}", headers=auth(mallory))).status_code == 404
    assert (await client.delete(f"/api/groups/{gid}/members/alice", headers=auth(mallory))).status_code == 404


async def test_member_management_rules(client, make_user, clock):
    owner, admin = await make_user("owner"), await make_user("admin")
    m1, m2 = await make_user("m1"), await make_user("m2")
    group = await create_group(client, owner)
    for user in (admin, m1, m2):
        await join(client, group, user)
    await set_role(group["id"], admin, "admin")
    base = f"/api/groups/{group['id']}/members"

    # A member can't remove anyone else; an admin can't remove the owner or another admin.
    assert (await client.delete(f"{base}/m2", headers=auth(m1))).status_code == 403
    assert (await client.delete(f"{base}/owner", headers=auth(admin))).status_code == 403
    await set_role(group["id"], m2, "admin")
    assert (await client.delete(f"{base}/m2", headers=auth(admin))).status_code == 403
    await set_role(group["id"], m2, "member")

    # An admin removes a member; the owner removes an admin; a member leaves.
    assert (await client.delete(f"{base}/m2", headers=auth(admin))).status_code == 204
    assert (await client.delete(f"{base}/admin", headers=auth(owner))).status_code == 204
    assert (await client.delete(f"{base}/m1", headers=auth(m1))).status_code == 204
    assert (await client.delete(f"{base}/m1", headers=auth(owner))).status_code == 404

    # The owner can't leave, only delete.
    r = await client.delete(f"{base}/owner", headers=auth(owner))
    assert r.status_code == 409 and r.json()["error"]["code"] == "owner_cannot_leave"
    detail = (await client.get(f"/api/groups/{group['id']}", headers=auth(owner))).json()
    assert [m["user"]["username"] for m in detail["members"]] == ["owner"]
    # Someone who was removed no longer sees the group.
    assert (await client.get(f"/api/groups/{group['id']}", headers=auth(m1))).status_code == 404


async def test_delete_group_removes_members_but_not_games(client, make_user, clock):
    alice, bob = await make_user("alice"), await make_user("bob")
    group = await create_group(client, alice)
    await join(client, group, bob)
    await add_game(bob, 30, NOW - timedelta(hours=1))

    assert (await client.delete(f"/api/groups/{group['id']}", headers=auth(bob))).status_code == 403
    assert (await client.delete(f"/api/groups/{group['id']}", headers=auth(alice))).status_code == 204
    async with SessionLocal() as session:
        assert (await session.execute(select(func.count()).select_from(Group))).scalar() == 0
        assert (await session.execute(select(func.count()).select_from(GroupMember))).scalar() == 0
        assert (await session.execute(select(func.count()).select_from(Game))).scalar() == 1
    assert (await client.get(f"/api/invites/{group['invite_code']}")).status_code == 404


# --- leaderboard --------------------------------------------------------------------------------


async def leaderboard(client, group, viewer, **params):
    r = await client.get(f"/api/groups/{group['id']}/leaderboard", params=params, headers=auth(viewer))
    assert r.status_code == 200, r.text
    return [(e["rank"], e["user"]["username"], e["value"], e["games"]) for e in r.json()["entries"]]


async def test_leaderboard_periods_and_metrics(client, make_user, clock):
    alice, bob, carol = await make_user("alice"), await make_user("bob"), await make_user("carol")
    group = await create_group(client, alice)
    await join(client, group, bob)
    await join(client, group, carol)

    # alice: 60 forty days ago, 40 ten days ago, 45 and 35 this week
    await add_game(alice, 60, NOW - timedelta(days=40))
    await add_game(alice, 40, NOW - timedelta(days=10))
    await add_game(alice, 45, NOW - timedelta(days=2))
    await add_game(alice, 35, NOW - timedelta(days=1))
    # bob: 50 twenty days ago, 30 this week. carol: never played.
    await add_game(bob, 50, NOW - timedelta(days=20))
    await add_game(bob, 30, NOW - timedelta(days=3))
    # Custom games never count.
    custom = {
        "duration": 30,
        "ops": {"add": True, "sub": False, "mul": False, "div": False},
        "add": {"a": [1, 9], "b": [1, 9]},
        "mul": {"a": [2, 12], "b": [2, 100]},
    }
    await add_game(bob, 99, NOW - timedelta(hours=5), settings=custom)

    assert await leaderboard(client, group, alice, period="week", metric="best") == [
        (1, "alice", 45.0, 2),
        (2, "bob", 30.0, 1),
        (None, "carol", None, 0),
    ]
    assert await leaderboard(client, group, bob, period="month", metric="best") == [
        (1, "bob", 50.0, 2),
        (2, "alice", 45.0, 3),
        (None, "carol", None, 0),
    ]
    assert await leaderboard(client, group, alice, period="all", metric="best") == [
        (1, "alice", 60.0, 4),
        (2, "bob", 50.0, 2),
        (None, "carol", None, 0),
    ]
    assert await leaderboard(client, group, alice, period="all", metric="avg10") == [
        (1, "alice", 45.0, 4),  # (60 + 40 + 45 + 35) / 4
        (2, "bob", 40.0, 2),
        (None, "carol", None, 0),
    ]
    assert await leaderboard(client, group, alice, period="week", metric="avg10") == [
        (1, "alice", 40.0, 2),
        (2, "bob", 30.0, 1),
        (None, "carol", None, 0),
    ]
    bad = await client.get(f"/api/groups/{group['id']}/leaderboard", params={"period": "year"}, headers=auth(alice))
    assert bad.status_code == 422


async def test_avg10_uses_only_the_last_ten_games(client, make_user, clock):
    alice = await make_user("alice")
    group = await create_group(client, alice)
    for i in range(12):  # oldest two are 100s, the last ten are 20s
        await add_game(alice, 100 if i < 2 else 20, NOW - timedelta(hours=12 - i))
    assert await leaderboard(client, group, alice, period="all", metric="avg10") == [(1, "alice", 20.0, 10)]


async def test_leaderboard_ties_share_a_rank(client, make_user, clock):
    alice, bob, carol = await make_user("alice"), await make_user("bob"), await make_user("carol")
    group = await create_group(client, alice)
    await join(client, group, bob)
    await join(client, group, carol)
    await add_game(alice, 40, NOW - timedelta(hours=3))
    await add_game(bob, 40, NOW - timedelta(hours=2))
    await add_game(carol, 30, NOW - timedelta(hours=1))
    assert await leaderboard(client, group, alice) == [
        (1, "alice", 40.0, 1),
        (1, "bob", 40.0, 1),
        (3, "carol", 30.0, 1),
    ]


async def test_since_joining_filter(client, make_user, clock):
    alice, bob = await make_user("alice"), await make_user("bob")
    await add_game(bob, 70, NOW - timedelta(days=3))  # before bob joined
    group = await create_group(client, alice)
    await join(client, group, bob)  # joins "now"
    clock.shift(timedelta(hours=1))
    await add_game(bob, 30, NOW + timedelta(minutes=30))

    # History from before joining is shown by default...
    assert (await leaderboard(client, group, alice, period="all"))[0] == (1, "bob", 70.0, 2)
    # ...and hidden with the filter.
    assert (await leaderboard(client, group, alice, period="all", since_joining="true"))[0] == (
        1,
        "bob",
        30.0,
        1,
    )
    series = await client.get(
        f"/api/groups/{group['id']}/series", params={"since_joining": "true"}, headers=auth(alice)
    )
    bob_points = next(m["points"] for m in series.json()["members"] if m["user"]["username"] == "bob")
    assert bob_points == [{"date": "2026-06-15", "best": 30}]


# --- overlay series and feed -------------------------------------------------------------------------


async def test_series_plots_each_member_by_their_own_local_date(client, make_user, clock):
    alice = await make_user("alice", timezone="America/New_York")
    kenji = await make_user("kenji", timezone="Asia/Tokyo")
    group = await create_group(client, alice)
    await join(client, group, kenji)

    moment = utc(2026, 6, 14, 2)  # Jun 13, 10 PM in New York; Jun 14, 11 AM in Tokyo
    await add_game(alice, 30, moment)
    await add_game(alice, 44, moment + timedelta(minutes=5))
    await add_game(kenji, 50, moment)
    await add_game(kenji, 20, utc(2026, 1, 1, 3))  # outside the 90-day window

    body = (await client.get(f"/api/groups/{group['id']}/series", headers=auth(kenji))).json()
    by_user = {m["user"]["username"]: m["points"] for m in body["members"]}
    assert by_user == {
        "alice": [{"date": "2026-06-13", "best": 44}],
        "kenji": [{"date": "2026-06-14", "best": 50}],
    }
    everything = await client.get(f"/api/groups/{group['id']}/series", params={"range": "all"}, headers=auth(kenji))
    kenji_all = next(m["points"] for m in everything.json()["members"] if m["user"]["username"] == "kenji")
    assert [p["date"] for p in kenji_all] == ["2026-01-01", "2026-06-14"]


async def test_group_feed_is_members_ranked_games_newest_first(client, make_user, clock):
    alice, bob, outsider = await make_user("alice"), await make_user("bob"), await make_user("zed")
    group = await create_group(client, alice)
    await join(client, group, bob)
    await add_game(alice, 31, NOW - timedelta(hours=3))
    await add_game(bob, 32, NOW - timedelta(hours=2))
    await add_game(outsider, 99, NOW - timedelta(hours=1))
    for i in range(22):
        await add_game(alice, 1, NOW - timedelta(days=2, minutes=i))

    first = (await client.get(f"/api/groups/{group['id']}/feed", headers=auth(bob))).json()
    assert [(g["user"]["username"], g["score"]) for g in first["items"][:2]] == [("bob", 32), ("alice", 31)]
    assert len(first["items"]) == 20 and first["next_cursor"]
    second = (
        await client.get(f"/api/groups/{group['id']}/feed", params={"cursor": first["next_cursor"]}, headers=auth(bob))
    ).json()
    assert len(second["items"]) == 4 and second["next_cursor"] is None
    assert all(g["user"]["username"] != "zed" for g in first["items"] + second["items"])
