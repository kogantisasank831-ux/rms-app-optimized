import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";

import { type Application, listApplications } from "../../api/endpoints/applications";
import {
  createOffer, generateLetter, getOffer, listOffers, type Offer,
  type OfferSummary, transitionOffer, updateOffer,
} from "../../api/endpoints/offers";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";

// Offer's own lifecycle status → candidate-facing label + tag style.
const OFFER_STATUS: Record<string, { label: string; cls: string }> = {
  DRAFT: { label: "Draft", cls: "tag-wait" },
  RELEASED: { label: "Offer shared", cls: "tag-ok" },
  ACCEPTED: { label: "Accepted", cls: "tag-ok" },
  DECLINED: { label: "Declined", cls: "tag-neg" },
  WITHDRAWN: { label: "Withdrawn", cls: "tag-hold" },
};
function OfferStatus({ status }: { status?: string }) {
  if (!status) return <span className="tag tag-hold">Not created</span>;
  const s = OFFER_STATUS[status] ?? { label: status, cls: "tag-wait" };
  return <span className={`tag ${s.cls}`}>{s.label}</span>;
}

// Candidates who can receive an offer: shortlisted, in any interview round, or already at offer.
// Creating an offer auto-advances the candidate to OFFER (see backend system_move_to_offer).
const ELIGIBLE_STAGES = ["SHORTLISTED", "INTERVIEW_R1", "INTERVIEW_R2", "INTERVIEW_MGMT", "OFFER", "OFFER_ACCEPTED"];
const STAGE_LABEL: Record<string, string> = {
  SHORTLISTED: "Shortlisted", INTERVIEW_R1: "Interview R1", INTERVIEW_R2: "Interview R2",
  INTERVIEW_MGMT: "Management", OFFER: "Offer", OFFER_ACCEPTED: "Offer accepted",
};

