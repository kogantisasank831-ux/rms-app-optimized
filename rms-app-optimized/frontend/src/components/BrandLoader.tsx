import { TcgLoader } from "./TcgLoader";

/**
 * Full-screen branded boot loader. Shown while auth hydrates from a stored token,
 * so the very first frame the user sees is the branded TCG mark — not plain "Loading…".
 * Renders the same TCG loader + welcome as the Dashboard's CommandCenterLoader, so the
 * hand-off from boot → dashboard loader is visually seamless (one continuous animation).
 */
export function BrandLoader() {
  return (
    <div className="brand-boot" role="status" aria-live="polite">
      <TcgLoader />
      <div className="cc-wordmark">tcg<span>digital</span></div>
      <div className="cc-welcome">Find work that moves ideas forward</div>
      <div className="cc-line" aria-hidden="true">Gearing up for your best experience</div>
      <div className="cc-bar"><i /></div>
      <span className="sr-only">Application is loading</span>
    </div>
  );
}
