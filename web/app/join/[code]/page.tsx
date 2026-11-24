import { Suspense } from "react";
import { PageSkeleton } from "@/components/Skeleton";
import { JoinView } from "@/components/views/JoinView";

export const metadata = { title: "Join a group · Zetamaxx" };

// The invite code is only known at request time, so the view that reads it renders inside Suspense.
export default function JoinPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <JoinView />
    </Suspense>
  );
}