export default function OffersPage() {
  const appsQ = useQuery({ queryKey: ["apps", "offer-eligible"], queryFn: () => listApplications({ limit: 100 }) });
  const offersQ = useQuery({ queryKey: ["offers"], queryFn: listOffers });
  const rows = (appsQ.data?.items ?? []).filter((a) => ELIGIBLE_STAGES.includes(a.current_stage));
  const offerByApp = new Map((offersQ.data ?? []).map((o) => [o.application_id, o]));
  const [active, setActive] = useState<{ app: Application; summary?: OfferSummary } | null>(null);

  const [pick, setPick] = useState("");
  const showLoader = useDelayedFlag(appsQ.isLoading);
  const openByAppId = (appId: string) => {
    const app = rows.find((a) => a.application_id === appId);
    if (app) setActive({ app, summary: offerByApp.get(appId) });
  };

  return (
    <div className="page">
      <div className="page-head">
        <div><h1>Offers</h1><div className="sub">Draft offers, generate the letter, share, and record responses</div></div>
        <div className="actions" style={{ display: "flex", alignItems: "center", gap: 8 }}>
          <label style={{ margin: 0, fontSize: ".78rem", color: "var(--ink-faint)" }}>Candidate</label>
          <select value={pick} style={{ minWidth: 260 }}
            onChange={(e) => { setPick(e.target.value); if (e.target.value) openByAppId(e.target.value); }}>
            <option value="">Select a candidate…</option>
            {rows.map((a) => {
              const s = offerByApp.get(a.application_id);
              return (
                <option key={a.application_id} value={a.application_id}>
                  {a.candidate_name} · {a.candidate_id.slice(0, 8)} · {a.rrf_code}{s ? ` — ${OFFER_STATUS[s.status]?.label ?? s.status}` : ""}
                </option>
              );
            })}
          </select>
        </div>
      </div>
      <div className="card" style={{ overflow: "hidden" }}>
        {appsQ.isLoading ? (showLoader ? <NeuralLoader label="Loading Offers" /> : null)
          : rows.length === 0 ? <div className="card-pad muted">No candidates are ready for an offer yet. Shortlist or interview a candidate in the pipeline first.</div>
            : (
              <table className="dt">
                <thead><tr><th>Candidate</th><th>Requisition</th><th>Stage</th><th style={{ textAlign: "right" }}>Offer Status</th><th style={{ textAlign: "right" }}>Action</th></tr></thead>
                <tbody>
                  {rows.map((a) => {
                    const summary = offerByApp.get(a.application_id);
                    return (
                      <tr key={a.application_id}>
                        <td style={{ fontWeight: 600 }}>{a.candidate_name}</td>
                        <td className="code">{a.rrf_code}</td>
                        <td className="muted">{STAGE_LABEL[a.current_stage] ?? a.current_stage}</td>
                        <td style={{ textAlign: "right" }}><OfferStatus status={summary?.status} /></td>
                        <td style={{ textAlign: "right" }}>
                          <button className="btn-sm" onClick={() => setActive({ app: a, summary })}>
                            {summary ? "Open offer" : "Create offer"}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            )}
      </div>
      {active && <OfferWorkspace app={active.app} existingId={active.summary?.offer_id} onClose={() => { setActive(null); setPick(""); }} />}
    </div>
  );
}

type Form = {
  candidate_name: string; designation: string; monthly_gross: string;
  ctc_annual: string; joining_date: string; work_location: string; valid_until: string;
};
const toForm = (app: Application, o?: Offer | null): Form => ({
  candidate_name: o?.candidate_name ?? app.candidate_name ?? "",
  designation: o?.designation ?? "",
  monthly_gross: o?.monthly_gross ?? "",
  ctc_annual: o?.ctc_annual ?? "",
  joining_date: o?.joining_date ?? "",
  work_location: o?.work_location ?? "Kolkata",
  valid_until: o?.valid_until ?? "",
});

function OfferWorkspace({ app, existingId, onClose }: { app: Application; existingId?: string; onClose: () => void }) {
  const qc = useQueryClient();
  const [offer, setOffer] = useState<Offer | null>(null);
  const [f, setF] = useState<Form>(() => toForm(app));
  const [editing, setEditing] = useState(!existingId);   // create mode, or "Edit terms" toggled on
  const [letterUrl, setLetterUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const upd = (k: keyof Form, v: string) => setF((s) => ({ ...s, [k]: v }));
  const wrap = <T,>(p: Promise<T>) => p.catch((e) => { setError((e as { message?: string }).message ?? "Failed"); throw e; });

  // Keep fetching pure. Syncing query data in an effect also handles the important case
  // where React Query serves a fresh cached offer and never calls queryFn.
  const offerQ = useQuery({
    queryKey: ["offer", existingId],
    enabled: !!existingId,
    queryFn: () => getOffer(existingId!),
  });
  useEffect(() => {
    if (!offerQ.data) return;
    setOffer(offerQ.data);
    setF(toForm(app, offerQ.data));
  }, [app, offerQ.data]);
  const showOfferLoader = useDelayedFlag(!!existingId && offerQ.isLoading && !offer);

  const payload = () => ({
    candidate_name: f.candidate_name.trim() || undefined,
    designation: f.designation.trim(),
    monthly_gross: f.monthly_gross.trim() || undefined,
    ctc_annual: f.ctc_annual.trim(),
    joining_date: f.joining_date,
    work_location: f.work_location.trim(),
    valid_until: f.valid_until || undefined,
  });

  const createM = useMutation({
    mutationFn: () => wrap(createOffer({ application_id: app.application_id, ...payload() })),
    // Creating an offer moves the candidate to OFFER — refresh both offers and the pipeline kanban.
    onSuccess: (o) => { setError(null); setOffer(o); qc.setQueryData(["offer", o.offer_id], o); setEditing(false); qc.invalidateQueries({ queryKey: ["offers"] }); qc.invalidateQueries({ queryKey: ["apps"] }); },
  });
  const saveM = useMutation({
    mutationFn: () => wrap(updateOffer(offer!.offer_id, payload())),
    onSuccess: (o) => { setError(null); setOffer(o); qc.setQueryData(["offer", o.offer_id], o); setEditing(false); setLetterUrl(null); qc.invalidateQueries({ queryKey: ["offers"] }); },
  });
  const letterM = useMutation({
    mutationFn: () => wrap(generateLetter(offer!.offer_id)),
    onSuccess: (r) => { setError(null); setLetterUrl(r.download_url); setOffer((o) => o ? { ...o, letter_object_key: r.letter_object_key } : o); qc.invalidateQueries({ queryKey: ["offers"] }); },
  });
  const trM = useMutation({
    mutationFn: (action: string) => wrap(transitionOffer(offer!.offer_id, action, `${action.toLowerCase()} via offers console`)),
    onSuccess: (_d, action) => {
      setError(null);
      setOffer((o) => o ? { ...o, status: action === "RELEASE" ? "RELEASED" : action === "ACCEPT" ? "ACCEPTED" : action === "DECLINE" ? "DECLINED" : "WITHDRAWN" } : o);
      qc.invalidateQueries({ queryKey: ["apps"] }); qc.invalidateQueries({ queryKey: ["offers"] });
    },
  });

  const canSubmit = f.designation.trim() && f.ctc_annual.trim() && f.joining_date && f.work_location.trim();
  const isDraft = !offer || offer.status === "DRAFT";
  const letterReady = !!offer?.letter_object_key;

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()} style={{ maxWidth: 600, maxHeight: "88vh", overflowY: "auto" }}>
        <div className="spread">
          <h3 style={{ marginBottom: 2 }}>Offer · {app.candidate_name}</h3>
          {offer && <OfferStatus status={offer.status} />}
        </div>
        <p className="muted" style={{ marginTop: 0, fontSize: ".85rem" }}>{app.rrf_code}{offer ? ` · ${offer.offer_code}` : ""}</p>

        {editing ? (
          <>
            <div className="grid-fields">
              <div style={{ gridColumn: "1 / -1" }}><label>Candidate name (as on letter)</label><input value={f.candidate_name} onChange={(e) => upd("candidate_name", e.target.value)} placeholder="Defaults to the applicant's name" /></div>
              <div><label>Designation</label><input value={f.designation} onChange={(e) => upd("designation", e.target.value)} placeholder="e.g. Consultant" /></div>
              <div><label>Monthly Gross</label><input value={f.monthly_gross} onChange={(e) => upd("monthly_gross", e.target.value)} placeholder="e.g. Rs. 1,16,117" /></div>
              <div><label>Total Cost to Company</label><input value={f.ctc_annual} onChange={(e) => upd("ctc_annual", e.target.value)} placeholder="e.g. Rs. 15,00,000/-" /></div>
              <div><label>Base / joining location</label><input value={f.work_location} onChange={(e) => upd("work_location", e.target.value)} placeholder="e.g. Mumbai" /></div>
              <div><label>Joining date</label><input type="date" value={f.joining_date} onChange={(e) => upd("joining_date", e.target.value)} /></div>
              <div><label>Confirm acceptance by</label><input type="date" value={f.valid_until} onChange={(e) => upd("valid_until", e.target.value)} /></div>
            </div>
            {error && <p className="error-text">{error}</p>}
            <div className="row" style={{ justifyContent: "flex-end", marginTop: 16, gap: 8 }}>
              <button className="btn-ghost" onClick={() => (offer ? setEditing(false) : onClose())}>Cancel</button>
              {offer
                ? <button disabled={saveM.isPending || !canSubmit} onClick={() => saveM.mutate()}>{saveM.isPending ? "Saving…" : "Save changes"}</button>
                : <button disabled={createM.isPending || !canSubmit} onClick={() => createM.mutate()}>{createM.isPending ? "Creating…" : "Create draft offer"}</button>}
            </div>
          </>
        ) : offer ? (
          <>
            <div className="card card-pad" style={{ marginTop: 12 }}>
              <Term k="Candidate" v={offer.candidate_name ?? app.candidate_name} />
              <Term k="Designation" v={offer.designation} />
              <Term k="Monthly Gross" v={offer.monthly_gross ?? "—"} />
              <Term k="Total Cost to Company" v={offer.ctc_annual} />
              <Term k="Base location" v={offer.work_location} />
              <Term k="Joining on/before" v={offer.joining_date} />
              <Term k="Confirm acceptance by" v={offer.valid_until ?? "—"} />
            </div>

            <div className="stack" style={{ gap: 12, marginTop: 14 }}>
              <div className="row" style={{ gap: 8, flexWrap: "wrap" }}>
                {isDraft && <button className="btn-sm btn-ghost" onClick={() => setEditing(true)}>Edit terms</button>}
                <button className="btn-sm btn-ghost" disabled={letterM.isPending} onClick={() => letterM.mutate()}>{letterM.isPending ? "Generating…" : letterReady ? "Regenerate letter" : "Generate letter"}</button>
                {(letterUrl || letterReady) && letterUrl && <a href={letterUrl} target="_blank" rel="noreferrer" className="chip">Open letter ↗</a>}
              </div>
              {!letterReady && <p className="muted" style={{ fontSize: ".8rem", margin: 0 }}>Generate the letter before sharing the offer (INV-10).</p>}
              {offer.status === "RELEASED" && <p className="muted" style={{ fontSize: ".8rem", margin: 0, color: "var(--pos)" }}>Shared — the candidate can now see this offer and letter on their portal.</p>}
              <div className="row" style={{ flexWrap: "wrap", gap: 8 }}>
                <button className="btn-sm" disabled={offer.status !== "DRAFT" || !letterReady || trM.isPending} onClick={() => trM.mutate("RELEASE")}>Share offer with candidate</button>
                <button className="btn-sm" disabled={offer.status !== "RELEASED" || trM.isPending} onClick={() => trM.mutate("ACCEPT")}>Mark accepted</button>
                <button className="btn-sm btn-ghost" disabled={offer.status !== "RELEASED" || trM.isPending} onClick={() => trM.mutate("DECLINE")}>Mark declined</button>
              </div>
            </div>
            {error && <p className="error-text">{error}</p>}
            <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}><button onClick={onClose}>Done</button></div>
          </>
        ) : offerQ.isError ? <p className="error-text" style={{ marginTop: 16 }}>{(offerQ.error as { message?: string }).message ?? "Could not load offer."}</p>
          : showOfferLoader ? <NeuralLoader label="Loading Offer" /> : null}
      </div>
    </div>
  );
}

function Term({ k, v }: { k: string; v: string }) {
  return (
    <div className="spread" style={{ padding: "4px 0", borderBottom: "1px solid var(--line)" }}>
      <span className="muted" style={{ fontSize: ".82rem" }}>{k}</span>
      <span style={{ fontSize: ".85rem", fontWeight: 600 }}>{v}</span>
    </div>
  );
}
