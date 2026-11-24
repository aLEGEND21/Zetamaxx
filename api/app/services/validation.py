"""Server-side validation of a submitted game.

The server replays the problem sequence from the seed it issued, so a client
cannot invent problems, and checks the timings against its own clock.
"""

from dataclasses import dataclass
from datetime import datetime

from app.game.generator import generate_sequence
from app.game.settings import OPS

SUM_TOLERANCE_MS = 2_000  # slack on the client's own timings
DEADLINE_GRACE_MS = 30_000  # the game must arrive within this long after it should end
MIN_HUMAN_MS = 150  # nobody answers a two-digit problem faster
MAX_FAST_FRACTION = 0.10  # more than this share of sub-150ms answers is rejected
MAX_PROBLEMS = 2_000


class Rejected(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message


@dataclass
class Validated:
    problems: list[dict]  # [{op, a, b, ms}], exactly as stored
    score: int
    flagged: bool
    avg_ms: dict[str, int | None]


def validate_submission(
    *, seed: int, settings: dict, started_at: datetime, received_at: datetime, problems: list[dict]
) -> Validated:
    duration_ms = settings["duration"] * 1000
    elapsed_ms = (received_at - started_at).total_seconds() * 1000

    # Strict deadline: received within 30 seconds of when the game should finish.
    if elapsed_ms > duration_ms + DEADLINE_GRACE_MS:
        raise Rejected("too_late", "This game was submitted too long after it ended")

    # A game nobody answered (the page was left open, say) counts as abandoned, not as a score of zero.
    if not problems:
        raise Rejected("no_answers", "A game with no answers is not saved")

    if len(problems) > MAX_PROBLEMS:
        raise Rejected("problems_mismatch", "Too many problems")

    # The submitted problems must be exactly the first N the seed produces.
    expected = generate_sequence(seed, settings, len(problems))
    for got, want in zip(problems, expected, strict=True):
        if (got["op"], got["a"], got["b"]) != (want["op"], want["a"], want["b"]):
            raise Rejected("problems_mismatch", "Submitted problems do not match this game")

    total_ms = sum(p["ms"] for p in problems)
    if total_ms > duration_ms + SUM_TOLERANCE_MS:
        raise Rejected("time_exceeded", "Solve times add up to more than the game's duration")
    if elapsed_ms < total_ms - SUM_TOLERANCE_MS:
        raise Rejected("too_fast", "This game was submitted before it could have been played")

    fast = sum(1 for p in problems if p["ms"] < MIN_HUMAN_MS)
    if fast / len(problems) > MAX_FAST_FRACTION:
        raise Rejected("answers_too_fast", "Too many answers were faster than humanly possible")

    stored = [{"op": p["op"], "a": p["a"], "b": p["b"], "ms": p["ms"]} for p in problems]
    return Validated(problems=stored, score=len(stored), flagged=fast > 0, avg_ms=op_averages(stored))


def op_averages(problems: list[dict]) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for op in OPS:
        times = [p["ms"] for p in problems if p["op"] == op]
        result[op] = round(sum(times) / len(times)) if times else None
    return result
