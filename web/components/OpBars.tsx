"use client";

import { Bar, BarChart, LabelList, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { formatMs } from "@/lib/format";
import { OPS, OP_LABELS, type Op } from "@/lib/settings";

export type OpSpeeds = Record<Op, number | null>;

type Props = {
  primary: OpSpeeds;
  primaryLabel: string;
  /** Optional second series, e.g. all-time next to the last 10 games. */
  secondary?: OpSpeeds;
  secondaryLabel?: string;
};

/** Average solve time per operation. Longer bar = slower = weakest operation. */
export function OpBars({ primary, primaryLabel, secondary, secondaryLabel }: Props) {
  // Operations that were never played (switched off in custom mode) get no row.
  const data = OPS.map((op) => ({
    label: OP_LABELS[op],
    primary: primary[op],
    secondary: secondary ? secondary[op] : null,
  })).filter((d) => d.primary != null || d.secondary != null);
  if (data.length === 0) return <p className="py-6 text-center text-sm text-muted">No solved problems yet.</p>;

  return (
    <div className="w-full" style={{ height: 16 + data.length * (secondary ? 48 : 40) }} role="img" aria-label="Average solve time per operation">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} layout="vertical" margin={{ top: 0, right: 56, bottom: 0, left: 0 }} barGap={secondary ? 7 : 2}>
          <XAxis type="number" hide domain={[0, "dataMax"]} />
          <YAxis
            type="category"
            dataKey="label"
            width={104}
            axisLine={false}
            tickLine={false}
            tick={{ fill: "var(--muted)", fontSize: 13 }}
          />
          <Tooltip
            cursor={{ fill: "rgba(0,0,0,0.03)" }}
            formatter={(value, name) => [formatMs(Number(value)), name === "primary" ? primaryLabel : secondaryLabel]}
            contentStyle={{ borderRadius: 8, border: "1px solid var(--border)", fontSize: 13 }}
          />
          <Bar dataKey="primary" fill="var(--accent)" radius={3} barSize={secondary ? 8 : 14} isAnimationActive={false}>
            <LabelList
              dataKey="primary"
              position="right"
              formatter={(v) => (v == null ? "" : formatMs(Number(v)))}
              style={{ fill: "var(--text)", fontSize: 12, fontFamily: "var(--font-mono)" }}
            />
          </Bar>
          {secondary && (
            <Bar dataKey="secondary" fill="#c9c9c9" radius={3} barSize={8} isAnimationActive={false}>
              <LabelList
                dataKey="secondary"
                position="right"
                formatter={(v) => (v == null ? "" : formatMs(Number(v)))}
                style={{ fill: "var(--muted)", fontSize: 12, fontFamily: "var(--font-mono)" }}
              />
            </Bar>
          )}
        </BarChart>
      </ResponsiveContainer>
      <span className="sr-only">
        {data.map((d) => `${d.label}: ${formatMs(d.primary)}`).join(", ")}
      </span>
    </div>
  );
}

export function OpBarsLegend({ primaryLabel, secondaryLabel }: { primaryLabel: string; secondaryLabel: string }) {
  return (
    <div className="flex gap-4 text-xs text-muted">
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2 w-2 rounded-sm bg-accent" /> {primaryLabel}
      </span>
      <span className="flex items-center gap-1.5">
        <span className="inline-block h-2 w-2 rounded-sm bg-[#c9c9c9]" /> {secondaryLabel}
      </span>
    </div>
  );
}
