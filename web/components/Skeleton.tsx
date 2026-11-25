import { Card } from "./ui";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-lg bg-border/60 ${className}`} />;
}

const TILE_LABELS = ["Personal best", "Recent average", "Streak", "Improvement"];

/** Placeholder for the profile page, laid out like the page itself so nothing jumps when the data arrives. */
export function ProfileSkeleton() {
  return (
    <main className="mx-auto w-full max-w-content flex-1 px-4 py-8" aria-busy="true" aria-label="Loading profile">
      <div className="mb-6 flex items-center gap-4">
        <div aria-hidden="true" className="h-16 w-16 shrink-0 animate-pulse rounded-full bg-border/60" />
        <div>
          <Skeleton className="h-8 w-48" />
          <Skeleton className="mt-1 h-4 w-56 max-w-full" />
        </div>
      </div>

      <div className="space-y-4">
        <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
          {TILE_LABELS.map((label) => (
            <div key={label} className="rounded-card border border-border bg-surface p-4 sm:p-5">
              <p className="text-xs text-muted">{label}</p>
              <Skeleton className="mt-1 h-8 w-16" />
              <Skeleton className="mt-0.5 h-4 w-24" />
            </div>
          ))}
        </div>
        <Card title="Progress" aside={<Skeleton className="h-8 w-56" />}>
          <Skeleton className="h-64" />
        </Card>
        <Card title="Activity">
          <Skeleton className="h-39" />
        </Card>
        <Card title="Recent games">
          <div className="space-y-2">
            {[0, 1, 2].map((i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        </Card>
      </div>
    </main>
  );
}

/** Generic page placeholder: a title and a few cards. */
export function PageSkeleton() {
  return (
    <main className="mx-auto w-full max-w-content flex-1 px-4 py-8" aria-busy="true" aria-label="Loading">
      <Skeleton className="h-8 w-48" />
      <div className="mt-6 grid gap-4 sm:grid-cols-2">
        <Skeleton className="h-32" />
        <Skeleton className="h-32" />
      </div>
      <Skeleton className="mt-4 h-64" />
    </main>
  );
}
