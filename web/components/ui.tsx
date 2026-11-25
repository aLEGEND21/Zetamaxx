import type { ReactNode } from "react";

export function PageShell({ title, actions, children }: { title?: ReactNode; actions?: ReactNode; children: ReactNode }) {
  return (
    <main className="mx-auto w-full max-w-content flex-1 px-4 py-8">
      {(title || actions) && (
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          {title && <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>}
          {actions}
        </div>
      )}
      {children}
    </main>
  );
}

export function Card({ title, aside, children, className = "" }: { title?: ReactNode; aside?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-card border border-border bg-surface p-4 sm:p-5 ${className}`}>
      {(title || aside) && (
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          {title && <h2 className="text-sm font-medium">{title}</h2>}
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return <p className="py-8 text-center text-sm text-muted">{children}</p>;
}

export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <p role="alert" className="py-6 text-center text-sm text-danger">
      {children}
    </p>
  );
}

type SegmentedProps<T extends string> = {
  label: string;
  value: T;
  options: readonly { value: T; label: string }[];
  onChange: (value: T) => void;
};

/** A small row of mutually exclusive choices (chart range, leaderboard period...). */
export function Segmented<T extends string>({ label, value, options, onChange }: SegmentedProps<T>) {
  return (
    <div className="flex h-8 rounded-lg border border-border bg-bg p-0.5 text-xs" role="group" aria-label={label}>
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          aria-pressed={option.value === value}
          onClick={() => onChange(option.value)}
          className={`flex items-center rounded-md px-2.5 transition-colors duration-150 ${
            option.value === value ? "bg-surface text-text shadow-[0_0_0_1px_var(--border)]" : "text-muted hover:text-text"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export const RANGE_OPTIONS = [
  { value: "30d", label: "30 days" },
  { value: "90d", label: "90 days" },
  { value: "1y", label: "1 year" },
  { value: "all", label: "All" },
] as const;
