"use client";

import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { ApiError, api } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import { claimPendingGame, onLateEvent, retryQueuedFinishes } from "@/lib/pending";
import type { Me } from "@/lib/types";
import { ToastProvider, useToast } from "./Toasts";

const FALLBACK_TIMEZONE = "America/New_York";

/** On first sign-in, tell the server which timezone this browser is in. */
function TimezoneSync() {
  const { me } = useMe();
  const needsTimezone = me !== undefined && !me.timezone_set;

  useEffect(() => {
    if (!needsTimezone) return;
    const browserZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
    const send = (timezone: string) => api<Me>("/me", { method: "PATCH", body: { timezone } });
    send(browserZone).catch((error) => {
      // A browser reporting a zone the server does not know must not leave the user unset.
      if (error instanceof ApiError && error.status === 422) return send(FALLBACK_TIMEZONE);
    }).catch(() => {});
  }, [needsTimezone]);

  return null;
}

/** Finishes what an earlier visit could not: queued saves and a guest game waiting to be claimed. */
function PendingSync() {
  const { me } = useMe();
  const signedIn = me !== undefined;
  const toast = useToast();
  const queryClient = useQueryClient();

  useEffect(
    () =>
      onLateEvent(({ outcome, source }) => {
        if (outcome.state === "saved") {
          const score = outcome.result.score;
          toast(source === "claim" ? `Saved your score of ${score} to your account.` : `Saved your game (score ${score}).`);
          void queryClient.invalidateQueries();
        } else if (outcome.state === "rejected") {
          toast(`A game couldn't be saved: ${outcome.message}`, "error");
        }
      }),
    [toast, queryClient],
  );

  useEffect(() => {
    void retryQueuedFinishes();
  }, []);

  useEffect(() => {
    if (signedIn) void claimPendingGame();
  }, [signedIn]);

  return null;
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            refetchOnWindowFocus: false,
            retry: (count, error) => !(error instanceof ApiError) && count < 2,
          },
        },
      }),
  );
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <TimezoneSync />
        <PendingSync />
        {children}
      </ToastProvider>
    </QueryClientProvider>
  );
}
