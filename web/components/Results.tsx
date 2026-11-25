"use client";

import type { ReactNode } from "react";
import { slowest, type SolvedProblem } from "@/lib/engine";
import { formatMs } from "@/lib/format";
import { answerOf, displayProblem } from "@/lib/generator";
import { describeSettings, type GameSettings } from "@/lib/settings";

type Props = {
  score: number;
  /** False when the clock ran out with nothing answered: shown as "DNF" rather than a score of 0. */
  attempted?: boolean;
  problems: SolvedProblem[];
  settings: GameSettings;
  /** Shown next to the score: PB badge, save state, sign-up prompt. */
  status?: ReactNode;
  /** Buttons under the results ("Play again"). */
  actions?: ReactNode;
};

export function Results({ score, attempted = true, problems, settings, status, actions }: Props) {
  const slow = slowest(problems, 5);
  return (
    <section className="fade-in mx-auto w-full max-w-xl" aria-label="Results">
      <div className="flex flex-col items-center gap-2 text-center">
        <p className="text-sm text-muted">{describeSettings(settings)}</p>
        <p className="nums text-7xl font-medium leading-none" data-testid="final-score">
          {attempted ? score : <abbr title="Did not finish" className="no-underline">DNF</abbr>}
        </p>
        <div className="flex min-h-7 items-center justify-center text-sm text-muted" aria-live="polite">
          {status}
        </div>
      </div>

      {actions && <div className="mt-6 flex justify-center gap-3">{actions}</div>}

      {slow.length > 0 && (
        <div className="mx-auto mt-8 max-w-sm rounded-card border border-border bg-surface p-4">
          <h2 className="mb-2 text-sm font-medium">Slowest problems</h2>
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
        </div>
      )}
    </section>
  );
}
