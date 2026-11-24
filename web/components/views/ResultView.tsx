"use client";

import { useQuery } from "@tanstack/react-query";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useRef } from "react";
import { buttonClass } from "@/components/Button";
import { Results } from "@/components/Results";
import { PageSkeleton } from "@/components/Skeleton";
import { PageShell } from "@/components/ui";
import { displayName } from "@/components/UserLink";
import { ApiError, api, errorMessage } from "@/lib/api";
import { SOCIAL } from "@/lib/features";
import { formatLocalDateTime } from "@/lib/format";
import type { GameDetail, Stats } from "@/lib/types";

const PRIVATE_NOTE = SOCIAL ? "Game details are shared with friends and group members." : "Only the player can see the details of a game.";

function Message({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <PageShell>
      <div className="mx-auto max-w-md py-16 text-center">
        <h1 className="text-xl font-semibold">{title}</h1>
        <p className="mt-2 text-sm text-muted">{children}</p>
        <Link href="/" className={buttonClass("primary", "mt-6")}>
          Play
        </Link>
      </div>
    </PageShell>
  );
}

/** One finished game: the same results panel the game screen shows, at a shareable address. */
export function ResultView() {
  const { gameId } = useParams<{ gameId: string }>();
  const game = useQuery({ queryKey: ["game", gameId], queryFn: () => api<GameDetail>(`/games/${gameId}`) });
  const username = game.data?.user.username;
  // The PB is public, so it can mark this game even for viewers who are not the player.
  const stats = useQuery({
    queryKey: ["stats", username, null],
    queryFn: () => api<Stats>(`/users/${username}/stats`),
    enabled: !!username && !!game.data?.is_ranked,
  });

  // "Play again" takes focus once the results are on screen, so Enter starts the next game.
  const playAgain = useRef<HTMLAnchorElement>(null);
  const loaded = game.isSuccess;
  useEffect(() => {
    if (loaded) playAgain.current?.focus();
  }, [loaded]);

  if (game.isPending) return <PageSkeleton />;
  if (game.isError) {
    const status = game.error instanceof ApiError ? game.error.status : 0;
    if (status === 404) return <Message title="Game not found">This game doesn&apos;t exist, or was never saved.</Message>;
    if (status === 401) return <Message title="Sign in to see this game">{PRIVATE_NOTE}</Message>;
    if (status === 403) return <Message title="This game is private">{PRIVATE_NOTE}</Message>;
    return <Message title="Couldn't load this game">{errorMessage(game.error)}</Message>;
  }

  const data = game.data;
  const isPb = data.is_ranked && stats.data?.pb != null && data.score >= stats.data.pb;
  return (
    <PageShell>
      <Results
        score={data.score}
        problems={data.problems}
        settings={data.settings}
        status={
          <span className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1">
            {isPb && (
              <span className="rounded-full bg-accent px-2.5 py-0.5 text-xs font-medium text-white" data-testid="pb-badge">
                Personal best
              </span>
            )}
            <span>
              <Link href={`/u/${data.user.username}`} className="text-text underline-offset-2 hover:underline">
                {displayName(data.user)}
              </Link>
              {" · "}
              {formatLocalDateTime(data.local_finished_at)}
            </span>
          </span>
        }
        actions={
          <Link href="/" ref={playAgain} className={buttonClass("primary")} data-testid="play-again">
            Play again
          </Link>
        }
      />
    </PageShell>
  );
}
