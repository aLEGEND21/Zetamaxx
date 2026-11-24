"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import Link from "next/link";
import type { ReactNode } from "react";
import { api, errorMessage } from "@/lib/api";
import { formatLocalDateTime } from "@/lib/format";
import { describeSettings } from "@/lib/settings";
import type { GameSummary, Page } from "@/lib/types";
import { Avatar } from "./Avatar";
import { Button } from "./Button";
import { Skeleton } from "./Skeleton";
import { EmptyState, ErrorNote } from "./ui";
import { displayName } from "./UserLink";

type Props = {
  /** API path including any filters, e.g. "/games?user=ada&ranked=true". */
  path: string;
  /** Feeds show who played; a single player's history does not. */
  showUser?: boolean;
  empty: ReactNode;
};

/** A paginated list of games, newest first. Each row opens that game's results. */
export function GameList({ path, showUser = false, empty }: Props) {
  const query = useInfiniteQuery({
    queryKey: ["games", path],
    queryFn: ({ pageParam }) =>
      api<Page<GameSummary>>(pageParam ? `${path}${path.includes("?") ? "&" : "?"}cursor=${encodeURIComponent(pageParam)}` : path),
    initialPageParam: "",
    getNextPageParam: (last) => last.next_cursor ?? undefined,
  });

  if (query.isPending) {
    return (
      <div className="space-y-2" aria-busy="true">
        {[0, 1, 2].map((i) => (
          <Skeleton key={i} className="h-10" />
        ))}
      </div>
    );
  }
  if (query.isError) return <ErrorNote>{errorMessage(query.error)}</ErrorNote>;

  const games = query.data.pages.flatMap((page) => page.items);
  if (games.length === 0) return <EmptyState>{empty}</EmptyState>;

  return (
    <>
      <ul className="divide-y divide-border">
        {games.map((game) => (
          <li key={game.id}>
            <Link
              href={`/results/${game.id}`}
              className="-mx-2 flex items-center gap-3 rounded-lg px-2 py-2.5 transition-colors duration-150 hover:bg-bg"
            >
              {showUser && <Avatar user={game.user} size={28} />}
              <span className="min-w-0 flex-1">
                {showUser && <span className="block truncate text-sm font-medium">{displayName(game.user)}</span>}
                <span className="block truncate text-xs text-muted">
                  {formatLocalDateTime(game.local_finished_at)}
                  {!game.is_ranked && ` · ${describeSettings(game.settings)}`}
                </span>
              </span>
              <span className="nums text-lg font-medium">{game.score}</span>
            </Link>
          </li>
        ))}
      </ul>
      {query.hasNextPage && (
        <div className="mt-3 flex justify-center">
          <Button variant="ghost" onClick={() => query.fetchNextPage()} disabled={query.isFetchingNextPage}>
            {query.isFetchingNextPage ? "Loading…" : "Load more"}
          </Button>
        </div>
      )}
    </>
  );
}
