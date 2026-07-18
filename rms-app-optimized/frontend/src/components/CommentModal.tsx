import { type FormEvent, useState } from "react";

import type { ApiError } from "../api/client";

/**
 * The ONE way to fire any state transition (LLD): a mandatory-comment modal (INV-01).
 * onSubmit throws on failure; the modal surfaces the API error and stays open.
 */
export function CommentModal({
  title,
  hint,
  actionLabel = "Confirm",
  onSubmit,
  onClose,
}: {
  title: string;
  hint?: string;
  actionLabel?: string;
  onSubmit: (comment: string) => Promise<void>;
  onClose: () => void;
}) {
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!comment.trim()) { setError("A comment is required."); return; }
    setBusy(true); setError(null);
    try {
      await onSubmit(comment.trim());
      onClose();
    } catch (err) {
      setError((err as ApiError).message ?? "Action failed");
    } finally {
      setBusy(false);
    }
  }

  const close = () => { if (!busy) onClose(); };

  return (
    <div className="modal-overlay" onMouseDown={close}>
      <form className="modal" onMouseDown={(e) => e.stopPropagation()} onSubmit={submit}>
        <h3>{title}</h3>
        {hint && <p className="muted" style={{ marginTop: 0, fontSize: ".85rem" }}>{hint}</p>}
        <label htmlFor="cm">Comment (required)</label>
        <textarea id="cm" rows={4} value={comment} autoFocus
          onChange={(e) => setComment(e.target.value)} placeholder="Reason for this action…" />
        {error && <p className="error-text" style={{ marginBottom: 0 }}>{error}</p>}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button type="button" className="btn-ghost" disabled={busy} onClick={close}>Cancel</button>
          <button type="submit" disabled={busy}>{busy ? "Working…" : actionLabel}</button>
        </div>
      </form>
    </div>
  );
}

