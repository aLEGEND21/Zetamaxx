"use client";

import { useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useEffect, useEffectEvent, useRef, useState } from "react";
import { flushSync } from "react-dom";
import { GameEngine, type SolvedProblem } from "@/lib/engine";
import { onLateEvent, submitFinish, type SaveOutcome } from "@/lib/pending";
import { CUSTOM_MODE } from "@/lib/features";
import { activeSettings, readPrefs, savePrefs, usePrefs } from "@/lib/prefs";
import { prefetchTicket, requestTicket, takeReadyTicket, type Ticket } from "@/lib/session";
import type { GameSettings } from "@/lib/settings";
import { digitsOnly, displaySeconds } from "@/lib/timer";
import { Button } from "./Button";
import { Results } from "./Results";

type SaveState = SaveOutcome | { state: "saving" } | { state: "local" } | { state: "empty" };

// Everything the screen shows. The live game (engine, clock) lives in refs and
// this snapshot only changes when something visible changes: a correct answer,
// a new second on the timer, or a phase change. Keystrokes do not re-render.
//
// There is no "ready" screen: a game starts as soon as the page is open.
// "starting" is the short wait for the server's seed before the clock runs.
type View = {
  phase: "starting" | "playing" | "finished";
  display: string;
  index: number;
  score: number;
  seconds: number;
  problems: SolvedProblem[];
  settings: GameSettings;
  startId: string | null;
  save: SaveState;
};

/** Sized and placed so the crown stands on the text's baseline and reaches the top of its capitals. */
function CrownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0.7 16 16" fill="currentColor" aria-hidden="true">
      <path d="M1.9 4.6a.6.6 0 0 1 .98-.46L5.4 6.2l2.1-3.3a.6.6 0 0 1 1 0l2.1 3.3 2.52-2.06a.6.6 0 0 1 .98.56l-1.1 6.3a.6.6 0 0 1-.6.5H3.6a.6.6 0 0 1-.6-.5L1.9 4.7Z" />
      <rect x="3" y="12.6" width="10" height="1.4" rx=".7" />
    </svg>
  );
}

/** The Enter key's symbol, as a hint that Enter plays again. */
function EnterIcon() {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      className="opacity-70"
    >
      <path d="M13 3.5v4a2 2 0 0 1-2 2H3.5" />
      <path d="M6 7 3.5 9.5 6 12" />
    </svg>
  );
}

function startingView(settings: GameSettings): View {
  return {
    phase: "starting",
    display: "",
    index: 0,
    score: 0,
    seconds: settings.duration,
    problems: [],
    settings,
    startId: null,
    save: { state: "saving" },
  };
}

function isOtherControl(target: EventTarget | null): boolean {
  return target instanceof HTMLElement && target.closest("button, a, input, select, textarea") !== null;
}

function SaveStatus({ save }: { save: SaveState }) {
  switch (save.state) {
    case "saving":
      return <span>Saving…</span>;
    case "saved":
      return save.result.is_pb ? (
        <span
          className="inline-flex items-center gap-1.5 rounded-full bg-accent px-3.5 py-1.5 text-xs font-medium leading-none text-white"
          data-testid="pb-badge"
        >
          <CrownIcon />
          New PR
        </span>
      ) : (
        <span data-testid="saved">
          Saved{save.result.previous_best != null && <> · best <span className="nums">{save.result.previous_best}</span></>}
        </span>
      );
    case "guest":
      return (
        <span data-testid="guest-prompt">
          <Link href="/sign-up" className="text-accent underline-offset-2 hover:underline">
            Sign up to save this score
          </Link>{" "}
          <span className="text-muted">(or </span>
          <Link href="/sign-in" className="text-accent underline-offset-2 hover:underline">
            sign in
          </Link>
          <span className="text-muted">) within 15 minutes</span>
        </span>
      );
    case "queued":
      return <span>Can&apos;t reach the server. Retrying for the next 30 seconds…</span>;
    case "local":
      return <span>Played offline, so this game wasn&apos;t saved.</span>;
    case "empty":
      return <span data-testid="not-attempted">Game not attempted</span>;
    case "rejected":
      return <span className="text-danger">Not saved: {save.message}</span>;
  }
}

