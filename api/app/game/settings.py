"""Game settings: shape, validation, the standard (ranked) config, and hashing."""

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

Op = Literal["add", "sub", "mul", "div"]
OPS: tuple[Op, ...] = ("add", "sub", "mul", "div")
DURATIONS = (30, 60, 120, 300)
RANGE_MIN, RANGE_MAX = 1, 9999


class OpToggles(BaseModel):
    model_config = ConfigDict(extra="forbid")
    add: bool
    sub: bool
    mul: bool
    div: bool


class Ranges(BaseModel):
    """Inclusive [lo, hi] ranges for the two operands."""

    model_config = ConfigDict(extra="forbid")
    a: tuple[int, int]
    b: tuple[int, int]

    @model_validator(mode="after")
    def _check(self):
        for lo, hi in (self.a, self.b):
            if not (RANGE_MIN <= lo <= hi <= RANGE_MAX):
                raise ValueError(f"ranges must satisfy {RANGE_MIN} <= lo <= hi <= {RANGE_MAX}")
        return self


class GameSettings(BaseModel):
    """Subtraction reuses the addition ranges and division the multiplication
    ranges, because they are those problems in reverse."""

    model_config = ConfigDict(extra="forbid")
    duration: Literal[30, 60, 120, 300]
    ops: OpToggles
    add: Ranges
    mul: Ranges

    @model_validator(mode="after")
    def _at_least_one_op(self):
        if not any(getattr(self.ops, op) for op in OPS):
            raise ValueError("enable at least one operation")
        return self

    def as_dict(self) -> dict:
        return self.model_dump(mode="json")


STANDARD: dict = {
    "duration": 120,
    "ops": {"add": True, "sub": True, "mul": True, "div": True},
    "add": {"a": [2, 100], "b": [2, 100]},
    "mul": {"a": [2, 12], "b": [2, 100]},
}


def canonical_json(settings: dict) -> str:
    return json.dumps(settings, sort_keys=True, separators=(",", ":"))


def settings_hash(settings: dict) -> str:
    return hashlib.sha256(canonical_json(settings).encode()).hexdigest()


STANDARD_HASH = settings_hash(STANDARD)


def is_standard(settings: dict) -> bool:
    return settings_hash(settings) == STANDARD_HASH
