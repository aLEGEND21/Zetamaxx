"""Stats against hand-computed fixtures, including the timezone and daylight-saving cases."""

from datetime import date, timedelta

import pytest

from app.services import stats
from tests.conftest import auth
from tests.helpers import add_game, utc

CUSTOM = {
    "duration": 30,
    "ops": {"add": True, "sub": False, "mul": False, "div": False},
    "add": {"a": [1, 9], "b": [1, 9]},
    "mul": {"a": [2, 12], "b": [2, 100]},
}


async def get_stats(client, user, viewer=None, **params):
    r = await client.get(f"/api/users/{user.username}/stats", params=params, headers=auth(viewer or user))
    assert r.status_code == 200, r.text
    return r.json()


async def test_empty_profile(client, make_user, clock):
    alice = await make_user("alice")
    body = await get_stats(client, alice)
    assert body["visible"] is True and body["is_self"] is True
    assert body["pb"] is None and body["games"] == 0 and body["recent_avg"] is None
    assert body["improvement"] is None and body["streak"] == 0 and body["last_played"] is None

    series = await client.get("/api/users/alice/series", headers=auth(alice))
    assert series.json()["points"] == []
    activity = await client.get("/api/users/alice/activity", headers=auth(alice))
    assert activity.json()["total"] == 0 and len(activity.json()["days"]) == 365


async def test_pb_recent_average_and_count(client, make_user, clock):
    alice = await make_user("alice")
    # 12 ranked games, oldest first. The last 10 are 22..40 step 2 (mean 31).
    scores = [50, 10, 22, 24, 26, 28, 30, 32, 34, 36, 38, 40]
    for i, score in enumerate(scores):
        await add_game(alice, score, utc(2026, 6, 1, 15) + timedelta(hours=i))
    # Custom games never touch ranked stats.
    await add_game(alice, 99, utc(2026, 6, 2, 15), settings=CUSTOM)

    body = await get_stats(client, alice)
    assert body["pb"] == 50 and body["games"] == 12
    assert body["recent_avg"] == 31.0
    assert body["last_played"] == "2026-06-01T22:00:00"  # 02:00 UTC next day is 22:00 EDT


async def test_settings_hash_filter_switches_to_that_config(client, make_user, clock):
    alice = await make_user("alice")
    await add_game(alice, 40, utc(2026, 6, 1, 15))
    first = await add_game(alice, 12, utc(2026, 6, 2, 15), settings=CUSTOM)
    await add_game(alice, 18, utc(2026, 6, 3, 15), settings=CUSTOM)

    body = await get_stats(client, alice, settings_hash=first.settings_hash)
    assert body["pb"] == 18 and body["games"] == 2 and body["recent_avg"] == 15.0

    configs = (await client.get("/api/users/alice/configs", headers=auth(alice))).json()["configs"]
    assert len(configs) == 1
    assert configs[0]["settings"] == CUSTOM and configs[0]["settings_hash"] == first.settings_hash
    assert (configs[0]["games"], configs[0]["best"], configs[0]["avg"]) == (2, 18, 15.0)
    assert configs[0]["last_played"] == "2026-06-03"


async def test_improvement_compares_with_30_days_ago(client, make_user, clock):
    alice = await make_user("alice")
    now = utc(2026, 6, 15, 16)  # the frozen clock
    # 40 days ago: three games averaging 20.
    for i, score in enumerate([18, 20, 22]):
        await add_game(alice, score, now - timedelta(days=40) + timedelta(minutes=i))
    assert (await get_stats(client, alice))["improvement"] == 0.0  # nothing newer yet

    # This week: two games of 30. Recent average is now (18+20+22+30+30)/5 = 24.
    for i in range(2):
        await add_game(alice, 30, now - timedelta(days=2) + timedelta(minutes=i))
    body = await get_stats(client, alice)
    assert body["recent_avg"] == 24.0
    assert body["improvement"] == 4.0  # 24 now vs 20 as of 30 days ago


async def test_improvement_is_null_without_history_30_days_back(client, make_user, clock):
    alice = await make_user("alice")
    await add_game(alice, 30, utc(2026, 6, 14, 16))
    assert (await get_stats(client, alice))["improvement"] is None


async def test_daily_series_and_rolling_average(client, make_user, clock):
    alice = await make_user("alice", timezone="UTC")
    # Day 1: 10, 20   Day 2: 30   Day 4: 40, 50, 60, 70, 80
    games = [(10, 10), (10, 20), (11, 30), (13, 40), (13, 50), (13, 60), (13, 70), (13, 80)]
    for i, (day, score) in enumerate(games):
        await add_game(alice, score, utc(2026, 6, day, 12, i))

    r = await client.get("/api/users/alice/series", params={"range": "30d"}, headers=auth(alice))
    body = r.json()
    assert body["to"] == "2026-06-15" and body["from"] == "2026-05-17"
    assert body["points"] == [
        {"date": "2026-06-10", "best": 20, "avg": 15.0, "games": 2, "rolling_avg": 15.0},
        {"date": "2026-06-11", "best": 30, "avg": 30.0, "games": 1, "rolling_avg": 20.0},
        # After the 8th game the window is the last 7: 20..80, mean 50.
        {"date": "2026-06-13", "best": 80, "avg": 60.0, "games": 5, "rolling_avg": 50.0},
    ]


