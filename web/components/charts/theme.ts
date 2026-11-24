// Shared chart styling: muted axes, no gridline clutter, exact values in tooltips.

export const AXIS_TICK = { fill: "var(--muted)", fontSize: 12 };
export const AXIS_LINE = { stroke: "var(--border)" };
export const LINE_WIDTH = 1.5;

/** Fixed per-member colours for group charts, in assignment order. The order
 *  keeps neighbouring colours distinguishable for colour-blind readers
 *  (checked with a palette validator), so do not reorder or extend it. */
export const MEMBER_COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];

/** Light to dark blue for "how many": the activity heatmap. */
export const HEAT_COLORS = ["var(--border)", "#b7d3f6", "#6da7ec", "#2a78d6", "#184f95"];

export const TOOLTIP_BOX = "rounded-lg border border-border bg-surface px-3 py-2 text-xs shadow-sm";
