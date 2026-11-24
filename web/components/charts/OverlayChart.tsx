"use client";

import { useState } from "react";
import { CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { displayName } from "@/components/UserLink";
import { dayNumber, fromDayNumber } from "@/lib/dates";
import { formatLocalDate } from "@/lib/format";
import type { GroupSeries } from "@/lib/types";
import { AXIS_LINE, AXIS_TICK, LINE_WIDTH, MEMBER_COLORS, TOOLTIP_BOX } from "./theme";

type Member = GroupSeries["members"][number];
type Row = { day: number; values: Record<string, number> };
type Shown = { member: Member; color: string };

function OverlayTooltip({ active, payload, shown }: { active?: boolean; payload?: readonly { payload: Row }[]; shown: Shown[] }) {
  const row = active ? payload?.[0]?.payload : undefined;
  if (!row) return null;
  const lines = shown
    .filter(({ member }) => row.values[member.user.username] !== undefined)
    .sort((x, y) => row.values[y.member.user.username] - row.values[x.member.user.username]);
  return (
    <div className={TOOLTIP_BOX}>
      <p className="mb-1 text-muted">{formatLocalDate(fromDayNumber(row.day), true)}</p>
      {lines.map(({ member, color }) => (
        <p key={member.user.username} className="flex items-center gap-2">
          <span className="inline-block h-0.5 w-3" style={{ backgroundColor: color }} />
          <strong className="nums font-medium">{row.values[member.user.username]}</strong>
          <span className="text-muted">{displayName(member.user)}</span>
        </p>
      ))}
    </div>
  );
}

/** Daily best per member, one line each. Members are switched on and off with
 *  the chips below the chart; at most eight show at once, one per colour, and a
 *  member keeps their colour for as long as they stay switched on. */
export function OverlayChart({ data }: { data: GroupSeries }) {
  const members = data.members;
  // slots[i] is the username drawn in MEMBER_COLORS[i], or null when that colour is free.
  const [slots, setSlots] = useState<(string | null)[]>(() => {
    const withGames = members.filter((m) => m.points.length > 0).map((m) => m.user.username);
    return MEMBER_COLORS.map((_, i) => withGames[i] ?? null);
  });
  const present = new Set(members.map((m) => m.user.username));
  const slotOf = (username: string) => slots.findIndex((name) => name === username);
  const full = slots.every((name) => name !== null && present.has(name));

  const toggle = (username: string) => {
    setSlots((current) => {
      const next = current.map((name) => (name !== null && present.has(name) ? name : null)); // drop members who left
      const index = next.indexOf(username);
      if (index >= 0) next[index] = null;
      else if (next.includes(null)) next[next.indexOf(null)] = username;
      return next;
    });
  };

  const shown: Shown[] = members
    .filter((member) => slotOf(member.user.username) >= 0)
    .map((member) => ({ member, color: MEMBER_COLORS[slotOf(member.user.username)] }));

  // One row per calendar day on which any shown member played.
  const byDay = new Map<number, Row>();
  for (const { member } of shown) {
    for (const point of member.points) {
      const day = dayNumber(point.date);
      const row = byDay.get(day) ?? { day, values: {} };
      row.values[member.user.username] = point.best;
      byDay.set(day, row);
    }
  }
  const rows = [...byDay.values()].sort((x, y) => x.day - y.day);
  const sparse = rows.length <= 45;

  return (
    <div>
      {rows.length === 0 ? (
        <p className="flex h-64 items-center justify-center text-sm text-muted">
          {shown.length === 0 ? "Pick members below to compare them." : "No ranked games in this period."}
        </p>
      ) : (
        <div className="h-64 w-full" role="img" aria-label="Daily best score for each selected member">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: -12 }}>
              <CartesianGrid vertical={false} stroke="var(--border)" strokeOpacity={0.6} />
              <XAxis
                dataKey="day"
                type="number"
                domain={["dataMin", "dataMax"]}
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
              <Tooltip content={<OverlayTooltip shown={shown} />} cursor={{ stroke: "var(--muted)", strokeWidth: 1 }} />
              {shown.map(({ member, color }) => (
                <Line
                  key={member.user.username}
                  // A function, not a key string: usernames may contain dots, which a key path would split on.
                  dataKey={(row: Row) => row.values[member.user.username]}
                  name={member.user.username}
                  stroke={color}
                  strokeWidth={LINE_WIDTH}
                  connectNulls
                  dot={sparse ? { r: 2.5, fill: color, stroke: "var(--surface)", strokeWidth: 1 } : false}
                  activeDot={{ r: 4, fill: color, stroke: "var(--surface)", strokeWidth: 2 }}
                  isAnimationActive={false}
                />
              ))}
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}

      <div className="mt-3 flex flex-wrap gap-2" role="group" aria-label="Members shown in the chart">
        {members.map((member) => {
          const slot = slotOf(member.user.username);
          const on = slot >= 0;
          return (
            <button
              key={member.user.username}
              type="button"
              aria-pressed={on}
              disabled={!on && full}
              title={!on && full ? "Eight members at most. Switch one off first." : undefined}
              onClick={() => toggle(member.user.username)}
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 ${
                on ? "border-border bg-surface text-text" : "border-transparent bg-bg text-muted hover:text-text"
              }`}
            >
              <span
                className="inline-block h-2.5 w-2.5 rounded-full border"
                style={on ? { backgroundColor: MEMBER_COLORS[slot], borderColor: MEMBER_COLORS[slot] } : { borderColor: "var(--muted)" }}
              />
              {displayName(member.user)}
              {member.points.length === 0 && <span className="text-muted">(no games)</span>}
            </button>
          );
        })}
      </div>
    </div>
  );
}
