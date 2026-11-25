/** The Zetamaxx mark: a white z centred on a dark tile. Same drawing as app/icon.svg (the favicon). */
export function Logo({ size = 26 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden="true" className="shrink-0">
      <rect width="32" height="32" rx="7" fill="var(--text)" />
      <path
        d="M10.8 10.4h10.4l-10.4 11.2h10.4"
        fill="none"
        stroke="var(--surface)"
        strokeWidth="3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}
