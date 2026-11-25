"""start / finish / claim validation and game history."""

from datetime import timedelta

import pytest
from sqlalchemy import func, select

from app.db import SessionLocal
from app.game.settings import STANDARD
from app.models import Game, GameStart
from tests.conftest import auth
from tests.helpers import add_game, finish, play, solved, start, utc

CUSTOM = {
    "duration": 30,
    "ops": {"add": True, "sub": False, "mul": False, "div": False},
    "add": {"a": [1, 9], "b": [1, 9]},
    "mul": {"a": [2, 12], "b": [2, 100]},
}


async def count(model) -> int:
    async with SessionLocal() as session:
        return (await session.execute(select(func.count()).select_from(model))).scalar()


async def only_game() -> Game:
    async with SessionLocal() as session:
        return (await session.execute(select(Game))).scalar_one()


# --- start -------------------------------------------------------------------------------------


async def test_start_as_guest_and_as_user(client, make_user, clock):
    alice = await make_user("alice")
    guest = await start(client)
    mine = await start(client, alice)
    for started in (guest, mine):
        assert started["settings"] == STANDARD and started["is_ranked"] is True
        assert 0 <= started["seed"] < 2**32
        assert started["server_time"].startswith("2026-06-15T16:00:00")
    async with SessionLocal() as session:
        rows = {s.id: s.user_id for s in (await session.execute(select(GameStart))).scalars()}
    assert rows[guest["start_id"]] is None and rows[mine["start_id"]] == alice.id


async def test_start_with_custom_settings_is_unranked(client, clock):
    started = await start(client, settings=CUSTOM)
    assert started["is_ranked"] is False and started["settings"] == CUSTOM


async def test_start_rejects_invalid_settings(client):
    r = await client.post("/api/games/start", json={"settings": {**STANDARD, "duration": 45}})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validation_error"


# --- finish: the happy path ----------------------------------------------------------------------


async def test_finish_saves_the_game(client, make_user, clock):
    alice = await make_user("alice")
    r = await play(client, clock, alice, count=12, ms=2500)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["saved"] is True and body["score"] == 12 and body["is_pb"] is True
    assert body["previous_best"] is None
    game = body["game"]
    assert game["score"] == 12 and game["duration_s"] == 120 and game["is_ranked"] is True
    assert game["user"]["username"] == "alice"
    assert len(game["problems"]) == 12 and game["problems"][0]["ms"] == 2500
    assert all(v in (2500, None) for v in game["avg_ms"].values())
    assert any(v == 2500 for v in game["avg_ms"].values())

    saved = await only_game()
    assert saved.user_id == alice.id and saved.flagged is False
    assert saved.finished_at == utc(2026, 6, 15, 16, 2)
    async with SessionLocal() as session:
        assert (await session.get(GameStart, saved.start_id)).consumed is True


async def test_pb_is_only_reported_when_beaten(client, make_user, clock):
    alice = await make_user("alice")
    assert (await play(client, clock, alice, count=10)).json()["is_pb"] is True
    lower = (await play(client, clock, alice, count=8)).json()
    assert lower["is_pb"] is False and lower["previous_best"] == 10
    tie = (await play(client, clock, alice, count=10)).json()
    assert tie["is_pb"] is False
    assert (await play(client, clock, alice, count=11)).json()["is_pb"] is True


async def test_custom_games_have_their_own_pb(client, make_user, clock):
    alice = await make_user("alice")
    await play(client, clock, alice, count=30)
    custom = (await play(client, clock, alice, count=5, settings=CUSTOM)).json()
    assert custom["is_pb"] is True and custom["game"]["is_ranked"] is False
    assert custom["game"]["duration_s"] == 30


async def test_client_sent_score_is_ignored(client, make_user, clock):
    alice = await make_user("alice")
    started = await start(client, alice)
    clock.shift(120)
    r = await finish(client, started, solved(started["seed"], STANDARD, 7), alice, score=999)
    assert r.status_code == 200
    assert r.json()["score"] == 7 and (await only_game()).score == 7


