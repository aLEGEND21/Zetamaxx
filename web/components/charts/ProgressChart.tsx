"use client";

import { CartesianGrid, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dayNumber, fromDayNumber, timeOfDayFraction } from "@/lib/dates";
import { formatLocalDate, formatLocalDateTime } from "@/lib/format";
import type { Series } from "@/lib/types";
import { AXIS_LINE, AXIS_TICK, LINE_WIDTH, TOOLTIP_BOX } from "./theme";

export const PROGRESS_RANGES = [
  { value: "7d", label: "7 days" },
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
  { value: "1y", label: "1 year" },
] as const;

/** One plotted point: a single game (7-day view) or a whole day (longer views). */
type Row = {
  /** Position on the time axis, in days since 1970 (fractional for a game: the time it was played). */
  x: number;
  when: string;
  value: number;
  valueLabel: string;
  rolling_avg: number;
  note?: string;
};

function toRows(series: Series): Row[] {
  if (series.per === "game") {
    return series.points.map((game) => ({
      x: dayNumber(game.at.slice(0, 10)) + timeOfDayFraction(game.at),
      when: formatLocalDateTime(game.at),
      value: game.score,
      valueLabel: "score",
      rolling_avg: game.rolling_avg,
    }));
  }
  return series.points.map((day) => ({
    x: dayNumber(day.date),
    when: formatLocalDate(day.date, true),
    value: day.best,
    valueLabel: "best",
    rolling_avg: day.rolling_avg,
    note: `${day.games} ${day.games === 1 ? "game" : "games"} · day average ${day.avg.toFixed(1)}`,
  }));
}

function ProgressTooltip({ active, payload }: { active?: boolean; payload?: readonly { payload: Row }[] }) {
  const row = active ? payload?.[0]?.payload : undefined;
  if (!row) return null;
  return (
    <div className={TOOLTIP_BOX}>
      <p className="mb-1 text-muted">{row.when}</p>
      <p className="nums flex items-center gap-2">
        <span className="inline-block h-0.5 w-3 bg-accent" /> <strong className="font-medium">{row.value}</strong>
        <span className="text-muted">{row.valueLabel}</span>
      </p>
      <p className="nums flex items-center gap-2">
        <span className="inline-block h-0.5 w-3 bg-[#9a9a9a]" /> <strong className="font-medium">{row.rolling_avg.toFixed(1)}</strong>
        <span className="text-muted">7-game average</span>
      </p>
      {row.note && <p className="mt-1 text-muted">{row.note}</p>}
    </div>
  );
}

export function ProgressLegend({ perGame }: { perGame: boolean }) {
  return (
    <div className="flex gap-4 text-xs text-muted">
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-0.5 w-3 bg-accent" /> {perGame ? "Each game" : "Daily best"}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-0.5 w-3 bg-[#9a9a9a]" /> 7-game average
      </span>
    </div>
  );
}

/**
 * Scores over time with the 7-game rolling average, on a real time axis.
 * The 7-day view plots every game at the moment it was played, so games sit
 * closer together or further apart as they actually were; longer views plot
 * each day's best.
 */
export function ProgressChart({ series }: { series: Series }) {
  const rows = toRows(series);
  const perGame = series.per === "game";
  const from = dayNumber(series.from);
  // A game played today sits somewhere inside today, so that view runs to the end of the day.
  const to = dayNumber(series.to) + (perGame ? 1 : 0);
  // In that view each day is a column: its label sits under the middle of the day, with a faint line at each midnight.
  const days = perGame ? Array.from({ length: to - from }, (_, i) => from + i) : [];
  const dayTicks = perGame ? days.map((day) => day + 0.5) : undefined;
  const showDots = rows.length <= (perGame ? 150 : 45);

  return (
    <div
      className="h-64 w-full"
      role="img"
      aria-label={`${perGame ? "Score of every game" : "Daily best score"} from ${series.from} to ${series.to}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.6} />
          <XAxis
            dataKey="x"
            type="number"
            domain={[from, Math.max(to, from + 1)]}
            ticks={dayTicks}
            tickFormatter={(day) => formatLocalDate(fromDayNumber(Math.floor(Number(day))))}
            tick={AXIS_TICK}
            tickLine={false}
            axisLine={AXIS_LINE}
            tickCount={6}
            minTickGap={32}
          />
          <YAxis
            domain={["auto", "auto"]}
            allowDecimals={false}
            tick={{ ...AXIS_TICK, fontFamily: "var(--font-mono)" }}
            tickLine={false}
            axisLine={false}
            width={48}
          />
          {days.slice(1).map((midnight) => (
            <ReferenceLine key={midnight} x={midnight} stroke="var(--border)" strokeOpacity={0.6} />
          ))}
          <Tooltip content={<ProgressTooltip />} cursor={{ stroke: "var(--muted)", strokeWidth: 1 }} />
          <Line
            dataKey="rolling_avg"
            stroke="#9a9a9a"
            strokeWidth={LINE_WIDTH}
            dot={false}
            activeDot={false}
            isAnimationActive={false}
          />
          <Line
            dataKey="value"
            stroke="var(--accent)"
            strokeWidth={LINE_WIDTH}
            dot={showDots ? { r: 2.5, fill: "var(--accent)", stroke: "var(--surface)", strokeWidth: 1 } : false}
            activeDot={{ r: 4, fill: "var(--accent)", stroke: "var(--surface)", strokeWidth: 2 }}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
