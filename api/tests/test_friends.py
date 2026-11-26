"""Friends: requests, accept / decline / cancel, and the feed."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.db import SessionLocal
from app.models import Friendship
from tests.conftest import auth
from tests.helpers import add_game, utc

NOW = utc(2026, 6, 15, 16)


async def request(client, sender, username: str):
    return await client.post("/api/friends/requests", json={"username": username}, headers=auth(sender))


async def befriend(client, a, b):
    assert (await request(client, a, b.username)).status_code == 200
    r = await client.post(f"/api/friends/requests/{a.username}/accept", headers=auth(b))
    assert r.status_code == 200, r.text


async def lists(client, user) -> dict[str, list[str]]:
    body = (await client.get("/api/friends", headers=auth(user))).json()
    return {key: [entry["user"]["username"] for entry in body[key]] for key in ("friends", "incoming", "outgoing")}


async def test_request_then_accept(client, make_user, clock):
    alice, bob = await make_user("alice"), await make_user("bob")
    r = await request(client, alice, "Bob")  # usernames are case-insensitive
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert await lists(client, alice) == {"friends": [], "incoming": [], "outgoing": ["bob"]}
    assert await lists(client, bob) == {"friends": [], "incoming": ["alice"], "outgoing": []}

    # Only the person who was asked can accept.
    assert (await client.post("/api/friends/requests/bob/accept", headers=auth(alice))).status_code == 404
    accepted = await client.post("/api/friends/requests/alice/accept", headers=auth(bob))
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"
    assert await lists(client, alice) == {"friends": ["bob"], "incoming": [], "outgoing": []}
    assert await lists(client, bob) == {"friends": ["alice"], "incoming": [], "outgoing": []}
    async with SessionLocal() as session:
        friendship = (await session.execute(select(Friendship))).scalar_one()
    assert friendship.status == "accepted" and friendship.responded_at == NOW


async def test_request_errors(client, make_user, clock):
    alice, bob = await make_user("alice"), await make_user("bob")
    cases = [("alice", 409, "self_request"), ("nobody", 404, "not_found")]
    for username, status, code in cases:
        r = await request(client, alice, username)
        assert (r.status_code, r.json()["error"]["code"]) == (status, code)
    assert (await request(client, alice, "bob")).status_code == 200
    again = await request(client, alice, "bob")
    assert (again.status_code, again.json()["error"]["code"]) == (409, "already_requested")
    await client.post("/api/friends/requests/alice/accept", headers=auth(bob))
    for sender, username in ((alice, "bob"), (bob, "alice")):
        r = await request(client, sender, username)
        assert (r.status_code, r.json()["error"]["code"]) == (409, "already_friends")
    assert (await client.post("/api/friends/requests", json={"username": "bob"})).status_code == 401


async def test_requesting_someone_who_already_asked_you_accepts(client, make_user, clock):
    alice, bob = await make_user("alice"), await make_user("bob")
    await request(client, alice, "bob")
    r = await request(client, bob, "alice")
    assert r.status_code == 200 and r.json()["status"] == "accepted"
    assert (await lists(client, alice))["friends"] == ["bob"]
    async with SessionLocal() as session:
        assert (await session.execute(select(func.count()).select_from(Friendship))).scalar() == 1


async def test_database_refuses_a_duplicate_pair_in_either_direction(make_user):
    alice, bob = await make_user("alice"), await make_user("bob")
    async with SessionLocal() as session:
        session.add(Friendship(requester_id=alice.id, addressee_id=bob.id))
        await session.commit()
    for requester, addressee in ((bob, alice), (alice, bob)):
        async with SessionLocal() as session:
            session.add(Friendship(requester_id=requester.id, addressee_id=addressee.id))
            with pytest.raises(IntegrityError):
                await session.commit()
    async with SessionLocal() as session:
        session.add(Friendship(requester_id=alice.id, addressee_id=alice.id))
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_decline_cancel_and_unfriend(client, make_user, clock):
    alice, bob, carol = await make_user("alice"), await make_user("bob"), await make_user("carol")

    # Decline: bob deletes alice's incoming request.
    await request(client, alice, "bob")
    assert (await client.delete("/api/friends/alice", headers=auth(bob))).status_code == 204
    assert await lists(client, alice) == {"friends": [], "incoming": [], "outgoing": []}

    # Cancel: alice withdraws her own request.
    await request(client, alice, "carol")
    assert (await client.delete("/api/friends/carol", headers=auth(alice))).status_code == 204
    assert (await lists(client, carol))["incoming"] == []

    # Unfriend, from either side; afterwards a new request is possible.
    await befriend(client, alice, bob)
    assert (await client.delete("/api/friends/alice", headers=auth(bob))).status_code == 204
    assert (await lists(client, alice))["friends"] == []
    assert (await request(client, bob, "alice")).json()["status"] == "pending"

    assert (await client.delete("/api/friends/carol", headers=auth(bob))).status_code == 404
    assert (await client.delete("/api/friends/nobody", headers=auth(bob))).status_code == 404


async def test_friends_list_shows_pb_and_last_played(client, make_user, clock):
    alice = await make_user("alice")
    bob = await make_user("bob", timezone="America/Chicago", display_name="Bob B")
    carol = await make_user("carol")
    await befriend(client, alice, bob)
    await befriend(client, carol, alice)
    await add_game(bob, 41, utc(2026, 6, 10, 18))
    await add_game(bob, 55, utc(2026, 6, 12, 18))
    await add_game(bob, 38, utc(2026, 6, 14, 3, 15))  # 10:15 PM on Jun 13 in Chicago

    body = (await client.get("/api/friends", headers=auth(alice))).json()
    assert body["friends"] == [
        {
            "user": {"username": "bob", "display_name": "Bob B", "avatar_url": None},
            "pb": 55,
            "last_played": "2026-06-13T22:15:00",
        },
        {
            "user": {"username": "carol", "display_name": None, "avatar_url": None},
            "pb": None,
            "last_played": None,
        },
    ]
    assert (await client.get("/api/friends")).status_code == 401


async def test_friends_feed(client, make_user, clock):
    alice, bob, carol, dave = [await make_user(n) for n in ("alice", "bob", "carol", "dave")]
    await befriend(client, alice, bob)
    await befriend(client, carol, alice)
    await request(client, dave, "alice")  # pending only: not a friend yet

    await add_game(bob, 31, NOW - timedelta(hours=4))
    await add_game(carol, 32, NOW - timedelta(hours=3))
    await add_game(dave, 99, NOW - timedelta(hours=2))
    await add_game(alice, 50, NOW - timedelta(hours=1))  # my own games are not in my friends feed
    for i in range(21):
        await add_game(bob, 1, NOW - timedelta(days=1, minutes=i))

    first = (await client.get("/api/friends/feed", headers=auth(alice))).json()
    assert [(g["user"]["username"], g["score"]) for g in first["items"][:2]] == [("carol", 32), ("bob", 31)]
    assert len(first["items"]) == 20 and first["next_cursor"]
    second = (
        await client.get("/api/friends/feed", params={"cursor": first["next_cursor"]}, headers=auth(alice))
    ).json()
    assert len(second["items"]) == 3 and second["next_cursor"] is None
    assert (await client.get("/api/friends/feed", headers=auth(dave))).json()["items"] == []
    assert (await client.get("/api/friends/feed")).status_code == 401