async def test_game_with_no_answers_is_not_saved(client, make_user, clock):
    alice = await make_user("alice")
    r = await play(client, clock, alice, count=0)
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_answers"
    assert await count(Game) == 0 and await count(GameStart) == 0  # no game, and the start is gone too


# --- finish: rejections --------------------------------------------------------------------------


async def expect_rejected(r, code: str, status: int = 422):
    assert r.status_code == status, r.text
    assert r.json()["error"]["code"] == code
    assert await count(Game) == 0


async def test_tampered_problems_are_rejected_and_the_start_is_burned(client, make_user, clock):
    alice = await make_user("alice")
    started = await start(client, alice)
    clock.shift(120)
    problems = solved(started["seed"], STANDARD, 10)
    problems[4]["b"] += 1
    await expect_rejected(await finish(client, started, problems, alice), "problems_mismatch")
    # The start is gone: an honest retry with the same start no longer works.
    assert await count(GameStart) == 0
    retry = await finish(client, started, solved(started["seed"], STANDARD, 10), alice)
    await expect_rejected(retry, "start_not_found", 404)


async def test_problems_from_another_seed_are_rejected(client, make_user, clock):
    alice = await make_user("alice")
    started = await start(client, alice)
    clock.shift(120)
    wrong_seed = (started["seed"] + 1) % 2**32
    r = await finish(client, started, solved(wrong_seed, STANDARD, 10), alice)
    await expect_rejected(r, "problems_mismatch")


async def test_skipping_or_reordering_problems_is_rejected(client, make_user, clock):
    alice = await make_user("alice")
    for mutate in (lambda p: p[1:], lambda p: [p[1], p[0], *p[2:]]):
        started = await start(client, alice)
        clock.shift(120)
        r = await finish(client, started, mutate(solved(started["seed"], STANDARD, 10)), alice)
        await expect_rejected(r, "problems_mismatch")


async def test_replayed_start_id_is_rejected(client, make_user, clock):
    alice = await make_user("alice")
    started = await start(client, alice)
    clock.shift(120)
    problems = solved(started["seed"], STANDARD, 10)
    assert (await finish(client, started, problems, alice)).status_code == 200
    again = await finish(client, started, problems, alice)
    assert again.status_code == 409 and again.json()["error"]["code"] == "start_consumed"
    assert await count(Game) == 1


async def test_someone_elses_start_is_rejected(client, make_user, clock):
    alice, bob = await make_user("alice"), await make_user("bob")
    started = await start(client, alice)
    clock.shift(120)
    problems = solved(started["seed"], STANDARD, 10)
    await expect_rejected(await finish(client, started, problems, bob), "not_your_start", 403)
    await expect_rejected(await finish(client, started, problems), "not_your_start", 401)
    # The rightful owner can still submit it.
    assert (await finish(client, started, problems, alice)).status_code == 200


async def test_unknown_start_is_404(client, make_user):
    alice = await make_user("alice")
    r = await client.post("/api/games/finish", json={"start_id": "nope", "problems": []}, headers=auth(alice))
    assert r.status_code == 404 and r.json()["error"]["code"] == "start_not_found"


async def test_malformed_problems_are_422(client, make_user, clock):
    alice = await make_user("alice")
    started = await start(client, alice)
    for bad in ([{"op": "pow", "a": 1, "b": 2, "ms": 500}], [{"op": "add", "a": 1, "b": 2, "ms": -5}], "x"):
        r = await client.post(
            "/api/games/finish", json={"start_id": started["start_id"], "problems": bad}, headers=auth(alice)
        )
        assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


# --- finish: timing rules ------------------------------------------------------------------------


