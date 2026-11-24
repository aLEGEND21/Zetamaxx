"""The shared-fixture contract test. Never skip it."""

import json

import pytest

from app.game.fixture import FIXTURE_PATH
from app.game.generator import draw_int, generate_sequence
from app.game.prng import mulberry32
from app.game.settings import STANDARD, GameSettings, is_standard, settings_hash

FIXTURE = json.loads(FIXTURE_PATH.read_text())


def test_fixture_has_expected_shape():
    assert len(FIXTURE["seeds"]) == 5
    assert set(FIXTURE["configs"]) == {"standard", "custom"}
    assert FIXTURE["configs"]["standard"] == STANDARD
    for by_seed in FIXTURE["problems"].values():
        assert all(len(rows) == 200 for rows in by_seed.values())


@pytest.mark.parametrize("seed", FIXTURE["seeds"])
def test_prng_matches_fixture(seed):
    rng = mulberry32(seed)
    assert [rng() for _ in range(10)] == FIXTURE["prng"][str(seed)]


def test_prng_known_values():
    # Reference values from the canonical JavaScript mulberry32 with seed 1.
    rng = mulberry32(1)
    assert [int(rng() * 4294967296) for _ in range(3)] == [2693262067, 11749833, 2265367787]


@pytest.mark.parametrize("config", ["standard", "custom"])
@pytest.mark.parametrize("seed", FIXTURE["seeds"])
def test_generator_matches_fixture(config, seed):
    settings = FIXTURE["configs"][config]
    got = [
        [p["op"], p["a"], p["b"], p["answer"], p["display"]]
        for p in generate_sequence(seed, settings, FIXTURE["count"])
    ]
    assert got == FIXTURE["problems"][config][str(seed)]


def test_standard_ranges_and_answers():
    seen_ops = set()
    for p in generate_sequence(7, STANDARD, 2000):
        seen_ops.add(p["op"])
        if p["op"] == "add":
            assert 2 <= p["a"] <= 100 and 2 <= p["b"] <= 100 and p["answer"] == p["a"] + p["b"]
        elif p["op"] == "sub":
            assert 2 <= p["b"] <= 100 and 2 <= p["answer"] <= 100 and p["answer"] == p["a"] - p["b"]
        elif p["op"] == "mul":
            assert 2 <= p["a"] <= 12 and 2 <= p["b"] <= 100 and p["answer"] == p["a"] * p["b"]
        else:
            assert 2 <= p["b"] <= 12 and 2 <= p["answer"] <= 100 and p["answer"] * p["b"] == p["a"]
    assert seen_ops == {"add", "sub", "mul", "div"}


def test_draw_int_covers_inclusive_range():
    rng = mulberry32(99)
    values = {draw_int(rng, 2, 5) for _ in range(500)}
    assert values == {2, 3, 4, 5}


def test_settings_hash_is_stable_and_order_independent():
    reordered = {"mul": STANDARD["mul"], "add": STANDARD["add"], "ops": STANDARD["ops"], "duration": 120}
    assert settings_hash(reordered) == settings_hash(STANDARD)
    assert is_standard(GameSettings.model_validate(STANDARD).as_dict())
    assert not is_standard({**STANDARD, "duration": 60})


@pytest.mark.parametrize(
    "bad",
    [
        {**STANDARD, "duration": 45},
        {**STANDARD, "ops": {"add": False, "sub": False, "mul": False, "div": False}},
        {**STANDARD, "add": {"a": [50, 10], "b": [2, 100]}},
        {**STANDARD, "mul": {"a": [0, 12], "b": [2, 100]}},
        {**STANDARD, "extra": 1},
    ],
)
def test_invalid_settings_rejected(bad):
    with pytest.raises(ValueError):
        GameSettings.model_validate(bad)
