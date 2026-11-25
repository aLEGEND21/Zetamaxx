"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams } from "next/navigation";
import { Fragment, useState } from "react";
import { Avatar } from "@/components/Avatar";
import { Heatmap } from "@/components/charts/Heatmap";
import { PROGRESS_RANGES, ProgressLegend } from "@/components/charts/ProgressChart";
import { FriendButton } from "@/components/FriendButton";
import { GameList } from "@/components/GameList";
import { ProfileSkeleton, Skeleton } from "@/components/Skeleton";
import { TimezoneSelect } from "@/components/TimezoneSelect";
import { Card, EmptyState, ErrorNote, PageShell, Segmented } from "@/components/ui";
import { displayName } from "@/components/UserLink";
import { ApiError, api, errorMessage } from "@/lib/api";
import { formatLocalDateTime, formatScore, signed } from "@/lib/format";
import { CUSTOM_MODE, SOCIAL } from "@/lib/features";
import { useMe } from "@/lib/hooks";
import { describeSettings } from "@/lib/settings";
import type { Activity, ConfigSummary, GameSort, ProgressRange, Series, Stats } from "@/lib/types";

// Chart code loads after the page shell, so the profile header appears immediately.
const ProgressChart = dynamic(() => import("@/components/charts/ProgressChart").then((m) => m.ProgressChart), {
  ssr: false,
  loading: () => <div className="h-64" />,
});

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-card border border-border bg-surface p-4 sm:p-5">
      <p className="text-xs text-muted">{label}</p>
      <p className="nums mt-1 text-2xl font-medium">{value}</p>
      {note && <p className="mt-0.5 text-xs text-muted">{note}</p>}
    </div>
  );
}

function withHash(path: string, hash: string | null): string {
  return hash ? `${path}${path.includes("?") ? "&" : "?"}settings_hash=${hash}` : path;
}

function Charts({ username, hash }: { username: string; hash: string | null }) {
  const [range, setRange] = useState<ProgressRange>("7d");
  const series = useQuery({
    queryKey: ["series", username, hash, range],
    queryFn: () => api<Series>(withHash(`/users/${username}/series?range=${range}`, hash)),
    placeholderData: keepPreviousData,
  });
  const activity = useQuery({
    queryKey: ["activity", username, hash],
    queryFn: () => api<Activity>(withHash(`/users/${username}/activity`, hash)),
  });

  return (
    <>
      <Card
        title="Progress"
        aside={
          <div className="flex flex-wrap items-center gap-3">
            <ProgressLegend perGame={range === "7d"} />
            <Segmented label="Range" value={range} options={PROGRESS_RANGES} onChange={setRange} />
          </div>
        }
      >
        {series.isPending ? (
          <Skeleton className="h-64" />
        ) : series.isError ? (
          <ErrorNote>{errorMessage(series.error)}</ErrorNote>
        ) : series.data.points.length === 0 ? (
          <EmptyState>No games in this period</EmptyState>
        ) : (
          <div className={series.isPlaceholderData ? "opacity-60 transition-opacity" : "transition-opacity"}>
            <ProgressChart series={series.data} />
          </div>
        )}
      </Card>

      <Card title="Activity">
        {activity.isPending ? (
          <Skeleton className="h-39" />
        ) : activity.isError ? (
          <ErrorNote>{errorMessage(activity.error)}</ErrorNote>
        ) : (
          <Heatmap activity={activity.data} />
        )}
      </Card>
    </>
  );
}

const SORT_OPTIONS: readonly { value: GameSort; label: string }[] = [
  { value: "newest", label: "Newest first" },
  { value: "oldest", label: "Oldest first" },
  { value: "score_desc", label: "Highest score" },
  { value: "score_asc", label: "Lowest score" },
];

function RecentGames({ username, hash }: { username: string; hash: string | null }) {
  const [sort, setSort] = useState<GameSort>("newest");
  const filter = hash ? `settings_hash=${hash}` : "ranked=true";
  return (
    <Card
      title="Recent games"
      aside={
        <select
          aria-label="Sort games"
          value={sort}
          onChange={(event) => setSort(event.target.value as GameSort)}
          className="h-8 rounded-lg border border-border bg-surface px-2 text-xs"
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      }
    >
      <GameList path={`/games?user=${username}&${filter}&sort=${sort}`} empty="No games yet" />
    </Card>
  );
}