async def test_strict_deadline_30_seconds_after_the_game_should_end(client, make_user, clock):
    alice = await make_user("alice")
    on_time = await play(client, clock, alice, late_s=29)
    assert on_time.status_code == 200

    late = await play(client, clock, alice, late_s=31)
    assert late.status_code == 422 and late.json()["error"]["code"] == "too_late"
    assert await count(Game) == 1
    assert await count(GameStart) == 1  # only the on-time game's start remains


async def test_solve_times_cannot_exceed_the_duration(client, make_user, clock):
    alice = await make_user("alice")
    ok = await play(client, clock, alice, count=61, ms=2000)  # 122s: inside the 2s tolerance
    assert ok.status_code == 200
    r = await play(client, clock, alice, count=62, ms=2000)  # 124s
    assert r.status_code == 422 and r.json()["error"]["code"] == "time_exceeded"


async def test_game_cannot_be_submitted_before_it_could_have_been_played(client, make_user, clock):
    alice = await make_user("alice")
    started = await start(client, alice)
    clock.shift(5)  # five seconds after starting...
    r = await finish(client, started, solved(started["seed"], STANDARD, 40, ms=2000), alice)  # ...80s of solving
    await expect_rejected(r, "too_fast")


async def test_superhuman_answers(client, make_user, clock):
    alice = await make_user("alice")

    async def submit(fast_count: int):
        started = await start(client, alice)
        clock.shift(120)
        problems = solved(started["seed"], STANDARD, 20, ms=1000)
        for p in problems[:fast_count]:
            p["ms"] = 100
        return await finish(client, started, problems, alice)

    # One or two fast answers out of 20 (<= 10%): accepted but flagged.
    for fast in (1, 2):
        r = await submit(fast)
        assert r.status_code == 200, r.text
    async with SessionLocal() as session:
        assert [g.flagged for g in (await session.execute(select(Game))).scalars()] == [True, True]

    # Three out of 20 (15%): rejected.
    r = await submit(3)
    assert r.status_code == 422 and r.json()["error"]["code"] == "answers_too_fast"
    assert await count(Game) == 2

    # 149ms is too fast, 150ms is fine.
    started = await start(client, alice)
    clock.shift(120)
    r = await finish(client, started, solved(started["seed"], STANDARD, 10, ms=150), alice)
    assert r.status_code == 200
    async with SessionLocal() as session:
        newest = (await session.execute(select(Game).order_by(Game.finished_at.desc()))).scalars().first()
    assert newest.flagged is False


# --- abandoned games leave nothing -----------------------------------------------------------------


async def test_restarted_games_are_never_saved_and_their_starts_are_pruned(client, make_user, clock):
    alice = await make_user("alice")
    await start(client, alice)  # started, then restarted: never finished
    await start(client)  # a guest who walked away
    assert await count(GameStart) == 2 and await count(Game) == 0

    clock.shift(timedelta(minutes=17))
    kept = await start(client, alice)  # any later start sweeps the dead ones
    async with SessionLocal() as session:
        ids = [s.id for s in (await session.execute(select(GameStart))).scalars()]
    assert ids == [kept["start_id"]]
    assert await count(Game) == 0
    r = await client.get("/api/games", headers=auth(alice))
    assert r.json() == {"items": [], "next_cursor": None}


async def test_pruning_keeps_finished_games(client, make_user, clock):
    alice = await make_user("alice")
    assert (await play(client, clock, alice)).status_code == 200
    clock.shift(timedelta(hours=3))
    await start(client, alice)
    assert await count(Game) == 1 and await count(GameStart) == 2


# --- guests and claiming -------------------------------------------------------------------------


