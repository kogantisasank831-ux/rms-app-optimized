import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";

import {
  type AssessmentCategory, type CategoryAssessment, type Feedback,
  getFeedback, type Interview, myInterviews, priorFeedback, type PriorFeedback, submitFeedback,
} from "../../api/endpoints/interviews";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";
import { StatusTag } from "../../components/StatusTag";

const CATEGORY_LABEL: Record<AssessmentCategory, string> = {
  behavioural: "Behavioural", technical: "Technical", process_knowledge: "Process knowledge",
};
// R1_TECH is always the first round, so it can never have a prior round.
const hasPriorRound = (round: string) => round !== "R1_TECH";

export default function MyInterviews() {
  const navigate = useNavigate();
  const q = useQuery({ queryKey: ["my-interviews"], queryFn: myInterviews });
  const items = q.data ?? [];
  const showLoader = useDelayedFlag(q.isLoading);
  const [fb, setFb] = useState<Interview | null>(null);
  const [prior, setPrior] = useState<Interview | null>(null);
  const [view, setView] = useState<Interview | null>(null);
  const [toast, setToast] = useState<string | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);

  useEffect(() => () => { if (toastTimer.current) clearTimeout(toastTimer.current); }, []);

  const showToast = (msg: string) => {
    if (toastTimer.current) clearTimeout(toastTimer.current);
    setToast(msg);
    toastTimer.current = setTimeout(() => { setToast(null); toastTimer.current = null; }, 3500);
  };

  return (
    <div className="page">
      {toast && (
        <div className="toast toast-success" role="status">
          <span className="toast-check">✓</span>{toast}
        </div>
      )}
      <div className="page-head"><div><h1>Interviews</h1><div className="sub">Panels you are assigned to</div></div></div>
      {q.isLoading ? (showLoader ? <NeuralLoader label="Loading Interviews" /> : null)
        : items.length === 0 ? <div className="card card-pad muted">No interviews assigned to you.</div>
          : (
            <div className="stack">
              {items.map((iv) => (
                <div className="card card-pad link" role="button" tabIndex={0} key={iv.interview_id}
                  style={{ cursor: "pointer" }}
                  onClick={() => navigate(`/interviews/${iv.interview_id}`)}
                  onKeyDown={(e) => { if (e.key === "Enter") navigate(`/interviews/${iv.interview_id}`); }}>
                  <div className="spread">
                    <div>
                      <b>{iv.candidate_name ?? "Candidate"} · {iv.round.replace(/_/g, " ")}</b>
                      <div className="muted" style={{ fontSize: ".82rem", marginTop: 2 }}>{new Date(iv.scheduled_start).toLocaleString()} · {iv.mode}</div>
                    </div>
                    <StatusTag value={iv.status} />
                  </div>
                  <div className="row" style={{ marginTop: 10, flexWrap: "wrap", gap: 6 }}>
                    {iv.panelists.map((p) => <span key={p.user_id} className="chip">{p.full_name}{p.is_lead ? " · lead" : ""}</span>)}
                  </div>
                  <div className="row" style={{ marginTop: 12, flexWrap: "wrap", gap: 8 }} onClick={(e) => e.stopPropagation()}>
                    <button className="btn-sm btn-ghost" onClick={() => navigate(`/interviews/${iv.interview_id}`)}>View details & questions</button>
                    {hasPriorRound(iv.round) && <button className="btn-sm btn-ghost" onClick={() => setPrior(iv)}>Prior feedback</button>}
                    {iv.status === "COMPLETED" && <button className="btn-sm btn-ghost" onClick={() => setView(iv)}>View feedback</button>}
                    {iv.status === "SCHEDULED" && <button className="btn-sm" onClick={() => setFb(iv)}>Submit feedback</button>}
                  </div>
                </div>
              ))}
            </div>
          )}
      {fb && <FeedbackModal iv={fb} onClose={() => setFb(null)} onSuccess={() => showToast("Feedback submitted successfully.")} />}
      {prior && <PriorModal iv={prior} onClose={() => setPrior(null)} />}
      {view && <ViewFeedbackModal iv={view} onClose={() => setView(null)} />}
    </div>
  );
}

interface CatState { rating: number | null; comments: string }
const EMPTY_CAT: CatState = { rating: null, comments: "" };

// Management is a behavioural/leadership round — no technical or process-knowledge scoring.
const isTechnicalRound = (round: string) => round !== "MANAGEMENT";

