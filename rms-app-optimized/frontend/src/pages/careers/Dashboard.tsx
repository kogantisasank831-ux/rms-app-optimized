import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import { applyToJob, getJob, listJobs, myPortal, respondToOffer, type PortalApplication } from "../../api/endpoints/careers";
import { useAuth } from "../../auth/AuthContext";
import { Ic, Icon, TcgLogo } from "../../components/brand";
import { CareersLoaderMark } from "./CareersLoaderMark";
import { jobCategory, writeJobCache } from "./jobCache";

const MILESTONES = [
  { key: "APPLIED", label: "Applied" },
  { key: "SCREENING", label: "Screening" },
  { key: "SHORTLISTED", label: "Shortlisted" },
  { key: "INTERVIEW", label: "Interviews" },
  { key: "OFFER", label: "Offer" },
  { key: "JOINED", label: "Joined" },
];
function milestoneIndex(stage: string): number {
  if (stage === "APPLIED") return 0;
  if (stage === "SCREENING") return 1;
  if (stage === "SHORTLISTED") return 2;
  if (stage.startsWith("INTERVIEW")) return 3;
  if (stage === "OFFER" || stage === "OFFER_ACCEPTED") return 4;
  if (stage === "JOINED") return 5;
  return 0;
}
const ROUND_LABEL: Record<string, string> = { R1_TECH: "Technical Round 1", R2_TECH: "Technical Round 2", MANAGEMENT: "Management Round" };
function fmtDT(iso: string | null): string {
  if (!iso) return "TBD";
  return new Date(iso).toLocaleString(undefined, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}
function initials(name?: string): string {
  return (name ?? "").split(" ").filter(Boolean).slice(0, 2).map((w) => w[0]).join("").toUpperCase() || "?";
}

const LOADER_MESSAGES = [
  "Preparing your career experience",
  "Discovering teams and opportunities",
  "Connecting talent with possibility",
  "Almost ready",
];
const MIN_DURATION = 450;
const MAX_DURATION = 5000;
const EXIT_DURATION = 580;

export default function Dashboard() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [msg, setMsg] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const [cat, setCat] = useState("All");
  const [query, setQuery] = useState("");

  const portalQ = useQuery({ queryKey: ["portal"], queryFn: myPortal });
  const jobsQ = useQuery({ queryKey: ["careers-jobs"], queryFn: listJobs });
  const apps = useMemo(() => portalQ.data?.applications ?? [], [portalQ.data?.applications]);
  const appliedIds = useMemo(() => new Set(apps.map((a) => a.rrf_id)), [apps]);
  const allOpen = useMemo(() => (jobsQ.data ?? []).filter((j) => !appliedIds.has(j.rrf_id)), [jobsQ.data, appliedIds]);

  // Category chips (derived from the roles that are actually open), each with a live count.
  const categories = useMemo(() => {
    const counts = new Map<string, number>();
    for (const j of allOpen) counts.set(jobCategory(j), (counts.get(jobCategory(j)) ?? 0) + 1);
    const ordered = [...counts.entries()].sort((a, b) => b[1] - a[1]);
    return [["All", allOpen.length] as [string, number], ...ordered];
  }, [allOpen]);
  const openJobs = useMemo(() => {
    const base = cat === "All" ? allOpen : allOpen.filter((j) => jobCategory(j) === cat);
    const q = query.trim().toLowerCase();
    if (!q) return base;
    return base.filter((j) => `${j.title} ${j.tags.join(" ")} ${j.department ?? ""}`.toLowerCase().includes(q));
  }, [allOpen, cat, query]);

  // Warm a small first screen of role details during idle time. Prefetching every opening
  // at once can create a large request burst on slower devices and networks.
  useEffect(() => {
    const run = () => {
      for (const j of allOpen.slice(0, 8)) {
        void qc.prefetchQuery({
          queryKey: ["careers-job", j.job_code],
          queryFn: () => getJob(j.job_code).then((d) => { writeJobCache(j.job_code, d); return d; }),
          staleTime: 5 * 60_000,
        });
      }
    };
    const w = window as Window & {
      requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
      cancelIdleCallback?: (id: number) => void;
    };
    if (w.requestIdleCallback) {
      const id = w.requestIdleCallback(run, { timeout: 1500 });
      return () => w.cancelIdleCallback?.(id);
    }
    const timer = setTimeout(run, 250);
    return () => clearTimeout(timer);
  }, [allOpen, qc]);

  const applyM = useMutation({
    mutationFn: (rrfId: string) => applyToJob(rrfId),
    onSuccess: () => { setErr(null); setMsg("Application submitted — we'll keep you posted here."); qc.invalidateQueries({ queryKey: ["portal"] }); },
    onError: (e) => setErr((e as { message?: string }).message ?? "Could not submit application."),
  });

  // Auto-apply when arriving from a role. Track the actual requisition id rather than a
  // one-time boolean, so a second role can be applied to without remounting the dashboard.
  const applyId = params.get("apply");
  const handledApplyId = useRef<string | null>(null);
  useEffect(() => {
    if (!applyId || portalQ.isLoading || handledApplyId.current === applyId) return;
    handledApplyId.current = applyId;

    const nextParams = new URLSearchParams(params);
    nextParams.delete("apply");
    setParams(nextParams, { replace: true });

    if (appliedIds.has(applyId)) {
      setErr(null);
      setMsg("You have already applied to this role.");
      return;
    }
    applyM.mutate(applyId);
  }, [applyId, appliedIds, applyM, params, portalQ.isLoading, setParams]);

  /* ---- branded loader: hold until data settles (min duration), then reveal ---- */
  const dataReady = !portalQ.isLoading && !jobsQ.isLoading;
  const [skipLoader] = useState(() => portalQ.data !== undefined && jobsQ.data !== undefined);
  const [minElapsed, setMinElapsed] = useState(skipLoader);
  const [forced, setForced] = useState(false);
  const [leaving, setLeaving] = useState(false);
  const [hidden, setHidden] = useState(skipLoader);
  const [msgIndex, setMsgIndex] = useState(0);
  const [swap, setSwap] = useState(false);

  useEffect(() => {
    if (skipLoader) return;
    let swapTimer: ReturnType<typeof setTimeout> | null = null;
    const t1 = setTimeout(() => setMinElapsed(true), MIN_DURATION);
    const t2 = setTimeout(() => setForced(true), MAX_DURATION);
    const rotation = setInterval(() => {
      setSwap(true);
      if (swapTimer) clearTimeout(swapTimer);
      swapTimer = setTimeout(() => { setMsgIndex((i) => (i + 1) % LOADER_MESSAGES.length); setSwap(false); }, 200);
    }, 850);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      clearInterval(rotation);
      if (swapTimer) clearTimeout(swapTimer);
    };
  }, [skipLoader]);

  useEffect(() => {
    if (leaving) return;
    if (forced || (minElapsed && dataReady)) {
      setLeaving(true);
      const t = setTimeout(() => setHidden(true), EXIT_DURATION + 40);
      return () => clearTimeout(t);
    }
  }, [forced, minElapsed, dataReady, leaving]);

  const openJob = (jobCode: string) => navigate(`/careers/jobs/${encodeURIComponent(jobCode)}`);

  return (
    <div className="cdash">
      {!hidden && (
        <div className={`loader${leaving ? " is-leaving" : ""}`} role="status" aria-live="polite">
          <div className="loader-inner">
            <CareersLoaderMark />
            <div className="loader-wordmark">tcg<span>digital</span></div>
            <h1 className="loader-title">Find work that moves ideas forward</h1>
            <p className={`loader-message${swap ? " swap" : ""}`}>{LOADER_MESSAGES[msgIndex]}</p>
            <div className="loader-progress" aria-hidden="true" />
          </div>
        </div>
      )}

      <div className={`app${leaving || hidden ? " is-ready" : ""}`} aria-hidden={leaving || hidden ? undefined : true}>
        <header className="header">
          <a className="brand" href="/careers" onClick={(e) => { e.preventDefault(); navigate("/careers"); }} aria-label="TCG Digital Careers home">
            <TcgLogo />
            <span className="careers-badge">Careers</span>
          </a>

          <label className="header-search" aria-label="Search open roles">
            <Icon path={Ic.search} size={16} />
            <input type="search" placeholder="Search roles, teams or skills…" value={query} onChange={(e) => setQuery(e.target.value)} />
          </label>

          <div className="header-actions">
            <div className="profile">
              <div className="avatar">
                {user?.photo_icon_url ? <img src={user.photo_icon_url} alt="" /> : initials(user?.full_name)}
              </div>
              <div className="profile-copy">
                <strong>{user?.full_name}</strong>
                <span>Candidate</span>
              </div>
            </div>
            <button className="signout" onClick={() => { logout(); navigate("/careers"); }}>
              <svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round">
                <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" /><path d="M16 17l5-5-5-5" /><path d="M21 12H9" />
              </svg>
              <span className="label">Sign out</span>
            </button>
          </div>
        </header>

        <main className="page">
          <section className="welcome">
            <div>
              <h1>Welcome back, <span>{user?.full_name?.split(" ")[0] ?? "there"}</span></h1>
              <p>Track your applications, interviews and offers — all in one place.</p>
            </div>
          </section>

          {msg && <div className="banner ok">{msg}</div>}
          {err && <div className="banner err">{err}</div>}

          {/* Applications */}
          <section className="application-section">
            <div className="section-heading">
              <h2>Your applications</h2>
              {apps.length > 0 && <span>· {apps.length}</span>}
            </div>
            {portalQ.isLoading ? (
              <div className="application-card" style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 10 }}>
                <svg width={18} height={18} viewBox="0 0 24 24" fill="none" stroke="var(--navy)" strokeWidth={2.4} strokeLinecap="round" style={{ animation: "rms-spin .8s linear infinite" }} aria-hidden="true">
                  <path d="M12 3a9 9 0 1 0 9 9" />
                </svg>
                <p style={{ margin: 0, color: "var(--muted)" }}>Fetching your applications…</p>
              </div>
            ) : apps.length === 0 ? (
              <div className="application-card" style={{ textAlign: "center" }}>
                <p style={{ margin: 0, color: "var(--muted)" }}>You haven't applied to any roles yet. Browse open positions below.</p>
              </div>
            ) : apps.map((a) => <ApplicationCard key={a.application_id} a={a} />)}
          </section>

          {/* Open roles */}
          <section className="roles-section">
            <div className="roles-head">
              <div className="roles-title">
                <h2>Open roles · <span>{openJobs.length}</span></h2>
                <p>Opportunities selected for your experience and interests.</p>
              </div>
              <label className="role-search" aria-label="Search open roles">
                <Icon path={Ic.search} size={16} />
                <input type="search" placeholder="Search open roles…" value={query} onChange={(e) => setQuery(e.target.value)} />
              </label>
            </div>

            {allOpen.length > 0 && (
              <div className="filters">
                {categories.map(([label, count]) => (
                  <button key={label} className={`filter${cat === label ? " active" : ""}`} onClick={() => setCat(label)}>
                    {label} <span>{count}</span>
                  </button>
                ))}
              </div>
            )}

            {allOpen.length === 0 ? (
              <div className="empty">You've applied to everything that's open — nice. Check back soon for new roles.</div>
            ) : openJobs.length === 0 ? (
              <div className="empty">No roles match your current search.</div>
            ) : (
              <div className="jobs">
                {openJobs.map((j) => (
                  <article
                    key={j.rrf_id}
                    className="job-card"
                    role="link"
                    tabIndex={0}
                    onClick={() => openJob(j.job_code)}
                    onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openJob(j.job_code); } }}
                  >
                    <div className="job-top">
                      <span className="category">{jobCategory(j)}</span>
                      <span className="job-id">{j.job_code}</span>
                    </div>
                    <h3>{j.title}</h3>
                    <p>{j.blurb ?? "Join our team and help build what comes next."}</p>
                    <div className="meta-row">
                      <span><Icon path={Ic.pin} size={13} />{j.location}{j.wfh_allowed ? " · Hybrid" : ""}</span>
                      <span><Icon path={Ic.brief} size={13} />{j.min_experience_years}+ yrs</span>
                    </div>
                    {j.tags.length > 0 && <div className="tags">{j.tags.slice(0, 3).map((t) => <span key={t} className="tag">{t}</span>)}</div>}
                    <div className="job-footer">
                      <span className="openings">{j.openings} opening{j.openings === 1 ? "" : "s"}</span>
                      <button className="apply" disabled={applyM.isPending} onClick={(e) => { e.stopPropagation(); applyM.mutate(j.rrf_id); }}>
                        {applyM.isPending && applyM.variables === j.rrf_id ? "Applying…" : <>Apply now <Icon path={Ic.arrow} size={14} sw={2.2} /></>}
                      </button>
                    </div>
                  </article>
                ))}
              </div>
            )}
          </section>
        </main>

        <footer className="footer">
          <div>© 2026 TCG Digital Careers</div>
          <div>Privacy · Accessibility · Candidate support</div>
        </footer>
      </div>
    </div>
  );
}

