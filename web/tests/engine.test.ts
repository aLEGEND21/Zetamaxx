import { describe, expect, it } from "vitest";
import { GameEngine, opAverages, slowest } from "@/lib/engine";
import { generateSequence } from "@/lib/generator";
import { STANDARD } from "@/lib/settings";
import { digitsOnly, displaySeconds, isOver, remainingMs } from "@/lib/timer";

describe("timer", () => {
  it("counts down from the clock, not from ticks", () => {
    expect(remainingMs(1000, 1000, 120_000)).toBe(120_000);
    expect(remainingMs(1000, 61_000, 120_000)).toBe(60_000);
    expect(remainingMs(1000, 121_000, 120_000)).toBe(0);
    expect(remainingMs(1000, 999_999, 120_000)).toBe(0); // never negative
  });

  it("is unaffected by how often it is sampled", () => {
    // Sampling late (a janky frame, a background tab) gives the same answer
    // as sampling on time: there is no accumulated state to drift.
    const startedAt = 5_000.25;
    const lateSample = remainingMs(startedAt, startedAt + 90_000.5, 120_000);
    expect(lateSample).toBeCloseTo(29_999.5);
  });

  it("shows whole seconds, rounding up", () => {
    expect(displaySeconds(120_000)).toBe(120);
    expect(displaySeconds(119_999)).toBe(120);
    expect(displaySeconds(119_000)).toBe(119);
    expect(displaySeconds(1)).toBe(1);
    expect(displaySeconds(0)).toBe(0);
  });

  it("knows when time is up", () => {
    expect(isOver(0, 119_999, 120_000)).toBe(false);
    expect(isOver(0, 120_000, 120_000)).toBe(true);
  });

  it("keeps only digits", () => {
    expect(digitsOnly("12a-3 .4")).toBe("1234");
    expect(digitsOnly("abc")).toBe("");
  });
});

describe("GameEngine", () => {
  const seed = 42;
  const expected = generateSequence(seed, STANDARD, 5);

  it("advances only on the exact answer and logs solve times", () => {
    const engine = new GameEngine(seed, STANDARD, 1000);
    expect(engine.current).toEqual(expected[0]);

    expect(engine.submit("", 1100)).toBe(false);
    expect(engine.submit(String(expected[0].answer).slice(0, 1), 1200)).toBe(false);
    expect(engine.score).toBe(0);

    expect(engine.submit(String(expected[0].answer), 2500)).toBe(true);
    expect(engine.score).toBe(1);
    expect(engine.current).toEqual(expected[1]);
    expect(engine.solved[0]).toEqual({ op: expected[0].op, a: expected[0].a, b: expected[0].b, ms: 1500 });

    // The next problem's clock starts when it is shown.
    expect(engine.submit(String(expected[1].answer), 3250)).toBe(true);
    expect(engine.solved[1].ms).toBe(750);
  });

  it("accepts nothing once time is up", () => {
    const engine = new GameEngine(seed, STANDARD, 0);
    expect(engine.submit(String(expected[0].answer), 120_000)).toBe(false);
    expect(engine.score).toBe(0);
    expect(engine.over(120_000)).toBe(true);
    expect(engine.remaining(120_000)).toBe(0);
  });

  it("produces the same problems as the generator for the seed", () => {
    const engine = new GameEngine(seed, STANDARD, 0);
    for (let i = 0; i < 5; i++) {
      expect(engine.current).toEqual(expected[i]);
      engine.submit(String(engine.current.answer), (i + 1) * 1000);
    }
    expect(engine.solved.reduce((sum, p) => sum + p.ms, 0)).toBe(5000);
  });
});

describe("result helpers", () => {
  const problems = [
    { op: "add" as const, a: 1, b: 2, ms: 1000 },
    { op: "add" as const, a: 3, b: 4, ms: 2000 },
    { op: "mul" as const, a: 5, b: 6, ms: 900 },
  ];

  it("averages per operation", () => {
    expect(opAverages(problems)).toEqual({ add: 1500, sub: null, mul: 900, div: null });
  });

  it("lists the slowest problems first", () => {
    expect(slowest(problems, 2).map((p) => p.ms)).toEqual([2000, 1000]);
  });
});