export function ProfileView() {
  const { username } = useParams<{ username: string }>();
  const { me, isSignedIn } = useMe();
  const [mode, setMode] = useState<"ranked" | "custom">("ranked");
  const [pickedHash, setPickedHash] = useState<string | null>(null);

  const overview = useQuery({ queryKey: ["stats", username, null], queryFn: () => api<Stats>(`/users/${username}/stats`) });
  const visible = overview.data?.visible === true;
  const configs = useQuery({
    queryKey: ["configs", username],
    queryFn: () => api<{ configs: ConfigSummary[] }>(`/users/${username}/configs`),
    enabled: visible && CUSTOM_MODE,
  });
  const configList = configs.data?.configs ?? [];
  // In custom mode every number on the page is for one configuration.
  const hash = mode === "custom" ? (configList.find((c) => c.settings_hash === pickedHash) ?? configList[0])?.settings_hash ?? null : null;
  const custom = useQuery({
    queryKey: ["stats", username, hash],
    queryFn: () => api<Stats>(withHash(`/users/${username}/stats`, hash)),
    enabled: visible && hash !== null,
  });

  if (overview.isPending) return <ProfileSkeleton />;
  if (overview.isError) {
    const missing = overview.error instanceof ApiError && overview.error.status === 404;
    return (
      <PageShell>
        <div className="mx-auto max-w-md py-16 text-center">
          <h1 className="text-xl font-semibold">{missing ? "No such player" : "Couldn't load this profile"}</h1>
          <p className="mt-2 text-sm text-muted">{missing ? `Nobody here is called “${username}”` : errorMessage(overview.error)}</p>
        </div>
      </PageShell>
    );
  }

  const base = overview.data;
  const user = base.user;
  const header = (
    <div className="mb-6 flex flex-wrap items-center justify-between gap-4">
      <div className="flex min-w-0 items-center gap-4">
        <Avatar user={user} size={64} />
        <div className="min-w-0">
          <h1 className="truncate text-2xl font-semibold tracking-tight">{displayName(user)}</h1>
          <p className="truncate text-sm text-muted">
            @{user.username}
            {base.last_played && ` · last played ${formatLocalDateTime(base.last_played)}`}
          </p>
        </div>
      </div>
      {SOCIAL && !base.is_self && isSignedIn && me && <FriendButton username={user.username} />}
      {base.is_self && me && <TimezoneSelect me={me} />}
    </div>
  );

  if (!base.visible) {
    return (
      <PageShell>
        {header}
        <div className="grid gap-4 sm:grid-cols-4">
          <Tile label="Personal record" value={formatScore(base.pb)} />
        </div>
        <Card className="mt-4">
          <EmptyState>
            {!SOCIAL
              ? "Only the personal record is public. The rest of a player's stats are private."
              : isSignedIn
                ? "Full stats are shared with friends and people in the same group."
                : "Sign in to add this player as a friend. Full stats are shared with friends and group members."}
          </EmptyState>
        </Card>
      </PageShell>
    );
  }

  const stats = mode === "custom" ? custom.data : base;
  const showModes = configList.length > 0;
  return (
    <PageShell>
      {header}
      {showModes && (
        <div className="mb-4 flex flex-wrap items-center gap-3">
          <Segmented
            label="Game type"
            value={mode}
            options={[
              { value: "ranked", label: "Ranked" },
              { value: "custom", label: "Custom" },
            ]}
            onChange={setMode}
          />
          {mode === "custom" && (
            <select
              aria-label="Custom configuration"
              value={hash ?? ""}
              onChange={(event) => setPickedHash(event.target.value)}
              className="h-8 max-w-full rounded-lg border border-border bg-surface px-2 text-xs"
            >
              {configList.map((config) => (
                <option key={config.settings_hash} value={config.settings_hash}>
                  {describeSettings(config.settings)} ({config.games} {config.games === 1 ? "game" : "games"})
                </option>
              ))}
            </select>
          )}
        </div>
      )}

      {!stats ? (
        <Skeleton className="h-24" />
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <Tile label="Personal record" value={formatScore(stats.pb)} note={`${stats.games ?? 0} ${stats.games === 1 ? "game" : "games"}`} />
            <Tile label="Recent average" value={formatScore(stats.recent_avg, 1)} note="last 10 games" />
            <Tile
              label="Streak"
              value={`${stats.streak ?? 0}`}
              note={stats.streak === 1 ? "day in a row" : "days in a row"}
            />
            <Tile
              label="Improvement"
              value={stats.improvement == null ? "–" : signed(stats.improvement)}
              note="recent average vs 30 days ago"
            />
          </div>

          {(stats.games ?? 0) === 0 ? (
            <Card>
              <EmptyState>
                {base.is_self ? (
                  <>
                    No games yet.{" "}
                    <Link href="/" className="text-accent-ink underline-offset-2 hover:underline">
                      Play your first one
                    </Link>
                    .
                  </>
                ) : (
                  "No games yet"
                )}
              </EmptyState>
            </Card>
          ) : (
            // Keyed, so switching configuration resets the chart range and the sort order.
            <Fragment key={hash ?? "ranked"}>
              <Charts username={user.username} hash={hash} />
              <RecentGames username={user.username} hash={hash} />
            </Fragment>
          )}
        </div>
      )}
    </PageShell>
  );
}
