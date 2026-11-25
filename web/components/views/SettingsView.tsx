"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { useToast } from "@/components/Toasts";
import { Card, PageShell, Segmented } from "@/components/ui";
import { savePrefs, usePrefs } from "@/lib/prefs";
import {
  DURATIONS,
  OPS,
  OP_LABELS,
  RANGE_MAX,
  RANGE_MIN,
  STANDARD,
  cloneSettings,
  isStandard,
  sameSettings,
  validateSettings,
  type GameSettings,
  type Range,
} from "@/lib/settings";

const INPUT = "h-9 rounded-lg border border-border bg-surface px-2 text-sm";

function RangeInputs({ label, value, onChange }: { label: string; value: Range; onChange: (range: Range) => void }) {
  const field = (index: 0 | 1, name: string) => (
    <input
      type="number"
      inputMode="numeric"
      min={RANGE_MIN}
      max={RANGE_MAX}
      aria-label={`${label}, ${name}`}
      value={Number.isNaN(value[index]) ? "" : value[index]}
      onChange={(event) => {
        const next: Range = [...value];
        next[index] = event.target.value === "" ? NaN : Number(event.target.value);
        onChange(next);
      }}
      className={`nums w-20 ${INPUT}`}
    />
  );
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      ({field(0, "from")}
      <span className="text-muted">to</span>
      {field(1, "to")})
    </span>
  );
}

function CustomModeForm({ initial }: { initial: GameSettings }) {
  const prefs = usePrefs();
  const toast = useToast();
  const [draft, setDraft] = useState(() => cloneSettings(initial));
  const problem = validateSettings(draft);
  const dirty = !sameSettings(draft, prefs.custom);
  const update = (change: (next: GameSettings) => void) => {
    const next = cloneSettings(draft);
    change(next);
    setDraft(next);
  };

  return (
    <form
      className="space-y-5"
      onSubmit={(event) => {
        event.preventDefault();
        if (problem) return;
        savePrefs({ mode: "custom", custom: draft });
        toast("Custom mode saved. It's selected for your next game.");
      }}
    >
      <div className="flex flex-wrap items-center gap-3">
        <span className="w-24 text-sm">Duration</span>
        <Segmented
          label="Duration"
          value={String(draft.duration)}
          options={DURATIONS.map((d) => ({ value: String(d), label: `${d}s` }))}
          onChange={(value) => update((next) => (next.duration = Number(value)))}
        />
      </div>

      <fieldset className="flex flex-wrap items-center gap-x-5 gap-y-2">
        <legend className="float-left w-24 text-sm">Operations</legend>
        {OPS.map((op) => (
          <label key={op} className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={draft.ops[op]}
              onChange={(event) => update((next) => (next.ops[op] = event.target.checked))}
              className="h-4 w-4 accent-[var(--text)]"
            />
            {OP_LABELS[op]}
          </label>
        ))}
      </fieldset>

      <div className="space-y-3">
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-24 text-sm">Addition</span>
          <RangeInputs label="Addition, first number" value={draft.add.a} onChange={(range) => update((next) => (next.add.a = range))} />
          <span className="nums">+</span>
          <RangeInputs label="Addition, second number" value={draft.add.b} onChange={(range) => update((next) => (next.add.b = range))} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="w-24 text-sm">Multiplication</span>
          <RangeInputs label="Multiplication, first number" value={draft.mul.a} onChange={(range) => update((next) => (next.mul.a = range))} />
          <span className="nums">×</span>
          <RangeInputs label="Multiplication, second number" value={draft.mul.b} onChange={(range) => update((next) => (next.mul.b = range))} />
        </div>
        <p className="text-xs text-muted">
          Subtraction uses the addition problems in reverse, and division the multiplication problems in reverse.
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-3">
        <Button type="submit" variant="primary" disabled={!!problem || (!dirty && prefs.mode === "custom")}>
          Save and use custom mode
        </Button>
        <Button variant="ghost" onClick={() => setDraft(cloneSettings(STANDARD))} disabled={isStandard(draft)}>
          Reset to standard
        </Button>
        <span className="text-sm" role="status">
          {problem ? (
            <span className="text-danger">{problem}</span>
          ) : isStandard(draft) ? (
            <span className="text-muted">These are the standard settings, so games count as ranked.</span>
          ) : (
            <span className="text-muted">Custom games are unranked and tracked separately.</span>
          )}
        </span>
      </div>
    </form>
  );
}

/** Only reachable while CUSTOM_MODE is on (proxy.ts answers 404 otherwise). Guests can use it too. */
export function SettingsView() {
  const prefs = usePrefs();
  return (
    <PageShell title="Custom mode">
      <Card>
        {/* Remounts when the stored settings load or change in another tab. */}
        <CustomModeForm key={JSON.stringify(prefs.custom)} initial={prefs.custom} />
      </Card>
    </PageShell>
  );
}