async def test_guest_game_is_held_then_claimed(client, make_user, clock):
    r = await play(client, clock, None, count=9)
    assert r.status_code == 200
    assert r.json() == {"saved": False, "score": 9, "game": None, "is_pb": False, "previous_best": None}
    assert await count(Game) == 0
    async with SessionLocal() as session:
        held = (await session.execute(select(GameStart))).scalar_one()
    assert held.user_id is None and held.consumed is False and len(held.guest_problems) == 9

    # The guest signs up (in Los Angeles) five minutes later and claims the game.
    clock.shift(timedelta(minutes=5))
    carol = await make_user("carol", timezone="America/Los_Angeles")
    claim = await client.post("/api/games/claim", json={"start_id": held.id}, headers=auth(carol))
    assert claim.status_code == 200, claim.text
    assert claim.json()["saved"] is True and claim.json()["score"] == 9 and claim.json()["is_pb"] is True

    game = await only_game()
    assert game.user_id == carol.id and game.score == 9
    # It happened when it was played, not when it was claimed, in the claimer's timezone.
    assert game.finished_at == utc(2026, 6, 15, 16, 2)
    assert game.timezone == "America/Los_Angeles" and game.local_finished_at == "2026-06-15T09:02:00"

    again = await client.post("/api/games/claim", json={"start_id": held.id}, headers=auth(carol))
    assert again.status_code == 409 and again.json()["error"]["code"] == "start_consumed"
    assert await count(Game) == 1


async def test_guest_game_obeys_the_same_validation(client, clock):
    late = await play(client, clock, None, late_s=31)
    assert late.status_code == 422 and late.json()["error"]["code"] == "too_late"
    started = await start(client)
    clock.shift(120)
    problems = solved(started["seed"], STANDARD, 5)
    problems[0]["a"] += 1
    r = await finish(client, started, problems)
    assert r.status_code == 422 and r.json()["error"]["code"] == "problems_mismatch"
    assert await count(GameStart) == 0


async def test_guest_cannot_submit_twice(client, clock):
    started = await start(client)
    clock.shift(120)
    assert (await finish(client, started, solved(started["seed"], STANDARD, 5))).status_code == 200
    again = await finish(client, started, solved(started["seed"], STANDARD, 50))
    assert again.status_code == 409


async def test_claim_expires_after_15_minutes(client, make_user, clock):
    carol = await make_user("carol")
    started = await start(client)
    clock.shift(120)
    await finish(client, started, solved(started["seed"], STANDARD, 5))
    clock.shift(timedelta(minutes=13, seconds=1))  # 15m01s after the start
    r = await client.post("/api/games/claim", json={"start_id": started["start_id"]}, headers=auth(carol))
    assert r.status_code == 410 and r.json()["error"]["code"] == "claim_expired"
    assert await count(Game) == 0


async def test_claim_requires_a_finished_guest_game(client, make_user, clock):
    alice, carol = await make_user("alice"), await make_user("carol")
    unfinished = await start(client)
    owned = await start(client, alice)
    for start_id, code, status in (
        (unfinished["start_id"], "not_claimable", 409),
        (owned["start_id"], "not_claimable", 409),
        ("missing", "start_not_found", 404),
    ):
        r = await client.post("/api/games/claim", json={"start_id": start_id}, headers=auth(carol))
        assert (r.status_code, r.json()["error"]["code"]) == (status, code)
    r = await client.post("/api/games/claim", json={"start_id": unfinished["start_id"]})
    assert r.status_code == 401


async def test_signed_in_user_can_finish_a_start_issued_while_signed_out(client, make_user, clock):
    # e.g. the page loaded before the session was ready: the start has no user.
    alice = await make_user("alice")
    started = await start(client)
    clock.shift(120)
    r = await finish(client, started, solved(started["seed"], STANDARD, 6), alice)
    assert r.status_code == 200 and r.json()["saved"] is True
    assert (await only_game()).user_id == alice.id


# --- history ----------------------------------------------------------------------------------------


