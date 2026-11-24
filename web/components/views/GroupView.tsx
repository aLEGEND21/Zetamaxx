"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import dynamic from "next/dynamic";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useState } from "react";
import { Button, buttonClass } from "@/components/Button";
import { ConfirmButton } from "@/components/ConfirmButton";
import { GameList } from "@/components/GameList";
import { PageSkeleton, Skeleton } from "@/components/Skeleton";
import { useToast } from "@/components/Toasts";
import { Card, EmptyState, ErrorNote, PageShell, RANGE_OPTIONS, Segmented } from "@/components/ui";
import { UserLink } from "@/components/UserLink";
import { ApiError, api, errorMessage } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import type { GroupDetail, GroupMember, GroupSeries, Leaderboard, RangeKey, Role } from "@/lib/types";

const OverlayChart = dynamic(() => import("@/components/charts/OverlayChart").then((m) => m.OverlayChart), {
  ssr: false,
  loading: () => <div className="h-64" />,
});

const PERIODS = [
  { value: "week", label: "7 days" },
  { value: "month", label: "30 days" },
  { value: "all", label: "All time" },
] as const;
const METRICS = [
  { value: "best", label: "Best" },
  { value: "avg10", label: "Avg of last 10" },
] as const;
type Period = (typeof PERIODS)[number]["value"];
type Metric = (typeof METRICS)[number]["value"];

