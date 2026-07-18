import { useMutation, useQuery } from "@tanstack/react-query";
import { type FormEvent, type ReactNode, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";

import type { ApiError } from "../../api/client";
import { createRrf, type RrfSkillIn } from "../../api/endpoints/rrfs";
import { listSkills } from "../../api/endpoints/skills";

export default function RrfCreate() {
  const nav = useNavigate();
  const [f, setF] = useState({
    position_title: "", positions_count: 1, assignment_location: "Offshore (India)",
    justification: "", project_name: "", project_type: "T_AND_M" as "T_AND_M" | "FIXED_FEE",
    needed_by_date: "", min_experience_years: 3, wfh_allowed: false, bu_id: 1,
  });
  const [skills, setSkills] = useState<RrfSkillIn[]>([]);
  const [q, setQ] = useState("");
  const [error, setError] = useState<string | null>(null);

  const skillsQ = useQuery({ queryKey: ["skills", "picker", q], queryFn: () => listSkills({ q, limit: 8 }), enabled: q.trim().length > 0 });
  const results = useMemo(() => (skillsQ.data?.items ?? []).filter((s) => !skills.some((x) => x.skill_id === s.skill_id)), [skillsQ.data, skills]);
  const nameById = useMemo(() => new Map((skillsQ.data?.items ?? []).map((s) => [s.skill_id, s.skill_name])), [skillsQ.data]);
  const [names, setNames] = useState<Map<number, string>>(new Map());

  function addSkill(skillId: number, skillName: string, reqType: "ESSENTIAL" | "DESIRED") {
    setNames((previous) => new Map(previous).set(skillId, skillName));
    setSkills((previous) => [...previous, { skill_id: skillId, req_type: reqType, priority: reqType === "ESSENTIAL" ? 5 : 3 }]);
    setQ("");
  }

  const create = useMutation({
    mutationFn: () => createRrf({ ...f, skills }),
    onSuccess: (r) => nav(`/rrfs/${r.rrf_id}`),
    onError: (e) => setError((e as unknown as ApiError).message ?? "Create failed"),
  });

  function submit(e: FormEvent) { e.preventDefault(); setError(null); create.mutate(); }
  const upd = (k: string, v: unknown) => setF((s) => ({ ...s, [k]: v }));

  return (
    <div className="page" style={{ maxWidth: 860 }}>
      <div className="page-head"><div><h1>New Requisition</h1><div className="sub">Creates a DRAFT you can submit for approval</div></div></div>
      <form className="card card-pad stack" onSubmit={submit}>
        <div className="grid-fields">
          <L label="Position title"><input value={f.position_title} onChange={(e) => upd("position_title", e.target.value)} required /></L>
          <L label="Project name"><input value={f.project_name} onChange={(e) => upd("project_name", e.target.value)} required /></L>
          <L label="Positions"><input type="number" min={1} value={f.positions_count} onChange={(e) => upd("positions_count", Number(e.target.value))} /></L>
          <L label="Project type"><select value={f.project_type} onChange={(e) => upd("project_type", e.target.value)}><option value="T_AND_M">T &amp; M</option><option value="FIXED_FEE">Fixed Fee</option></select></L>
          <L label="Assignment location"><input value={f.assignment_location} onChange={(e) => upd("assignment_location", e.target.value)} required /></L>
          <L label="Needed by"><input type="date" value={f.needed_by_date} onChange={(e) => upd("needed_by_date", e.target.value)} required /></L>
          <L label="Min experience (yrs)"><input type="number" min={0} step={0.5} value={f.min_experience_years} onChange={(e) => upd("min_experience_years", Number(e.target.value))} /></L>
          <L label="Business Unit ID"><input type="number" min={1} value={f.bu_id} onChange={(e) => upd("bu_id", Number(e.target.value))} /></L>
        </div>
        <L label="Justification"><textarea rows={3} value={f.justification} onChange={(e) => upd("justification", e.target.value)} required /></L>

        <div>
          <label>Skills (add at least one ESSENTIAL before submitting)</label>
          <div className="row" style={{ flexWrap: "wrap", gap: 6, marginBottom: 8 }}>
            {skills.map((s) => (
              <span key={s.skill_id} className="badge" style={s.req_type === "ESSENTIAL" ? { background: "var(--navy)", color: "#fff" } : undefined}>
                {nameById.get(s.skill_id) ?? names.get(s.skill_id) ?? `#${s.skill_id}`} · {s.req_type === "ESSENTIAL" ? "must" : "nice"}
                <button type="button" className="btn-sm" style={{ background: "transparent", color: "inherit", padding: "0 0 0 8px" }}
                  onClick={() => setSkills((p) => p.filter((x) => x.skill_id !== s.skill_id))}>✕</button>
              </span>
            ))}
          </div>
          <input placeholder="Search skills…" value={q} onChange={(e) => setQ(e.target.value)} />
          {q && results.length > 0 && (
            <div className="card" style={{ marginTop: 6, padding: 6 }}>
              {results.map((s) => (
                <div key={s.skill_id} className="spread" style={{ padding: "6px 8px" }}>
                  <span style={{ fontSize: ".85rem" }}>{s.skill_name}</span>
                  <span className="row">
                    <button type="button" className="btn-sm" onClick={() => addSkill(s.skill_id, s.skill_name, "ESSENTIAL")}>+ Essential</button>
                    <button type="button" className="btn-sm btn-ghost" onClick={() => addSkill(s.skill_id, s.skill_name, "DESIRED")}>+ Desired</button>
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>

        {error && <p className="error-text" style={{ margin: 0 }}>{error}</p>}
        <div className="row" style={{ justifyContent: "flex-end" }}>
          <button type="button" className="btn-ghost" onClick={() => nav("/rrfs")}>Cancel</button>
          <button type="submit" disabled={create.isPending}>{create.isPending ? "Creating…" : "Create requisition"}</button>
        </div>
      </form>
    </div>
  );
}

function L({ label, children }: { label: string; children: ReactNode }) {
  return <div><label>{label}</label>{children}</div>;
}
