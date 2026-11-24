"""mulberry32, bit-for-bit identical to web/lib/prng.ts.

JavaScript does this arithmetic on 32-bit integers; Python ints are unbounded,
so every step is masked back to 32 bits.
"""

from collections.abc import Callable

MASK = 0xFFFFFFFF


def _imul(a: int, b: int) -> int:
    """JavaScript's Math.imul: 32-bit integer multiply."""
    return (a * b) & MASK


def mulberry32(seed: int) -> Callable[[], float]:
    """Return rng() -> float in [0, 1). `seed` is a 32-bit unsigned integer."""
    state = seed & MASK

    def rng() -> float:
        nonlocal state
        state = (state + 0x6D2B79F5) & MASK
        t = state
        t = _imul(t ^ (t >> 15), t | 1)
        t ^= (t + _imul(t ^ (t >> 7), t | 61)) & MASK
        return ((t ^ (t >> 14)) & MASK) / 4294967296

    return rng
