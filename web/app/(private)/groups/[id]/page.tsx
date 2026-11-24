import { Suspense } from "react";
import { PageSkeleton } from "@/components/Skeleton";
import { GroupView } from "@/components/views/GroupView";

export const metadata = { title: "Group · Zetamaxx" };

// The group id is only known at request time, so the view that reads it renders inside Suspense.
export default function GroupPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <GroupView />
    </Suspense>
  );
}
