import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";

import { getApplication, type ScreeningResult } from "../api/endpoints/applications";

const REC_TAG: Record<string, string> = { SHORTLIST: "tag-ok", REVIEW: "tag-wait", REJECT: "tag-neg" };
const FIT_TAG: Record<string, string> = { EXCEEDS: "tag-ok", MEETS: "tag-wait", BELOW: "tag-neg" };

export function ScreeningAssessment({ applicationId, candidateName, onClose }: { applicationId: string; candidateName: string; onClose: () => void }) {
  const q = useQuery({ queryKey: ["application", applicationId], queryFn: () => getApplication(applicationId) });
  const r: ScreeningResult | null | undefined = q.data?.ai_screen_result;
  const score = q.data?.ai_screen_score;

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()} style={{ width: "min(760px, 92vw)", maxHeight: "82vh", overflowY: "auto" }}>
        <div className="spread" style={{ alignItems: "flex-start" }}>
          <div>
            <h3 style={{ margin: 0 }}>AI Screening — {candidateName}</h3>
            <div className="sub">Resume-screening agent assessment</div>
          </div>
          {score != null && <div style={{ fontSize: "2rem", fontWeight: 800, letterSpacing: "-.03em", lineHeight: 1, color: "var(--navy)" }}>{Math.round(score)}<span style={{ fontSize: ".8rem", color: "var(--ink-soft)", fontWeight: 700 }}>/100</span></div>}
        </div>

        {q.isLoading ? <p className="muted" style={{ marginTop: 16 }}>Loading assessment…</p>
          : !r ? <p className="muted" style={{ marginTop: 16 }}>No assessment yet — run <b>AI Screen</b> on this candidate first.</p>
          : (
            <div className="stack" style={{ gap: 16, marginTop: 16 }}>
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                {r.recommendation && <span className={`tag ${REC_TAG[r.recommendation] ?? "tag-wait"}`}>Rec: {r.recommendation}</span>}
                {r.experience_fit && <span className={`tag ${FIT_TAG[r.experience_fit] ?? "tag-wait"}`}>Experience: {r.experience_fit}</span>}
              </div>

              {r.rationale && <Section title="Rationale"><p style={{ margin: 0 }}>{r.rationale}</p></Section>}

              {!!r.essential_skill_coverage?.length && (
                <Section title="Essential skill coverage">
                  <table className="dt">
                    <thead><tr><th>Skill</th><th style={{ width: 60 }}>Found</th><th>Evidence</th></tr></thead>
                    <tbody>
                      {r.essential_skill_coverage.map((s, i) => (
                        <tr key={i}>
                          <td style={{ fontWeight: 600 }}>{s.skill}</td>
                          <td><span className={`tag ${s.present ? "tag-ok" : "tag-neg"}`}>{s.present ? "Yes" : "No"}</span></td>
                          <td className="muted" style={{ fontSize: ".8rem" }}>{s.evidence || "—"}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </Section>
              )}

              {!!r.missing_essential_skills?.length && (
                <Section title="Missing essential skills"><ChipRow items={r.missing_essential_skills} tone="tag-neg" /></Section>
              )}
              {!!r.desired_skills_found?.length && (
                <Section title="Desired skills found"><ChipRow items={r.desired_skills_found} tone="tag-ok" /></Section>
              )}
              {!!r.strengths?.length && <Section title="Strengths"><Bullets items={r.strengths} /></Section>}
              {!!r.risks?.length && <Section title="Risks"><Bullets items={r.risks} /></Section>}
            </div>
          )}

        <div className="row" style={{ justifyContent: "flex-end", marginTop: 20 }}>
          <button className="btn-ghost" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <div>
      <div style={{ fontSize: ".72rem", fontWeight: 700, letterSpacing: ".06em", textTransform: "uppercase", color: "var(--accent)", paddingBottom: 6 }}>{title}</div>
      {children}
    </div>
  );
}
function ChipRow({ items, tone }: { items: string[]; tone: string }) {
  return <div className="row" style={{ gap: 6, flexWrap: "wrap" }}>{items.map((x, i) => <span key={i} className={`tag ${tone}`}>{x}</span>)}</div>;
}
function Bullets({ items }: { items: string[] }) {
  return <ul style={{ margin: 0, paddingLeft: 18 }}>{items.map((x, i) => <li key={i} style={{ marginBottom: 4 }}>{x}</li>)}</ul>;
}
