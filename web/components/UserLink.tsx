import Link from "next/link";
import type { ReactNode } from "react";
import type { UserBrief } from "@/lib/types";
import { Avatar } from "./Avatar";

export function displayName(user: UserBrief): string {
  return user.display_name || user.username;
}

/** Avatar and name, linking to the player's profile. */
export function UserLink({ user, size = 28, sub }: { user: UserBrief; size?: number; sub?: ReactNode }) {
  return (
    <Link href={`/u/${user.username}`} className="group flex min-w-0 items-center gap-2.5">
      <Avatar user={user} size={size} />
      <span className="min-w-0">
        <span className="block truncate text-sm font-medium group-hover:underline">{displayName(user)}</span>
        {sub && <span className="block truncate text-xs text-muted">{sub}</span>}
      </span>
    </Link>
  );
}
