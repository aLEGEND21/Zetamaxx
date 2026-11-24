/** The Zetamaxx mark: a Z whose stroke is a division slash. Same drawing as app/icon.svg (the favicon). */
export function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
      <rect width="32" height="32" rx="7" fill="var(--text)" />
      <path d="M22 10 10 22" fill="none" stroke="var(--accent)" strokeWidth="3.2" strokeLinecap="round" />
      <path d="M10 10h12M10 22h12" fill="none" stroke="var(--surface)" strokeWidth="3.2" strokeLinecap="round" />
    </svg>
  );
}
