// The game itself, with no React and no network: a seed, the settings, the
// current problem, and the log of solved problems. The UI feeds it keystrokes
// and clock readings.

import { generateProblem, type Problem } from "./generator";
import { mulberry32, type Rng } from "./prng";
import type { GameSettings, Op } from "./settings";
import { isOver, remainingMs } from "./timer";

export type SolvedProblem = { op: Op; a: number; b: number; ms: number };

export class GameEngine {
  readonly durationMs: number;
  readonly solved: SolvedProblem[] = [];
  current: Problem;
  private readonly rng: Rng;
  private shownAt: number;

  constructor(
    readonly seed: number,
    readonly settings: GameSettings,
    readonly startedAt: number,
  ) {
    this.durationMs = settings.duration * 1000;
    this.rng = mulberry32(seed);
    this.current = generateProblem(this.rng, settings);
    this.shownAt = startedAt;
  }

  get score(): number {
    return this.solved.length;
  }

  remaining(now: number): number {
    return remainingMs(this.startedAt, now, this.durationMs);
  }

  over(now: number): boolean {
    return isOver(this.startedAt, now, this.durationMs);
  }

  /** Call on every keystroke. Returns true when `input` is the answer, in
   *  which case the problem is logged and the next one becomes current. */
  submit(input: string, now: number): boolean {
    if (this.over(now) || input !== String(this.current.answer)) return false;
    const { op, a, b } = this.current;
    this.solved.push({ op, a, b, ms: Math.round(now - this.shownAt) });
    this.current = generateProblem(this.rng, this.settings);
    this.shownAt = now;
    return true;
  }
}

export function slowest(problems: SolvedProblem[], count = 5): SolvedProblem[] {
  return [...problems].sort((x, y) => y.ms - x.ms).slice(0, count);
}
