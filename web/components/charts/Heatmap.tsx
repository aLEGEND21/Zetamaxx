"use client";

import { useEffect, useRef, useState } from "react";
import { monthOf, weekday } from "@/lib/dates";
import { formatLocalDate } from "@/lib/format";
import type { Activity } from "@/lib/types";
import { HEAT_COLORS } from "./theme";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
// A 16px pitch: a year (53 weeks) spans 844px, which fills the card at the full content width.
const CELL = 12;
const GAP = 4;

function level(games: number): number {
  if (games === 0) return 0;
  if (games === 1) return 1;
  if (games <= 3) return 2;
  if (games <= 6) return 3;
  return 4;
}

function describe(day: { date: string; games: number }): string {
  const count = day.games === 0 ? "No games" : day.games === 1 ? "1 game" : `${day.games} games`;
  return `${count} on ${formatLocalDate(day.date, true)}`;
}

/** "12 games", with the figure in the mono font like every other number that changes. */
function GameCount({ games, none = "0 games" }: { games: number; none?: string }) {
  if (games === 0) return <>{none}</>;
  return (
    <>
      <span className="nums">{games}</span> {games === 1 ? "game" : "games"}
    </>
  );
}

/** The last 365 days as a contribution-style grid: one column per week, Sunday on top. */
export function Heatmap({ activity }: { activity: Activity }) {
  const [hovered, setHovered] = useState<{ date: string; games: number } | null>(null);
  const scroller = useRef<HTMLDivElement>(null);

  // On narrow screens the grid scrolls sideways; start at the most recent weeks.
  useEffect(() => {
    const element = scroller.current;
    if (element) element.scrollLeft = element.scrollWidth;
  }, [activity]);

  const days = activity.days;
  if (days.length === 0) return null;
  const offset = weekday(days[0].date); // empty cells before the first day
  const weeks = Math.ceil((offset + days.length) / 7);

  // A month label sits above the first week that contains the 1st of that month.
  const monthLabels: { week: number; label: string }[] = [];
  days.forEach((day, index) => {
    if (day.date.endsWith("-01")) monthLabels.push({ week: Math.floor((offset + index) / 7), label: MONTHS[monthOf(day.date) - 1] });
  });

  return (
    <div>
      <div ref={scroller} className="overflow-x-auto pb-1">
        <div style={{ width: weeks * (CELL + GAP) - GAP }}>
          <div className="relative mb-1 h-4 text-xs text-muted" aria-hidden="true">
            {monthLabels.map(({ week, label }) => (
              <span key={`${week}-${label}`} className="absolute" style={{ left: week * (CELL + GAP) }}>
                {label}
              </span>
            ))}
          </div>
          <div
            role="img"
            aria-label={`${activity.total} games in the last year`}
            className="grid grid-flow-col"
            style={{ gridTemplateRows: `repeat(7, ${CELL}px)`, gridAutoColumns: CELL, gap: GAP }}
            onMouseLeave={() => setHovered(null)}
          >
            {Array.from({ length: offset }, (_, i) => (
              <span key={`pad-${i}`} />
            ))}
            {days.map((day) => (
              <span
                key={day.date}
                title={describe(day)}
                onMouseEnter={() => setHovered(day)}
                className="rounded-[3px] outline-offset-1 hover:outline hover:outline-1 hover:outline-muted"
                style={{ backgroundColor: HEAT_COLORS[level(day.games)] }}
              />
            ))}
          </div>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center justify-between gap-2 text-xs text-muted">
        <span aria-live="off">
          {hovered ? (
            <>
              <GameCount games={hovered.games} none="No games" /> on {formatLocalDate(hovered.date, true)}
            </>
          ) : (
            <>
              <GameCount games={activity.total} /> in the last year
            </>
          )}
        </span>
        <span className="flex items-center gap-1" aria-hidden="true">
          Less
          {HEAT_COLORS.map((color) => (
            <span key={color} className="inline-block rounded-[3px]" style={{ width: CELL, height: CELL, backgroundColor: color }} />
          ))}
          More
        </span>
      </div>
    </div>
  );
}
