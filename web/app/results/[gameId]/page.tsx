import { Suspense } from "react";
import { PageSkeleton } from "@/components/Skeleton";
import { ResultView } from "@/components/views/ResultView";

export const metadata = { title: "Results · Zetamaxx" };

// The game id is only known at request time, so the view that reads it renders inside Suspense.
export default function ResultPage() {
  return (
    <Suspense fallback={<PageSkeleton />}>
      <ResultView />
    </Suspense>
  );
}
