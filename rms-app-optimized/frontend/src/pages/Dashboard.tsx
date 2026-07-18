import { useQuery } from "@tanstack/react-query";
import { type KeyboardEvent as ReactKeyboardEvent, useCallback, useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useNavigate } from "react-router-dom";

import { getInsights, getMetrics, type Metrics } from "../api/endpoints/dashboard";
import { useAuth } from "../auth/AuthContext";
import { TcgLoader } from "../components/TcgLoader";
import { usePrefetchWorkspace } from "../store/prefetchWorkspace";

const STAGE_ORDER = [
  "APPLIED", "SCREENING", "SHORTLISTED", "INTERVIEW_R1", "INTERVIEW_R2",
  "INTERVIEW_MGMT", "OFFER", "OFFER_ACCEPTED", "JOINED",
];
const STAGE_LABEL: Record<string, string> = {
  APPLIED: "Applied", SCREENING: "Screening", SHORTLISTED: "Shortlisted",
  INTERVIEW_R1: "Interview 1", INTERVIEW_R2: "Interview 2", INTERVIEW_MGMT: "Management",
  OFFER: "Offer", OFFER_ACCEPTED: "Accepted", JOINED: "Joined",
};

function num(m: Metrics, k: string): number | null {
  const v = m[k]?.value;
  return typeof v === "number" ? v : v == null ? null : Number(v) || 0;
}
function greeting(): string {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}
function fmtTime(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return isNaN(d.getTime()) ? "" : d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
}

/* tiny inline icon set */
const P: Record<string, string> = {
  bars: "M4 20V10M10 20V4M16 20v-8M22 20H2",
  check: "M4 12l2 5h12l2-5M9 3h6l1 4H8z",
  clock: "M12 12V7M12 12l4 2M12 21a9 9 0 100-18 9 9 0 000 18z",
  gift: "M20 12v9H4v-9M2 7h20v5H2zM12 22V7M12 7S9 3 6.5 3 4 6 6 7h6zM12 7s3-4 5.5-4S20 6 18 7h-6z",
  users: "M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2M9 11a4 4 0 100-8 4 4 0 000 8zM23 21v-2a4 4 0 00-3-3.9M16 3.1a4 4 0 010 7.8",
  briefcase: "M20 7H4a2 2 0 00-2 2v10a2 2 0 002 2h16a2 2 0 002-2V9a2 2 0 00-2-2zM16 7V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v2",
  cal: "M3 4h18v17H3zM8 2v4M16 2v4M3 10h18",
  target: "M12 21a9 9 0 100-18 9 9 0 000 18zM12 16a4 4 0 100-8 4 4 0 000 8zM12 12h.01",
  spark: "M12 3l1.9 5.7L20 11l-6.1 1.9L12 19l-1.9-6.1L4 11l6.1-1.9z",
  doc: "M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8zM14 2v6h6",
  arrow: "M9 6l6 6-6 6",
  arrUp: "M6 18L18 6M11 6h7v7",
  arrDn: "M6 6l12 12M11 18h7v-7",
};
function Svg({ d, s = 18 }: { d: string; s?: number }) {
  return <svg viewBox="0 0 24 24" width={s} height={s} fill="none" stroke="currentColor" strokeWidth="1.9" strokeLinecap="round" strokeLinejoin="round"><path d={d} /></svg>;
}

/**
 * Branded welcome loader. Cycles reassurance while the metrics query is in flight, then snaps
 * to "Done!" and fades out the instant data is ready — no artificial delay. Pure CSS, no assets.
 */