function LeaderboardCard({ groupId, sinceJoining }: { groupId: string; sinceJoining: boolean }) {
  const [period, setPeriod] = useState<Period>("week");
  const [metric, setMetric] = useState<Metric>("best");
  const board = useQuery({
    queryKey: ["group", groupId, "leaderboard", period, metric, sinceJoining],
    queryFn: () =>
      api<Leaderboard>(`/groups/${groupId}/leaderboard?period=${period}&metric=${metric}&since_joining=${sinceJoining}`),
    placeholderData: keepPreviousData,
  });

  return (
    <Card
      title="Leaderboard"
      aside={
        <div className="flex flex-wrap gap-2">
          <Segmented label="Period" value={period} options={PERIODS} onChange={setPeriod} />
          <Segmented label="Metric" value={metric} options={METRICS} onChange={setMetric} />
        </div>
      }
    >
      {board.isPending ? (
        <Skeleton className="h-32" />
      ) : board.isError ? (
        <ErrorNote>{errorMessage(board.error)}</ErrorNote>
      ) : (
        <table className={`w-full text-sm transition-opacity ${board.isPlaceholderData ? "opacity-60" : ""}`}>
          <thead>
            <tr className="text-left text-xs text-muted">
              <th className="w-8 pb-2 font-normal">#</th>
              <th className="pb-2 font-normal">Player</th>
              <th className="pb-2 text-right font-normal">{metric === "best" ? "Best" : "Average"}</th>
              <th className="w-20 pb-2 text-right font-normal">Games</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {board.data.entries.map((entry) => (
              <tr key={entry.user.username} className={entry.value == null ? "text-muted" : ""}>
                <td className="nums py-2">{entry.rank ?? "–"}</td>
                <td className="py-2">
                  <UserLink user={entry.user} size={24} />
                </td>
                <td className="nums py-2 text-right text-base font-medium">
                  {entry.value == null ? "–" : metric === "best" ? entry.value.toFixed(0) : entry.value.toFixed(1)}
                </td>
                <td className="nums py-2 text-right text-muted">{entry.games}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  );
}

function ChartCard({ groupId, sinceJoining }: { groupId: string; sinceJoining: boolean }) {
  const [range, setRange] = useState<RangeKey>("90d");
  const series = useQuery({
    queryKey: ["group", groupId, "series", range, sinceJoining],
    queryFn: () => api<GroupSeries>(`/groups/${groupId}/series?range=${range}&since_joining=${sinceJoining}`),
    placeholderData: keepPreviousData,
  });
  return (
    <Card title="Daily best" aside={<Segmented label="Range" value={range} options={RANGE_OPTIONS} onChange={setRange} />}>
      {series.isPending ? (
        <Skeleton className="h-64" />
      ) : series.isError ? (
        <ErrorNote>{errorMessage(series.error)}</ErrorNote>
      ) : (
        <div className={`transition-opacity ${series.isPlaceholderData ? "opacity-60" : ""}`}>
          <OverlayChart data={series.data} />
        </div>
      )}
    </Card>
  );
}

function InviteCard({ group }: { group: GroupDetail }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const link = `${typeof window === "undefined" ? "" : window.location.origin}/join/${group.invite_code}`;
  const canManage = group.my_role !== "member";
  const regenerate = useMutation({
    mutationFn: () => api<{ invite_code: string }>(`/groups/${group.id}/invite/regenerate`, { method: "POST" }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["group", group.id, "detail"] });
      toast("New invite link created. The old one no longer works.");
    },
    onError: (error) => toast(errorMessage(error), "error"),
  });
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(link);
      toast("Invite link copied.");
    } catch {
      toast("Couldn't copy. Select the link and copy it by hand.", "error");
    }
  };

  return (
    <Card title="Invite link">
      <div className="flex flex-wrap items-center gap-2">
        <input
          readOnly
          aria-label="Invite link"
          value={link}
          onFocus={(event) => event.target.select()}
          className="nums h-10 min-w-0 flex-1 rounded-lg border border-border bg-bg px-3 text-xs"
        />
        <Button variant="primary" onClick={copy}>
          Copy
        </Button>
        {canManage && (
          <ConfirmButton
            variant="ghost"
            warning="The current link will stop working."
            confirmLabel="Make a new link"
            disabled={regenerate.isPending}
            onConfirm={() => regenerate.mutate()}
          >
            Regenerate
          </ConfirmButton>
        )}
      </div>
      <p className="mt-2 text-xs text-muted">Anyone with this link can join and see members&apos; stats.</p>
    </Card>
  );
}

function canRemove(myRole: Role, member: GroupMember, isMe: boolean): boolean {
  if (isMe) return false; // leaving has its own button
  if (myRole === "owner") return true;
  return myRole === "admin" && member.role === "member";
}

function MembersCard({ group, myUsername }: { group: GroupDetail; myUsername: string | undefined }) {
  const queryClient = useQueryClient();
  const router = useRouter();
  const toast = useToast();
  const onError = (error: unknown) => toast(errorMessage(error), "error");
  const remove = useMutation({
    mutationFn: (username: string) => api(`/groups/${group.id}/members/${encodeURIComponent(username)}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["group", group.id] }),
    onError,
  });
  const leaveOrDelete = useMutation({
    mutationFn: () =>
      group.my_role === "owner"
        ? api(`/groups/${group.id}`, { method: "DELETE" })
        : api(`/groups/${group.id}/members/${encodeURIComponent(myUsername ?? "")}`, { method: "DELETE" }),
    onSuccess: () => {
      // Remove this group's cached data before leaving the page so nothing refetches a group that is gone.
      queryClient.removeQueries({ queryKey: ["group", group.id] });
      void queryClient.invalidateQueries();
      router.push("/groups");
    },
    onError,
  });

  return (
    <Card title={`Members (${group.members.length})`}>
      <ul className="divide-y divide-border">
        {group.members.map((member) => (
          <li key={member.user.username} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
            <UserLink
              user={member.user}
              sub={`${member.role === "member" ? "" : `${member.role} · `}joined ${new Date(member.joined_at).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" })}`}
            />
            {canRemove(group.my_role, member, member.user.username === myUsername) && (
              <ConfirmButton
                variant="ghost"
                warning={`Remove ${member.user.username} from the group?`}
                confirmLabel="Remove"
                disabled={remove.isPending}
                onConfirm={() => remove.mutate(member.user.username)}
              >
                Remove
              </ConfirmButton>
            )}
          </li>
        ))}
      </ul>
      <div className="mt-4 border-t border-border pt-4">
        {group.my_role === "owner" ? (
          <ConfirmButton
            variant="danger"
            warning="This removes the group for everyone. Games are kept."
            confirmLabel="Delete group"
            disabled={leaveOrDelete.isPending}
            onConfirm={() => leaveOrDelete.mutate()}
          >
            Delete group
          </ConfirmButton>
        ) : (
          <ConfirmButton
            variant="danger"
            warning="You'll need a new invite to come back."
            confirmLabel="Leave group"
            disabled={leaveOrDelete.isPending || !myUsername}
            onConfirm={() => leaveOrDelete.mutate()}
          >
            Leave group
          </ConfirmButton>
        )}
      </div>
    </Card>
  );
}

export function GroupView() {
  const { id } = useParams<{ id: string }>();
  const { me } = useMe();
  const [sinceJoining, setSinceJoining] = useState(false);
  const group = useQuery({ queryKey: ["group", id, "detail"], queryFn: () => api<GroupDetail>(`/groups/${id}`) });

  if (group.isPending) return <PageSkeleton />;
  if (group.isError) {
    const missing = group.error instanceof ApiError && group.error.status === 404;
    return (
      <PageShell>
        <div className="mx-auto max-w-md py-16 text-center">
          <h1 className="text-xl font-semibold">{missing ? "Group not found" : "Couldn't load this group"}</h1>
          <p className="mt-2 text-sm text-muted">
            {missing ? "It may have been deleted, or you're not a member." : errorMessage(group.error)}
          </p>
          <Link href="/groups" className={buttonClass("secondary", "mt-6")}>
            Your groups
          </Link>
        </div>
      </PageShell>
    );
  }

  const data = group.data;
  return (
    <PageShell>
      <div className="mb-6">
        <h1 className="text-2xl font-semibold tracking-tight">{data.name}</h1>
        {data.description && <p className="mt-1 text-sm text-muted">{data.description}</p>}
      </div>

      <label className="mb-4 flex w-fit items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={sinceJoining}
          onChange={(event) => setSinceJoining(event.target.checked)}
          className="h-4 w-4 accent-[var(--text)]"
        />
        Only count games since each member joined
      </label>

      <div className="space-y-4">
        <LeaderboardCard groupId={data.id} sinceJoining={sinceJoining} />
        {data.members.length === 0 ? (
          <Card>
            <EmptyState>No members.</EmptyState>
          </Card>
        ) : (
          <ChartCard groupId={data.id} sinceJoining={sinceJoining} />
        )}
        <div className="grid gap-4 md:grid-cols-2">
          <Card title="Recent games">
            <GameList path={`/groups/${data.id}/feed`} showUser empty="Ranked games from members will show up here." />
          </Card>
          <div className="space-y-4">
            <InviteCard group={data} />
            <MembersCard group={data} myUsername={me?.username} />
          </div>
        </div>
      </div>
    </PageShell>
  );
}
