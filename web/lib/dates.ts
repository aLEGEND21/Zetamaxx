// Calendar-date arithmetic on "YYYY-MM-DD" strings from the API.
//
// A date is turned into a day number (days since 1970-01-01) with Date.UTC, and
// back with UTC getters. No local timezone is ever involved, so a date can
// never shift to the previous day the way `new Date("2026-11-24")` does in US
// timezones.

const DAY_MS = 86_400_000;

export function dayNumber(localDate: string): number {
  const [year, month, day] = localDate.split("-").map(Number);
  return Date.UTC(year, month - 1, day) / DAY_MS;
}

export function fromDayNumber(day: number): string {
  return new Date(day * DAY_MS).toISOString().slice(0, 10);
}

/** 0 = Sunday ... 6 = Saturday. */
export function weekday(localDate: string): number {
  return (((dayNumber(localDate) + 4) % 7) + 7) % 7; // 1970-01-01 was a Thursday
}

export function monthOf(localDate: string): number {
  return Number(localDate.slice(5, 7));
}
