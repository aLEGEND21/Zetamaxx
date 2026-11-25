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
  /** Shown under the score: PB badge, save state, sign-up prompt. */
  status?: ReactNode;
  /** Buttons under the results ("Play again"). */
  actions?: ReactNode;
};

/** The line above the score that names the mode, such as "Standard · 120s". */
export function ResultsMode({ settings }: Pick<Props, "settings">) {
  return <p className="text-sm text-muted">{describeSettings(settings)}</p>;
}

export function FinalScore({ score, attempted = true }: Pick<Props, "score" | "attempted">) {
  return (
    <p className="nums text-6xl font-medium leading-none sm:text-7xl" data-testid="final-score">
      {attempted ? score : <abbr title="Did not finish" className="no-underline">DNF</abbr>}
    </p>
  );
}

/** Everything under the score: the status line, the buttons and the slowest problems. */
export function ResultsDetails({ problems, status, actions }: Pick<Props, "problems" | "status" | "actions">) {
  const slow = slowest(problems, 5);
  return (
    <>
      <div className="flex min-h-7 items-center justify-center text-center text-sm text-muted" aria-live="polite">
        {status}
      </div>

      {actions && <div className="mt-6 flex justify-center gap-3">{actions}</div>}

      {slow.length > 0 && (
        <div className="mx-auto mt-8 w-full max-w-sm rounded-card border border-border bg-surface p-4">
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
    </>
  );
}

/** The results as one block, for a saved game's own page. The game screen lays the same parts out itself. */
export function Results({ score, attempted, problems, settings, status, actions }: Props) {
  return (
    <section className="fade-in mx-auto w-full max-w-xl" aria-label="Results">
      <div className="mb-2 flex flex-col items-center gap-2 text-center">
        <ResultsMode settings={settings} />
        <FinalScore score={score} attempted={attempted} />
      </div>
      <ResultsDetails problems={problems} status={status} actions={actions} />
    </section>
  );
}
