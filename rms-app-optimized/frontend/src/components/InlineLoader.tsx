/**
 * Small, fluid, lightweight inline SVG loader for element-level loading states
 * (a section whose data is still fetching) — three softly pulsing neural-accent dots.
 * Not a full-screen takeover: use this so a page shell renders instantly and only the
 * still-loading pieces animate. See `.inline-loader` in index.css.
 */
export function InlineLoader({ label }: { label?: string }) {
  return (
    <span className="inline-loader" role="status" aria-label={label ?? "Loading"}>
      <svg viewBox="0 0 44 12" focusable="false" aria-hidden="true">
        <circle cx="6" cy="6" r="4" />
        <circle cx="22" cy="6" r="4" />
        <circle cx="38" cy="6" r="4" />
      </svg>
      {label && <span className="inline-loader__label">{label}</span>}
    </span>
  );
}
