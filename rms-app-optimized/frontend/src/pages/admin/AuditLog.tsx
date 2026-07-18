import { useQuery } from "@tanstack/react-query";
import { useState } from "react";

import { listRuns } from "../../api/endpoints/agents";
import { listAudit } from "../../api/endpoints/dashboard";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";
import { StatusTag } from "../../components/StatusTag";

export default function AuditLog() {
  const [tab, setTab] = useState<"audit" | "agents">("audit");
  const auditQ = useQuery({ queryKey: ["audit"], queryFn: () => listAudit({ limit: 50 }), enabled: tab === "audit" });
  const runsQ = useQuery({ queryKey: ["runs"], queryFn: () => listRuns({ limit: 50 }), enabled: tab === "agents" });
  const showAudit = useDelayedFlag(auditQ.isLoading);
  const showRuns = useDelayedFlag(runsQ.isLoading);

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Audit &amp; AI Runs</h1><div className="sub">Append-only ledger (INV-02) + agent observability (INV-12)</div></div>
        <div className="actions">
          <button className={tab === "audit" ? "" : "btn-ghost"} onClick={() => setTab("audit")}>Audit log</button>
          <button className={tab === "agents" ? "" : "btn-ghost"} onClick={() => setTab("agents")}>AI runs</button>
        </div>
      </div>

      <div className="card" style={{ overflow: "hidden" }}>
        {tab === "audit" ? (
          auditQ.isLoading ? (showAudit ? <NeuralLoader label="Loading Audit Log" /> : null) : (
            <table className="dt">
              <thead><tr><th>Time</th><th>Entity</th><th>Action</th><th>By</th></tr></thead>
              <tbody>
                {(auditQ.data?.items ?? []).map((r) => (
                  <tr key={r.audit_id}>
                    <td className="muted tnum">{new Date(r.created_at).toLocaleString()}</td>
                    <td><span className="chip">{r.entity_type}</span> <span className="code">{r.entity_id.slice(0, 8)}…</span></td>
                    <td style={{ fontWeight: 600 }}>{r.action}</td>
                    <td className="muted">{r.performed_by ? `${r.performed_by.slice(0, 8)}…` : "system"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          runsQ.isLoading ? (showRuns ? <NeuralLoader label="Loading AI Runs" /> : null) : (
            <table className="dt">
              <thead><tr><th>Time</th><th>Agent</th><th>Entity</th><th style={{ textAlign: "right" }}>Tokens</th><th style={{ textAlign: "right" }}>Latency</th><th style={{ textAlign: "right" }}>Status</th></tr></thead>
              <tbody>
                {(runsQ.data?.items ?? []).map((r) => (
                  <tr key={r.run_id}>
                    <td className="muted tnum">{new Date(r.created_at).toLocaleString()}</td>
                    <td style={{ fontWeight: 600, textTransform: "capitalize" }}>{r.agent_name.replace(/_/g, " ")}</td>
                    <td className="muted">{r.entity_type}</td>
                    <td className="tnum muted" style={{ textAlign: "right" }}>{(r.prompt_tokens ?? 0) + (r.completion_tokens ?? 0)}</td>
                    <td className="tnum muted" style={{ textAlign: "right" }}>{r.latency_ms ?? "—"}ms</td>
                    <td style={{ textAlign: "right" }}><StatusTag value={r.status === "SUCCESS" ? "APPROVED" : r.status === "FAILURE" ? "REJECTED" : "PENDING_APPROVAL"} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>
    </div>
  );
}
