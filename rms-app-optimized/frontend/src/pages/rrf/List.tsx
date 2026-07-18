import { useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { listRrfs } from "../../api/endpoints/rrfs";
import { useAuth } from "../../auth/AuthContext";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";
import { StatusTag } from "../../components/StatusTag";

const CAN_CREATE = ["ADMIN", "HIRING_MANAGER"];
const STATUS_LABEL: Record<string, string> = {
  DRAFT: "Draft", PENDING_APPROVAL: "Pending Approval", APPROVED: "Approved", REJECTED: "Rejected",
  ON_HOLD: "On Hold", CANCEL_REQUESTED: "Cancel Requested", CANCELLED: "Cancelled", CLOSED: "Closed",
};

export default function RrfList() {
  const { user } = useAuth();
  const [params, setParams] = useSearchParams();
  const status = params.get("status") ?? "";
  const q = useQuery({ queryKey: ["rrfs"], queryFn: () => listRrfs({ limit: 100 }) });
  const all = q.data?.items ?? [];
  const items = status ? all.filter((r) => r.status === status) : all;
  const showLoader = useDelayedFlag(q.isLoading);

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Requisitions</h1>
          <div className="sub">
            {status ? `Filtered · ${STATUS_LABEL[status] ?? status}` : "Role-scoped requisition list"}
          </div>
        </div>
        <div className="actions" style={{ gap: 8 }}>
          {status && <button className="btn-ghost" onClick={() => { params.delete("status"); setParams(params, { replace: true }); }}>Clear filter ({items.length})</button>}
          {user && CAN_CREATE.includes(user.role) && (
            <Link to="/rrfs/new"><button>+ New Requisition</button></Link>
          )}
        </div>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {q.isLoading ? (
          showLoader ? <NeuralLoader label="Loading Requisitions" /> : null
        ) : items.length === 0 ? (
          <div className="card-pad muted">{status ? `No requisitions in ${STATUS_LABEL[status] ?? status}.` : "No requisitions visible for your role."}</div>
        ) : (
          <table className="dt">
            <thead><tr><th>Code</th><th>Position</th><th>Project</th><th>Business Unit</th><th style={{ textAlign: "right" }}>Needed by</th><th style={{ textAlign: "right" }}>Status</th></tr></thead>
            <tbody>
              {items.map((r) => (
                <tr key={r.rrf_id}>
                  <td><Link to={`/rrfs/${r.rrf_id}`} className="code">{r.rrf_code}</Link></td>
                  <td style={{ fontWeight: 600 }}>{r.position_title}</td>
                  <td className="muted">{r.project_name}</td>
                  <td className="muted">{r.bu_name ?? r.bu_id}</td>
                  <td className="muted tnum" style={{ textAlign: "right" }}>{r.needed_by_date}</td>
                  <td style={{ textAlign: "right" }}><StatusTag value={r.status} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