function FeedbackModal({ iv, onClose, onSuccess }: { iv: Interview; onClose: () => void; onSuccess: () => void }) {
  const qc = useQueryClient();
  const technicalRound = isTechnicalRound(iv.round);
  const [rating, setRating] = useState(4);
  const [rec, setRec] = useState("SELECT");
  const [behavioural, setBehavioural] = useState<CatState>({ ...EMPTY_CAT });
  const [technical, setTechnical] = useState<CatState>({ ...EMPTY_CAT });
  const [processKnowledge, setProcessKnowledge] = useState<CatState>({ ...EMPTY_CAT });
  const [strengths, setStrengths] = useState("");
  const [weaknesses, setWeaknesses] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState(false);

  const buildAssessments = (): { category: AssessmentCategory; rating: number | null; comments?: string }[] => {
    const out: { category: AssessmentCategory; rating: number | null; comments?: string }[] = [
      { category: "behavioural", rating: behavioural.rating, comments: behavioural.comments.trim() || undefined },
    ];
    // Technical & process knowledge only apply to technical rounds (R1/R2), never Management.
    if (technicalRound) {
      out.push({ category: "technical", rating: technical.rating, comments: technical.comments.trim() || undefined });
      // Process knowledge is optional — include it only if the interviewer filled anything in.
      if (processKnowledge.rating != null || processKnowledge.comments.trim()) {
        out.push({ category: "process_knowledge", rating: processKnowledge.rating, comments: processKnowledge.comments.trim() || undefined });
      }
    }
    return out;
  };

  const m = useMutation({
    mutationFn: () => submitFeedback(iv.interview_id, {
      overall_rating: rating, recommendation: rec,
      strengths: strengths.trim() || undefined, weaknesses: weaknesses.trim() || undefined,
      raw_notes: notes.trim() || undefined,
      assessments: buildAssessments(),
    }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["my-interviews"] });
      qc.invalidateQueries({ queryKey: ["feedback", iv.interview_id] });
      // Close instantly and raise the page-level success toast — the AI summary keeps running
      // in the background with no UI lag.
      setDone(true);
      onSuccess();
      onClose();
    },
    onError: (e) => setError((e as { message?: string }).message ?? "Failed"),
  });

  const submit = () => {
    if (behavioural.rating == null || (technicalRound && technical.rating == null)) {
      setError(technicalRound
        ? "Give a rating for Behavioural and Technical (Process knowledge is optional)."
        : "Give a rating for Behavioural.");
      return;
    }
    setError(null);
    m.mutate();
  };

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal modal-scroll" onMouseDown={(e) => e.stopPropagation()} style={{ maxWidth: 560, maxHeight: "88vh" }}>
        <div className="modal-body">
          <h3 style={{ marginBottom: 2 }}>Consolidated feedback</h3>
          <p className="muted" style={{ marginTop: 0, fontSize: ".85rem" }}>{iv.candidate_name} · {iv.round.replace(/_/g, " ")}</p>

          <CategorySection title={CATEGORY_LABEL.behavioural} value={behavioural} onChange={setBehavioural} />
          {technicalRound && <>
            <CategorySection title={CATEGORY_LABEL.technical} value={technical} onChange={setTechnical} />
            <CategorySection title={CATEGORY_LABEL.process_knowledge} optional value={processKnowledge} onChange={setProcessKnowledge} />
          </>}

          <div style={{ borderTop: "1px solid var(--line)", margin: "14px 0 4px" }} />
          <label style={{ fontWeight: 700 }}>Overall</label>
          <div className="grid-fields" style={{ marginTop: 6 }}>
            <div><label>Overall rating (1–5)</label><input type="number" min={1} max={5} step={0.5} value={rating} onChange={(e) => setRating(Number(e.target.value))} /></div>
            <div><label>Recommendation</label><select value={rec} onChange={(e) => setRec(e.target.value)}><option>SELECT</option><option>HOLD</option><option>REJECT</option></select></div>
          </div>
          <label style={{ marginTop: 12 }}>Key strengths</label><textarea rows={2} value={strengths} onChange={(e) => setStrengths(e.target.value)} />
          <label style={{ marginTop: 10 }}>Areas of concern</label><textarea rows={2} value={weaknesses} onChange={(e) => setWeaknesses(e.target.value)} />
          <label style={{ marginTop: 10 }}>Overall feedback / notes</label><textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Summary rationale for the recommendation" />

          {done && <p className="success-text">✓ Feedback submitted — the AI summary is being generated.</p>}
          {error && <p className="error-text">{error}</p>}
          <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
            <button className="btn-ghost" onClick={onClose}>Cancel</button>
            <button disabled={m.isPending || done} onClick={submit}>{done ? "Submitted ✓" : m.isPending ? "Submitting…" : "Submit feedback"}</button>
          </div>
        </div>
      </div>
    </div>
  );
}

function CategorySection({ title, optional, value, onChange }: {
  title: string; optional?: boolean; value: CatState; onChange: (v: CatState) => void;
}) {
  return (
    <div className="card card-pad" style={{ marginTop: 12 }}>
      <div className="spread" style={{ alignItems: "center" }}>
        <label style={{ margin: 0, fontWeight: 700 }}>{title} {optional && <span className="muted" style={{ fontWeight: 400, fontSize: ".78rem" }}>· optional</span>}</label>
        <RatingPicker value={value.rating} onChange={(r) => onChange({ ...value, rating: r })} />
      </div>
      <textarea rows={2} style={{ marginTop: 8 }} placeholder={`${title} comments`} value={value.comments} onChange={(e) => onChange({ ...value, comments: e.target.value })} />
    </div>
  );
}