export function Game() {
  const prefs = usePrefs();
  const settings = activeSettings(prefs);
  const queryClient = useQueryClient();
  const [view, setView] = useState<View>(() => startingView(settings));
  const engineRef = useRef<GameEngine | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const restartRef = useRef<HTMLButtonElement>(null);
  const frameRef = useRef(0);
  const endTimerRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  // Each start gets a number, so a ticket that arrives after a restart (or after leaving the page) is ignored.
  const attemptRef = useRef(0);

  function stopClock() {
    cancelAnimationFrame(frameRef.current);
    clearTimeout(endTimerRef.current);
  }

  async function save(startId: string, problems: SolvedProblem[]) {
    const outcome = await submitFinish({ start_id: startId, problems });
    setView((v) => (v.startId === startId && v.phase === "finished" ? { ...v, save: outcome } : v));
    if (outcome.state === "saved") void queryClient.invalidateQueries();
  }

  function finish(engine: GameEngine, ticket: Ticket) {
    if (engineRef.current !== engine) return;
    stopClock();
    engineRef.current = null;
    // A game nobody answered (the page was left open) is treated as abandoned: nothing is sent or saved.
    const unanswered = engine.solved.length === 0;
    setView((v) => ({
      ...v,
      phase: "finished",
      seconds: 0,
      score: engine.score,
      problems: engine.solved,
      save: unanswered ? { state: "empty" } : ticket.startId ? { state: "saving" } : { state: "local" },
    }));
    if (ticket.startId && !unanswered) void save(ticket.startId, engine.solved);
    prefetchTicket(settings);
  }

  function play(ticket: Ticket): View {
    const engine = new GameEngine(ticket.seed, ticket.settings, performance.now());
    engineRef.current = engine;
    let shown = ticket.settings.duration;

    // The display follows the clock; the timeout guarantees the game ends on
    // time even if the tab is in the background and frames are paused.
    const tick = () => {
      const remaining = engine.remaining(performance.now());
      if (remaining <= 0) return finish(engine, ticket);
      const seconds = displaySeconds(remaining);
      if (seconds !== shown) {
        shown = seconds;
        setView((v) => ({ ...v, seconds }));
      }
      frameRef.current = requestAnimationFrame(tick);
    };
    frameRef.current = requestAnimationFrame(tick);
    endTimerRef.current = setTimeout(() => finish(engine, ticket), engine.durationMs);

    return {
      ...startingView(ticket.settings),
      phase: "playing",
      display: engine.current.display,
      startId: ticket.startId,
    };
  }

  /** Starts a new game now: on page load, from "Play again", or as a restart in the middle of one. */
  async function start() {
    const attempt = ++attemptRef.current;
    stopClock();
    engineRef.current = null; // a game in progress is simply dropped, never saved

    // Read the stored choice directly: on first load the rendered value can still be the default.
    const next = activeSettings(readPrefs());
    const ready = takeReadyTicket(next);
    const nextView = ready ? play(ready) : startingView(next);
    if (inputRef.current) {
      inputRef.current.value = "";
      setView(nextView);
    } else {
      // Coming from the results: render the input inside the key press or tap,
      // so it can take focus at once (and mobile keyboards open).
      flushSync(() => setView(nextView));
    }
    inputRef.current?.focus();
    if (ready) return;

    // No fresh ticket on hand: ask for one now. The clock starts when it arrives.
    const ticket = await requestTicket(next);
    if (attemptRef.current !== attempt) return; // restarted, or left the page, while waiting
    setView(play(ticket));
  }

  function onInput(event: React.FormEvent<HTMLInputElement>) {
    const el = event.currentTarget;
    const digits = digitsOnly(el.value);
    if (digits !== el.value) el.value = digits;
    const engine = engineRef.current;
    if (!engine) {
      el.value = "";
      return;
    }
    if (engine.submit(digits, performance.now())) {
      el.value = "";
      setView((v) => ({ ...v, display: engine.current.display, index: engine.score, score: engine.score }));
    }
  }

  const onKeyDown = useEffectEvent((event: KeyboardEvent) => {
    if (event.metaKey || event.ctrlKey || event.altKey) return;
    const restart = event.key === "Escape";
    const playAgain = event.key === "Enter" && view.phase === "finished" && !isOtherControl(event.target);
    if (restart || playAgain) {
      event.preventDefault();
      void start();
    }
  });

  const startOnLoad = useEffectEvent(() => void start());

  const leavePage = useEffectEvent(() => {
    attemptRef.current++; // a ticket still on its way must not start a game on a page that is gone
    stopClock();
    engineRef.current = null;
  });

  useEffect(() => {
    const handler = (event: KeyboardEvent) => onKeyDown(event);
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  // A queued save that goes through (or is refused) later updates the results on screen.
  useEffect(
    () =>
      onLateEvent(({ startId, outcome }) =>
        setView((v) => (v.startId === startId && v.phase === "finished" ? { ...v, save: outcome } : v)),
      ),
    [],
  );

  // Opening the page starts a game. A tab opened in the background waits until
  // it is looked at, so the clock never runs unseen.
  useEffect(() => {
    if (document.visibilityState === "visible") {
      startOnLoad();
      return;
    }
    const onVisible = () => {
      if (document.visibilityState !== "visible") return;
      document.removeEventListener("visibilitychange", onVisible);
      startOnLoad();
    };
    document.addEventListener("visibilitychange", onVisible);
    return () => document.removeEventListener("visibilitychange", onVisible);
  }, []);

  useEffect(() => {
    // Hook for the end-to-end test, which cannot do arithmetic at human speed.
    if (process.env.NEXT_PUBLIC_E2E === "1") {
      (window as unknown as Record<string, unknown>).__zetamaxx = {
        answer: () => (engineRef.current ? String(engineRef.current.current.answer) : null),
      };
    }
    return () => leavePage();
  }, []);

  const active = view.phase !== "finished";

  return (
    <div className="relative mx-auto flex w-full max-w-content flex-1 flex-col px-4">
      <div className="nums flex justify-between pt-3.5 text-sm text-muted">
        <span aria-live="polite" data-testid="score">
          Score {view.score}
        </span>
        <span aria-label="Seconds left" data-testid="timer">
          {view.seconds}
        </span>
      </div>

      <div className="flex flex-1 flex-col items-center justify-center pb-24 pt-8">
        {active && (
          <div className="flex w-full flex-col items-center gap-4">
            <p
              key={view.index}
              className={`nums min-h-[1.25em] text-[40px] leading-tight sm:text-[64px] ${view.index > 0 ? "correct-flash" : ""}`}
              data-testid="problem"
            >
              {view.phase === "starting" ? (
                // Waiting for the server's seed: a placeholder the size of a problem, so nothing jumps.
                <span
                  aria-hidden="true"
                  data-testid="problem-skeleton"
                  className="inline-block h-[0.8em] w-[4.2em] animate-pulse rounded-lg bg-border/60 align-middle"
                />
              ) : (
                view.display
              )}
            </p>
            <input
              ref={inputRef}
              onInput={onInput}
              onBlur={(event) => {
                // Keep typing focus unless the player tabbed to Restart.
                if (event.relatedTarget !== restartRef.current && engineRef.current) {
                  requestAnimationFrame(() => engineRef.current && inputRef.current?.focus());
                }
              }}
              autoFocus
              inputMode="numeric"
              pattern="[0-9]*"
              autoComplete="off"
              autoCorrect="off"
              spellCheck={false}
              aria-label="Answer"
              data-testid="answer"
              className="nums w-56 border-b border-border bg-transparent pb-1 text-center text-[40px] leading-tight outline-none focus:border-text focus-visible:outline-none sm:w-72 sm:text-[64px]"
            />
            <button
              ref={restartRef}
              type="button"
              onClick={() => void start()}
              className="mt-8 rounded px-2 py-1 text-xs text-muted hover:text-text"
            >
              Restart <span className="nums opacity-70">(Esc)</span>
            </button>
          </div>
        )}

        {view.phase === "finished" && (
          <Results
            score={view.score}
            attempted={view.save.state !== "empty"}
            problems={view.problems}
            settings={view.settings}
            status={<SaveStatus save={view.save} />}
            actions={
              <>
                <Button variant="primary" autoFocus onClick={() => void start()} aria-keyshortcuts="Enter" data-testid="play-again">
                  Play again <EnterIcon />
                </Button>
                {CUSTOM_MODE && (
                  // With no start screen, the mode for the next game is chosen here.
                  <div className="flex rounded-lg border border-border bg-surface p-0.5 text-sm" role="group" aria-label="Mode for the next game">
                    {(["standard", "custom"] as const).map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        aria-pressed={prefs.mode === mode}
                        onClick={() => savePrefs({ ...prefs, mode })}
                        className={`rounded-md px-3 py-1 capitalize transition-colors duration-150 ${
                          prefs.mode === mode ? "bg-text text-surface" : "text-muted hover:text-text"
                        }`}
                      >
                        {mode}
                      </button>
                    ))}
                  </div>
                )}
              </>
            }
          />
        )}
      </div>
    </div>
  );
}