async def test_series_range_keeps_rolling_history(client, make_user, clock):
    alice = await make_user("alice", timezone="UTC")
    await add_game(alice, 10, utc(2026, 1, 5, 12))  # long before the 30-day window
    await add_game(alice, 30, utc(2026, 6, 14, 12))
    r = await client.get("/api/users/alice/series", params={"range": "30d"}, headers=auth(alice))
    # Only the recent day is in range, but its rolling mean still includes the old game.
    assert r.json()["points"] == [{"date": "2026-06-14", "best": 30, "avg": 30.0, "games": 1, "rolling_avg": 20.0}]
    everything = await client.get("/api/users/alice/series", params={"range": "all"}, headers=auth(alice))
    assert [p["date"] for p in everything.json()["points"]] == ["2026-01-05", "2026-06-14"]
    assert everything.json()["from"] == "2026-01-05"
    bad = await client.get("/api/users/alice/series", params={"range": "2w"}, headers=auth(alice))
    assert bad.status_code == 422


async def test_activity_has_365_distinct_days_across_dst(client, make_user, clock):
    alice = await make_user("alice", timezone="America/New_York")
    clock.move_to(utc(2026, 11, 24, 18))
    # Games on both DST change days and one today.
    await add_game(alice, 10, utc(2026, 3, 8, 16))
    await add_game(alice, 10, utc(2026, 3, 8, 17))
    await add_game(alice, 10, utc(2026, 11, 1, 5, 30))
    await add_game(alice, 10, utc(2026, 11, 1, 6, 30))  # the repeated 1 AM hour
    await add_game(alice, 10, utc(2026, 11, 24, 17))

    body = (await client.get("/api/users/alice/activity", headers=auth(alice))).json()
    days = [d["date"] for d in body["days"]]
    assert len(days) == 365 and len(set(days)) == 365
    assert days[-1] == "2026-11-24" and days[0] == "2025-11-25"
    assert days == sorted(days)
    by_date = {d["date"]: d["games"] for d in body["days"]}
    assert by_date["2026-03-08"] == 2 and by_date["2026-11-01"] == 2 and by_date["2026-11-24"] == 1
    assert body["total"] == 5


def test_date_range_steps_whole_dates():
    days = stats.date_range(date(2026, 11, 24), 365)
    assert len(set(days)) == 365
    assert all(b - a == timedelta(days=1) for a, b in zip(days, days[1:], strict=False))
    assert date(2026, 3, 8) in days and date(2026, 11, 1) in days


# --- streak -------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "played_days_ago, expected",
    [
        ([], 0),
        ([0], 1),
        ([1], 1),  # yesterday still counts as a live streak
        ([2], 0),  # two days ago does not
        ([0, 1, 2], 3),
        ([1, 2, 3], 3),
        ([0, 2, 3], 1),  # gap yesterday
        ([0, 1, 3, 4], 2),
    ],
)
async def test_streak(client, make_user, clock, played_days_ago, expected):
    alice = await make_user("alice", timezone="UTC")
    for days_ago in played_days_ago:
        await add_game(alice, 10, utc(2026, 6, 15, 9) - timedelta(days=days_ago))
        await add_game(alice, 10, utc(2026, 6, 15, 10) - timedelta(days=days_ago))  # two a day: still one day
    assert (await get_stats(client, alice))["streak"] == expected


async def test_streak_uses_the_owners_today_not_the_servers(client, make_user, clock):
    # 11:30 PM Eastern on Nov 24 is already 04:30 UTC on Nov 25 (and Nov 25 13:30 in Tokyo,
    # the forced process timezone). The owner's "today" is still Nov 24.
    alice = await make_user("alice", timezone="America/New_York")
    for day in (22, 23, 24):
        await add_game(alice, 10, utc(2026, 11, day, 20))  # 3 PM Eastern each day
    clock.move_to(utc(2026, 11, 25, 4, 30))
    await add_game(alice, 10, utc(2026, 11, 25, 4, 29))  # 11:29 PM Eastern, Nov 24
    assert (await get_stats(client, alice))["streak"] == 3

    # A Tokyo player with games on the same UTC instants has different days.
    kenji = await make_user("kenji", timezone="Asia/Tokyo")
    for day in (22, 23, 24):
        await add_game(kenji, 10, utc(2026, 11, day, 20))  # 5 AM the next day in Tokyo: Nov 23, 24, 25
    assert (await get_stats(client, kenji))["streak"] == 3


async def test_changing_timezone_does_not_change_a_past_streak(client, make_user, clock):
    alice = await make_user("alice", timezone="America/New_York")
    clock.move_to(utc(2026, 11, 24, 23))  # 6 PM Eastern, Nov 24
    for day in (22, 23, 24):
        await add_game(alice, 10, utc(2026, 11, day, 22))
    assert (await get_stats(client, alice))["streak"] == 3
    activity_before = (await client.get("/api/users/alice/activity", headers=auth(alice))).json()

    r = await client.patch("/api/me", json={"timezone": "Europe/London"}, headers=auth(alice))
    assert r.status_code == 200
    assert (await get_stats(client, alice))["streak"] == 3
    activity_after = (await client.get("/api/users/alice/activity", headers=auth(alice))).json()
    played = lambda body: [d for d in body["days"] if d["games"]]  # noqa: E731
    assert played(activity_after) == played(activity_before)


# --- visibility (strangers) -----------------------------------------------------------------------


async def test_strangers_and_guests_see_only_username_and_pb(client, make_user, clock):
    alice, bob = await make_user("alice", display_name="Alice A"), await make_user("bob")
    await add_game(alice, 42, utc(2026, 6, 14, 12))
    for headers in (auth(bob), {}):
        r = await client.get("/api/users/alice/stats", headers=headers)
        assert r.status_code == 200
        assert r.json() == {
            "user": {"username": "alice", "display_name": None, "avatar_url": None},
            "visible": False,
            "is_self": False,
            "pb": 42,
        }
        for path in ("series", "activity", "configs"):
            denied = await client.get(f"/api/users/alice/{path}", headers=headers)
            assert denied.status_code == 403 and denied.json()["error"]["code"] == "forbidden"
    assert (await client.get("/api/users/nobody/stats")).status_code == 404
