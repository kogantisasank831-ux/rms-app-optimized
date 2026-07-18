import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";

import { matchCandidates, type RankedCandidate } from "../../api/endpoints/applications";
import { getRrf, transitionRrf } from "../../api/endpoints/rrfs";
import { useAuth } from "../../auth/AuthContext";
import { CommentModal } from "../../components/CommentModal";
import { JdPanel } from "../../components/JdPanel";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";
import { StatusTag } from "../../components/StatusTag";

interface Act { action: string; label: string; roles: string[]; from: string[]; }
const ACTIONS: Act[] = [
  { action: "SUBMIT", label: "Submit for approval", roles: ["HIRING_MANAGER", "ADMIN"], from: ["DRAFT", "REJECTED"] },
  { action: "APPROVE", label: "Approve", roles: ["BU_HEAD", "ADMIN"], from: ["PENDING_APPROVAL"] },
  { action: "REJECT", label: "Reject", roles: ["BU_HEAD", "ADMIN"], from: ["PENDING_APPROVAL"] },
  { action: "HOLD", label: "Hold", roles: ["BU_HEAD", "HR", "ADMIN"], from: ["APPROVED"] },
  { action: "RESUME", label: "Resume", roles: ["BU_HEAD", "HR", "ADMIN"], from: ["ON_HOLD"] },
  { action: "REQUEST_CANCEL", label: "Request cancel", roles: ["HIRING_MANAGER", "ADMIN"], from: ["APPROVED"] },
  { action: "CONFIRM_CANCEL", label: "Confirm cancel", roles: ["BU_HEAD", "ADMIN"], from: ["CANCEL_REQUESTED"] },
  { action: "DECLINE_CANCEL", label: "Decline cancel", roles: ["BU_HEAD", "ADMIN"], from: ["CANCEL_REQUESTED"] },
];

export default function RrfDetail() {
  const { rrfId = "" } = useParams();
  const { user } = useAuth();
  const qc = useQueryClient();
  const [modal, setModal] = useState<Act | null>(null);
  const [ranked, setRanked] = useState<RankedCandidate[] | null>(null);

  const q = useQuery({ queryKey: ["rrf", rrfId], queryFn: () => getRrf(rrfId), enabled: !!rrfId });
  const rrf = q.data;
  const matchM = useMutation({ mutationFn: () => matchCandidates(rrfId), onSuccess: (r) => setRanked(r.ranked) });

  const avail = rrf && user
    ? ACTIONS.filter((a) => a.roles.includes(user.role) && a.from.includes(rrf.status))
    : [];
  const canMatch = user && ["ADMIN", "HR", "HIRING_MANAGER"].includes(user.role);
  const showLoader = useDelayedFlag(q.isLoading);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <div className="sub"><Link to="/rrfs" style={{ color: "var(--accent)" }}>← Requisitions</Link></div>
          <h1 style={{ marginTop: 6 }}>{rrf?.position_title ?? "…"}</h1>
        </div>
        {avail.length > 0 && (
          <div className="actions">
            {avail.map((a) => (
              <button key={a.action} className={a.action === "REJECT" ? "btn-ghost" : ""} onClick={() => setModal(a)}>{a.label}</button>
            ))}
          </div>
        )}
      </div>

      {q.isLoading ? (showLoader ? <NeuralLoader label="Loading Requisition" /> : null)
        : !rrf ? <div className="card card-pad error-text">Could not load this requisition.</div>
          : (
            <div className="grid-2">
              <div className="col">
                <div className="card card-pad">
                  <div className="spread">
                    <span className="code">{rrf.rrf_code}</span>
                    <StatusTag value={rrf.status} />
                  </div>
                  <p className="muted" style={{ margin: "6px 0 16px" }}>{rrf.project_name} · {rrf.project_type}</p>
                  <div className="grid-fields">
                    <Field l="Business Unit" v={rrf.bu_name ?? String(rrf.bu_id)} />
                    <Field l="Positions" v={`${rrf.positions_filled}/${rrf.positions_count}`} />
                    <Field l="Location" v={rrf.assignment_location} />
                    <Field l="Min experience" v={`${rrf.min_experience_years} yrs`} />
                    <Field l="WFH" v={rrf.wfh_allowed ? "Allowed" : "No"} />
                    <Field l="Needed by" v={rrf.needed_by_date} />
                  </div>
                  <div style={{ marginTop: 16 }}>
                    <label>Skills</label>
                    <div className="row" style={{ flexWrap: "wrap", gap: 6 }}>
                      {rrf.skills.map((s) => (
                        <span key={s.skill_id} className="badge" style={s.req_type === "ESSENTIAL" ? { background: "var(--navy)", color: "#fff" } : undefined}>
                          {s.skill_name} · {s.req_type === "ESSENTIAL" ? "must" : "nice"}
                        </span>
                      ))}
                      {rrf.skills.length === 0 && <span className="muted">No skills added.</span>}
                    </div>
                  </div>
                </div>
                <JdPanel rrfId={rrf.rrf_id} />
              </div>

              <div className="col">
                {canMatch && (
                  <div className="card">
                    <div className="panel-head"><div><h3>AI Candidate Match</h3><div className="sub">candidate_matching agent (advisory)</div></div>
                      <button className="btn-sm" onClick={() => matchM.mutate()} disabled={matchM.isPending}>{matchM.isPending ? "Ranking…" : "Run match"}</button>
                    </div>
                    <div style={{ padding: "0 20px 16px" }}>
                      {ranked == null ? <p className="muted" style={{ fontSize: ".85rem" }}>Run to rank the active candidate pool for this RRF.</p>
                        : ranked.length === 0 ? <p className="muted" style={{ fontSize: ".85rem" }}>No candidates in the pool yet.</p>
                          : ranked.map((c) => (
                            <div key={c.candidate_id} className="spread" style={{ padding: "10px 0", borderTop: "1px solid var(--line-2)" }}>
                              <div>
                                <div style={{ fontWeight: 600, fontSize: ".85rem" }}>{c.candidate_id.slice(0, 8)}…</div>
                                <div className="faint" style={{ fontSize: ".72rem" }}>{c.note}</div>
                              </div>
                              <b className="tnum">{Math.round(c.score)}</b>
                            </div>
                          ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}

      {modal && (
        <CommentModal
          title={modal.label}
          hint={`Requisition ${rrf?.rrf_code}`}
          actionLabel={modal.label}
          onClose={() => setModal(null)}
          onSubmit={async (comment) => {
            await transitionRrf(rrfId, modal.action, comment);
            qc.invalidateQueries({ queryKey: ["rrf", rrfId] });
            qc.invalidateQueries({ queryKey: ["rrfs"] });
          }}
        />
      )}
    </div>
  );
}

function Field({ l, v }: { l: string; v: string }) {
  return <div><label style={{ marginBottom: 2 }}>{l}</label><div style={{ fontWeight: 600 }}>{v}</div></div>;
}