async def test_history_is_paginated_newest_first(client, make_user):
    alice = await make_user("alice")
    for i in range(25):
        await add_game(alice, 10 + i, utc(2026, 6, 1, 12) + timedelta(hours=i))
    first = (await client.get("/api/games", headers=auth(alice))).json()
    assert [g["score"] for g in first["items"]] == list(range(34, 14, -1))
    assert first["next_cursor"]
    second = (await client.get("/api/games", params={"cursor": first["next_cursor"]}, headers=auth(alice))).json()
    assert [g["score"] for g in second["items"]] == [14, 13, 12, 11, 10]
    assert second["next_cursor"] is None
    assert "problems" not in first["items"][0]


async def test_history_sort_orders(client, make_user):
    alice = await make_user("alice")
    # Scores repeat, so every score order has ties, which come newest first.
    scores = [12, 30, 12, 7, 30, 21, 7, 30]
    games = [await add_game(alice, score, utc(2026, 6, 1, 12) + timedelta(hours=i)) for i, score in enumerate(scores)]
    played = list(range(len(games)))  # indexes in the order played
    expected = {
        "newest": played[::-1],
        "oldest": played,
        "score_desc": sorted(played, key=lambda i: (-scores[i], -i)),
        "score_asc": sorted(played, key=lambda i: (scores[i], -i)),
    }
    for sort, order in expected.items():
        # Three per page, so page boundaries land inside runs of equal scores.
        seen, cursor = [], None
        while True:
            params = {"sort": sort, "limit": 3} | ({"cursor": cursor} if cursor else {})
            page = (await client.get("/api/games", params=params, headers=auth(alice))).json()
            seen += [g["id"] for g in page["items"]]
            cursor = page["next_cursor"]
            if cursor is None:
                break
        assert seen == [games[i].id for i in order], sort

    default = (await client.get("/api/games", headers=auth(alice))).json()
    assert [g["id"] for g in default["items"]] == [g.id for g in games[::-1]]


async def test_history_sort_rejects_bad_input(client, make_user):
    alice = await make_user("alice")
    for i in range(3):
        await add_game(alice, 10 + i, utc(2026, 6, 1, 12) + timedelta(hours=i))
    unknown = await client.get("/api/games", params={"sort": "fastest"}, headers=auth(alice))
    assert (unknown.status_code, unknown.json()["error"]["code"]) == (422, "validation_error")

    # A cursor only works with the sort order that issued it.
    by_time = (await client.get("/api/games", params={"limit": 1}, headers=auth(alice))).json()["next_cursor"]
    by_score = (await client.get("/api/games", params={"limit": 1, "sort": "score_asc"}, headers=auth(alice))).json()[
        "next_cursor"
    ]
    for sort, cursor in (("score_desc", by_time), ("newest", by_score), ("oldest", by_score)):
        r = await client.get("/api/games", params={"sort": sort, "cursor": cursor}, headers=auth(alice))
        assert (r.status_code, r.json()["error"]["code"]) == (422, "invalid_cursor"), sort


async def test_history_filters(client, make_user):
    alice = await make_user("alice")
    await add_game(alice, 30, utc(2026, 6, 1, 12))
    custom = await add_game(alice, 5, utc(2026, 6, 2, 12), settings=CUSTOM)
    by_name = await client.get("/api/games", params={"user": "ALICE", "ranked": "true"}, headers=auth(alice))
    assert [g["score"] for g in by_name.json()["items"]] == [30]
    unranked = await client.get("/api/games", params={"ranked": "false"}, headers=auth(alice))
    assert [g["score"] for g in unranked.json()["items"]] == [5]
    by_hash = await client.get("/api/games", params={"settings_hash": custom.settings_hash}, headers=auth(alice))
    assert [g["id"] for g in by_hash.json()["items"]] == [custom.id]


