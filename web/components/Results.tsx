"use client";

import dynamic from "next/dynamic";
import type { ReactNode } from "react";
import { opAverages, slowest, type SolvedProblem } from "@/lib/engine";
import { formatMs } from "@/lib/format";
import { answerOf, displayProblem } from "@/lib/generator";
import { describeSettings, type GameSettings } from "@/lib/settings";

// Charts are loaded only when results are shown, keeping the game screen light.
const OpBars = dynamic(() => import("./OpBars").then((m) => m.OpBars), {
  ssr: false,
  loading: () => <div className="h-44" />,
});

type Props = {
  score: number;
  problems: SolvedProblem[];
  settings: GameSettings;
  /** Shown next to the score: PB badge, save state, sign-up prompt. */
  status?: ReactNode;
  /** Buttons under the results ("Play again"). */
  actions?: ReactNode;
};

export function Results({ score, problems, settings, status, actions }: Props) {
  const slow = slowest(problems, 5);
  return (
    <section className="fade-in mx-auto w-full max-w-xl" aria-label="Results">
      <div className="flex flex-col items-center gap-2 text-center">
        <p className="text-sm text-muted">{describeSettings(settings)}</p>
        <p className="nums text-7xl font-medium leading-none" data-testid="final-score">
          {score}
        </p>
        <div className="min-h-6 text-sm text-muted" aria-live="polite">
          {status}
        </div>
      </div>

      {actions && <div className="mt-6 flex justify-center gap-3">{actions}</div>}

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        <div className="rounded-card border border-border bg-surface p-4">
          <h2 className="mb-2 text-sm font-medium">Speed by operation</h2>
          <OpBars primary={opAverages(problems)} primaryLabel="This game" />
        </div>
        <div className="rounded-card border border-border bg-surface p-4">
          <h2 className="mb-2 text-sm font-medium">Slowest problems</h2>
          {slow.length === 0 ? (
            <p className="py-6 text-center text-sm text-muted">No solved problems yet.</p>
          ) : (
            <ol className="nums space-y-1.5 text-sm">
              {slow.map((p, i) => (
                <li key={i} className="flex justify-between gap-4">
                  <span>
                    {displayProblem(p.op, p.a, p.b)} = {answerOf(p.op, p.a, p.b)}
                  </span>
                  <span className="text-muted">{formatMs(p.ms)}</span>
                </li>
              ))}
            </ol>
          )}
        </div>
      </div>
    </section>
  );
}
