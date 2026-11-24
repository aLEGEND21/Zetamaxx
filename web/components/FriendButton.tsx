"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, errorMessage } from "@/lib/api";
import type { Friends } from "@/lib/types";
import { Button } from "./Button";
import { useToast } from "./Toasts";

export function useFriends(enabled = true) {
  return useQuery({ queryKey: ["friends"], queryFn: () => api<Friends>("/friends"), enabled });
}

/** Friend actions keyed by username; each refreshes everything friendship can unlock. */
export function useFriendActions() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const options = {
    onSuccess: () => queryClient.invalidateQueries(),
    onError: (error: unknown) => toast(errorMessage(error), "error"),
  };
  const request = useMutation({
    mutationFn: (username: string) =>
      api<{ status: "pending" | "accepted" }>("/friends/requests", { method: "POST", body: { username } }),
    ...options,
  });
  const accept = useMutation({
    mutationFn: (username: string) => api(`/friends/requests/${encodeURIComponent(username)}/accept`, { method: "POST" }),
    ...options,
  });
  const remove = useMutation({
    mutationFn: (username: string) => api(`/friends/${encodeURIComponent(username)}`, { method: "DELETE" }),
    ...options,
  });
  return { request, accept, remove };
}

/** The one friendship action that makes sense for this user right now. */
export function FriendButton({ username }: { username: string }) {
  const friends = useFriends();
  const { request, accept, remove } = useFriendActions();
  if (!friends.data) return null;

  const has = (list: { user: { username: string } }[]) => list.some((entry) => entry.user.username === username);
  if (has(friends.data.friends)) return <span className="text-sm text-muted">Friends</span>;
  if (has(friends.data.incoming)) {
    return (
      <Button variant="primary" disabled={accept.isPending} onClick={() => accept.mutate(username)}>
        Accept friend request
      </Button>
    );
  }
  if (has(friends.data.outgoing)) {
    return (
      <Button disabled={remove.isPending} onClick={() => remove.mutate(username)}>
        Cancel request
      </Button>
    );
  }
  return (
    <Button variant="primary" disabled={request.isPending} onClick={() => request.mutate(username)}>
      Add friend
    </Button>
  );
}
