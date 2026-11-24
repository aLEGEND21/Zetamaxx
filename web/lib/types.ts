// Shapes returned by the API (api/app/schemas).

import type { SolvedProblem } from "./engine";
import type { GameSettings, Op } from "./settings";

export type UserBrief = { username: string; display_name: string | null; avatar_url: string | null };

export type Me = UserBrief & { id: string; timezone: string; timezone_set: boolean; created_at: string };

export type GameSummary = {
  id: string;
  user: UserBrief;
  score: number;
  duration_s: number;
  is_ranked: boolean;
  settings_hash: string;
  settings: GameSettings;
  avg_ms: Record<Op, number | null>;
  /** Wall-clock time in the player's own timezone, e.g. "2026-11-24T22:41:05". */
  local_finished_at: string;
  local_date: string;
};

export type GameDetail = GameSummary & { problems: SolvedProblem[] };

export type Page<T> = { items: T[]; next_cursor: string | null };

/** Strangers only get `user.username` and `pb`; everything else needs `visible`. */
export type Stats = {
  user: UserBrief;
  visible: boolean;
  is_self: boolean;
  pb: number | null;
  games?: number;
  recent_avg?: number | null;
  improvement?: number | null;
  streak?: number;
  last_played?: string | null;
};

export type RangeKey = "30d" | "90d" | "1y" | "all";

/** Ranges of the profile's progress chart. */
export type ProgressRange = "7d" | "30d" | "90d" | "1y";
export type SeriesPoint = { date: string; best: number; avg: number; games: number; rolling_avg: number };
/** One game, at the player's local time, e.g. "2026-11-24T22:41:05". */
export type GamePoint = { at: string; score: number; rolling_avg: number };
/** The 7-day range has one point per game; longer ranges have one per day. */
export type Series = { range: ProgressRange; from: string; to: string } & (
  | { per: "game"; points: GamePoint[] }
  | { per: "day"; points: SeriesPoint[] }
);
export type Activity = { days: { date: string; games: number }[]; total: number };
export type ConfigSummary = {
  settings_hash: string;
  settings: GameSettings;
  games: number;
  best: number;
  avg: number;
  last_played: string;
};

export type Role = "owner" | "admin" | "member";
export type GroupSummary = { id: string; name: string; description: string | null; my_role: Role; member_count: number };
export type GroupMember = { user: UserBrief; role: Role; joined_at: string };
export type GroupDetail = {
  id: string;
  name: string;
  description: string | null;
  invite_code: string;
  my_role: Role;
  created_at: string;
  members: GroupMember[];
};
export type LeaderboardEntry = { user: UserBrief; value: number | null; games: number; rank: number | null };
export type Leaderboard = { period: string; metric: string; since_joining: boolean; entries: LeaderboardEntry[] };
export type GroupSeries = { range: RangeKey; members: { user: UserBrief; points: { date: string; best: number }[] }[] };
export type InvitePreview = {
  group: { id: string; name: string; description: string | null; member_count: number; owner: UserBrief };
  already_member: boolean;
};

export type FriendEntry = { user: UserBrief; pb: number | null; last_played: string | null };
export type Friends = { friends: FriendEntry[]; incoming: { user: UserBrief }[]; outgoing: { user: UserBrief }[] };
