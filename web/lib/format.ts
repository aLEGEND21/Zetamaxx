// Display helpers. Dates and times from the API are already in the player's
// local time and arrive as plain strings; they are formatted as text and never
// passed to `new Date()` (which would treat "YYYY-MM-DD" as UTC midnight).

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** 1520 -> "1.52s" */
export function formatMs(ms: number | null | undefined): string {
  return ms == null ? "–" : `${(ms / 1000).toFixed(2)}s`;
}

/** "2026-11-24" -> "Nov 24" (or "Nov 24, 2026" with the year). */
export function formatLocalDate(localDate: string, withYear = false): string {
  const [year, month, day] = localDate.split("-").map(Number);
  const base = `${MONTHS[month - 1]} ${day}`;
  return withYear ? `${base}, ${year}` : base;
}

/** "2026-11-24T22:41:05" -> "10:41 PM", exactly as the player experienced it. */
export function formatLocalTime(localDateTime: string): string {
  const [hour, minute] = localDateTime.slice(11, 16).split(":").map(Number);
  const suffix = hour < 12 ? "AM" : "PM";
  return `${hour % 12 === 0 ? 12 : hour % 12}:${String(minute).padStart(2, "0")} ${suffix}`;
}

/** "2026-11-24T22:41:05" -> "Nov 24, 10:41 PM" */
export function formatLocalDateTime(localDateTime: string): string {
  return `${formatLocalDate(localDateTime.slice(0, 10))}, ${formatLocalTime(localDateTime)}`;
}

export function formatScore(value: number | null | undefined, digits = 0): string {
  return value == null ? "–" : value.toFixed(digits);
}

export function signed(value: number, digits = 1): string {
  const text = Math.abs(value).toFixed(digits);
  return value > 0 ? `+${text}` : value < 0 ? `−${text}` : text;
}
