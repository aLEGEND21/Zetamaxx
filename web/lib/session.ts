// Where a game gets its seed: a "ticket" issued by POST /api/games/start.
//
// The server only accepts a game it receives within 30 seconds of when it
// should end, counted from when the ticket was issued. So a ticket fetched
// ahead of time (to make "Play again" instant) is only used while it is fresh;
// otherwise a new one is requested the moment play begins.

import { api, NetworkError } from "./api";
import { randomSeed } from "./prng";
import { sameSettings, type GameSettings } from "./settings";

export type Ticket = {
  /** Server start id, or null for an offline game that cannot be saved. */
  startId: string | null;
  seed: number;
  settings: GameSettings;
};

type StartResponse = { start_id: string; seed: number; settings: GameSettings; is_ranked: boolean };

/** A prefetched ticket may be used for this long (leaves 10s of the server's 30s for the network). */
export const FRESH_MS = 20_000;

type Prefetched = { settings: GameSettings; promise: Promise<Ticket | null>; ticket: Ticket | null; issuedAt: number };
let prefetched: Prefetched | null = null;

async function fetchTicket(settings: GameSettings): Promise<Ticket> {
  const started = await api<StartResponse>("/games/start", { method: "POST", body: { settings } });
  return { startId: started.start_id, seed: started.seed, settings: started.settings };
}

function isFresh(entry: Prefetched): boolean {
  return entry.ticket !== null && performance.now() - entry.issuedAt < FRESH_MS;
}

/** Get the next ticket ready in the background so starting is instant. */
export function prefetchTicket(settings: GameSettings): void {
  const current = prefetched;
  if (current && sameSettings(current.settings, settings)) {
    const inFlight = current.ticket === null;
    if (inFlight || isFresh(current)) return;
  }
  const entry: Prefetched = { settings, ticket: null, issuedAt: 0, promise: Promise.resolve(null) };
  entry.promise = fetchTicket(settings).then(
    (ticket) => {
      entry.ticket = ticket;
      entry.issuedAt = performance.now();
      return ticket;
    },
    () => {
      if (prefetched === entry) prefetched = null;
      return null;
    },
  );
  prefetched = entry;
}

/** A fresh prefetched ticket, if there is one. Synchronous: no waiting. */
export function takeReadyTicket(settings: GameSettings): Ticket | null {
  const entry = prefetched;
  if (!entry || !sameSettings(entry.settings, settings) || !isFresh(entry)) return null;
  prefetched = null;
  return entry.ticket;
}

/** A ticket for a game that starts now. Falls back to an offline (unsaved) game when the API is unreachable. */
export async function requestTicket(settings: GameSettings): Promise<Ticket> {
  const entry = prefetched;
  if (entry && sameSettings(entry.settings, settings) && entry.ticket === null) {
    // A prefetch is already on its way: use it rather than asking twice.
    prefetched = null;
    const ticket = await entry.promise;
    if (ticket) return ticket;
  }
  prefetched = null;
  try {
    return await fetchTicket(settings);
  } catch (error) {
    if (error instanceof NetworkError) return { startId: null, seed: randomSeed(), settings };
    throw error;
  }
}
