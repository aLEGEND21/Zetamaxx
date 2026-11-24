"use client";

// Which settings the next game uses. Kept in localStorage so guests have them
// too; the server validates whatever is sent to /api/games/start.

import { useSyncExternalStore } from "react";
import { CUSTOM_MODE } from "./features";
import { STANDARD, cloneSettings, validateSettings, type GameSettings } from "./settings";

export type Prefs = { mode: "standard" | "custom"; custom: GameSettings };

const KEY = "zetamaxx.prefs";
const CHANGED = "zetamaxx:prefs";

export const DEFAULT_CUSTOM: GameSettings = { ...cloneSettings(STANDARD), duration: 60 };
const DEFAULT_PREFS: Prefs = { mode: "standard", custom: DEFAULT_CUSTOM };

let cachedRaw: string | null | undefined;
let cachedPrefs: Prefs = DEFAULT_PREFS;

function parse(raw: string | null): Prefs {
  if (!raw) return DEFAULT_PREFS;
  try {
    const value = JSON.parse(raw) as Prefs;
    if (validateSettings(value.custom) !== null) return DEFAULT_PREFS;
    return { mode: value.mode === "custom" ? "custom" : "standard", custom: value.custom };
  } catch {
    return DEFAULT_PREFS;
  }
}

/** The stored choice, read straight from this browser (not for use during server rendering). */
export function readPrefs(): Prefs {
  let raw: string | null = null;
  try {
    raw = localStorage.getItem(KEY);
  } catch {
    // Storage blocked: use defaults.
  }
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedPrefs = parse(raw);
  }
  return cachedPrefs;
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("storage", onChange);
  window.addEventListener(CHANGED, onChange);
  return () => {
    window.removeEventListener("storage", onChange);
    window.removeEventListener(CHANGED, onChange);
  };
}

export function usePrefs(): Prefs {
  return useSyncExternalStore(subscribe, readPrefs, () => DEFAULT_PREFS);
}

export function savePrefs(prefs: Prefs): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(prefs));
  } catch {
    // Storage blocked: the choice lasts for this page only.
  }
  window.dispatchEvent(new Event(CHANGED));
}

export function activeSettings(prefs: Prefs): GameSettings {
  // While custom mode is switched off, a choice saved earlier in this browser is ignored.
  return CUSTOM_MODE && prefs.mode === "custom" ? prefs.custom : STANDARD;
}