function statusPill(status: string): { cls: string; label: string } {
  const map: Record<string, { cls: string; label: string }> = {
    ACTIVE: { cls: "", label: "In progress" },
    ON_HOLD: { cls: "hold", label: "On hold" },
    REJECTED: { cls: "neg", label: "Not selected" },
    WITHDRAWN: { cls: "hold", label: "Withdrawn" },
    HIRED: { cls: "", label: "Hired 🎉" },
  };
  return map[status] ?? { cls: "hold", label: status };
}

function ApplicationCard({ a }: { a: PortalApplication }) {
  const qc = useQueryClient();
  // Only reveal the OFFER milestone once HR has generated and shared the letter
  // (offer.status RELEASED/ACCEPTED/DECLINED). Until then, hold at Interviews even
  // if the pipeline stage is internally OFFER.
  const offerShared = !!a.offer && (a.offer.status === "RELEASED" || a.offer.status === "ACCEPTED" || a.offer.status === "DECLINED");
  let cur = milestoneIndex(a.current_stage);
  if (cur === 4 && !offerShared) cur = 3;
  const rejected = a.status === "REJECTED" || a.status === "WITHDRAWN";
  const pill = statusPill(a.status);

  const [respErr, setRespErr] = useState<string | null>(null);
  const [reason, setReason] = useState("");
  const respondM = useMutation({
    mutationFn: (action: "ACCEPT" | "DECLINE") => respondToOffer(a.offer!.offer_id, action, reason.trim() || undefined),
    onSuccess: () => { setRespErr(null); setReason(""); qc.invalidateQueries({ queryKey: ["portal"] }); },
    onError: (e) => setRespErr((e as { message?: string }).message ?? "Could not submit your response."),
  });

  return (
    <article className="application-card">
      <div className="application-top">
        <div>
          <h3>{a.title}</h3>
          <p>{a.job_code} · {a.location}</p>
        </div>
        <span className={`status-pill ${pill.cls}`}>{pill.label}</span>
      </div>

      {!rejected && (
        <>
          <div className="progress-track" aria-label="Application progress">
            {MILESTONES.map((m, i) => (
              <span key={m.key} className={`step-bar${i < cur ? " done" : ""}${i === cur ? " active" : ""}`} />
            ))}
          </div>
          <div className="progress-labels">
            {MILESTONES.map((m, i) => (
              <span key={m.key} className={i < cur ? "done" : i === cur ? "active" : ""}>{m.label}</span>
            ))}
          </div>
        </>
      )}

      {/* Interviews */}
      {a.interviews.map((iv) => (
        <div key={iv.interview_id} className="cd-box iv" style={{ marginTop: 16 }}>
          <div className="rowline">
            <div>
              <b style={{ fontSize: ".9rem" }}>{ROUND_LABEL[iv.round] ?? iv.round} scheduled</b>
              <div style={{ fontSize: ".8rem", color: "var(--ink-soft)", marginTop: 2 }}>
                {fmtDT(iv.scheduled_start)} · {iv.mode === "IN_PERSON" ? (iv.location || "In person") : iv.mode === "TELEPHONIC" ? "Phone" : "Video call"}
              </div>
            </div>
            {iv.join_link && (
              <a className="apply" href={iv.join_link} target="_blank" rel="noreferrer" style={{ textDecoration: "none" }}>
                <Icon path={Ic.video} size={14} /> Join call
              </a>
            )}
          </div>
        </div>
      ))}

      {/* Offer */}
      {a.offer && (a.offer.status === "RELEASED" || a.offer.status === "ACCEPTED" || a.offer.status === "DECLINED") && (
        <div className="cd-box offer" style={{ marginTop: 16 }}>
          <div className="rowline">
            <div>
              <b style={{ fontSize: ".9rem", color: a.offer.status === "DECLINED" ? "var(--ink-soft)" : "var(--pos)" }}>
                {a.offer.status === "ACCEPTED" ? "Offer accepted 🎉" : a.offer.status === "DECLINED" ? "Offer declined" : "You've received an offer!"}
              </b>
              <div style={{ fontSize: ".8rem", color: "var(--ink-soft)", marginTop: 2 }}>
                {a.offer.designation} · {a.offer.ctc_annual} · joining {a.offer.joining_date ?? "TBD"} · {a.offer.work_location}
              </div>
            </div>
            {a.offer.letter_url && (
              <a className="offer-letter-btn" href={a.offer.letter_url} target="_blank" rel="noreferrer"
                style={{ display: "inline-flex", alignItems: "center", gap: 7, padding: "9px 16px", borderRadius: 999, background: "var(--pos-soft)", color: "var(--pos)", border: "1px solid color-mix(in srgb, var(--pos) 32%, transparent)", fontSize: ".78rem", fontWeight: 700, textDecoration: "none", whiteSpace: "nowrap" }}>
                <Icon path={Ic.award} size={14} /> View offer letter
              </a>
            )}
          </div>

          {a.offer.status === "RELEASED" && (
            <>
              <textarea
                value={reason}
                onChange={(e) => setReason(e.target.value)}
                placeholder="Add a comment…"
                rows={2}
                style={{ width: "100%", marginTop: 12, padding: "10px 12px", borderRadius: 12, border: "1px solid var(--line)", background: "#f8fafc", color: "var(--ink)", font: "inherit", fontSize: ".82rem", resize: "vertical" }}
              />
              <div style={{ display: "flex", gap: 10, marginTop: 10, justifyContent: "flex-end" }}>
                <button className="apply" disabled={respondM.isPending} onClick={() => respondM.mutate("ACCEPT")} style={{ background: "var(--pos)", marginLeft: 0 }}>
                  <Icon path={Ic.check} size={14} sw={2.4} /> {respondM.isPending && respondM.variables === "ACCEPT" ? "Accepting…" : "Accept offer"}
                </button>
                <button className="apply" disabled={respondM.isPending}
                  onClick={() => {
                    if (!reason.trim()) { setRespErr("Please add a reason before declining the offer."); return; }
                    if (window.confirm("Decline this offer? This cannot be undone.")) respondM.mutate("DECLINE");
                  }}
                  style={{ background: "transparent", color: "var(--neg)", border: "1px solid var(--neg)", marginLeft: 0 }}>
                  <Icon path={Ic.x} size={14} sw={2.4} /> {respondM.isPending && respondM.variables === "DECLINE" ? "Declining…" : "Decline"}
                </button>
              </div>
              {respErr && <div style={{ fontSize: ".78rem", color: "var(--neg)", marginTop: 8 }}>{respErr}</div>}
            </>
          )}
        </div>
      )}
    </article>
  );
}