async def test_history_and_detail_are_private(client, make_user):
    alice, bob = await make_user("alice"), await make_user("bob")
    game = await add_game(alice, 30, utc(2026, 6, 1, 12))

    mine = await client.get(f"/api/games/{game.id}", headers=auth(alice))
    assert mine.status_code == 200 and len(mine.json()["problems"]) == 30

    for headers in (auth(bob), {}):
        assert (await client.get(f"/api/games/{game.id}", headers=headers)).status_code == 403
        assert (await client.get("/api/games", params={"user": "alice"}, headers=headers)).status_code == 403
    assert (await client.get("/api/games")).status_code == 401
    assert (await client.get("/api/games", params={"user": "nobody"}, headers=auth(bob))).status_code == 404
    assert (await client.get("/api/games/missing", headers=auth(bob))).status_code == 404
    bad_cursor = await client.get("/api/games", params={"cursor": "garbage"}, headers=auth(alice))
    assert bad_cursor.status_code == 422


# --- local-time snapshots ----------------------------------------------


@pytest.mark.parametrize(
    "moment, expected",
    [
        # 03:30 UTC on Nov 25 is still the evening of Nov 24 in New York (EST).
        (utc(2026, 11, 25, 3, 30), ("2026-11-24", 22, -300, "2026-11-24T22:30:00")),
        # The same clock time in July is EDT.
        (utc(2026, 7, 25, 3, 30), ("2026-07-24", 23, -240, "2026-07-24T23:30:00")),
        # Spring forward, 2026-03-08: 06:59 UTC is 01:59 EST, 07:00 UTC is 03:00 EDT.
        (utc(2026, 3, 8, 6, 59), ("2026-03-08", 1, -300, "2026-03-08T01:59:00")),
        (utc(2026, 3, 8, 7, 0), ("2026-03-08", 3, -240, "2026-03-08T03:00:00")),
        (utc(2026, 3, 9, 3, 59), ("2026-03-08", 23, -240, "2026-03-08T23:59:00")),
        # Fall back, 2026-11-01: 05:30 UTC is 01:30 EDT, 06:30 UTC is 01:30 EST. Same local day.
        (utc(2026, 11, 1, 5, 30), ("2026-11-01", 1, -240, "2026-11-01T01:30:00")),
        (utc(2026, 11, 1, 6, 30), ("2026-11-01", 1, -300, "2026-11-01T01:30:00")),
        (utc(2026, 11, 2, 4, 59), ("2026-11-01", 23, -300, "2026-11-01T23:59:00")),
    ],
)
async def test_local_fields_for_a_new_york_player(client, make_user, clock, moment, expected):
    alice = await make_user("alice", timezone="America/New_York")
    clock.move_to(moment - timedelta(seconds=120))
    assert (await play(client, clock, alice)).status_code == 200
    game = await only_game()
    assert game.finished_at == moment and game.timezone == "America/New_York"
    assert (game.local_date, game.local_hour, game.utc_offset_min, game.local_finished_at) == expected


async def test_changing_timezone_never_rewrites_past_games(client, make_user, clock):
    alice = await make_user("alice", timezone="America/New_York")
    clock.move_to(utc(2026, 11, 25, 3, 28))
    await play(client, clock, alice)
    before = await only_game()

    r = await client.patch("/api/me", json={"timezone": "Asia/Kolkata"}, headers=auth(alice))
    assert r.status_code == 200
    after = await only_game()
    for field in ("timezone", "utc_offset_min", "local_finished_at", "local_date", "local_hour"):
        assert getattr(after, field) == getattr(before, field)

    # Only games from now on use the new timezone.
    clock.move_to(utc(2026, 11, 25, 3, 40))
    await play(client, clock, alice)
    async with SessionLocal() as session:
        newest = (await session.execute(select(Game).order_by(Game.finished_at.desc()))).scalars().first()
    assert (newest.timezone, newest.local_date, newest.utc_offset_min) == ("Asia/Kolkata", "2026-11-25", 330)


async def test_game_timestamps_read_back_as_aware_utc(client, make_user, clock):
    alice = await make_user("alice")
    await play(client, clock, alice)
    game = await only_game()
    assert game.finished_at.tzinfo is not None and game.finished_at.utcoffset() == timedelta(0)
