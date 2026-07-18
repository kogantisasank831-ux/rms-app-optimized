import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";

import { createUser, listRoles, listUsers, setUserActive, updateUser, uploadUserPhoto, type DirectoryUser } from "../../api/endpoints/users";
import { Avatar } from "../../components/Avatar";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";
import { useObjectUrl } from "../../hooks/useObjectUrl";

export default function Users() {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<DirectoryUser | null>(null);
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const usersQ = useQuery({
    queryKey: ["users", "admin", q],
    queryFn: () => listUsers({ q, include_inactive: true, limit: 100 }),
  });
  const items = usersQ.data?.items ?? [];
  const showLoader = useDelayedFlag(usersQ.isLoading);

  const toggle = useMutation({
    mutationFn: (u: DirectoryUser) => setUserActive(u.user_id, !(u.is_active ?? true)),
    onSuccess: (u) => {
      setError(null);
      setResult(`${u.full_name} is now ${u.is_active ? "active" : "deactivated"}.`);
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: (e) => setError((e as { message?: string }).message ?? "Update failed"),
  });

  return (
    <div className="page">
      <div className="page-head">
        <div>
          <h1>Employees</h1>
          <div className="sub">Manage staff details, roles and profile photos · selectable as interview panelists (INV-05)</div>
        </div>
        <div className="actions">
          <button onClick={() => { setResult(null); setError(null); setCreating(true); }}>+ New employee</button>
        </div>
      </div>
      {result && <div className="card card-pad" style={{ color: "var(--pos)", fontWeight: 600 }}>{result}</div>}
      {error && <div className="card card-pad error-text">{error}</div>}

      <div className="card" style={{ overflow: "hidden" }}>
        <div className="panel-head">
          <h3>Directory</h3>
          <input placeholder="Search name or email…" value={q} onChange={(e) => setQ(e.target.value)} style={{ width: 240 }} />
        </div>
        {usersQ.isLoading ? (showLoader ? <NeuralLoader label="Loading Employees" /> : null)
          : usersQ.isError ? <div className="card-pad error-text">Couldn't load employees. Please try again.</div>
            : (
              <table className="dt">
                <thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Designation</th><th>Status</th><th style={{ width: 170 }} /></tr></thead>
                <tbody>
                  {items.map((u) => {
                    const active = u.is_active ?? true;
                    return (
                      <tr key={u.user_id} style={{ opacity: active ? 1 : 0.55 }}>
                        <td style={{ fontWeight: 600 }}>
                          <div className="cell-person">
                            <Avatar name={u.full_name} src={u.photo_icon_url} size={30} />
                            <span className="nm">{u.full_name}</span>
                          </div>
                        </td>
                        <td className="muted">{u.email}</td>
                        <td>{u.role_name}</td>
                        <td className="muted">{u.designation ?? "—"}</td>
                        <td>
                          <span className={`tag ${active ? "tag-ok" : "tag-hold"}`}>{active ? "Active" : "Inactive"}</span>
                        </td>
                        <td>
                          <div className="row" style={{ gap: 6, justifyContent: "flex-end" }}>
                            <button className="btn-sm btn-ghost" onClick={() => { setResult(null); setError(null); setEditing(u); }}>Edit</button>
                            <button className="btn-sm btn-ghost" disabled={toggle.isPending} onClick={() => toggle.mutate(u)}>
                              {active ? "Deactivate" : "Reactivate"}
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                  {items.length === 0 && <tr><td colSpan={6} className="muted" style={{ padding: 16 }}>No employees match.</td></tr>}
                </tbody>
              </table>
            )}
      </div>

      {creating && (
        <NewEmployeeModal
          onClose={() => setCreating(false)}
          onDone={(msg) => { setCreating(false); setError(null); setResult(msg); qc.invalidateQueries({ queryKey: ["users"] }); }}
        />
      )}

      {editing && (
        <EditEmployeeModal
          user={editing}
          onClose={() => setEditing(null)}
          onDone={(msg) => { setEditing(null); setError(null); setResult(msg); qc.invalidateQueries({ queryKey: ["users"] }); }}
        />
      )}
    </div>
  );
}

function NewEmployeeModal({ onClose, onDone }: { onClose: () => void; onDone: (msg: string) => void }) {
  const rolesQ = useQuery({ queryKey: ["users", "roles"], queryFn: listRoles });
  const roles = rolesQ.data ?? [];
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("");
  const [designation, setDesignation] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const effectiveRole = role || roles[0]?.role_code || "";

  const m = useMutation({
    mutationFn: () => createUser({
      full_name: fullName.trim(),
      email: email.trim(),
      role: effectiveRole,
      designation: designation.trim() || null,
      password: password.trim() || null,
    }),
    onSuccess: () => onDone(`Added ${fullName.trim()}. They can now be picked as a panelist.`),
    onError: (e) => setError((e as { message?: string }).message ?? "Could not create employee"),
  });

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <h3>New employee</h3>
        <div className="sub" style={{ marginBottom: 12 }}>Added to the directory and selectable when scheduling interviews.</div>
        <label>Full name</label>
        <input value={fullName} autoFocus onChange={(e) => setFullName(e.target.value)} placeholder="Enter employee's full name" />
        <label style={{ marginTop: 12 }}>Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com" />
        <label style={{ marginTop: 12 }}>Role</label>
        <select value={effectiveRole} onChange={(e) => setRole(e.target.value)}>
          {roles.map((r) => <option key={r.role_code} value={r.role_code}>{r.role_name}</option>)}
        </select>
        <label style={{ marginTop: 12 }}>Designation</label>
        <input value={designation} onChange={(e) => setDesignation(e.target.value)} placeholder="e.g. Principal Engineer (optional)" />
        <label style={{ marginTop: 12 }}>Temporary password</label>
        <input value={password} onChange={(e) => setPassword(e.target.value)} placeholder="Leave blank for default (Passw0rd!23)" />
        {error && <p className="error-text">{error}</p>}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button disabled={!fullName.trim() || !email.trim() || !effectiveRole || m.isPending} onClick={() => m.mutate()}>
            {m.isPending ? "Saving…" : "Create employee"}
          </button>
        </div>
      </div>
    </div>
  );
}

function EditEmployeeModal({ user, onClose, onDone }: { user: DirectoryUser; onClose: () => void; onDone: (msg: string) => void }) {
  const rolesQ = useQuery({ queryKey: ["users", "roles"], queryFn: listRoles });
  const roles = rolesQ.data ?? [];
  const [fullName, setFullName] = useState(user.full_name);
  const [email, setEmail] = useState(user.email);
  const [role, setRole] = useState(user.role);
  const [designation, setDesignation] = useState(user.designation ?? "");
  const [active, setActive] = useState(user.is_active ?? true);
  const [photo, setPhoto] = useState<File | null>(null);
  const photoUrl = useObjectUrl(photo);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  function pickPhoto(f: File | null) {
    setPhoto(f);
  }

  const m = useMutation({
    mutationFn: async () => {
      // Only send changed detail fields; keeps the email-uniqueness check off unchanged emails.
      const payload: { full_name?: string; email?: string; designation?: string | null; role?: string; is_active?: boolean } = {};
      if (fullName.trim() !== user.full_name) payload.full_name = fullName.trim();
      if (email.trim() !== user.email) payload.email = email.trim();
      if ((designation.trim() || "") !== (user.designation ?? "")) payload.designation = designation.trim();
      if (role !== user.role) payload.role = role;
      if (active !== (user.is_active ?? true)) payload.is_active = active;
      if (Object.keys(payload).length > 0) await updateUser(user.user_id, payload);
      if (photo) await uploadUserPhoto(user.user_id, photo);
    },
    onSuccess: () => onDone(`Saved changes to ${fullName.trim()}.`),
    onError: (e) => setError((e as { message?: string }).message ?? "Could not save changes"),
  });

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <h3>Edit employee</h3>
        <div className="sub" style={{ marginBottom: 14 }}>Update this person's details, role and profile photo.</div>

        <div style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 6 }}>
          <Avatar name={fullName || user.full_name} src={photoUrl ?? user.photo_url ?? user.photo_icon_url} size={64} radius={16} />
          <div>
            <button className="btn-sm btn-ghost" onClick={() => fileRef.current?.click()}>{photo ? "Change photo" : "Upload photo"}</button>
            <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" style={{ display: "none" }} onChange={(e) => pickPhoto(e.target.files?.[0] ?? null)} />
            {photo && <div className="muted" style={{ fontSize: ".74rem", marginTop: 4 }}>{photo.name}</div>}
          </div>
        </div>

        <label style={{ marginTop: 12 }}>Full name</label>
        <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Full name" />
        <label style={{ marginTop: 12 }}>Email</label>
        <input value={email} onChange={(e) => setEmail(e.target.value)} placeholder="name@company.com" />
        <label style={{ marginTop: 12 }}>Role</label>
        <select value={role} onChange={(e) => setRole(e.target.value)}>
          {roles.map((r) => <option key={r.role_code} value={r.role_code}>{r.role_name}</option>)}
        </select>
        <label style={{ marginTop: 12 }}>Designation</label>
        <input value={designation} onChange={(e) => setDesignation(e.target.value)} placeholder="e.g. Principal Engineer (optional)" />
        <label style={{ marginTop: 12, display: "flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
          <input type="checkbox" style={{ width: "auto" }} checked={active} onChange={(e) => setActive(e.target.checked)} /> Active
        </label>

        {error && <p className="error-text">{error}</p>}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button disabled={!fullName.trim() || !email.trim() || m.isPending} onClick={() => m.mutate()}>
            {m.isPending ? "Saving…" : "Save changes"}
          </button>
        </div>
      </div>
    </div>
  );
}
