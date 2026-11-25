/** Sized and placed so the crown stands on the text's baseline and reaches the top of its capitals. */
function CrownIcon() {
  return (
    <svg width="12" height="12" viewBox="0 0.7 16 16" fill="currentColor" aria-hidden="true">
      <path d="M1.9 4.6a.6.6 0 0 1 .98-.46L5.4 6.2l2.1-3.3a.6.6 0 0 1 1 0l2.1 3.3 2.52-2.06a.6.6 0 0 1 .98.56l-1.1 6.3a.6.6 0 0 1-.6.5H3.6a.6.6 0 0 1-.6-.5L1.9 4.7Z" />
      <rect x="3" y="12.6" width="10" height="1.4" rx=".7" />
    </svg>
  );
}

/** The pill that marks a personal best: "New PR" when it was just set, "Personal best" on a saved game. */
export function BestBadge({ children }: { children: string }) {
  return (
    <span
      className="inline-flex items-center gap-1.5 rounded-full bg-accent-ink px-3.5 py-1.5 text-xs font-medium leading-none text-white"
      data-testid="pb-badge"
    >
      <CrownIcon />
      {children}
    </span>
  );
}