const CC_LINES = ["Gearing up for your best experience", "Sit back — we're pouring the coffee ☕", "Almost there"];
function CommandCenterLoader({ ready, onDismiss }: { ready: boolean; onDismiss: () => void }) {
  const [i, setI] = useState(0);
  const [done, setDone] = useState(false);
  const [leaving, setLeaving] = useState(false);

  useEffect(() => {
    if (ready) return;
    const t = setInterval(() => setI((n) => Math.min(n + 1, CC_LINES.length - 1)), 1300);
    return () => clearInterval(t);
  }, [ready]);

  useEffect(() => {
    if (!ready) return;
    setDone(true);
    const a = setTimeout(() => setLeaving(true), 700);   // hold "Done!" briefly
    const b = setTimeout(onDismiss, 1120);               // then reveal the dashboard
    return () => { clearTimeout(a); clearTimeout(b); };
  }, [ready, onDismiss]);

  // Portal to <body> so the fixed full-screen overlay sits at the exact same viewport
  // position as the auth-boot BrandLoader (and isn't offset by the route-view transform).
  // This makes the boot → command-center loader hand-off look like one continuous animation.
  return createPortal(
    <div className={`cc-loader${leaving ? " leaving" : ""}`} role="status" aria-live="polite">
      <TcgLoader />
      <div className="cc-wordmark">tcg<span>digital</span></div>
      <div className="cc-welcome">Welcome to DataAlchemists ATS</div>
      <div className="cc-line" key={done ? "done" : i} aria-hidden="true">{done ? "Done! ✨" : CC_LINES[i]}</div>
      <div className={`cc-bar${done ? " done" : ""}`}><i /></div>
      <span className="sr-only">Application is loading</span>
    </div>,
    document.body,
  );
}

interface Trend { spark: number[]; delta: number | null; unit: "abs" | "pct" | "days"; up_is_good: boolean; }

