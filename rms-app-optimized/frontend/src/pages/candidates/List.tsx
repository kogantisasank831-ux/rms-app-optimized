import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { listCandidates } from "../../api/endpoints/candidates";
import { useAuth } from "../../auth/AuthContext";
import { Avatar } from "../../components/Avatar";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";

const CAN_UPLOAD = ["ADMIN", "HR"];

export default function CandidateList() {
  const { user } = useAuth();
  const q = useQuery({ queryKey: ["candidates"], queryFn: () => listCandidates({ limit: 100 }) });
  const items = q.data?.items ?? [];
  const showLoader = useDelayedFlag(q.isLoading);

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Candidates</h1><div className="sub">Talent pool · role-scoped</div></div>
        {user && CAN_UPLOAD.includes(user.role) && <div className="actions"><Link to="/candidates/new"><button>+ Upload Candidate</button></Link></div>}
      </div>
      <div className="card" style={{ overflow: "hidden" }}>
        {q.isLoading ? (showLoader ? <NeuralLoader label="Loading Candidates" /> : null)
          : items.length === 0 ? <div className="card-pad muted">No candidates visible.</div>
            : (
              <table className="dt">
                <thead><tr><th>Name</th><th>Email</th><th>Company</th><th style={{ textAlign: "right" }}>Experience</th><th>Source</th></tr></thead>
                <tbody>
                  {items.map((c) => (
                    <tr key={c.candidate_id}>
                      <td style={{ fontWeight: 600 }}>
                        <div className="cell-person">
                          <Avatar name={c.full_name} src={c.photo_icon_url} size={30} />
                          <Link to={`/candidates/${c.candidate_id}`} className="nm">{c.full_name}</Link>
                        </div>
                      </td>
                      <td className="muted">{c.email}</td>
                      <td className="muted">{c.current_company ?? "—"}</td>
                      <td className="muted tnum" style={{ textAlign: "right" }}>{c.total_experience_years ?? "—"} yrs</td>
                      <td><span className="chip">{c.source}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
      </div>
    </div>
  );
}
