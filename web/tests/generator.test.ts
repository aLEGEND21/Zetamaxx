// The shared-fixture contract test. Never skip it.
import { describe, expect, it } from "vitest";
import fixture from "../../shared/fixtures/problems.json";
import { answerOf, displayProblem, drawInt, generateSequence } from "@/lib/generator";
import { mulberry32 } from "@/lib/prng";
import { STANDARD, isStandard, validateSettings, type GameSettings, type Op } from "@/lib/settings";

type Row = [Op, number, number, number, string];
const configs = fixture.configs as unknown as Record<string, GameSettings>;
const problems = fixture.problems as unknown as Record<string, Record<string, Row[]>>;
const prng = fixture.prng as Record<string, number[]>;

describe("mulberry32", () => {
  it("matches the canonical reference values", () => {
    const rng = mulberry32(1);
    const firstThree = [rng(), rng(), rng()].map((x) => Math.floor(x * 4294967296));
    expect(firstThree).toEqual([2693262067, 11749833, 2265367787]);
  });

  it.each(fixture.seeds)("matches the Python fixture for seed %i", (seed) => {
    const rng = mulberry32(seed);
    expect(Array.from({ length: 10 }, () => rng())).toEqual(prng[String(seed)]);
  });
});

describe("generator", () => {
  it("has the expected fixture shape", () => {
    expect(fixture.seeds).toHaveLength(5);
    expect(Object.keys(configs).sort()).toEqual(["custom", "standard"]);
    expect(configs.standard).toEqual(STANDARD);
  });

  for (const config of ["standard", "custom"]) {
    it.each(fixture.seeds)(`reproduces the ${config} fixture for seed %i`, (seed) => {
      const got = generateSequence(seed, configs[config], fixture.count).map(
        (p): Row => [p.op, p.a, p.b, p.answer, p.display],
      );
      expect(got).toHaveLength(200);
      expect(got).toEqual(problems[config][String(seed)]);
    });
  }

  it("can rebuild display and answer from the stored {op, a, b}", () => {
    for (const p of generateSequence(7, STANDARD, 500)) {
      expect(displayProblem(p.op, p.a, p.b)).toBe(p.display);
      expect(answerOf(p.op, p.a, p.b)).toBe(p.answer);
    }
  });

  it("draws cover the inclusive range", () => {
    const rng = mulberry32(99);
    const seen = new Set(Array.from({ length: 500 }, () => drawInt(rng, 2, 5)));
    expect([...seen].sort()).toEqual([2, 3, 4, 5]);
  });
});

describe("settings", () => {
  it("recognises the standard config", () => {
    expect(isStandard(STANDARD)).toBe(true);
    expect(isStandard({ ...STANDARD, duration: 60 })).toBe(false);
    expect(validateSettings(STANDARD)).toBeNull();
  });

  it("rejects invalid configs", () => {
    expect(validateSettings({ ...STANDARD, duration: 45 })).not.toBeNull();
    expect(validateSettings({ ...STANDARD, ops: { add: false, sub: false, mul: false, div: false } })).not.toBeNull();
    expect(validateSettings({ ...STANDARD, add: { a: [50, 10], b: [2, 100] } })).not.toBeNull();
    expect(validateSettings({ ...STANDARD, mul: { a: [0, 12], b: [2, 100] } })).not.toBeNull();
  });
});
