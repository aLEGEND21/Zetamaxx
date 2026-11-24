"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/Button";
import { Skeleton } from "@/components/Skeleton";
import { Card, EmptyState, ErrorNote, PageShell } from "@/components/ui";
import { api, errorMessage } from "@/lib/api";
import type { GroupDetail, GroupSummary } from "@/lib/types";

const INPUT = "h-10 w-full rounded-lg border border-border bg-surface px-3 text-sm";

function CreateGroup() {
  const router = useRouter();
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const create = useMutation({
    mutationFn: () =>
      api<GroupDetail>("/groups", { method: "POST", body: { name: name.trim(), description: description.trim() || null } }),
    onSuccess: (group) => {
      void queryClient.invalidateQueries({ queryKey: ["groups"] });
      router.push(`/groups/${group.id}`);
    },
  });

  return (
    <form
      className="space-y-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (name.trim()) create.mutate();
      }}
    >
      <div>
        <label htmlFor="group-name" className="mb-1 block text-xs text-muted">
          Name
        </label>
        <input id="group-name" value={name} maxLength={40} onChange={(e) => setName(e.target.value)} className={INPUT} />
      </div>
      <div>
        <label htmlFor="group-description" className="mb-1 block text-xs text-muted">
          Description (optional)
        </label>
        <input
          id="group-description"
          value={description}
          maxLength={280}
          onChange={(e) => setDescription(e.target.value)}
          className={INPUT}
        />
      </div>
      <Button type="submit" variant="primary" disabled={create.isPending || name.trim() === ""}>
        Create group
      </Button>
      {create.isError && (
        <p className="text-sm text-danger" role="alert">
          {errorMessage(create.error)}
        </p>
      )}
    </form>
  );
}

export function GroupsView() {
  const groups = useQuery({ queryKey: ["groups"], queryFn: () => api<{ groups: GroupSummary[] }>("/groups") });
  return (
    <PageShell title="Groups">
      <div className="grid gap-4 md:grid-cols-[1fr_320px]">
        <Card title="Your groups">
          {groups.isPending ? (
            <Skeleton className="h-24" />
          ) : groups.isError ? (
            <ErrorNote>{errorMessage(groups.error)}</ErrorNote>
          ) : groups.data.groups.length === 0 ? (
            <EmptyState>You&apos;re not in any groups yet. Create one, or open an invite link from a friend.</EmptyState>
          ) : (
            <ul className="divide-y divide-border">
              {groups.data.groups.map((group) => (
                <li key={group.id}>
                  <Link
                    href={`/groups/${group.id}`}
                    className="-mx-2 flex items-center justify-between gap-3 rounded-lg px-2 py-3 transition-colors duration-150 hover:bg-bg"
                  >
                    <span className="min-w-0">
                      <span className="block truncate text-sm font-medium">{group.name}</span>
                      {group.description && <span className="block truncate text-xs text-muted">{group.description}</span>}
                    </span>
                    <span className="shrink-0 text-xs text-muted">
                      {group.member_count} {group.member_count === 1 ? "member" : "members"}
                      {group.my_role !== "member" && ` · ${group.my_role}`}
                    </span>
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title="Create a group" className="self-start">
          <CreateGroup />
        </Card>
      </div>
    </PageShell>
  );
}
