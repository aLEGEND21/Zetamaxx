// mulberry32, bit-for-bit identical to api/app/game/prng.py.

export type Rng = () => number;

/** Returns rng() -> number in [0, 1). `seed` is a 32-bit unsigned integer. */
export function mulberry32(seed: number): Rng {
  let state = seed >>> 0;
  return () => {
    state = (state + 0x6d2b79f5) >>> 0;
    let t = state;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** A random 32-bit seed for games that are not backed by the server. */
export function randomSeed(): number {
  return crypto.getRandomValues(new Uint32Array(1))[0];
}
