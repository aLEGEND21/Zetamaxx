// Problem generator, identical to api/app/game/generator.py (same draws, same order).
//
// Draw order per problem:
//   1. the operation, from the enabled ones in the fixed order add, sub, mul, div
//   2. the first operand
//   3. the second operand
//
// `a` and `b` are the operands as displayed, so every problem reads `a <symbol> b`:
//   add  x + y        answer x + y
//   sub  (x+y) - x    answer y      (an addition problem in reverse)
//   mul  x * y        answer x * y
//   div  (x*y) / x    answer y      (a multiplication problem in reverse)

import { mulberry32, type Rng } from "./prng";
import { OPS, OP_SYMBOLS, type GameSettings, type Op } from "./settings";

export type Problem = { op: Op; a: number; b: number; display: string; answer: number };

export function drawInt(rng: Rng, lo: number, hi: number): number {
  return lo + Math.floor(rng() * (hi - lo + 1));
}

export function displayProblem(op: Op, a: number, b: number): string {
  return `${a} ${OP_SYMBOLS[op]} ${b}`;
}

export function answerOf(op: Op, a: number, b: number): number {
  if (op === "add") return a + b;
  if (op === "sub") return a - b;
  if (op === "mul") return a * b;
  return a / b;
}

export function generateProblem(rng: Rng, settings: GameSettings): Problem {
  const enabled = OPS.filter((op) => settings.ops[op]);
  const op = enabled[Math.floor(rng() * enabled.length)];
  const ranges = op === "add" || op === "sub" ? settings.add : settings.mul;
  const x = drawInt(rng, ranges.a[0], ranges.a[1]);
  const y = drawInt(rng, ranges.b[0], ranges.b[1]);
  let a: number, b: number, answer: number;
  if (op === "add") [a, b, answer] = [x, y, x + y];
  else if (op === "sub") [a, b, answer] = [x + y, x, y];
  else if (op === "mul") [a, b, answer] = [x, y, x * y];
  else [a, b, answer] = [x * y, x, y];
  return { op, a, b, display: displayProblem(op, a, b), answer };
}

export function generateSequence(seed: number, settings: GameSettings, count: number): Problem[] {
  const rng = mulberry32(seed);
  return Array.from({ length: count }, () => generateProblem(rng, settings));
}
