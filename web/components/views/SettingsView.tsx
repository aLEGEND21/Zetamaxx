"use client";

import { Show, UserProfile } from "@clerk/nextjs";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useState } from "react";
import { Button, buttonClass } from "@/components/Button";
import { useToast } from "@/components/Toasts";
import { Card, PageShell, Segmented } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import { CUSTOM_MODE } from "@/lib/features";
import { useMe } from "@/lib/hooks";
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
import type { Me } from "@/lib/types";

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

function allTimezones(): string[] {
  try {
    return Intl.supportedValuesOf("timeZone");
  } catch {
    return [];
  }
}

function TimezoneForm({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [value, setValue] = useState(me.timezone);
  const [zones] = useState(allTimezones);
  const deviceZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const save = useMutation({
    mutationFn: (timezone: string) => api<Me>("/me", { method: "PATCH", body: { timezone } }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["me"], updated);
      setValue(updated.timezone);
      toast(`Timezone set to ${updated.timezone}.`);
    },
  });

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        save.mutate(value.trim());
      }}
    >
      <div className="flex flex-wrap items-center gap-3">
        <label htmlFor="timezone" className="sr-only">
          Timezone
        </label>
        <input
          id="timezone"
          list="timezones"
          value={value}
          onChange={(event) => setValue(event.target.value)}
          placeholder="Search, e.g. America/Chicago"
          autoComplete="off"
          spellCheck={false}
          className={`w-72 max-w-full ${INPUT}`}
        />
        <datalist id="timezones">
          {zones.map((zone) => (
            <option key={zone} value={zone} />
          ))}
        </datalist>
        <Button type="submit" variant="primary" disabled={save.isPending || value.trim() === "" || value.trim() === me.timezone}>
          Save
        </Button>
        {deviceZone !== me.timezone && (
          <Button variant="ghost" disabled={save.isPending} onClick={() => save.mutate(deviceZone)}>
            Use this device&apos;s ({deviceZone})
          </Button>
        )}
      </div>
      {save.isError && (
        <p className="text-sm text-danger" role="alert">
          {errorMessage(save.error)}
        </p>
      )}
      <p className="text-xs text-muted">
        Decides which day a game counts for (streaks, charts, time of day). Changes apply to future games only; past games
        keep the date they were played on.
      </p>
    </form>
  );
}

export function SettingsView() {
  const prefs = usePrefs();
  const { me } = useMe();
  return (
    <PageShell title="Settings">
      <div className="space-y-4">
        {CUSTOM_MODE && (
          <Card title="Custom mode">
            {/* Remounts when the stored settings load or change in another tab. */}
            <CustomModeForm key={JSON.stringify(prefs.custom)} initial={prefs.custom} />
          </Card>
        )}

        <Show when="signed-in">
          <Card title="Timezone">{me ? <TimezoneForm key={me.timezone} me={me} /> : <div className="h-9" />}</Card>
          <Card title="Account">
            <p className="mb-4 text-xs text-muted">
              Username, profile picture, email and connected accounts. Changes can take a few minutes to show up here.
            </p>
            <div className="overflow-x-auto">
              <UserProfile routing="hash" />
            </div>
          </Card>
        </Show>
        <Show when="signed-out">
          <Card title="Account">
            <p className="text-sm text-muted">Sign in to save scores, track progress, and set your timezone.</p>
            <Link href="/sign-in" className={buttonClass("primary", "mt-4")}>
              Sign in
            </Link>
          </Card>
        </Show>
      </div>
    </PageShell>
  );
}
