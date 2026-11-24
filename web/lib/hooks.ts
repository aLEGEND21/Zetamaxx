"use client";

import { useAuth } from "@clerk/nextjs";
import { useQuery } from "@tanstack/react-query";
import { api } from "./api";
import type { Me } from "./types";

/** The signed-in user's local row, or undefined for guests / while loading. */
export function useMe() {
  const { isLoaded, isSignedIn } = useAuth();
  const query = useQuery({
    queryKey: ["me"],
    queryFn: () => api<Me>("/me"),
    enabled: isLoaded && !!isSignedIn,
    staleTime: 5 * 60_000,
  });
  return { me: isSignedIn ? query.data : undefined, isLoaded: isLoaded && (!isSignedIn || !query.isLoading), isSignedIn: !!isSignedIn };
}
