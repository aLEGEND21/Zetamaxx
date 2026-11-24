"use client";

import { useState } from "react";
import { Button } from "@/components/Button";
import { ConfirmButton } from "@/components/ConfirmButton";
import { useFriendActions, useFriends } from "@/components/FriendButton";
import { GameList } from "@/components/GameList";
import { Skeleton } from "@/components/Skeleton";
import { useToast } from "@/components/Toasts";
import { Card, EmptyState, ErrorNote, PageShell } from "@/components/ui";
import { UserLink } from "@/components/UserLink";
import { errorMessage } from "@/lib/api";
import { formatLocalDateTime } from "@/lib/format";

function AddFriend() {
  const [username, setUsername] = useState("");
  const { request } = useFriendActions();
  const toast = useToast();
  return (
    <form
      className="flex flex-wrap items-center gap-2"
      onSubmit={(event) => {
        event.preventDefault();
        const name = username.trim().replace(/^@/, "");
        if (!name) return;
        request.mutate(name, {
          onSuccess: (result) => {
            setUsername("");
            toast(result.status === "accepted" ? `You and ${name} are now friends.` : `Friend request sent to ${name}.`);
          },
        });
      }}
    >
      <label htmlFor="add-friend" className="sr-only">
        Username
      </label>
      <input
        id="add-friend"
        value={username}
        onChange={(event) => setUsername(event.target.value)}
        placeholder="Username"
        autoComplete="off"
        autoCapitalize="none"
        spellCheck={false}
        className="h-10 w-56 max-w-full rounded-lg border border-border bg-surface px-3 text-sm"
      />
      <Button type="submit" variant="primary" disabled={request.isPending || username.trim() === ""}>
        Add friend
      </Button>
    </form>
  );
}

export function FriendsView() {
  const friends = useFriends();
  const { accept, remove } = useFriendActions();
  const busy = accept.isPending || remove.isPending;

  return (
    <PageShell title="Friends" actions={<AddFriend />}>
      {friends.isPending ? (
        <Skeleton className="h-40" />
      ) : friends.isError ? (
        <ErrorNote>{errorMessage(friends.error)}</ErrorNote>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-4">
            {(friends.data.incoming.length > 0 || friends.data.outgoing.length > 0) && (
              <Card title="Requests">
                <ul className="divide-y divide-border">
                  {friends.data.incoming.map(({ user }) => (
                    <li key={user.username} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                      <UserLink user={user} sub="wants to be friends" />
                      <span className="flex gap-2">
                        <Button variant="primary" disabled={busy} onClick={() => accept.mutate(user.username)}>
                          Accept
                        </Button>
                        <Button disabled={busy} onClick={() => remove.mutate(user.username)}>
                          Decline
                        </Button>
                      </span>
                    </li>
                  ))}
                  {friends.data.outgoing.map(({ user }) => (
                    <li key={user.username} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                      <UserLink user={user} sub="request sent" />
                      <Button disabled={busy} onClick={() => remove.mutate(user.username)}>
                        Cancel
                      </Button>
                    </li>
                  ))}
                </ul>
              </Card>
            )}

            <Card title="Your friends">
              {friends.data.friends.length === 0 ? (
                <EmptyState>No friends yet. Add someone by their username to see each other&apos;s stats.</EmptyState>
              ) : (
                <ul className="divide-y divide-border">
                  {friends.data.friends.map(({ user, pb, last_played }) => (
                    <li key={user.username} className="flex flex-wrap items-center justify-between gap-2 py-2.5">
                      <UserLink
                        user={user}
                        sub={last_played ? `last played ${formatLocalDateTime(last_played)}` : "hasn't played yet"}
                      />
                      <span className="flex items-center gap-3">
                        <span className="text-right">
                          <span className="nums block text-lg font-medium leading-tight">{pb ?? "–"}</span>
                          <span className="block text-[11px] text-muted">best</span>
                        </span>
                        <ConfirmButton
                          variant="ghost"
                          warning={`Remove ${user.username}?`}
                          confirmLabel="Remove"
                          disabled={busy}
                          onConfirm={() => remove.mutate(user.username)}
                        >
                          Remove
                        </ConfirmButton>
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </Card>
          </div>

          <Card title="Friends' recent games">
            <GameList path="/friends/feed" showUser empty="Your friends' ranked games will show up here." />
          </Card>
        </div>
      )}
    </PageShell>
  );
}
