"use client";

import { useState } from "react";
import type { UserBrief } from "@/lib/types";

// Muted backgrounds for the initials fallback; picked by a hash of the username
// so a user always gets the same colour.
const COLORS = ["#5b7c99", "#7a6c9c", "#5f8f7b", "#a0705c", "#8a7f52", "#6b8791", "#96687f", "#6f7f5a"];

function hashOf(text: string): number {
  let hash = 0;
  for (let i = 0; i < text.length; i++) hash = (hash * 31 + text.charCodeAt(i)) >>> 0;
  return hash;
}

function initialsOf(user: Pick<UserBrief, "username" | "display_name">): string {
  const words = (user.display_name ?? "").trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  return (words[0] ?? user.username).slice(0, 2).toUpperCase();
}

type Props = { user: UserBrief; size?: number; className?: string };

/** The user's Clerk picture, or an initials circle when it is missing or fails to load. */
export function Avatar({ user, size = 32, className = "" }: Props) {
  const [failedUrl, setFailedUrl] = useState<string | null>(null);
  const showImage = user.avatar_url && user.avatar_url !== failedUrl;
  const style = { width: size, height: size, fontSize: Math.max(10, Math.round(size * 0.38)) };

  if (showImage) {
    return (
      // Remote avatars come from Clerk's CDN; a plain <img> keeps them out of the image optimizer.
      // eslint-disable-next-line @next/next/no-img-element
      <img
        src={user.avatar_url!}
        alt=""
        width={size}
        height={size}
        style={style}
        className={`shrink-0 rounded-full border border-border object-cover ${className}`}
        onError={() => setFailedUrl(user.avatar_url)}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      style={{ ...style, backgroundColor: COLORS[hashOf(user.username.toLowerCase()) % COLORS.length] }}
      className={`inline-flex shrink-0 select-none items-center justify-center rounded-full font-medium text-white ${className}`}
    >
      {initialsOf(user)}
    </span>
  );
}
