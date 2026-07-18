import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { getCandidate } from "../../api/endpoints/candidates";
import { Avatar } from "../../components/Avatar";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";

export default function CandidateDetail() {
  const { candidateId = "" } = useParams();
  const q = useQuery({ queryKey: ["candidate", candidateId], queryFn: () => getCandidate(candidateId), enabled: !!candidateId });
  const c = q.data;
  const showLoader = useDelayedFlag(q.isLoading);

  return (
    <div className="page" style={{ maxWidth: 900 }}>
      <div className="page-head">
        <div>
          <div className="sub"><Link to="/candidates" style={{ color: "var(--accent)" }}>← Candidates</Link></div>
          <div style={{ display: "flex", alignItems: "center", gap: 14, marginTop: 6 }}>
            {c && <Avatar name={c.full_name} src={c.photo_url ?? c.photo_icon_url} size={52} radius={14} />}
            <h1>{c?.full_name ?? "…"}</h1>
          </div>
        </div>
        {c?.cv_download_url && <div className="actions"><a href={c.cv_download_url} target="_blank" rel="noreferrer"><button className="btn-ghost">Download CV</button></a></div>}
      </div>

      {q.isLoading ? (showLoader ? <NeuralLoader label="Loading Candidate" /> : null)
        : !c ? <div className="card card-pad error-text">Could not load this candidate.</div>
          : (
            <div className="stack">
              <div className="card card-pad">
                <div className="grid-fields">
                  <F l="Email" v={c.email} /><F l="Phone" v={c.phone ?? "—"} />
                  <F l="Experience" v={`${c.total_experience_years ?? "—"} yrs`} /><F l="Company" v={c.current_company ?? "—"} />
                  <F l="Notice period" v={c.notice_period_days ? `${c.notice_period_days} days` : "—"} />
                  <F l="Source" v={c.source} /><F l="CV file" v={c.cv_file_name} />
                </div>
              </div>
              <div className="card">
                <div className="panel-head"><h3>Extracted CV Text</h3></div>
                <pre style={{ whiteSpace: "pre-wrap", wordBreak: "break-word", padding: "0 20px 18px", margin: 0, fontFamily: "inherit", fontSize: ".85rem", lineHeight: 1.55, color: "var(--ink-soft)", maxHeight: 420, overflow: "auto" }}>
                  {c.cv_text || "No text extracted."}
                </pre>
              </div>
            </div>
          )}
    </div>
  );
}

function F({ l, v }: { l: string; v: string }) {
  return <div><label style={{ marginBottom: 2 }}>{l}</label><div style={{ fontWeight: 600 }}>{v}</div></div>;
}
