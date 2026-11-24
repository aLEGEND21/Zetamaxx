// Timer math. Everything takes explicit `performance.now()` readings, so the
// countdown is derived from the clock (it cannot drift) and is easy to test.

export function remainingMs(startedAt: number, now: number, durationMs: number): number {
  return Math.max(0, durationMs - (now - startedAt));
}

/** Whole seconds shown on screen: 120 at the start, 1 during the last second, 0 when over. */
export function displaySeconds(remaining: number): number {
  return Math.ceil(remaining / 1000);
}

export function isOver(startedAt: number, now: number, durationMs: number): boolean {
  return now - startedAt >= durationMs;
}

/** Keep only digits: the answer box ignores everything else. */
export function digitsOnly(value: string): string {
  return value.replace(/\D/g, "");
}
