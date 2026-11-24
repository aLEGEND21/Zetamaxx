import type { TimeBucket } from "@/lib/types";

const LABELS: Record<TimeBucket["bucket"], { name: string; hours: string }> = {
  morning: { name: "Morning", hours: "5 AM – 12 PM" },
  afternoon: { name: "Afternoon", hours: "12 – 5 PM" },
  evening: { name: "Evening", hours: "5 – 10 PM" },
  late_night: { name: "Late night", hours: "10 PM – 5 AM" },
};

/** When this player plays (bar length = games) and how they score then. */
export function TimeOfDay({ buckets }: { buckets: TimeBucket[] }) {
  const most = Math.max(...buckets.map((b) => b.games), 1);
  const scores = buckets.filter((b) => b.avg_score != null).map((b) => b.avg_score as number);
  const best = scores.length > 1 ? Math.max(...scores) : null;

  return (
    <ul className="space-y-3">
      {buckets.map((bucket) => {
        const label = LABELS[bucket.bucket];
        const isBest = best != null && bucket.avg_score === best;
        return (
          <li key={bucket.bucket} title={`${label.name} (${label.hours})`}>
            <div className="flex items-baseline justify-between gap-3 text-sm">
              <span>
                {label.name} <span className="text-xs text-muted">{label.hours}</span>
              </span>
              <span className="nums text-xs text-muted">
                {bucket.games} {bucket.games === 1 ? "game" : "games"}
                {bucket.avg_score != null && (
                  <>
                    {" · avg "}
                    <span className={isBest ? "font-medium text-text" : ""}>{bucket.avg_score.toFixed(1)}</span>
                  </>
                )}
              </span>
            </div>
            <div className="mt-1 h-2 rounded-r-[4px] bg-bg">
              <div
                className={`h-2 rounded-r-[4px] ${isBest ? "bg-accent" : "bg-[#c9c9c9]"}`}
                style={{ width: `${(bucket.games / most) * 100}%` }}
              />
            </div>
          </li>
        );
      })}
      {best != null && <li className="text-xs text-muted">Blue marks the time of day with the highest average score.</li>}
    </ul>
  );
}
