import { useMutation, useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { type Application } from "../api/endpoints/applications";
import { listByApplication, submitFeedback } from "../api/endpoints/interviews";

const STAGE_ROUND: Record<string, string> = { INTERVIEW_R1: "R1_TECH", INTERVIEW_R2: "R2_TECH", INTERVIEW_MGMT: "MANAGEMENT" };
const STAGE_ORDER = ["SHORTLISTED", "INTERVIEW_R1", "INTERVIEW_R2", "INTERVIEW_MGMT", "OFFER"];
const LABEL: Record<string, string> = { INTERVIEW_R1: "Round 1", INTERVIEW_R2: "Round 2", INTERVIEW_MGMT: "Management", OFFER: "Offer" };
const FORWARD = ["INTERVIEW_R2", "INTERVIEW_MGMT", "OFFER"];
const RECS = [
  { v: "SELECT", label: "Select", cls: "ok" },
  { v: "HOLD", label: "Hold", cls: "warn" },
  { v: "REJECT", label: "Reject", cls: "neg" },
];

export interface FeedbackNextMove {
  target: string;
  comment: string;
}

/**
 * Quick interview feedback straight from the pipeline board: capture overall rating +
 * recommendation (+ optional notes) for the candidate's scheduled interview, and — in the
 * same step — advance them to the next stage with a mandatory stage-change comment (INV-01).
 * Deeper, structured feedback still lives on the interview page.
 */
export function QuickFeedbackModal({ app, onClose, onDone, gateMode }: {
  app: Application;
  onClose: () => void;
  onDone: (nextMove?: FeedbackNextMove) => void | Promise<void>;
  gateMode?: boolean;
}) {
  const ivQ = useQuery({ queryKey: ["apps-interviews", app.application_id], queryFn: () => listByApplication(app.application_id) });

  const interviews = ivQ.data ?? [];
  const wantRound = STAGE_ROUND[app.current_stage];
  const scheduled = useMemo(
    // Never fall back to a different scheduled round: doing so records feedback against the
    // wrong interview and makes the pipeline's stage/round state irreconcilable.
    () => interviews.find((i) => i.status === "SCHEDULED" && i.round === wantRound),
    [interviews, wantRound],
  );
  const alreadyDone = !scheduled && interviews.some((i) => i.status === "COMPLETED" && (!wantRound || i.round === wantRound));

  const forwardTargets = FORWARD.filter((s) => STAGE_ORDER.indexOf(s) > STAGE_ORDER.indexOf(app.current_stage));

  const [rating, setRating] = useState(0);
  const [rec, setRec] = useState("");
  const [strengths, setStrengths] = useState("");
  const [weaknesses, setWeaknesses] = useState("");
  const [notes, setNotes] = useState("");
  const [advance, setAdvance] = useState(true);
  const [target, setTarget] = useState(forwardTargets[0] ?? "");
  const [comment, setComment] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [continuing, setContinuing] = useState(false);

  // In gate mode the pipeline board drives the move itself (feedback → schedule → advance),
  // so this modal only records feedback and never advances the candidate.
  const wantsAdvance = !gateMode && rec === "SELECT" && advance && !!target;
  const valid = rating >= 1 && !!rec && (!wantsAdvance || comment.trim().length >= 3);

  const m = useMutation({
    mutationFn: async (): Promise<FeedbackNextMove | undefined> => {
      if (!scheduled) throw new Error("No scheduled interview to record feedback against.");
      await submitFeedback(scheduled.interview_id, {
        overall_rating: rating,
        recommendation: rec,
        strengths: strengths.trim() || undefined,
        weaknesses: weaknesses.trim() || undefined,
        raw_notes: notes.trim() || undefined,
      });
      // The parent pipeline owns the subsequent stage transition. This avoids the dangerous
      // partial-success case where feedback commits, the move fails because the next interview
      // is not scheduled, and retrying then hits "feedback already exists".
      return wantsAdvance ? { target, comment: comment.trim() } : undefined;
    },
    onSuccess: (nextMove) => onDone(nextMove),
    onError: (e) => setError((e as { message?: string }).message ?? "Could not save feedback."),
  });

  const close = () => { if (!m.isPending && !continuing) onClose(); };
  const continueExisting = async () => {
    setContinuing(true);
    setError(null);
    try {
      await onDone();
    } catch (e) {
      setError((e as { message?: string }).message ?? "Could not continue the move.");
      setContinuing(false);
    }
  };

  return (
    <div className="modal-overlay" onMouseDown={close}>
      <div className="modal" style={{ maxWidth: 520 }} onMouseDown={(e) => e.stopPropagation()}>
        <h3>Interview feedback — {app.candidate_name}</h3>
        <div className="muted" style={{ fontSize: ".8rem", marginTop: -4, marginBottom: 12 }}>
          {LABEL[app.current_stage] ?? app.current_stage}{scheduled ? ` · ${scheduled.round.replace(/_/g, " ")}` : ""}
        </div>
        {gateMode && scheduled && (
          <div className="card card-pad" style={{ background: "var(--skysoft)", borderColor: "#C9DCFF", fontSize: ".82rem", fontWeight: 600, color: "var(--navy)", padding: "10px 12px", marginBottom: 12 }}>
            Record this round's feedback to continue moving {app.candidate_name} to the next round.
          </div>
        )}

        {ivQ.isLoading ? (
          <p className="muted">Loading interview…</p>
        ) : ivQ.isError ? (
          <div className="card card-pad error-text">
            Could not load this candidate's interviews. {(ivQ.error as { message?: string })?.message ?? ""}
            <div className="row" style={{ justifyContent: "flex-end", marginTop: 12 }}>
              <button className="btn-sm btn-ghost" onClick={() => ivQ.refetch()}>Retry</button>
              <button className="btn-sm" onClick={close}>Close</button>
            </div>
          </div>
        ) : !scheduled ? (
          <div className="card card-pad" style={{ background: "var(--panel-soft)" }}>
            <p style={{ margin: 0 }}>
              {alreadyDone
                ? "Feedback is already recorded for this round."
                : "No scheduled interview for this round — schedule one first, then add feedback."}
            </p>
            {error && <p className="error-text" style={{ marginBottom: 0 }}>{error}</p>}
            <div className="row" style={{ justifyContent: "flex-end", marginTop: 14 }}>
              <Link className="btn-ghost btn-sm" to={`/interviews`} style={{ textDecoration: "none" }}>Open interviews</Link>
              {gateMode && alreadyDone
                ? <button className="btn-sm" disabled={continuing} onClick={continueExisting}>{continuing ? "Continuing…" : "Continue move"}</button>
                : <button className="btn-sm" onClick={close}>Close</button>}
            </div>
          </div>
        ) : (
          <>
            <label>Overall rating</label>
            <div className="qf-scale">
              {[1, 2, 3, 4, 5].map((n) => (
                <button key={n} className={rating >= n ? "on" : ""} onClick={() => setRating(n)} type="button">{n}</button>
              ))}
              <span className="muted" style={{ fontSize: ".78rem", marginLeft: 8 }}>{rating ? `${rating}/5` : "select"}</span>
            </div>

            <label style={{ marginTop: 12 }}>Recommendation</label>
            <div className="qf-recs">
              {RECS.map((r) => (
                <button key={r.v} type="button" className={`qf-rec ${r.cls}${rec === r.v ? " on" : ""}`} onClick={() => {
                  setRec(r.v);
                  if (r.v !== "SELECT") setAdvance(false);
                }}>{r.label}</button>
              ))}
            </div>

            <div className="qf-grid">
              <div><label style={{ marginTop: 12 }}>Strengths</label><textarea rows={2} value={strengths} onChange={(e) => setStrengths(e.target.value)} placeholder="Optional" /></div>
              <div><label style={{ marginTop: 12 }}>Concerns</label><textarea rows={2} value={weaknesses} onChange={(e) => setWeaknesses(e.target.value)} placeholder="Optional" /></div>
            </div>
            <label style={{ marginTop: 8 }}>Notes</label>
            <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional quick notes" />

            {!gateMode && forwardTargets.length > 0 && (
              <div className="qf-advance">
                <label className="qf-check">
                  <input type="checkbox" checked={advance} disabled={rec !== "SELECT"} onChange={(e) => setAdvance(e.target.checked)} style={{ width: "auto" }} />
                  Advance candidate after saving
                </label>
                {rec && rec !== "SELECT" && <div className="muted" style={{ fontSize: ".76rem", marginTop: 5 }}>Only a Select recommendation can advance the candidate.</div>}
                {advance && (
                  <>
                    <div className="row" style={{ gap: 10, marginTop: 8 }}>
                      <div style={{ flex: "0 0 160px" }}>
                        <label>Move to</label>
                        <select value={target} onChange={(e) => setTarget(e.target.value)}>
                          {forwardTargets.map((s) => <option key={s} value={s}>{LABEL[s] ?? s}</option>)}
                        </select>
                      </div>
                      <div style={{ flex: 1 }}>
                        <label>Stage-change comment (required)</label>
                        <input value={comment} onChange={(e) => setComment(e.target.value)} placeholder="Why this decision…" />
                      </div>
                    </div>
                  </>
                )}
              </div>
            )}

            {error && <p className="error-text" style={{ marginTop: 10 }}>{error}</p>}

            <div className="row" style={{ justifyContent: "flex-end", marginTop: 16, gap: 8 }}>
              <button className="btn-ghost" disabled={m.isPending} onClick={close}>Cancel</button>
              <button disabled={!valid || m.isPending} onClick={() => { setError(null); m.mutate(); }}>
                {m.isPending ? "Saving…" : gateMode ? "Save feedback & continue" : wantsAdvance ? `Save & move to ${LABEL[target] ?? target}` : "Save feedback"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
