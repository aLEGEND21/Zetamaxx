// Saving finished games, including the two cases that outlive the page:
//
//  - Offline: if `finish` cannot reach the server, the payload is kept in
//    localStorage and retried (a few times right away, then on next load). The
//    server only accepts a game within 30 seconds of its end, so a late retry
//    is rejected and dropped.
//  - Guests: the server validates the game immediately and holds it. The start
//    id is kept in localStorage and claimed once the guest signs in (15 minutes).

import { api, ApiError } from "./api";
import type { SolvedProblem } from "./engine";
import type { GameDetail } from "./types";

export type FinishPayload = { start_id: string; problems: SolvedProblem[] };
export type FinishResult = {
  saved: boolean;
  score: number;
  game: GameDetail | null;
  is_pb: boolean;
  previous_best: number | null;
};

export type SaveOutcome =
  | { state: "saved"; result: FinishResult }
  | { state: "guest"; score: number }
  | { state: "queued" }
  | { state: "rejected"; message: string };

/** Something that happened to a game after the fact (a retry or a claim). */
export type LateEvent = { startId: string; outcome: SaveOutcome; source: "retry" | "claim" };

const FINISH_KEY = "zetamaxx.pendingFinish";
const CLAIM_KEY = "zetamaxx.pendingClaim";
const RETRY_DELAYS_MS = [1_000, 3_000, 7_000, 12_000];

type PendingClaim = { start_id: string; score: number };

function read<T>(key: string, fallback: T): T {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : fallback;
  } catch {
    return fallback;
  }
}

function write(key: string, value: unknown): void {
  try {
    if (value === null || (Array.isArray(value) && value.length === 0)) localStorage.removeItem(key);
    else localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Storage full or blocked: the game simply cannot be retried later.
  }
}

const listeners = new Set<(event: LateEvent) => void>();

export function onLateEvent(listener: (event: LateEvent) => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

function emit(event: LateEvent) {
  listeners.forEach((listener) => listener(event));
}

function unqueue(startId: string) {
  write(FINISH_KEY, read<FinishPayload[]>(FINISH_KEY, []).filter((p) => p.start_id !== startId));
}

async function send(payload: FinishPayload): Promise<SaveOutcome> {
  try {
    const result = await api<FinishResult>("/games/finish", { method: "POST", body: payload });
    unqueue(payload.start_id);
    if (result.saved) return { state: "saved", result };
    write(CLAIM_KEY, { start_id: payload.start_id, score: result.score } satisfies PendingClaim);
    return { state: "guest", score: result.score };
  } catch (error) {
    if (error instanceof ApiError) {
      unqueue(payload.start_id);
      return { state: "rejected", message: error.message };
    }
    return { state: "queued" };
  }
}

/** Submit a game that just ended. */
export async function submitFinish(payload: FinishPayload): Promise<SaveOutcome> {
  const outcome = await send(payload);
  if (outcome.state === "queued") {
    write(FINISH_KEY, [...read<FinishPayload[]>(FINISH_KEY, []).filter((p) => p.start_id !== payload.start_id), payload]);
    scheduleRetries(payload, 0);
  }
  return outcome;
}

function scheduleRetries(payload: FinishPayload, attempt: number) {
  if (attempt >= RETRY_DELAYS_MS.length) return;
  setTimeout(async () => {
    const outcome = await send(payload);
    if (outcome.state === "queued") scheduleRetries(payload, attempt + 1);
    else emit({ startId: payload.start_id, outcome, source: "retry" });
  }, RETRY_DELAYS_MS[attempt]);
}

/** On page load: retry anything a previous visit could not send. */
export async function retryQueuedFinishes(): Promise<void> {
  for (const payload of read<FinishPayload[]>(FINISH_KEY, [])) {
    const outcome = await send(payload);
    if (outcome.state !== "queued") emit({ startId: payload.start_id, outcome, source: "retry" });
  }
}

export function hasPendingClaim(): boolean {
  return read<PendingClaim | null>(CLAIM_KEY, null) !== null;
}

/** After sign-in: attach the guest game played just before to this account. */
export async function claimPendingGame(): Promise<void> {
  const claim = read<PendingClaim | null>(CLAIM_KEY, null);
  if (!claim) return;
  try {
    const result = await api<FinishResult>("/games/claim", { method: "POST", body: { start_id: claim.start_id } });
    write(CLAIM_KEY, null);
    emit({ startId: claim.start_id, outcome: { state: "saved", result }, source: "claim" });
  } catch (error) {
    if (error instanceof ApiError) {
      write(CLAIM_KEY, null);
      // 401 just means the session was not ready; anything else is final.
      if (error.status === 401) write(CLAIM_KEY, claim);
      else emit({ startId: claim.start_id, outcome: { state: "rejected", message: error.message }, source: "claim" });
    }
  }
}
