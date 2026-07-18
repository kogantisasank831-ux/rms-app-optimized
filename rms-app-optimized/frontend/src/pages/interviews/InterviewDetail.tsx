import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import {
  generateQuestions, getInterview, type InterviewDetail as Detail,
  type SuggestedQuestion,
} from "../../api/endpoints/interviews";
import { useAuth } from "../../auth/AuthContext";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";
import { StatusTag } from "../../components/StatusTag";

const CAT_LABEL: Record<string, string> = {
  technical: "Technical", behavioural: "Behavioural", role_specific: "Role-specific",
  experience: "Experience deep-dive", process_knowledge: "Process knowledge",
};
const CAT_ORDER = ["technical", "role_specific", "experience", "process_knowledge", "behavioural"];
const GEN_ROLES = ["ADMIN", "HR", "HIRING_MANAGER"];

function groupByCategory(qs: SuggestedQuestion[]): [string, SuggestedQuestion[]][] {
  const map = new Map<string, SuggestedQuestion[]>();
  for (const q of qs) {
    const key = q.category || "role_specific";
    (map.get(key) ?? map.set(key, []).get(key)!).push(q);
  }
  const rank = (c: string) => { const i = CAT_ORDER.indexOf(c); return i === -1 ? CAT_ORDER.length : i; };
  return [...map.entries()].sort((a, b) => rank(a[0]) - rank(b[0]));
}

export default function InterviewDetail() {
  const { interviewId = "" } = useParams();
  const { user } = useAuth();
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["interview", interviewId], queryFn: () => getInterview(interviewId) });
  const iv: Detail | undefined = q.data;

  const gen = useMutation({
    mutationFn: () => generateQuestions(interviewId),
    onSuccess: (data) => qc.setQueryData(["interview", interviewId], data),
  });

  const showLoader = useDelayedFlag(q.isLoading);
  const canGenerate = GEN_ROLES.includes(user?.role ?? "");
  const questions = iv?.ai_interview_questions;
  const hasQuestions = !!questions?.questions?.length;

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <Link to="/interviews" className="linkbtn">← Interviews</Link>
          <h1 style={{ marginTop: 6 }}>{iv?.candidate?.full_name ?? "Interview"}</h1>
          <div className="sub">
            {iv ? `${iv.position_title} · ${iv.round.replace(/_/g, " ")}` : "Loading…"}
          </div>
        </div>
        {iv && <StatusTag value={iv.status} />}
      </div>

      {q.isLoading ? (showLoader ? <NeuralLoader label="Loading Interview" /> : null)
        : q.isError || !iv ? <div className="card card-pad error-text">Couldn't load this interview.</div>
          : (
            <div className="grid-2">
              {/* LEFT: candidate + interview context */}
              <div className="col">
                <div className="card card-pad">
                  <h3 style={{ marginTop: 0 }}>Candidate</h3>
                  <dl className="detail-list">
                    <Row label="Name" value={iv.candidate.full_name} />
                    <Row label="Email" value={iv.candidate.email} />
                    {iv.candidate.phone && <Row label="Phone" value={iv.candidate.phone} />}
                    <Row label="Experience" value={iv.candidate.total_experience_years != null ? `${iv.candidate.total_experience_years} yrs` : "—"} />
                    {iv.candidate.current_company && <Row label="Current company" value={iv.candidate.current_company} />}
                    {iv.ai_screen_score != null && <Row label="AI screen score" value={`${Math.round(iv.ai_screen_score)}/100`} />}
                    <Row label="Link to candidate" value={<Link to={`/candidates/${iv.candidate.candidate_id}`} className="linkbtn">Open profile →</Link>} />
                  </dl>
                </div>
                <div className="card card-pad">
                  <h3 style={{ marginTop: 0 }}>Interview</h3>
                  <dl className="detail-list">
                    <Row label="Role" value={iv.position_title} />
                    <Row label="Round" value={iv.round.replace(/_/g, " ")} />
                    <Row label="When" value={new Date(iv.scheduled_start).toLocaleString()} />
                    <Row label="Mode" value={iv.mode} />
                    {iv.meeting_link && <Row label="Meeting" value={<a href={iv.meeting_link} target="_blank" rel="noreferrer" className="linkbtn">Join link →</a>} />}
                    {iv.location && <Row label="Location" value={iv.location} />}
                    <Row label="Panel" value={
                      <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                        {iv.panelists.map((p) => <span key={p.user_id} className="chip">{p.full_name}{p.is_lead ? " · lead" : ""}</span>)}
                      </div>
                    } />
                  </dl>
                </div>
              </div>

              {/* RIGHT: AI-suggested questions */}
              <div className="col">
                <div className={`card card-pad${gen.isPending ? " ai-run" : ""}`}>
                  <div className="spread" style={{ alignItems: "flex-start" }}>
                    <div>
                      <h3 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
                        Suggested Questions <span className="badge">AI</span>
                      </h3>
                      <div className="sub">Tailored to this resume, the role's JD, and the round.</div>
                    </div>
                    {canGenerate && (
                      <button className="btn-sm" disabled={gen.isPending} onClick={() => gen.mutate()}>
                        {gen.isPending ? "Generating…" : hasQuestions ? "Re-generate" : "Generate"}
                      </button>
                    )}
                  </div>

                  {gen.isError && <p className="error-text">Couldn't generate questions. Please try again.</p>}

                  {!hasQuestions ? (
                    <p className="muted" style={{ marginTop: 14 }}>
                      {gen.isPending ? "The AI is drafting questions from the resume and job description…"
                        : canGenerate ? "No questions yet — click Generate to draft a tailored set."
                          : "No questions have been generated for this interview yet."}
                    </p>
                  ) : (
                    <div className="stack" style={{ gap: 16, marginTop: 14 }}>
                      {questions!.summary && <p style={{ margin: 0 }}>{questions!.summary}</p>}
                      {!!questions!.focus_areas?.length && (
                        <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                          {questions!.focus_areas.map((f, i) => <span key={i} className="chip">{f}</span>)}
                        </div>
                      )}
                      {groupByCategory(questions!.questions).map(([cat, items]) => (
                        <div key={cat}>
                          <div style={{ fontSize: ".72rem", fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--accent)", paddingBottom: 6 }}>
                            {CAT_LABEL[cat] ?? cat}
                          </div>
                          <div className="stack" style={{ gap: 10 }}>
                            {items.map((qn, i) => (
                              <div key={i} className="card card-pad" style={{ background: "var(--skysoft)" }}>
                                <b style={{ fontSize: ".9rem" }}>{i + 1}. {qn.question}</b>
                                {qn.rationale && <p className="muted" style={{ fontSize: ".8rem", margin: "6px 0 0" }}><b>Why:</b> {qn.rationale}</p>}
                                {qn.what_to_look_for && <p style={{ fontSize: ".8rem", margin: "4px 0 0" }}><b>Look for:</b> {qn.what_to_look_for}</p>}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>
          )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="spread" style={{ padding: "6px 0", borderBottom: "1px solid var(--line)", gap: 12 }}>
      <span className="muted" style={{ fontSize: ".82rem" }}>{label}</span>
      <span style={{ fontSize: ".88rem", fontWeight: 600, textAlign: "right" }}>{value}</span>
    </div>
  );
}
