import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { createSkill, importSkills, listSkills, type Skill, updateSkill } from "../../api/endpoints/skills";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";

export default function SkillImport() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<Skill | "new" | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const skillsQ = useQuery({ queryKey: ["skills", "admin", q], queryFn: () => listSkills({ q, limit: 100 }) });
  const items = skillsQ.data?.items ?? [];
  const showLoader = useDelayedFlag(skillsQ.isLoading);

  const m = useMutation({
    mutationFn: (file: File) => importSkills(file),
    onSuccess: (r) => { setError(null); setResult(`Imported ${r.rows} rows — ${r.inserted} new, ${r.updated} updated.`); qc.invalidateQueries({ queryKey: ["skills"] }); },
    onError: (e) => setError((e as { message?: string }).message ?? "Import failed"),
  });

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Skill Master</h1><div className="sub">Canonical skill vocabulary (INV-09)</div></div>
        <div className="actions">
          <button onClick={() => { setResult(null); setError(null); setEditing("new"); }}>+ New skill</button>
          <span className="xlsx-help">
            <button className="btn-ghost" disabled={m.isPending} onClick={() => fileRef.current?.click()}>
              {m.isPending ? "Importing…" : "Import .xlsx"}
            </button>
            <div className="xlsx-help__card" role="tooltip">
              <div className="xlsx-help__title">Skill Master import</div>
              <p className="xlsx-help__lead">
                Bulk-load the canonical skill vocabulary (INV-09). RRFs and AI screening reference these
                skills, so names must stay consistent. Re-importing <em>upserts</em> — matching names are
                updated, new ones added.
              </p>
              <div className="xlsx-help__cols">
                <div className="xlsx-help__col">
                  <code className="xlsx-help__name">skill_name</code>
                  <span className="xlsx-help__req xlsx-help__req--on">required</span>
                  <span className="xlsx-help__desc">Canonical name, e.g. Kubernetes</span>
                </div>
                <div className="xlsx-help__col">
                  <code className="xlsx-help__name">skill_category</code>
                  <span className="xlsx-help__req">optional</span>
                  <span className="xlsx-help__desc">Grouping, e.g. DevOps</span>
                </div>
                <div className="xlsx-help__col">
                  <code className="xlsx-help__name">aliases</code>
                  <span className="xlsx-help__req">optional</span>
                  <span className="xlsx-help__desc">Comma-separated or JSON array, e.g. K8s, kube</span>
                </div>
              </div>
              <div className="xlsx-help__note">First row must be the header. Only <code>.xlsx</code> is accepted.</div>
            </div>
          </span>
          <input ref={fileRef} type="file" accept=".xlsx" style={{ display: "none" }} onChange={(e) => { const file = e.target.files?.[0]; if (file) m.mutate(file); e.target.value = ""; }} />
        </div>
      </div>
      {result && <div className="card card-pad" style={{ color: "var(--pos)", fontWeight: 600 }}>{result}</div>}
      {error && <div className="card card-pad error-text">{error}</div>}

      <div className="card" style={{ overflow: "hidden" }}>
        <div className="panel-head"><h3>Skills</h3><input placeholder="Search skills…" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 220 }} /></div>
        {skillsQ.isLoading ? (showLoader ? <NeuralLoader label="Loading Skill Master" /> : null)
          : (
            <table className="dt">
              <thead><tr><th>Skill</th><th>Category</th><th>Aliases</th><th style={{ width: 80 }} /></tr></thead>
              <tbody>
                {items.map((s) => (
                  <tr key={s.skill_id}>
                    <td style={{ fontWeight: 600 }}>{s.skill_name}</td>
                    <td className="muted">{s.skill_category ?? "—"}</td>
                    <td className="muted">{s.aliases?.join(", ") || "—"}</td>
                    <td><button className="btn-sm btn-ghost" onClick={() => { setResult(null); setError(null); setEditing(s); }}>Edit</button></td>
                  </tr>
                ))}
                {items.length === 0 && <tr><td colSpan={4} className="muted" style={{ padding: 16 }}>No skills match.</td></tr>}
              </tbody>
            </table>
          )}
      </div>

      {editing && (
        <SkillModal
          skill={editing === "new" ? null : editing}
          onClose={() => setEditing(null)}
          onDone={(msg) => { setEditing(null); setResult(msg); qc.invalidateQueries({ queryKey: ["skills"] }); }}
        />
      )}
    </div>
  );
}

function SkillModal({ skill, onClose, onDone }: { skill: Skill | null; onClose: () => void; onDone: (msg: string) => void }) {
  const [name, setName] = useState(skill?.skill_name ?? "");
  const [category, setCategory] = useState(skill?.skill_category ?? "");
  const [aliases, setAliases] = useState((skill?.aliases ?? []).join(", "));
  const [error, setError] = useState<string | null>(null);

  const m = useMutation({
    mutationFn: () => {
      const payload = {
        skill_name: name.trim(),
        skill_category: category.trim() || null,
        aliases: aliases.split(",").map((a) => a.trim()).filter(Boolean),
      };
      return skill ? updateSkill(skill.skill_id, payload) : createSkill(payload);
    },
    onSuccess: () => onDone(skill ? `Updated "${name.trim()}".` : `Added "${name.trim()}".`),
    onError: (e) => setError((e as { message?: string }).message ?? "Save failed"),
  });

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <h3>{skill ? "Edit skill" : "New skill"}</h3>
        <label>Skill name</label>
        <input value={name} autoFocus onChange={(e) => setName(e.target.value)} placeholder="e.g. Kubernetes" />
        <label style={{ marginTop: 12 }}>Category</label>
        <input value={category} onChange={(e) => setCategory(e.target.value)} placeholder="e.g. DevOps (optional)" />
        <label style={{ marginTop: 12 }}>Aliases</label>
        <input value={aliases} onChange={(e) => setAliases(e.target.value)} placeholder="comma-separated (optional)" />
        {error && <p className="error-text">{error}</p>}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button disabled={!name.trim() || m.isPending} onClick={() => m.mutate()}>{m.isPending ? "Saving…" : "Save"}</button>
        </div>
      </div>
    </div>
  );
}
