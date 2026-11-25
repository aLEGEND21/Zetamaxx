"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { useToast } from "@/components/Toasts";
import { api, errorMessage } from "@/lib/api";
import type { Me } from "@/lib/types";

function allTimezones(): string[] {
  try {
    return Intl.supportedValuesOf("timeZone");
  } catch {
    return [];
  }
}

/** The signed-in player's timezone, shown on their own profile. Picking a zone saves it. */
export function TimezoneSelect({ me }: { me: Me }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [zones] = useState(allTimezones);
  const deviceZone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  const save = useMutation({
    mutationFn: (timezone: string) => api<Me>("/me", { method: "PATCH", body: { timezone } }),
    onSuccess: (updated) => {
      queryClient.setQueryData(["me"], updated);
      toast(`Timezone set to ${updated.timezone}.`);
    },
    onError: (error) => toast(errorMessage(error)),
  });
  // While a save is in flight, show the zone that was picked.
  const value = save.isPending ? save.variables : me.timezone;

  return (
    <label
      className="flex items-center gap-2 text-xs text-muted"
      title="Decides which day a game counts for in streaks and charts. Applies to future games only."
    >
      Timezone
      <select
        value={value}
        disabled={save.isPending}
        onChange={(event) => save.mutate(event.target.value)}
        className="h-8 max-w-56 rounded-lg border border-border bg-surface px-2 text-xs text-text"
      >
        {deviceZone !== me.timezone && <option value={deviceZone}>{deviceZone} (this device)</option>}
        {/* The saved zone can be one the browser does not list, such as UTC. */}
        {!zones.includes(me.timezone) && <option value={me.timezone}>{me.timezone}</option>}
        {zones.map((zone) => (
          <option key={zone} value={zone}>
            {zone}
          </option>
        ))}
      </select>
    </label>
  );
}