function RatingPicker({ value, onChange }: { value: number | null; onChange: (r: number) => void }) {
  return (
    <div className="row" style={{ gap: 4 }}>
      {[1, 2, 3, 4, 5].map((n) => (
        <button key={n} type="button" className={`btn-sm ${value === n ? "" : "btn-ghost"}`}
          style={{ minWidth: 30, padding: "3px 8px" }} onClick={() => onChange(n)} title={`${n} / 5`}>{n}</button>
      ))}
    </div>
  );
}

function PriorModal({ iv, onClose }: { iv: Interview; onClose: () => void }) {
  const q = useQuery({ queryKey: ["prior", iv.interview_id], queryFn: () => priorFeedback(iv.interview_id) });
  const rows: PriorFeedback[] = q.data ?? [];
  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()} style={{ maxWidth: 520 }}>
        <h3>Prior-round feedback</h3>
        {q.isLoading ? <p className="muted">Loading…</p>
          : rows.length === 0 ? <p className="muted" style={{ fontSize: ".85rem" }}>No feedback from earlier rounds yet — either this is the first round, or prior rounds haven't been completed.</p>
            : rows.map((r) => (
              <div key={r.round} className="card card-pad" style={{ marginTop: 10 }}>
                <div className="spread"><b>{r.round.replace(/_/g, " ")}</b><span className="chip">{r.recommendation} · {r.overall_rating}</span></div>
                {(r.assessments ?? []).length > 0 && (
                  <div className="row" style={{ flexWrap: "wrap", gap: 6, marginTop: 8 }}>
                    {(r.assessments ?? []).map((a: CategoryAssessment) => (
                      <span key={a.category} className="chip" title={a.comments ?? ""}>
                        {CATEGORY_LABEL[a.category] ?? a.category}{a.rating != null ? `: ${a.rating}/5` : ""}
                      </span>
                    ))}
                  </div>
                )}
                {r.strengths && <p style={{ fontSize: ".82rem", margin: "8px 0 0" }}><b>Strengths:</b> {r.strengths}</p>}
                {r.weaknesses && <p style={{ fontSize: ".82rem", margin: "4px 0 0" }} className="muted"><b>Concerns:</b> {r.weaknesses}</p>}
              </div>
            ))}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}><button onClick={onClose}>Close</button></div>
      </div>
    </div>
  );
}

function ViewFeedbackModal({ iv, onClose }: { iv: Interview; onClose: () => void }) {
  const q = useQuery({ queryKey: ["feedback", iv.interview_id], queryFn: () => getFeedback(iv.interview_id) });
  const fb: Feedback | null | undefined = q.data;
  const exec = (fb?.ai_summary as { executive_summary?: string } | null)?.executive_summary;
  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal modal-scroll" onMouseDown={(e) => e.stopPropagation()} style={{ maxWidth: 560, maxHeight: "88vh" }}>
        <div className="modal-body">
        <h3 style={{ marginBottom: 2 }}>Consolidated feedback</h3>
        <p className="muted" style={{ marginTop: 0, fontSize: ".85rem" }}>{iv.candidate_name} · {iv.round.replace(/_/g, " ")}</p>
        {q.isLoading ? <p className="muted">Loading…</p>
          : !fb ? <p className="muted" style={{ fontSize: ".85rem" }}>No consolidated feedback has been submitted for this interview.</p>
            : (
              <>
                <div className="spread" style={{ marginTop: 8 }}>
                  <span className="chip">Recommendation: {fb.recommendation}</span>
                  <span className="chip">Overall: {fb.overall_rating}/5</span>
                </div>
                {(fb.assessments ?? []).length > 0 && (
                  <div className="stack" style={{ marginTop: 10 }}>
                    {(fb.assessments ?? []).map((a: CategoryAssessment) => (
                      <div key={a.category} className="card card-pad">
                        <div className="spread"><b>{CATEGORY_LABEL[a.category] ?? a.category}</b><span className="chip">{a.rating != null ? `${a.rating}/5` : "—"}</span></div>
                        {a.comments && <p style={{ fontSize: ".82rem", margin: "6px 0 0" }}>{a.comments}</p>}
                      </div>
                    ))}
                  </div>
                )}
                {fb.strengths && <p style={{ fontSize: ".82rem", marginTop: 10 }}><b>Strengths:</b> {fb.strengths}</p>}
                {fb.weaknesses && <p style={{ fontSize: ".82rem", marginTop: 4 }} className="muted"><b>Concerns:</b> {fb.weaknesses}</p>}
                {fb.raw_notes && <p style={{ fontSize: ".82rem", marginTop: 8 }}><b>Notes:</b> {fb.raw_notes}</p>}
                {exec && (
                  <div className="card card-pad" style={{ marginTop: 12, background: "var(--skysoft)" }}>
                    <b style={{ fontSize: ".82rem" }}>AI summary</b>
                    <p style={{ fontSize: ".82rem", margin: "4px 0 0" }}>{exec}</p>
                  </div>
                )}
              </>
            )}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}><button onClick={onClose}>Close</button></div>
        </div>
      </div>
    </div>
  );
}
