"""Problem generator, identical to web/lib/generator.ts (same draws, same order).

Draw order per problem:
  1. the operation, from the enabled ones in the fixed order add, sub, mul, div
  2. the first operand
  3. the second operand

`a` and `b` are the operands as displayed, so every problem reads `a <symbol> b`:
  add  x + y        answer x + y
  sub  (x+y) - x    answer y      (an addition problem in reverse)
  mul  x * y        answer x * y
  div  (x*y) / x    answer y      (a multiplication problem in reverse)
"""

import math
from collections.abc import Callable
from typing import TypedDict

from app.game.prng import mulberry32
from app.game.settings import OPS

SYMBOLS = {"add": "+", "sub": "−", "mul": "×", "div": "÷"}


class Problem(TypedDict):
    op: str
    a: int
    b: int
    display: str
    answer: int


def draw_int(rng: Callable[[], float], lo: int, hi: int) -> int:
    return lo + math.floor(rng() * (hi - lo + 1))


def generate_problem(rng: Callable[[], float], settings: dict) -> Problem:
    enabled = [op for op in OPS if settings["ops"][op]]
    op = enabled[math.floor(rng() * len(enabled))]
    ranges = settings["add"] if op in ("add", "sub") else settings["mul"]
    x = draw_int(rng, ranges["a"][0], ranges["a"][1])
    y = draw_int(rng, ranges["b"][0], ranges["b"][1])
    if op == "add":
        a, b, answer = x, y, x + y
    elif op == "sub":
        a, b, answer = x + y, x, y
    elif op == "mul":
        a, b, answer = x, y, x * y
    else:
        a, b, answer = x * y, x, y
    return {"op": op, "a": a, "b": b, "display": f"{a} {SYMBOLS[op]} {b}", "answer": answer}


def generate_sequence(seed: int, settings: dict, count: int) -> list[Problem]:
    rng = mulberry32(seed)
    return [generate_problem(rng, settings) for _ in range(count)]
