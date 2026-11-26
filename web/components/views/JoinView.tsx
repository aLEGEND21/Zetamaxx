"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { Button, buttonClass } from "@/components/Button";
import { PageSkeleton } from "@/components/Skeleton";
import { PageShell } from "@/components/ui";
import { displayName } from "@/components/UserLink";
import { ApiError, api, errorMessage } from "@/lib/api";
import { useMe } from "@/lib/hooks";
import type { InvitePreview } from "@/lib/types";

/** What an invite link opens: a preview of the group and a Join button. */
export function JoinView() {
  const { code } = useParams<{ code: string }>();
  const router = useRouter();
  const queryClient = useQueryClient();
  const { isLoaded, isSignedIn } = useMe();
  const invite = useQuery({
    // Keyed by sign-in state so "already a member" is rechecked after signing in.
    queryKey: ["invite", code, isSignedIn],
    queryFn: () => api<InvitePreview>(`/invites/${encodeURIComponent(code)}`),
    enabled: isLoaded,
  });
  const join = useMutation({
    mutationFn: () => api<{ group_id: string }>(`/invites/${encodeURIComponent(code)}/join`, { method: "POST" }),
    onSuccess: ({ group_id }) => {
      void queryClient.invalidateQueries();
      router.push(`/groups/${group_id}`);
    },
  });

  if (!isLoaded || invite.isPending) return <PageSkeleton />;

  let body;
  if (invite.isError) {
    const missing = invite.error instanceof ApiError && invite.error.status === 404;
    body = (
      <>
        <h1 className="text-xl font-semibold">{missing ? "This invite link doesn't work" : "Couldn't load this invite"}</h1>
        <p className="mt-2 text-sm text-muted">
          {missing ? "It may have been replaced with a new one. Ask for a fresh link." : errorMessage(invite.error)}
        </p>
      </>
    );
  } else {
    const { group, already_member } = invite.data;
    body = (
      <>
        <p className="text-sm text-muted">You&apos;re invited to join</p>
        <h1 className="mt-1 text-2xl font-semibold tracking-tight">{group.name}</h1>
        {group.description && <p className="mt-2 text-sm">{group.description}</p>}
        <p className="mt-2 text-sm text-muted">
          {group.member_count} {group.member_count === 1 ? "member" : "members"} · created by {displayName(group.owner)}
        </p>
        <div className="mt-6 flex justify-center">
          {already_member ? (
            <Link href={`/groups/${group.id}`} className={buttonClass("primary")}>
              Open group
            </Link>
          ) : isSignedIn ? (
            <Button variant="primary" disabled={join.isPending} onClick={() => join.mutate()}>
              {join.isPending ? "Joining…" : "Join group"}
            </Button>
          ) : (
            // Clerk returns here after sign-in (or sign-up), where the button becomes "Join group".
            <Link href={`/sign-in?redirect_url=${encodeURIComponent(`/join/${code}`)}`} className={buttonClass("primary")}>
              Sign in to join
            </Link>
          )}
        </div>
        {join.isError && (
          <p className="mt-3 text-sm text-danger" role="alert">
            {errorMessage(join.error)}
          </p>
        )}
      </>
    );
  }

  return (
    <PageShell>
      <div className="mx-auto max-w-md rounded-card border border-border bg-surface p-8 text-center">{body}</div>
    </PageShell>
  );
}
