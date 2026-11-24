// Game settings: the same shape the API validates (api/app/game/settings.py).

export type Op = "add" | "sub" | "mul" | "div";
export const OPS: readonly Op[] = ["add", "sub", "mul", "div"];
export const DURATIONS = [30, 60, 120, 300] as const;
export const RANGE_MIN = 1;
export const RANGE_MAX = 9999;

export type Range = [number, number];
export type Ranges = { a: Range; b: Range };

/** Subtraction reuses the addition ranges and division the multiplication
 *  ranges, because they are those problems in reverse. */
export type GameSettings = {
  duration: number;
  ops: Record<Op, boolean>;
  add: Ranges;
  mul: Ranges;
};

export const STANDARD: GameSettings = {
  duration: 120,
  ops: { add: true, sub: true, mul: true, div: true },
  add: { a: [2, 100], b: [2, 100] },
  mul: { a: [2, 12], b: [2, 100] },
};

export const OP_LABELS: Record<Op, string> = {
  add: "Addition",
  sub: "Subtraction",
  mul: "Multiplication",
  div: "Division",
};

export const OP_SYMBOLS: Record<Op, string> = { add: "+", sub: "−", mul: "×", div: "÷" };

export function cloneSettings(s: GameSettings): GameSettings {
  return {
    duration: s.duration,
    ops: { ...s.ops },
    add: { a: [...s.add.a], b: [...s.add.b] },
    mul: { a: [...s.mul.a], b: [...s.mul.b] },
  };
}

export function sameSettings(x: GameSettings, y: GameSettings): boolean {
  const flat = (s: GameSettings) =>
    [s.duration, ...OPS.map((op) => s.ops[op]), ...s.add.a, ...s.add.b, ...s.mul.a, ...s.mul.b].join(",");
  return flat(x) === flat(y);
}

export function isStandard(s: GameSettings): boolean {
  return sameSettings(s, STANDARD);
}

/** Returns a message describing the first problem, or null when valid. */
export function validateSettings(s: GameSettings): string | null {
  if (!(DURATIONS as readonly number[]).includes(s.duration)) return "Pick a duration.";
  if (!OPS.some((op) => s.ops[op])) return "Enable at least one operation.";
  for (const range of [s.add.a, s.add.b, s.mul.a, s.mul.b]) {
    const [lo, hi] = range;
    if (!Number.isInteger(lo) || !Number.isInteger(hi)) return "Ranges must be whole numbers.";
    if (lo < RANGE_MIN || hi > RANGE_MAX) return `Ranges must stay between ${RANGE_MIN} and ${RANGE_MAX}.`;
    if (lo > hi) return "Each range must go from low to high.";
  }
  return null;
}

/** Short human summary, e.g. "60s · + × ÷ · (10–999)+(1–50) · (3–25)×(11–19)". */
export function describeSettings(s: GameSettings): string {
  if (isStandard(s)) return "Standard · 120s";
  const parts = [`${s.duration}s`, OPS.filter((op) => s.ops[op]).map((op) => OP_SYMBOLS[op]).join(" ")];
  if (s.ops.add || s.ops.sub) parts.push(`(${s.add.a[0]}–${s.add.a[1]}) + (${s.add.b[0]}–${s.add.b[1]})`);
  if (s.ops.mul || s.ops.div) parts.push(`(${s.mul.a[0]}–${s.mul.a[1]}) × (${s.mul.b[0]}–${s.mul.b[1]})`);
  return parts.join(" · ");
}
