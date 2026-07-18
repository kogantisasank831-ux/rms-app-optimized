import { useMutation } from "@tanstack/react-query";
import { type FormEvent, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ApiError } from "../../api/client";
import { createCandidate } from "../../api/endpoints/candidates";

export default function CandidateUpload() {
  const nav = useNavigate();
  const [f, setF] = useState({ full_name: "", email: "", phone: "", total_experience_years: 0, source: "PORTAL", notice_period_days: 30 });
  const [cv, setCv] = useState<File | null>(null);
  const [error, setError] = useState<string | null>(null);
  const upd = (k: string, v: unknown) => setF((s) => ({ ...s, [k]: v }));

  const m = useMutation({
    mutationFn: () => createCandidate(f, cv as File),
    onSuccess: (r) => nav(`/candidates/${r.candidate_id}`),
    onError: (e) => setError((e as unknown as ApiError).message ?? "Upload failed"),
  });
  function submit(e: FormEvent) { e.preventDefault(); if (!cv) { setError("A CV file (pdf/docx) is required."); return; } setError(null); m.mutate(); }

  return (
    <div className="page" style={{ maxWidth: 720 }}>
      <div className="page-head"><div><h1>Upload Candidate</h1><div className="sub">CV → MinIO; text extracted for AI screening</div></div></div>
      <form className="card card-pad stack" onSubmit={submit}>
        <div className="grid-fields">
          <div><label>Full name</label><input value={f.full_name} onChange={(e) => upd("full_name", e.target.value)} required /></div>
          <div><label>Email</label><input value={f.email} onChange={(e) => upd("email", e.target.value)} required /></div>
          <div><label>Phone</label><input value={f.phone} onChange={(e) => upd("phone", e.target.value)} /></div>
          <div><label>Experience (yrs)</label><input type="number" min={0} step={0.5} value={f.total_experience_years} onChange={(e) => upd("total_experience_years", Number(e.target.value))} /></div>
          <div><label>Source</label><select value={f.source} onChange={(e) => upd("source", e.target.value)}><option>DIRECT</option><option>REFERRAL</option><option>PORTAL</option><option>IJP</option></select></div>
          <div><label>Notice period (days)</label><input type="number" min={0} value={f.notice_period_days} onChange={(e) => upd("notice_period_days", Number(e.target.value))} /></div>
        </div>
        <div><label>CV file (.pdf / .docx, ≤10MB)</label><input type="file" accept=".pdf,.docx" onChange={(e) => setCv(e.target.files?.[0] ?? null)} /></div>
        {error && <p className="error-text" style={{ margin: 0 }}>{error}</p>}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn-ghost" onClick={() => nav("/candidates")}>Cancel</button>
          <button type="submit" disabled={m.isPending}>{m.isPending ? "Uploading…" : "Create candidate"}</button>
        </div>
      </form>
    </div>
  );
}
