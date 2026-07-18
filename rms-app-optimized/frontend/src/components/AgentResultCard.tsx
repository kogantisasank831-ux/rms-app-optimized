import { type ReactNode } from "react";

/**
 * Generic container for AI-agent output (LLD 7 "AgentResultCard"): titled card with an "AI"
 * badge and an optional run/re-run action. Reused across agents (jd_creation, screening, …).
 */
export function AgentResultCard({
  title,
  subtitle,
  actionLabel,
  onAction,
  busy,
  children,
}: {
  title: string;
  subtitle?: string;
  actionLabel?: string;
  onAction?: () => void;
  busy?: boolean;
  children?: ReactNode;
}) {
  return (
    <div className="card" style={{ padding: 20 }}>
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          marginBottom: children ? 14 : 0,
        }}
      >
        <div>
          <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
            {title}
            <span className="badge">AI</span>
          </h3>
          {subtitle && (
            <p style={{ margin: "4px 0 0", color: "var(--muted)", fontSize: "0.85rem" }}>
              {subtitle}
            </p>
          )}
        </div>
        {onAction && actionLabel && (
          <button onClick={onAction} disabled={busy}>
            {busy ? "Working…" : actionLabel}
          </button>
        )}
      </div>
      {children}
    </div>
  );
}
