"use client";

import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { dayNumber, fromDayNumber } from "@/lib/dates";
import { formatLocalDate } from "@/lib/format";
import type { Series, SeriesPoint } from "@/lib/types";
import { AXIS_LINE, AXIS_TICK, LINE_WIDTH, TOOLTIP_BOX } from "./theme";

type Row = SeriesPoint & { day: number };

function ProgressTooltip({ active, payload }: { active?: boolean; payload?: readonly { payload: Row }[] }) {
  const row = active ? payload?.[0]?.payload : undefined;
  if (!row) return null;
  return (
    <div className={TOOLTIP_BOX}>
      <p className="mb-1 text-muted">{formatLocalDate(row.date, true)}</p>
      <p className="nums flex items-center gap-2">
        <span className="inline-block h-0.5 w-3 bg-accent" /> <strong className="font-medium">{row.best}</strong>
        <span className="text-muted">best</span>
      </p>
      <p className="nums flex items-center gap-2">
        <span className="inline-block h-0.5 w-3 bg-[#9a9a9a]" /> <strong className="font-medium">{row.rolling_avg.toFixed(1)}</strong>
        <span className="text-muted">7-game average</span>
      </p>
      <p className="mt-1 text-muted">
        {row.games} {row.games === 1 ? "game" : "games"} · day average {row.avg.toFixed(1)}
      </p>
    </div>
  );
}

export function ProgressLegend() {
  return (
    <div className="flex gap-4 text-xs text-muted">
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-0.5 w-3 bg-accent" /> Daily best
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-0.5 w-3 bg-[#9a9a9a]" /> 7-game average
      </span>
    </div>
  );
}

/** Daily best score with the 7-game rolling average, on a real calendar axis. */
export function ProgressChart({ series }: { series: Series }) {
  const rows: Row[] = series.points.map((point) => ({ ...point, day: dayNumber(point.date) }));
  const from = Math.min(dayNumber(series.from), rows[0]?.day ?? Infinity);
  const to = dayNumber(series.to);
  const showDots = rows.length <= 45;

  return (
    <div className="h-64 w-full" role="img" aria-label={`Daily best score from ${series.from} to ${series.to}`}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
          <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.6} />
          <XAxis
            dataKey="day"
            type="number"
            domain={[from, Math.max(to, from + 1)]}
            tickFormatter={(day) => formatLocalDate(fromDayNumber(Number(day)))}
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
            dataKey="best"
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