/** Small trend line (with soft area fill) drawn from a real 30-day series. */
function Spark({ data, color }: { data: number[]; color: string }) {
  if (!data || data.length < 2) return null;
  const w = 120, h = 40, pad = 3;
  const min = Math.min(...data), max = Math.max(...data);
  const rng = max - min || 1;
  const pts = data.map((v, i) => {
    const x = pad + (i / (data.length - 1)) * (w - pad * 2);
    const y = pad + (1 - (v - min) / rng) * (h - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  const line = `M${pts.join(" L")}`;
  const area = `${line} L${w - pad},${h} L${pad},${h} Z`;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} preserveAspectRatio="none" style={{ color }}>
      <path d={area} fill="currentColor" fillOpacity={0.12} stroke="none" />
      <path d={line} fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** Formats a real period delta into {text, good} for the green/red pill. */
function fmtDelta(t?: Trend): { text: string; good: boolean } | null {
  if (!t || t.delta == null || t.delta === 0) return null;
  const d = t.delta;
  if (t.unit === "days") {
    // time-to-hire: a drop is "faster" (good)
    return d < 0 ? { text: `${Math.abs(d).toFixed(1)}d faster`, good: true } : { text: `${d.toFixed(1)}d slower`, good: false };
  }
  const good = d > 0 === t.up_is_good;
  const text = t.unit === "pct" ? `${Math.abs(d).toFixed(1)}%` : `${d > 0 ? "+" : ""}${d}`;
  return { text, good };
}

export default function Dashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const role = user?.role ?? "";
  const firstName = user?.full_name?.split(/\s+/)[0] ?? "there";
  const canGo = (roles: string[]) => roles.includes(role);

  // Two independent queries: the core renders immediately; AI insights stream in.
  const mq = useQuery({ queryKey: ["metrics"], queryFn: getMetrics });
  const iq = useQuery({ queryKey: ["insights"], queryFn: getInsights, staleTime: 60_000 });

  // Once the Command Center core is loaded, warm the other pages' caches in the background
  // (at browser idle) so navigating to them feels instant.
  usePrefetchWorkspace(mq.isSuccess, role);

  const m = mq.data ?? {};
  const ins = iq.data ?? {};

  // Branded welcome loader stays until data is ready + a brief "Done!", then the dashboard reveals.
  // Only on a cold load — if metrics are already cached (revisiting), skip straight to the dashboard.
  const [loaderGone, setLoaderGone] = useState(() => mq.data !== undefined);
  const dismissLoader = useCallback(() => setLoaderGone(true), []);

  const stages = (m.pipeline_by_stage?.value ?? {}) as Record<string, number>;
  const activeTotal = Object.values(stages).reduce((a, b) => a + (Number(b) || 0), 0);
  const maxStage = Math.max(1, ...Object.values(stages).map((x) => Number(x) || 0));
  const orderedStages = STAGE_ORDER.filter((s) => s in stages);

  // cumulative hiring funnel (Applied → Joined) with step conversion
  const hf = (m.hiring_funnel?.value ?? {}) as Record<string, number>;
  const funnelRows = [
    { key: "applied", label: "Applied", tip: "Total candidates who applied across all requisitions." },
    { key: "screened", label: "Screened", tip: "Candidates who ever reached Screening or beyond — cumulative, and still counted even if since advanced or rejected." },
    { key: "interviewed", label: "Interviewed", tip: "Candidates who ever reached an interview round or beyond — cumulative across all statuses." },
    { key: "offered", label: "Offered", tip: "Candidates who ever reached the Offer stage or beyond — cumulative across all statuses." },
    { key: "joined", label: "Joined", tip: "Candidates who joined." },
  ].map((r, i, arr) => {
    const count = Number(hf[r.key] ?? 0);
    const prev = i > 0 ? Number(hf[arr[i - 1].key] ?? 0) : null;
    const conv = prev && prev > 0 ? Math.round((count / prev) * 100) : null;
    return { ...r, count, conv };
  });
  const funnelTop = Math.max(1, Number(hf.applied ?? 0));
  const overallConv = funnelTop > 1 ? (Number(hf.joined ?? 0) / funnelTop) * 100 : 0;
  const schedule = (m.todays_schedule?.value ?? []) as { candidate: string; role: string; round: string; at: string | null; interview_id?: string }[];
  const risks = (m.requisitions_at_risk?.value ?? []) as { role: string; job_code: string; days_open: number | null; issue: string; risk: string }[];

  const RRF = ["ADMIN", "HR", "HIRING_MANAGER", "BU_HEAD"];
  const PIPE = ["ADMIN", "HR", "HIRING_MANAGER"];

  // ---- alert tiles (only render metrics that exist for this role) ----
  const alerts = ([
    { key: "pending_approvals", label: "Approvals Pending", sub: "Requisitions waiting for approval", icon: P.doc, tone: "amber", to: canGo(RRF) ? "/rrfs?status=PENDING_APPROVAL" : undefined },
    { key: "feedback_overdue", label: "Feedback Overdue", sub: "Interview feedback past due", icon: P.clock, tone: "red", to: "/interviews" },
    { key: "offers_expiring", label: "Offers Expiring", sub: "Expiring in the next 7 days", icon: P.gift, tone: "gold", to: canGo(PIPE) ? "/offers" : undefined },
    { key: "candidates_stalled", label: "Candidates Stalled", sub: "No activity in 7+ days", icon: P.users, tone: "violet", to: canGo(PIPE) ? "/pipeline" : undefined },
  ] as const).filter((a) => num(m, a.key) != null);

  // ---- headline KPI cards (icon · title · Last 30 days · value · delta · sub · sparkline) ----
  const trends = (m.kpi_trends?.value ?? {}) as Record<string, Trend>;
  const link = (to: string, roles: string[]) => (canGo(roles) ? to : undefined);
  const openRrfs = num(m, "open_rrfs");
  const pending = num(m, "pending_approvals") ?? 0;
  const tth = num(m, "avg_time_to_hire_days");
  const accRate = num(m, "offer_acceptance_rate");
  const accepted = num(m, "offers_accepted") ?? 0;
  const released = num(m, "offers_released") ?? 0;
  const filled = num(m, "positions_filled") ?? 0;

  type Card = { key: string; title: string; icon: string; value: string; unit?: string; sub: string; to?: string; color: string; trend?: Trend };
  const cards: Card[] = [];
  if (openRrfs != null)
    cards.push({ key: "req", title: "Active Requisitions", icon: P.briefcase, value: String(openRrfs), sub: pending > 0 ? `${pending} pending approval` : `${openRrfs} open now`, to: link("/rrfs?status=APPROVED", RRF), color: "var(--navy)", trend: trends.open_rrfs });
  if (m.pipeline_by_stage)
    cards.push({ key: "pipe", title: "Candidates in Pipeline", icon: P.users, value: String(activeTotal), sub: "across your roles", to: link("/pipeline", PIPE), color: "var(--accent-2)", trend: trends.pipeline });
  if (tth != null)
    cards.push({ key: "tth", title: "Avg. Time to Hire", icon: P.clock, value: String(Math.round(tth)), unit: "d", sub: `${filled} hired to date`, to: link("/pipeline", PIPE), color: "var(--pos)", trend: trends.avg_time_to_hire_days });
  if (accRate != null)
    cards.push({ key: "acc", title: "Offer Acceptance", icon: P.check, value: String(Math.round(accRate * 100)), unit: "%", sub: released > 0 ? `${accepted} of ${released} offers` : "no offers yet", to: link("/offers", PIPE), color: "var(--pos)" });

  // ---- AI assistant tiles ----
  const aiTiles: { key: string; lab: string; icon: string; to?: string; tip: string }[] = [
    { key: "resumes_screened", lab: "Resumes Screened", icon: P.doc, to: "/pipeline?view=table&stage=SCREENING", tip: "Resumes the AI screening agent has successfully processed (agent runs). Click to see candidates currently in Screening." },
    { key: "candidate_matches", lab: "Candidate Matches", icon: P.users, to: "/pipeline?view=table&sort=score", tip: "Shortlist matches produced by the AI matching agent. Click to see candidates ranked by AI score." },
    { key: "jd_drafts", lab: "JD Drafts Created", icon: P.spark, to: "/rrfs", tip: "Job descriptions drafted by the AI JD agent. Click to view requisitions." },
    { key: "feedback_summaries", lab: "Feedback Summaries", icon: P.check, to: "/interviews", tip: "Interview feedback consolidated by the AI summarization agent. Click to view interviews." },
    { key: "human_review_pending", lab: "Human Review Pending", icon: P.clock, to: "/pipeline?view=table&stage=SCREENING", tip: "AI-screened candidates currently in Screening, awaiting a human shortlist decision. Click to review them." },
    { key: "hours_saved", lab: "Hours Saved (est.)", icon: P.clock, tip: "Estimated time saved, based on completed AI actions × average minutes per equivalent manual task." },
  ];
  const hasInsights = Object.keys(ins).length > 0;

  const canCreate = canGo(["ADMIN", "HR", "HIRING_MANAGER"]);
  const pendingTotal = alerts.reduce((a, x) => a + (num(m, x.key) ?? 0), 0);
  const breakdown = alerts.filter((a) => (num(m, a.key) ?? 0) > 0).map((a) => `${num(m, a.key)} ${a.label.toLowerCase()}`).join(" · ");

  const ready = mq.isSuccess || mq.isError;

  return (
    <div className="page dash">
      {!loaderGone ? (
        <CommandCenterLoader ready={ready} onDismiss={dismissLoader} />
      ) : mq.isError ? (
        <>
          <div className="page-head"><div><h1>Dashboard</h1></div></div>
          <div className="card card-pad error-text">Couldn't load dashboard metrics. Check the backend is running.</div>
        </>
      ) : (
        <div className="cc-reveal">
          {/* hero — greeting + what needs your action + AI strip */}
          <section className="dash-hero hero-sheen anim">
            <div className="dh-main">
              <div className="dh-eyebrow"><span className="dh-dot pulse-dot" /> {greeting()}, {firstName}</div>
              <div className="dh-count-row">
                <span className="dh-count tnum">{pendingTotal}</span>
                <span className="dh-count-lab">{pendingTotal === 1 ? "item needs your action" : "items need your action"}</span>
              </div>
              <p className="dh-break">{breakdown || "You're all caught up — nothing pending right now."}</p>
            </div>
            <div className="dh-actions">
              {canCreate && <Link className="dh-btn primary" to="/rrfs/new">+ Create Requisition</Link>}
              {canGo(PIPE) && <Link className="dh-btn glass" to="/pipeline">Review Queue</Link>}
              {canGo(PIPE) && <Link className="dh-btn glass" to="/offers">Approve Offers</Link>}
            </div>
            {hasInsights && (
              <div className="dh-ai">
                <Svg d={P.spark} s={16} />
                <p><b>AI has run {num(ins, "resumes_screened") ?? 0} resume screens</b> — {num(ins, "human_review_pending") ?? 0} awaiting your review. Every recommendation is human-approved.</p>
                {canGo(PIPE) && <Link className="dh-ai-cta" to="/pipeline">Review now <Svg d={P.arrow} s={13} /></Link>}
              </div>
            )}
          </section>
          {/* alert tiles */}
          {alerts.length > 0 && (
            <section className="alert-tiles">
              {alerts.map((a) => {
                const count = num(m, a.key) ?? 0;
                const inner = (
                  <>
                    <div className="at-top">
                      <span className={`at-ic ${a.tone}`}><Svg d={a.icon} s={16} /></span>
                      <span className="at-lab">{a.label}</span>
                    </div>
                    <div className={`at-val tnum${count > 0 ? ` ${a.tone}` : ""}`}>{count}</div>
                    <div className="at-sub">{a.sub}</div>
                  </>
                );
                return a.to
                  ? <Link key={a.key} to={a.to} className="alert-tile link">{inner}</Link>
                  : <div key={a.key} className="alert-tile">{inner}</div>;
              })}
            </section>
          )}

          {/* headline KPI cards */}
          <section className="kpis">
            {cards.map((c) => {
              const delta = fmtDelta(c.trend);
              const inner = (
                <>
                  <div className="sc-top">
                    <span className="sc-ic"><Svg d={c.icon} s={16} /></span>
                    <span className="sc-title">{c.title}</span>
                    <span className="sc-window">Last 30 days</span>
                  </div>
                  <div className="sc-mid">
                    <div className="sc-val tnum">{c.value}{c.unit && <span className="u">{c.unit}</span>}</div>
                    {delta && (
                      <span className={`sc-delta ${delta.good ? "up" : "dn"}`}>
                        {delta.text}<Svg d={delta.good ? P.arrUp : P.arrDn} s={13} />
                      </span>
                    )}
                  </div>
                  <div className="sc-bot">
                    <span className="sc-sub">{c.sub}</span>
                    {c.trend?.spark && <span className="sc-spark"><Spark data={c.trend.spark} color={c.color} /></span>}
                  </div>
                </>
              );
              return c.to
                ? <Link className="stat-card link" key={c.key} to={c.to}>{inner}</Link>
                : <div className="stat-card" key={c.key}>{inner}</div>;
            })}
          </section>

          <section className="grid-2">
            {/* LEFT: pipeline + requisitions at risk */}
            <div className="col">
              {m.pipeline_by_stage && (
                <div className={`card${canGo(PIPE) ? " card-click" : ""}`}
                  {...(canGo(PIPE) ? { role: "link", tabIndex: 0, onClick: () => navigate("/pipeline"), onKeyDown: (e: ReactKeyboardEvent) => { if (e.key === "Enter") navigate("/pipeline"); } } : {})}>
                  <div className="panel-head"><div><h3 className="has-tip" data-tip="Number of candidates currently sitting in each stage. The % is the stage-to-stage conversion: this stage's count as a share of the previous stage's count. Over 100% means more candidates are in this stage than the one before it.">Candidate Pipeline</h3><div className="sub">Where active candidates sit right now</div></div><span className="chip">{activeTotal} active</span></div>
                  <div className="funnel pipe-funnel">
                    {orderedStages.map((s, i) => {
                      const prevStage = i > 0 ? orderedStages[i - 1] : null;
                      const prev = prevStage != null ? Number(stages[prevStage]) : null;
                      const conv = prev && prev > 0 ? Math.round((Number(stages[s]) / prev) * 100) : null;
                      const label = STAGE_LABEL[s] ?? s;
                      const prevLabel = prevStage != null ? (STAGE_LABEL[prevStage] ?? prevStage) : null;
                      return (
                        <div className="frow" key={s}>
                          <span className="fl">{label}</span>
                          <div className="track"><i style={{ width: `${Math.round((Number(stages[s]) / maxStage) * 100)}%` }} /></div>
                          <span className="fc tnum has-tip" data-tip={`${stages[s]} candidate(s) currently in ${label}.`}>{stages[s]}</span>
                          <span className="fconv has-tip" data-tip={conv != null
                            ? `Stage-to-stage conversion: ${stages[s]} in ${label} vs ${prev} in ${prevLabel} = ${conv}%. Over 100% means this stage holds more candidates than the previous one.`
                            : "No previous stage to compare against — this is the first stage."}>{conv != null ? `${conv}%` : ""}</span>
                        </div>
                      );
                    })}
                    {orderedStages.length === 0 && <p className="muted" style={{ padding: "8px 0" }}>No active candidates yet.</p>}
                  </div>
                </div>
              )}

              {m.requisitions_at_risk && (
                <div className="card">
                  <div className="panel-head"><div><h3>Requisitions at Risk</h3><div className="sub">Open roles needing attention</div></div><span className="chip">{risks.length}</span></div>
                  <div style={{ padding: "4px 20px 16px" }}>
                    {risks.length === 0 ? <p className="muted" style={{ padding: "8px 0" }}>No requisitions flagged — nice.</p> : (
                      <table className="mini-table">
                        <thead><tr><th>Role</th><th>Days Open</th><th>Issue</th><th style={{ textAlign: "right" }}>Risk</th></tr></thead>
                        <tbody>
                          {risks.map((r) => (
                            <tr key={r.job_code}>
                              <td><b>{r.role}</b><div className="muted" style={{ fontSize: ".72rem" }}>{r.job_code}</div></td>
                              <td className="tnum">{r.days_open ?? "—"}</td>
                              <td className="muted">{r.issue}</td>
                              <td style={{ textAlign: "right" }}><span className={`risk-tag ${r.risk === "At Risk" ? "hi" : "mid"}`}>{r.risk}</span></td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* RIGHT: hiring funnel + my tasks + today's schedule */}
            <div className="col">
              {m.hiring_funnel && (
                <div className={`card${canGo(PIPE) ? " card-click" : ""}`}
                  {...(canGo(PIPE) ? { role: "link", tabIndex: 0, onClick: () => navigate("/pipeline"), onKeyDown: (e: ReactKeyboardEvent) => { if (e.key === "Enter") navigate("/pipeline"); } } : {})}>
                  <div className="panel-head"><div><h3 className="has-tip" data-tip="Cumulative reach: how many candidates have ever passed through each milestone (any status), across all requisitions. Unlike Candidate Pipeline — which shows where active candidates sit right now — these totals only grow over time.">Hiring Funnel</h3><div className="sub">Cumulative reach across all requisitions</div></div><Link to="/pipeline" className="linkbtn">Details →</Link></div>
                  <div className="hfunnel">
                    {funnelRows.map((f) => (
                      <div className="hf-row" key={f.key}>
                        <div className="hf-top">
                          <span className="hf-lab has-tip" data-tip={f.tip}>{f.label}</span>
                          <span className="hf-nums">
                            <b className="tnum">{f.count}</b>
                          </span>
                        </div>
                        <div className="hf-bar"><i style={{ width: `${Math.max((f.count / funnelTop) * 100, f.count > 0 ? 5 : 0)}%` }} /></div>
                      </div>
                    ))}
                    <div className="hf-foot">
                      <span>Applied → Joined</span>
                      <b className="tnum">{overallConv.toFixed(1)}%</b>
                    </div>
                  </div>
                </div>
              )}

              {m.todays_schedule && (
                <div className={`card dash-fill${schedule.length > 0 ? " card-click" : ""}`}
                  {...(schedule.length > 0 ? { role: "button", tabIndex: 0, onClick: () => setScheduleOpen(true), onKeyDown: (e: ReactKeyboardEvent) => { if (e.key === "Enter") setScheduleOpen(true); } } : {})}>
                  <div className="panel-head">
                    <div>
                      <h3>Today's Schedule</h3>
                      <div className="sub">{schedule.length === 0 ? "No interviews scheduled today" : `${schedule.length} interview${schedule.length === 1 ? "" : "s"} scheduled today`}</div>
                    </div>
                    <Link to="/interviews" className="linkbtn" onClick={(e) => e.stopPropagation()}>View calendar</Link>
                  </div>
                  <div style={{ padding: "4px 12px 14px" }}>
                    {schedule.length === 0 ? <p className="muted" style={{ padding: "8px 8px" }}>Nothing on the calendar for today.</p> : (
                      <>
                        {schedule.slice(0, 2).map((s, i) => (
                          <div key={i} className="sched-row">
                            <span className="sched-time tnum">{fmtTime(s.at)}</span>
                            <div className="sched-body"><b>{s.candidate}</b><div className="muted" style={{ fontSize: ".72rem" }}>{s.role} · {s.round?.replace(/_/g, " ")}</div></div>
                          </div>
                        ))}
                        {schedule.length > 2 && <div className="sched-more">+{schedule.length - 2} more · view all</div>}
                      </>
                    )}
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* AI Hiring Assistant — streams in after the core renders */}
          {(role === "HR" || role === "ADMIN") && (
            <section className="card">
              <div className="panel-head">
                <div><h3>✦ AI Hiring Assistant</h3><div className="sub">Work your agents have done{iq.isLoading ? " · loading…" : ""}</div></div>
                {hasInsights && num(ins, "agent_runs_total") != null && <span className="chip">{num(ins, "agent_runs_total")} runs</span>}
              </div>
              <div className="ai-tiles">
                {aiTiles.map((t) => {
                  const inner = hasInsights ? (
                    <>
                      <span className="ai-ic"><Svg d={t.icon} s={16} /></span>
                      <div className="ai-val tnum">{num(ins, t.key) ?? "—"}</div>
                      <div className="ai-lab">{t.lab}</div>
                      {t.to && <span className="ai-go"><Svg d={P.arrow} s={12} /></span>}
                    </>
                  ) : null;
                  const cls = `ai-tile${!hasInsights ? " skeleton" : ""}${hasInsights && t.to ? " linked" : ""}${hasInsights ? " has-tip" : ""}`;
                  const tip = hasInsights ? t.tip : undefined;
                  return hasInsights && t.to
                    ? <Link key={t.key} to={t.to} className={cls} data-tip={tip}>{inner}</Link>
                    : <div key={t.key} className={cls} data-tip={tip}>{inner}</div>;
                })}
              </div>
            </section>
          )}

          {scheduleOpen && createPortal(
            <div className="modal-overlay sched-overlay" onMouseDown={() => setScheduleOpen(false)}>
              <div className="modal modal-scroll sched-modal" onMouseDown={(e) => e.stopPropagation()} role="dialog" aria-modal="true" aria-label="Today's schedule">
                <div className="sched-modal-head">
                  <div>
                    <h3>Today's Schedule</h3>
                    <div className="sub">{schedule.length} interview{schedule.length === 1 ? "" : "s"} scheduled today</div>
                  </div>
                  <button type="button" className="sched-close" aria-label="Close" onClick={() => setScheduleOpen(false)}>✕</button>
                </div>
                <div className="modal-body">
                  {schedule.map((s, i) => {
                    const row = (
                      <>
                        <span className="sched-time tnum">{fmtTime(s.at)}</span>
                        <div className="sched-body"><b>{s.candidate}</b><div className="muted" style={{ fontSize: ".72rem" }}>{s.role} · {s.round?.replace(/_/g, " ")}</div></div>
                      </>
                    );
                    return s.interview_id
                      ? <Link key={i} to={`/interviews/${s.interview_id}`} className="sched-row link" title="View interview & AI-suggested questions" onClick={() => setScheduleOpen(false)}>{row}</Link>
                      : <div key={i} className="sched-row">{row}</div>;
                  })}
                </div>
              </div>
            </div>,
            document.body,
          )}
        </div>
      )}
    </div>
  );
}
