import { useMutation, useQuery } from "@tanstack/react-query";
import { type ReactNode, useState } from "react";

import { type Interview, scheduleInterview } from "../api/endpoints/interviews";
import { type DirectoryUser, listUsers } from "../api/endpoints/users";

const ROUNDS = [
  { value: "R1_TECH", label: "Round 1 · Technical" },
  { value: "R2_TECH", label: "Round 2 · Technical" },
  { value: "MANAGEMENT", label: "Management" },
];
const MODES = [
  { value: "VIDEO", label: "Video" },
  { value: "IN_PERSON", label: "In person" },
  { value: "TELEPHONIC", label: "Telephonic" },
];
// Sensible default round for the candidate's current stage.
const DEFAULT_ROUND: Record<string, string> = {
  SHORTLISTED: "R1_TECH", INTERVIEW_R1: "R2_TECH", INTERVIEW_R2: "MANAGEMENT", INTERVIEW_MGMT: "MANAGEMENT",
};

export function ScheduleInterviewModal({
  applicationId, candidateName, stage, onClose, onDone, lockRound, moveHint,
}: {
  applicationId: string;
  candidateName: string;
  stage: string;
  onClose: () => void;
  onDone: (interview: Interview) => void | Promise<void>;
  lockRound?: string;
  moveHint?: string;
}) {
  const [round, setRound] = useState(lockRound ?? DEFAULT_ROUND[stage] ?? "R1_TECH");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [mode, setMode] = useState("VIDEO");
  const [meetingLink, setMeetingLink] = useState("");
  const [location, setLocation] = useState("");
  const [panel, setPanel] = useState<string[]>([]);       // selected user_ids (max 5)
  const [lead, setLead] = useState<string>("");           // one lead user_id
  const [error, setError] = useState<string | null>(null);

  const usersQ = useQuery({ queryKey: ["users", "panel"], queryFn: () => listUsers({ limit: 100 }) });
  const users = usersQ.data?.items ?? [];

  const toggle = (u: DirectoryUser) => {
    setError(null);
    setPanel((cur) => {
      if (cur.includes(u.user_id)) {
        if (lead === u.user_id) setLead("");
        return cur.filter((x) => x !== u.user_id);
      }
      if (cur.length >= 5) { setError("A panel can have at most 5 members (INV-05)."); return cur; }
      const next = [...cur, u.user_id];
      if (!lead) setLead(u.user_id);   // first pick becomes lead by default
      return next;
    });
  };

  const m = useMutation({
    mutationFn: () => scheduleInterview({
      application_id: applicationId,
      round,
      // datetime-local values have no offset. Convert the user's local selection to an
      // unambiguous UTC instant before sending it to the timezone-aware API/database.
      scheduled_start: new Date(start).toISOString(),
      scheduled_end: new Date(end).toISOString(),
      mode,
      meeting_link: mode === "VIDEO" ? meetingLink || undefined : undefined,
      location: mode === "IN_PERSON" ? location || undefined : undefined,
      panelists: panel.map((uid) => ({ user_id: uid, is_lead: uid === lead })),
    }),
    onSuccess: onDone,
    onError: (e) => setError((e as { message?: string }).message ?? "Could not schedule the interview."),
  });

  const validate = (): string | null => {
    if (!start || !end) return "Pick a start and end time.";
    const startAt = new Date(start);
    const endAt = new Date(end);
    if (Number.isNaN(startAt.getTime()) || Number.isNaN(endAt.getTime())) return "Pick valid start and end times.";
    if (endAt <= startAt) return "End time must be after the start time.";
    if (startAt.getTime() < Date.now() - 60_000) return "The interview start time cannot be in the past.";
    if (panel.length < 1 || panel.length > 5) return "Select 1 to 5 panel members (INV-05).";
    if (!lead || !panel.includes(lead)) return "Mark exactly one panel member as lead.";
    return null;
  };
  const submit = () => { const v = validate(); if (v) { setError(v); return; } m.mutate(); };
  const close = () => { if (!m.isPending) onClose(); };

  return (
    <div className="modal-overlay" onMouseDown={close}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()} style={{ width: "min(680px, 94vw)", maxHeight: "88vh", overflowY: "auto" }}>
        <h3 style={{ marginBottom: 2 }}>Schedule interview — {candidateName}</h3>
        <div className="sub" style={{ marginBottom: 12 }}>Panel of 1–5, one lead. Panelists are notified on save.</div>
        {moveHint && <div className="card card-pad" style={{ marginBottom: 12, background: "var(--skysoft)", borderColor: "#C9DCFF", fontSize: ".82rem", fontWeight: 600, color: "var(--navy)", padding: "10px 12px" }}>{moveHint}</div>}

        <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
          <Field label="Round">
            <select value={round} disabled={!!lockRound} onChange={(e) => setRound(e.target.value)}>{ROUNDS.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}</select>
          </Field>
          <Field label="Mode">
            <select value={mode} onChange={(e) => setMode(e.target.value)}>{MODES.map((r) => <option key={r.value} value={r.value}>{r.label}</option>)}</select>
          </Field>
        </div>

        <div className="row" style={{ gap: 12, flexWrap: "wrap" }}>
          <Field label="Start"><input type="datetime-local" value={start} onChange={(e) => setStart(e.target.value)} /></Field>
          <Field label="End"><input type="datetime-local" value={end} onChange={(e) => setEnd(e.target.value)} /></Field>
        </div>

        {mode === "VIDEO" && <Field label="Meeting link (optional)"><input value={meetingLink} onChange={(e) => setMeetingLink(e.target.value)} placeholder="https://…" /></Field>}
        {mode === "IN_PERSON" && <Field label="Location (optional)"><input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="Room / office" /></Field>}

        <div style={{ marginTop: 14 }}>
          <div className="spread" style={{ marginBottom: 6 }}>
            <label style={{ margin: 0 }}>Panel <span className="muted">({panel.length}/5 · one lead)</span></label>
          </div>
          {usersQ.isLoading ? <div className="muted">Loading directory…</div>
            : usersQ.isError ? (
              <div className="card card-pad error-text">
                Couldn't load the employee directory. {(usersQ.error as { message?: string })?.message ?? ""}
                <button className="btn-sm btn-ghost" style={{ marginLeft: 8 }} onClick={() => usersQ.refetch()}>Retry</button>
              </div>
            ) : (
            <div className="card" style={{ maxHeight: 230, overflowY: "auto", padding: 4 }}>
              {users.map((u) => {
                const on = panel.includes(u.user_id);
                return (
                  <div key={u.user_id} className="spread" style={{ padding: "7px 8px", borderRadius: 8, background: on ? "var(--skysoft)" : "transparent" }}>
                    <label style={{ display: "flex", alignItems: "center", gap: 9, margin: 0, cursor: "pointer", flex: 1 }}>
                      <input type="checkbox" checked={on} onChange={() => toggle(u)} style={{ width: "auto", margin: 0 }} />
                      <span><b style={{ fontSize: ".85rem" }}>{u.full_name}</b> <span className="muted" style={{ fontSize: ".78rem" }}>· {u.designation ?? u.role_name}</span></span>
                    </label>
                    {on && (
                      <label style={{ display: "flex", alignItems: "center", gap: 5, margin: 0, cursor: "pointer", fontSize: ".76rem" }} title="Mark as lead">
                        <input type="radio" name="lead" checked={lead === u.user_id} onChange={() => setLead(u.user_id)} style={{ width: "auto", margin: 0 }} /> Lead
                      </label>
                    )}
                  </div>
                );
              })}
              {users.length === 0 && <div className="muted" style={{ padding: 10 }}>No users available.</div>}
            </div>
          )}
        </div>

        {error && <p className="error-text" style={{ marginBottom: 0 }}>{error}</p>}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16, gap: 8 }}>
          <button className="btn-ghost" disabled={m.isPending} onClick={close}>Cancel</button>
          <button disabled={m.isPending} onClick={submit}>{m.isPending ? "Scheduling…" : "Schedule & notify"}</button>
        </div>
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div style={{ flex: "1 1 200px", minWidth: 180 }}>
      <label>{label}</label>
      {children}
    </div>
  );
}
