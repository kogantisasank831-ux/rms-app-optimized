import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Link, useSearchParams } from "react-router-dom";

import {
  type Application, type PipelineStats, type TransitionResult, createApplication, getApplication, getPipelineStats,
  listApplications, screenApplication, transitionApplication,
} from "../../api/endpoints/applications";
import { listCandidates } from "../../api/endpoints/candidates";
import { listRrfs } from "../../api/endpoints/rrfs";
import type { ApiError, Paged } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { CommentModal } from "../../components/CommentModal";
import { NeuralLoader, useDelayedFlag } from "../../components/NeuralLoader";
import { type FeedbackNextMove, QuickFeedbackModal } from "../../components/QuickFeedbackModal";
import { ScheduleInterviewModal } from "../../components/ScheduleInterviewModal";
import { ScreeningAssessment } from "../../components/ScreeningAssessment";

const INTERVIEW_STAGES = ["INTERVIEW_R1", "INTERVIEW_R2", "INTERVIEW_MGMT"];

const STAGES = ["APPLIED", "SCREENING", "SHORTLISTED", "INTERVIEW_R1", "INTERVIEW_R2", "INTERVIEW_MGMT", "OFFER", "OFFER_ACCEPTED", "JOINED"];
const LABEL: Record<string, string> = { APPLIED: "Applied", SCREENING: "Screening", SHORTLISTED: "Shortlisted", INTERVIEW_R1: "Round 1", INTERVIEW_R2: "Round 2", INTERVIEW_MGMT: "Management", OFFER: "Offer", OFFER_ACCEPTED: "Accepted", JOINED: "Joined" };
const PAGE_SIZES = [5, 10, 20];

const FLEX_FROM = ["SHORTLISTED", "INTERVIEW_R1", "INTERVIEW_R2", "INTERVIEW_MGMT"];
const FLEX_TO = ["INTERVIEW_R1", "INTERVIEW_R2", "INTERVIEW_MGMT", "OFFER"];

// Each interview stage ↔ the interview round that must be scheduled to land on it (mirrors backend _STAGE_ROUND).
const STAGE_ROUND: Record<string, string> = { INTERVIEW_R1: "R1_TECH", INTERVIEW_R2: "R2_TECH", INTERVIEW_MGMT: "MANAGEMENT" };
// Single-step forward target when an ADVANCE carries no explicit target (mirrors backend _DEFAULT_NEXT).
const DEFAULT_NEXT: Record<string, string> = {
  APPLIED: "SCREENING", SCREENING: "SHORTLISTED", SHORTLISTED: "INTERVIEW_R1",
  INTERVIEW_R1: "INTERVIEW_R2", INTERVIEW_R2: "INTERVIEW_MGMT", INTERVIEW_MGMT: "OFFER",
};

function legalMove(from: string, to: string): { action: string; target: string; label: string } | null {
  if (from === "APPLIED" && to === "SCREENING") return { action: "ADVANCE", target: to, label: "Advance to Screening" };
  if (from === "SCREENING" && to === "SHORTLISTED") return { action: "ADVANCE", target: to, label: "Advance to Shortlisted" };
  if (from === "OFFER_ACCEPTED" && to === "JOINED") return { action: "MARK_JOINED", target: to, label: "Mark Joined" };
  if (FLEX_FROM.includes(from) && FLEX_TO.includes(to) && STAGES.indexOf(to) > STAGES.indexOf(from)) {
    return { action: "ADVANCE", target: to, label: `Move to ${LABEL[to]}` };
  }
  return null;
}

function initials(name: string): string {
  return name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0]).join("").toUpperCase() || "?";
}
function scoreCls(s: number | null): string {
  if (s == null) return "na";
  return s >= 80 ? "hi" : s >= 60 ? "mid" : "lo";
}
const STATUS_BADGE: Record<string, { label: string; cls: string }> = {
  ACTIVE: { label: "Active", cls: "ok" },
  ON_HOLD: { label: "On hold", cls: "warn" },
  REJECTED: { label: "Rejected", cls: "neg" },
  WITHDRAWN: { label: "Withdrawn", cls: "mut" },
  HIRED: { label: "Hired", cls: "ok" },
};
function relDays(iso?: string): string {
  if (!iso) return "";
  const d = new Date(iso); if (isNaN(d.getTime())) return "";
  const days = Math.floor((Date.now() - d.getTime()) / 86400000);
  return days <= 0 ? "today" : days === 1 ? "1 day" : `${days} days`;
}

function matchesBoardFilters(app: Application, search: string, status: string): boolean {
  if (status && app.status !== status) return false;
  return !search || app.candidate_name.toLocaleLowerCase().includes(search.toLocaleLowerCase());
}

function sortBoardItems(items: Application[], sort: string): Application[] {
  return [...items].sort((a, b) => {
    if (sort === "name") return a.candidate_name.localeCompare(b.candidate_name);
    if (sort === "score") {
      const scoreDiff = (b.ai_screen_score ?? -Infinity) - (a.ai_screen_score ?? -Infinity);
      if (scoreDiff) return scoreDiff;
    }
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
}

type ModalState = { app: Application; action: string; label: string; target?: string } | null;

export default function Kanban() {
  const { user } = useAuth();
  const qc = useQueryClient();
  const canWrite = !!user && ["ADMIN", "HR", "HIRING_MANAGER"].includes(user.role);
  const canScreen = !!user && ["ADMIN", "HR"].includes(user.role);
  const canSchedule = canScreen;
  const canFeedback = canScreen;
  const canMarkJoined = !!user && ["ADMIN", "HR"].includes(user.role);

  const rrfsQ = useQuery({ queryKey: ["rrfs"], queryFn: () => listRrfs({ limit: 100 }) });
  const approved = useMemo(
    () => (rrfsQ.data?.items ?? []).filter((r) => ["APPROVED", "ON_HOLD", "CLOSED"].includes(r.status)),
    [rrfsQ.data?.items],
  );
  const [rrfId, setRrfId] = useState("");
  useEffect(() => {
    if (!approved.some((item) => item.rrf_id === rrfId)) setRrfId(approved[0]?.rrf_id ?? "");
  }, [approved, rrfId]);
  const rrf = approved.find((r) => r.rrf_id === rrfId);
  const canAddCandidate = canWrite && rrf?.status === "APPROVED";

  const statsQ = useQuery({ queryKey: ["pipeline-stats", rrfId], queryFn: () => getPipelineStats(rrfId), enabled: !!rrfId });

  // Deep-link filters: a dashboard tile can arrive with e.g. ?view=table&stage=SCREENING
  // to land pre-filtered on exactly the relevant candidates.
  const [searchParams] = useSearchParams();

  // filters / view state
  const [q, setQ] = useState("");
  const [dq, setDq] = useState("");
  useEffect(() => { const t = setTimeout(() => setDq(q.trim()), 300); return () => clearTimeout(t); }, [q]);
  const [status, setStatus] = useState(() => searchParams.get("status") ?? "");
  const [stage, setStage] = useState(() => searchParams.get("stage") ?? "");
  const [sort, setSort] = useState(() => searchParams.get("sort") ?? "score");
  // A stage deep-link only makes sense in the flat Table view (the board is one column per stage).
  const [showFilters, setShowFilters] = useState(() => !!(searchParams.get("stage") || searchParams.get("status")));
  const [showCustomize, setShowCustomize] = useState(false);
  const [view, setView] = useState<"board" | "table">(() =>
    searchParams.get("view") === "table" || searchParams.get("stage") ? "table" : "board");
  const [density, setDensity] = useState<"comfortable" | "compact">("comfortable");
  const [pageSize, setPageSize] = useState(10);

  const deepLinkKey = searchParams.toString();
  useEffect(() => {
    const nextStatus = searchParams.get("status") ?? "";
    const nextStage = searchParams.get("stage") ?? "";
    setStatus(nextStatus);
    setStage(nextStage);
    setSort(searchParams.get("sort") ?? "score");
    setShowFilters(!!(nextStage || nextStatus));
    setView(searchParams.get("view") === "table" || !!nextStage ? "table" : "board");
  }, [deepLinkKey, searchParams]);

  // shared modal / dnd state
  const [modal, setModal] = useState<ModalState>(null);
  const [adding, setAdding] = useState(false);
  const [assessing, setAssessing] = useState<Application | null>(null);
  // Scheduling can be standalone, or carry a `then` move to auto-complete once the round is booked.
  const [scheduling, setScheduling] = useState<{ app: Application; then?: { action: string; comment: string; target: string } } | null>(null);
  const [feedbackFor, setFeedbackFor] = useState<Application | null>(null);
  // Feedback gate for round-to-round moves: record the current round's feedback, then resume the move.
  const [feedbackGate, setFeedbackGate] = useState<{ app: Application; then: { action: string; comment: string; target: string } } | null>(null);
  const [dragApp, setDragApp] = useState<Application | null>(null);
  const [overStage, setOverStage] = useState<string | null>(null);
  const [dropErr, setDropErr] = useState<string | null>(null);
  const [recentMove, setRecentMove] = useState<{ applicationId: string; stage: string } | null>(null);
  useEffect(() => {
    if (!recentMove) return;
    const timer = window.setTimeout(() => setRecentMove(null), 420);
    return () => window.clearTimeout(timer);
  }, [recentMove]);

  const filters = useMemo(() => ({ dq, status, sort, pageSize, stage }), [dq, status, sort, pageSize, stage]);

  const refetchAll = () => {
    qc.invalidateQueries({ queryKey: ["apps", rrfId] });
    qc.invalidateQueries({ queryKey: ["pipeline-stats", rrfId] });
  };

  const refreshAffectedQueries = (fromStage: string, toStage: string) => {
    void qc.invalidateQueries({
      predicate: (query) => {
        const key = query.queryKey;
        return key[0] === "apps" && key[1] === rrfId
          && (key[2] === "table" || key[3] === fromStage || key[3] === toStage);
      },
    });
    void qc.invalidateQueries({ queryKey: ["pipeline-stats", rrfId] });
  };

  const applyTransition = (base: Application, result: TransitionResult) => {
    const moved: Application = {
      ...base,
      current_stage: result.current_stage,
      status: result.status,
      updated_at: new Date().toISOString(),
      current_round_feedback: result.current_stage === base.current_stage
        ? base.current_round_feedback
        : false,
    };

    // Update every cached board page atomically. The card leaves its old column and appears in
    // the target immediately, while only the two affected columns revalidate in the background.
    for (const query of qc.getQueryCache().findAll({ queryKey: ["apps", rrfId] })) {
      const key = query.queryKey;
      if (key[2] !== "board") continue;
      const old = query.state.data as Paged<Application> | undefined;
      if (!old) continue;

      const columnStage = String(key[3]);
      const search = String(key[4] ?? "");
      const statusFilter = String(key[5] ?? "");
      const sortMode = String(key[6] ?? "recent");
      const limit = Number(key[7] ?? 10);
      const page = Number(key[8] ?? 1);
      const oldMatches = columnStage === base.current_stage && matchesBoardFilters(base, search, statusFilter);
      const newMatches = columnStage === moved.current_stage && matchesBoardFilters(moved, search, statusFilter);
      const hadItem = old.items.some((item) => item.application_id === base.application_id);

      let items = old.items.filter((item) => item.application_id !== base.application_id);
      if (newMatches && (hadItem || page === 1)) items = sortBoardItems([...items, moved], sortMode).slice(0, limit);

      const total = Math.max(0, old.total + Number(newMatches) - Number(oldMatches));
      qc.setQueryData<Paged<Application>>(key, { items, total });
    }

    qc.setQueryData<Application>(["application", base.application_id], (old) => old ? { ...old, ...moved } : moved);
    if (base.current_stage !== moved.current_stage) {
      setRecentMove({ applicationId: moved.application_id, stage: moved.current_stage });
    }
    refreshAffectedQueries(base.current_stage, moved.current_stage);
  };

  const screenM = useMutation({
    mutationFn: (id: string) => screenApplication(id),
    onSuccess: () => refetchAll(),
    onError: (e) => setDropErr((e as { message?: string }).message ?? "AI screening failed."),
  });

  const openMove = (app: Application, targetStage: string) => {
    if (app.status !== "ACTIVE") { setDropErr(`${app.candidate_name} is ${app.status.replace("_", " ").toLowerCase()} — resume before moving.`); return; }
    const move = legalMove(app.current_stage, targetStage);
    if (!move) { setDropErr(app.current_stage === "OFFER" ? "Offer acceptance is recorded on the Offers page." : `Can't move ${app.candidate_name} to ${LABEL[targetStage]}.`); return; }
    if (move.action === "MARK_JOINED" && !canMarkJoined) {
      setDropErr("Only HR or Admin can mark a candidate as joined.");
      return;
    }
    setDropErr(null);
    setModal({ app, action: move.action, label: move.label, target: move.target });
  };
  const onDropStage = (stage: string) => {
    setOverStage(null);
    const app = dragApp; setDragApp(null);
    if (!canWrite || !app || app.current_stage === stage) return;
    openMove(app, stage);
  };

  // Run the transition; if it's blocked only because the interview round isn't booked yet,
  // escalate to the schedule modal and finish the move automatically once it's scheduled.
  const runMove = async (app: Application, action: string, comment: string, target?: string) => {
    const effTarget = target ?? DEFAULT_NEXT[app.current_stage];
    // Leaving any interview stage requires that CURRENT round's feedback first, including a
    // move to Offer. The server enforces the same invariant; this gate makes the workflow guided
    // rather than surfacing an avoidable transition error.
    const leavingInterview = action === "ADVANCE"
      && INTERVIEW_STAGES.includes(app.current_stage)
      && !!effTarget;
    if (leavingInterview && !app.current_round_feedback) {
      if (!canFeedback) {
        throw new Error("The current round's feedback must be submitted by HR, Admin, or the lead panelist before this move.");
      }
      setModal(null);
      setFeedbackGate({ app, then: { action, comment, target: effTarget } });
      return;
    }
    try {
      const result = await transitionApplication(app.application_id, action, comment, target);
      applyTransition(app, result);
    } catch (err) {
      const e = err as ApiError;
      const needsSchedule = action === "ADVANCE" && effTarget && STAGE_ROUND[effTarget]
        && e.code === "RMS-E-4221" && /schedule/i.test(e.message ?? "");
      if (needsSchedule) {
        if (!canSchedule) {
          throw new Error(`${LABEL[effTarget]} must be scheduled by HR or Admin before this move.`);
        }
        setModal(null);
        setScheduling({ app, then: { action, comment, target: effTarget } });
        return; // resolves so the CommentModal closes; move resumes after scheduling
      }

      // A second hiring user may have completed the same move while this request was in flight.
      // Treat that as success after verifying the authoritative stage instead of showing a false
      // error or attempting a duplicate transition.
      if (action === "ADVANCE" && effTarget && e.code === "RMS-E-4221") {
        const current = await getApplication(app.application_id).catch(() => null);
        if (current?.current_stage === effTarget) {
          applyTransition(app, {
            application_id: app.application_id,
            from_stage: app.current_stage,
            current_stage: current.current_stage,
            status: current.status,
            action,
            history_id: 0,
          });
          return;
        }
      }
      throw err; // any other failure surfaces in the CommentModal
    }
  };

  const cardActions = {
    canWrite,
    canScreen,
    canSchedule,
    canFeedback,
    canMarkJoined,
    canAddCandidate,
    screenM,
    setModal,
    setAssessing,
    setScheduling: (a: Application) => setScheduling({ app: a }),
    setFeedback: setFeedbackFor,
  };

  // Let a plain (vertical) mouse wheel scroll the board horizontally across stages.
  // If the cursor is over a column that can still scroll its own cards, let that happen first.
  const boardRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const board = boardRef.current;
    if (!board || view !== "board") return;
    const onWheel = (e: WheelEvent) => {
      if (e.deltaY === 0 || Math.abs(e.deltaX) > Math.abs(e.deltaY)) return;
      const body = (e.target as HTMLElement | null)?.closest<HTMLElement>(".pk-col-body");
      if (body) {
        const atTop = e.deltaY < 0 && body.scrollTop <= 0;
        const atBottom = e.deltaY > 0 && Math.ceil(body.scrollTop + body.clientHeight) >= body.scrollHeight;
        if (!atTop && !atBottom) return;
      }
      if (board.scrollWidth <= board.clientWidth) return;
      e.preventDefault();
      board.scrollLeft += e.deltaY;
    };
    // A native non-passive listener is required; React/Chrome may make wheel listeners passive,
    // which causes preventDefault warnings and lets the page scroll while crossing the board.
    board.addEventListener("wheel", onWheel, { passive: false });
    return () => board.removeEventListener("wheel", onWheel);
  }, [view, rrfId, rrfsQ.isLoading]);

  const showPipeLoader = useDelayedFlag(rrfsQ.isLoading);
  if (rrfsQ.isLoading) {
    return (
      <div className="page pk">
        <div className="page-head"><div><h1>Pipeline</h1><div className="sub">Hiring pipeline · Drag candidates between stages</div></div></div>
        {showPipeLoader && <NeuralLoader label="Loading Pipeline" />}
      </div>
    );
  }

  return (
    <div className="page pk">
      <div className="page-head">
        <div>
          <h1>{rrf?.position_title ?? "Pipeline"}</h1>
          <div className="sub">{rrf?.rrf_code ? `${rrf.rrf_code} · ` : ""}Hiring pipeline · Drag candidates between stages</div>
        </div>
        <div className="actions">
          <select value={rrfId} onChange={(e) => setRrfId(e.target.value)} style={{ width: 260 }}>
            {approved.map((r) => <option key={r.rrf_id} value={r.rrf_id}>{r.rrf_code} · {r.position_title}</option>)}
          </select>
          <button className={`btn-ghost${showFilters ? " on" : ""}`} onClick={() => setShowFilters((s) => !s)}>Filters</button>
          <div style={{ position: "relative" }}>
            <button className="btn-ghost" onClick={() => setShowCustomize((s) => !s)}>Customize</button>
            {showCustomize && (
              <div className="pk-pop" onMouseLeave={() => setShowCustomize(false)}>
                <div className="pk-pop-lab">View</div>
                <div className="pk-seg">
                  <button className={view === "board" ? "on" : ""} onClick={() => setView("board")}>Board</button>
                  <button className={view === "table" ? "on" : ""} onClick={() => setView("table")}>Table</button>
                </div>
                <div className="pk-pop-lab">Card density</div>
                <div className="pk-seg">
                  <button className={density === "comfortable" ? "on" : ""} onClick={() => setDensity("comfortable")}>Comfortable</button>
                  <button className={density === "compact" ? "on" : ""} onClick={() => setDensity("compact")}>Compact</button>
                </div>
              </div>
            )}
          </div>
          {canAddCandidate && rrfId && <button onClick={() => setAdding(true)}>+ Add candidate</button>}
        </div>
      </div>

      {/* KPI row */}
      {statsQ.data && <StatsRow s={statsQ.data} />}

      {/* filter bar */}
      {showFilters && (
        <div className="pk-filters card card-pad">
          <input placeholder="Search candidate name…" value={q} onChange={(e) => setQ(e.target.value)} style={{ maxWidth: 280 }} />
          <select value={status} onChange={(e) => setStatus(e.target.value)} style={{ maxWidth: 170 }}>
            <option value="">All statuses</option>
            <option value="ACTIVE">Active</option>
            <option value="ON_HOLD">On hold</option>
            <option value="REJECTED">Rejected</option>
            <option value="WITHDRAWN">Withdrawn</option>
            <option value="HIRED">Hired</option>
          </select>
          <select value={sort} onChange={(e) => setSort(e.target.value)} style={{ maxWidth: 170 }}>
            <option value="score">Sort: AI score</option>
            <option value="recent">Sort: Most recent</option>
            <option value="name">Sort: Name (A–Z)</option>
          </select>
          {view === "table" && (
            <select value={stage} onChange={(e) => setStage(e.target.value)} style={{ maxWidth: 180 }}>
              <option value="">All stages</option>
              {STAGES.map((s) => <option key={s} value={s}>{LABEL[s]}</option>)}
            </select>
          )}
          {(dq || status || stage || sort !== "score") && <button className="btn-ghost btn-sm" onClick={() => { setQ(""); setStatus(""); setStage(""); setSort("score"); }}>Clear</button>}
        </div>
      )}

      {/* active deep-link filter chip — makes an arrived-from-dashboard filter obvious + clearable */}
      {view === "table" && stage && (
        <div className="pk-activefilter">
          <span>Showing <b>{LABEL[stage]}</b> stage</span>
          <button onClick={() => setStage("")} title="Clear stage filter">✕</button>
        </div>
      )}

      {dropErr && <div className="card card-pad error-text" style={{ cursor: "pointer" }} onClick={() => setDropErr(null)}>{dropErr}</div>}

      {!rrfId ? <div className="card card-pad muted">No open requisitions.</div> : view === "table" ? (
        <TableView rrfId={rrfId} filters={filters} setPageSize={setPageSize} actions={cardActions} />
      ) : (
        <>
          <div className="pk-board" ref={boardRef}>
            {STAGES.map((stage) => (
              <StageColumn
                key={stage} rrfId={rrfId} stage={stage} filters={filters} density={density}
                actions={cardActions}
                dnd={{ dragApp, setDragApp, overStage, setOverStage, onDropStage, canWrite, setDropErr }}
                recentMove={recentMove}
                onAdd={() => setAdding(true)}
              />
            ))}
          </div>
          <div className="pk-pagesize">
            Rows per column
            {PAGE_SIZES.map((n) => (
              <button key={n} className={pageSize === n ? "on" : ""} onClick={() => setPageSize(n)}>{n}</button>
            ))}
          </div>
        </>
      )}

      {modal && (
        <CommentModal title={`${modal.label} — ${modal.app.candidate_name}`} actionLabel={modal.label} onClose={() => setModal(null)}
          onSubmit={(comment) => runMove(modal.app, modal.action, comment, modal.target)} />
      )}
      {adding && <AddCandidate rrfId={rrfId} onClose={() => setAdding(false)} onDone={() => { setAdding(false); refetchAll(); }} />}
      {assessing && <ScreeningAssessment applicationId={assessing.application_id} candidateName={assessing.candidate_name} onClose={() => setAssessing(null)} />}
      {scheduling && (() => {
        const scheduledFlow = scheduling;
        return (
        <ScheduleInterviewModal
          applicationId={scheduledFlow.app.application_id}
          candidateName={scheduledFlow.app.candidate_name}
          stage={scheduledFlow.app.current_stage}
          lockRound={scheduledFlow.then ? STAGE_ROUND[scheduledFlow.then.target] : undefined}
          moveHint={scheduledFlow.then ? `Booking this interview will move ${scheduledFlow.app.candidate_name} to ${LABEL[scheduledFlow.then.target]}.` : undefined}
          onClose={() => setScheduling(null)}
          onDone={async (interview) => {
            const s = scheduledFlow;
            setScheduling(null);
            void qc.invalidateQueries({ queryKey: ["apps-interviews", s.app.application_id] });
            void qc.invalidateQueries({ queryKey: ["my-interviews"] });

            try {
              let currentStage = interview.application_stage;
              let currentStatus = s.app.status;
              if (!currentStage) {
                const current = await getApplication(s.app.application_id);
                currentStage = current.current_stage;
                currentStatus = current.status;
              }

              if (s.then && currentStage !== s.then.target) {
                const result = await transitionApplication(
                  s.app.application_id,
                  s.then.action,
                  s.then.comment,
                  s.then.target,
                );
                applyTransition(s.app, result);
              } else if (currentStage && currentStage !== s.app.current_stage) {
                applyTransition(s.app, {
                  application_id: s.app.application_id,
                  from_stage: s.app.current_stage,
                  current_stage: currentStage,
                  status: currentStatus,
                  action: "ADVANCE",
                  history_id: 0,
                });
              } else {
                // The interview is saved even when no stage change is required. Refresh the
                // relevant cards so schedule-dependent actions update without touching 9 columns.
                refreshAffectedQueries(s.app.current_stage, s.app.current_stage);
              }
            } catch (err) {
              const current = await getApplication(s.app.application_id).catch(() => null);
              if (s.then && current?.current_stage === s.then.target) {
                applyTransition(s.app, {
                  application_id: s.app.application_id,
                  from_stage: s.app.current_stage,
                  current_stage: current.current_stage,
                  status: current.status,
                  action: s.then.action,
                  history_id: 0,
                });
              } else {
                setDropErr((err as ApiError).message ?? `Interview scheduled, but moving ${s.app.candidate_name} failed. The interview is saved; retry the move.`);
                refreshAffectedQueries(s.app.current_stage, s.then?.target ?? s.app.current_stage);
              }
            }
          }}
        />
        );
      })()}
      {feedbackFor && (() => {
        const feedbackApp = feedbackFor;
        return <QuickFeedbackModal
          app={feedbackApp}
          onClose={() => setFeedbackFor(null)}
          onDone={async (nextMove?: FeedbackNextMove) => {
            setFeedbackFor(null);
            void qc.invalidateQueries({ queryKey: ["apps-interviews", feedbackApp.application_id] });
            void qc.invalidateQueries({ queryKey: ["my-interviews"] });
            if (!nextMove) { refetchAll(); return; }
            try {
              await runMove(
                { ...feedbackApp, current_round_feedback: true },
                "ADVANCE",
                nextMove.comment,
                nextMove.target,
              );
            } catch (err) {
              setDropErr((err as ApiError).message ?? "Feedback was saved, but the stage move failed. Retry the move from the board.");
              refetchAll();
            }
          }}
        />;
      })()}
      {feedbackGate && (
        <QuickFeedbackModal
          app={feedbackGate.app}
          gateMode
          onClose={() => setFeedbackGate(null)}
          onDone={async () => {
            const g = feedbackGate;
            setFeedbackGate(null);
            if (!g) return;
            void qc.invalidateQueries({ queryKey: ["apps-interviews", g.app.application_id] });
            void qc.invalidateQueries({ queryKey: ["my-interviews"] });
            // Feedback recorded — resume the move. Mark current_round_feedback so the gate doesn't
            // re-trigger (refetch is async), then the schedule gate/advance run next.
            try {
              await runMove({ ...g.app, current_round_feedback: true }, g.then.action, g.then.comment, g.then.target);
            } catch (err) {
              setDropErr((err as ApiError).message ?? "Feedback was saved, but the stage move failed. Retry the move from the board.");
              refetchAll();
            }
          }}
        />
      )}
    </div>
  );
}

/* ---------- KPI row ---------- */
function StatsRow({ s }: { s: PipelineStats }) {
  const tiles = [
    { lab: "Active candidates", val: String(s.active_candidates), sub: `${s.added_this_week} added this week` },
    { lab: "Avg. time in stage", val: s.avg_days_in_stage != null ? `${s.avg_days_in_stage} days` : "—", sub: "per active candidate" },
    { lab: "Interview conversion", val: `${Math.round(s.interview_conversion * 100)}%`, sub: "reached interview" },
    { lab: "Offer acceptance", val: `${Math.round(s.offer_acceptance * 100)}%`, sub: `${s.offers_pending} pending` },
  ];
  return (
    <div className="pk-stats">
      {tiles.map((t) => (
        <div key={t.lab} className="pk-stat">
          <div className="pk-stat-lab">{t.lab}</div>
          <div className="pk-stat-val tnum">{t.val}</div>
          <div className="pk-stat-sub">{t.sub}</div>
        </div>
      ))}
    </div>
  );
}

/* ---------- Board column (own pagination) ---------- */
type Filters = { dq: string; status: string; sort: string; pageSize: number; stage: string };
type CardActions = {
  canWrite: boolean; canScreen: boolean; canSchedule: boolean; canFeedback: boolean;
  canMarkJoined: boolean; canAddCandidate: boolean;
  screenM: ReturnType<typeof useMutation<unknown, Error, string>>;
  setModal: (m: ModalState) => void; setAssessing: (a: Application) => void; setScheduling: (a: Application) => void;
  setFeedback: (a: Application) => void;
};
type Dnd = {
  dragApp: Application | null; setDragApp: (a: Application | null) => void;
  overStage: string | null; setOverStage: (s: string | null) => void;
  onDropStage: (s: string) => void; canWrite: boolean; setDropErr: (s: string | null) => void;
};

function StageColumn({ rrfId, stage, filters, density, actions, dnd, recentMove, onAdd }: {
  rrfId: string;
  stage: string;
  filters: Filters;
  density: string;
  actions: CardActions;
  dnd: Dnd;
  recentMove: { applicationId: string; stage: string } | null;
  onAdd: () => void;
}) {
  const [page, setPage] = useState(1);
  useEffect(() => { setPage(1); }, [rrfId, filters.dq, filters.status, filters.sort, filters.pageSize]);

  const query = useQuery({
    queryKey: ["apps", rrfId, "board", stage, filters.dq, filters.status, filters.sort, filters.pageSize, page],
    queryFn: () => listApplications({ rrf_id: rrfId, stage, status: filters.status || undefined, q: filters.dq || undefined, sort: filters.sort, page, limit: filters.pageSize }),
    enabled: !!rrfId,
    placeholderData: keepPreviousData,
  });
  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / filters.pageSize));
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);
  const candidateMove = dnd.dragApp ? legalMove(dnd.dragApp.current_stage, stage) : null;
  const isTarget = !!candidateMove && (candidateMove.action !== "MARK_JOINED" || actions.canMarkJoined);
  const [collapsed, setCollapsed] = useState(false);

  return (
    <div
      className={`pk-col${dnd.overStage === stage ? (isTarget ? " over-ok" : " over-no") : ""}`}
      onDragOver={(e) => {
        if (!dnd.dragApp) return;
        dnd.setOverStage(stage);
        if (isTarget) {
          e.preventDefault();
          e.dataTransfer.dropEffect = "move";
        } else {
          e.dataTransfer.dropEffect = "none";
        }
      }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node)) dnd.setOverStage(null); }}
      onDrop={(e) => {
        e.preventDefault();
        if (isTarget) dnd.onDropStage(stage);
        else { dnd.setOverStage(null); dnd.setDragApp(null); }
      }}
    >
      <div className="pk-col-head">
        <span className={`pk-dot s-${stage}`} />
        <b>{LABEL[stage]}</b>
        <span className="pk-count">{total}</span>
        <button className="pk-col-menu" title={collapsed ? "Expand" : "Collapse"} onClick={() => setCollapsed((c) => !c)}>⋯</button>
      </div>

      {!collapsed && (
        <>
          <div className={`pk-col-body ${density}`}>
            {query.isLoading ? [0, 1].map((i) => <div key={i} className="pk-card skeleton" style={{ height: 92 }} />)
              : items.length === 0 ? <div className="pk-empty">—</div>
              : items.map((a) => <Card
                  key={a.application_id}
                  a={a}
                  density={density}
                  actions={actions}
                  dnd={dnd}
                  justMoved={recentMove?.applicationId === a.application_id && recentMove.stage === stage}
                />)}
          </div>

          <div className="pk-col-foot">
            {total > filters.pageSize && (
              <div className="pk-pager">
                <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>‹</button>
                <span>{(page - 1) * filters.pageSize + 1}–{Math.min(page * filters.pageSize, total)} of {total}</span>
                <button disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>›</button>
              </div>
            )}
            {actions.canAddCandidate && <button className="pk-add" onClick={onAdd}>+ Add candidate</button>}
          </div>
        </>
      )}
    </div>
  );
}

/* ---------- Card ---------- */
type MenuItem = { label: string; onClick: () => void; cls?: string; disabled?: boolean };

function Card({ a, density, actions, dnd, justMoved }: {
  a: Application;
  density: string;
  actions: CardActions;
  dnd: Dnd;
  justMoved: boolean;
}) {
  const badge = STATUS_BADGE[a.status] ?? { label: a.status, cls: "mut" };
  const draggable = actions.canWrite && a.status === "ACTIVE";
  const busy = actions.screenM.isPending && actions.screenM.variables === a.application_id;
  const interviewStage = ["SHORTLISTED", "INTERVIEW_R1", "INTERVIEW_R2", "INTERVIEW_MGMT"].includes(a.current_stage);
  const inRound = INTERVIEW_STAGES.includes(a.current_stage);
  const fbDone = inRound && !!a.current_round_feedback;

  // Compact action model: one primary action inline, the rest tucked behind a "•••" menu.
  const acts: MenuItem[] = [];
  if (actions.canWrite && a.status === "ACTIVE") {
    if (inRound && !fbDone && actions.canFeedback) acts.push({ label: "+ Feedback", onClick: () => actions.setFeedback(a), cls: "pos" });
    if (interviewStage && actions.canSchedule) acts.push({ label: "Schedule", onClick: () => actions.setScheduling(a) });
    if (a.current_stage === "OFFER_ACCEPTED" && actions.canMarkJoined) {
      acts.push({ label: "Mark joined", onClick: () => actions.setModal({ app: a, action: "MARK_JOINED", label: "Mark joined", target: "JOINED" }), cls: "pos" });
    } else if (DEFAULT_NEXT[a.current_stage]) {
      acts.push({ label: "Advance", onClick: () => actions.setModal({ app: a, action: "ADVANCE", label: "Advance" }) });
    }
    acts.push({ label: "Hold", onClick: () => actions.setModal({ app: a, action: "HOLD", label: "Hold" }) });
    acts.push({ label: "Reject", onClick: () => actions.setModal({ app: a, action: "REJECT", label: "Reject" }), cls: "neg" });
    if (actions.canScreen) acts.push({ label: busy ? "Screening…" : a.ai_screen_score != null ? "Re-screen" : "AI Screen", onClick: () => actions.screenM.mutate(a.application_id), disabled: actions.screenM.isPending });
  }
  if (actions.canWrite && a.status === "ON_HOLD") acts.push({ label: "Resume", onClick: () => actions.setModal({ app: a, action: "RESUME", label: "Resume" }) });
  if (a.ai_screen_score != null) acts.push({ label: "Assessment", onClick: () => actions.setAssessing(a) });

  const primary = acts[0] ?? null;
  const rest = acts.slice(1);

  return (
    <div
      className={`pk-card${dnd.dragApp?.application_id === a.application_id ? " dragging" : ""}${draggable ? " grab" : ""}${justMoved ? " just-moved" : ""} ${density}`}
      draggable={draggable}
      aria-grabbed={dnd.dragApp?.application_id === a.application_id}
      onDragStart={(e) => {
        if ((e.target as HTMLElement).closest("a,button,input,select,textarea")) {
          e.preventDefault();
          return;
        }
        dnd.setDragApp(a);
        dnd.setDropErr(null);
        e.dataTransfer.effectAllowed = "move";
        // Firefox requires data to be set before it will start a native drag operation.
        e.dataTransfer.setData("text/plain", a.application_id);
      }}
      onDragEnd={() => { dnd.setDragApp(null); dnd.setOverStage(null); }}
    >
      <span className={`pk-risk ${scoreCls(a.ai_screen_score)}`} />
      <div className="pk-card-top">
        <span className="pk-avatar">{initials(a.candidate_name)}</span>
        <div className="pk-id">
          <b>{a.candidate_name}</b>
          <span>{[a.current_company, a.experience_years != null ? `${a.experience_years} yrs` : null].filter(Boolean).join(" · ") || "—"}</span>
        </div>
        <span className={`pk-score ${scoreCls(a.ai_screen_score)}`}>{a.ai_screen_score != null ? Math.round(a.ai_screen_score) : "—"}</span>
      </div>

      <div className="pk-badges">
        <span className={`pk-status ${badge.cls}`}>{badge.label}</span>
        {fbDone && <span className="pk-fbdone" title="Feedback recorded for this round">✓ Feedback</span>}
        <span className="pk-time">{relDays(a.updated_at ?? a.created_at)}</span>
      </div>

      {density !== "compact" && a.top_skills && a.top_skills.length > 0 && (
        <div className="pk-tags">{a.top_skills.map((t) => <span key={t} className="pk-tag">{t}</span>)}</div>
      )}

      <div className="pk-foot">
        <Link className="pk-link strong" draggable={false} to={`/candidates/${a.candidate_id}`}>Open</Link>
        {primary && <button className={`pk-link ${primary.cls ?? ""}`} disabled={primary.disabled} onClick={primary.onClick}>{primary.label}</button>}
        {rest.length > 0 && <CardMenu items={rest} />}
      </div>
    </div>
  );
}

/* Overflow menu — portalled so the column's scroll/overflow can't clip it. */
function CardMenu({ items }: { items: MenuItem[] }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const btnRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open) return;
    const close = () => setOpen(false);
    window.addEventListener("scroll", close, true);
    window.addEventListener("resize", close);
    document.addEventListener("mousedown", close);
    return () => {
      window.removeEventListener("scroll", close, true);
      window.removeEventListener("resize", close);
      document.removeEventListener("mousedown", close);
    };
  }, [open]);

  return (
    <div className="pk-menu-wrap">
      <button
        ref={btnRef}
        className="pk-more"
        title="More actions"
        onMouseDown={(e) => e.stopPropagation()}
        onClick={(e) => {
          e.stopPropagation();
          const r = btnRef.current!.getBoundingClientRect();
          setPos({ top: r.bottom + 4, left: Math.max(8, Math.min(r.right - 176, window.innerWidth - 184)) });
          setOpen((o) => !o);
        }}
      >
        •••
      </button>
      {open && createPortal(
        <div className="pk-menu" style={{ top: pos.top, left: pos.left }} onMouseDown={(e) => e.stopPropagation()}>
          {items.map((it) => (
            <button
              key={it.label}
              className={`pk-menu-item ${it.cls ?? ""}`}
              disabled={it.disabled}
              onClick={() => { setOpen(false); it.onClick(); }}
            >
              {it.label}
            </button>
          ))}
        </div>,
        document.body,
      )}
    </div>
  );
}

/* ---------- Table view ---------- */
function TableView({ rrfId, filters, setPageSize, actions }: { rrfId: string; filters: Filters; setPageSize: (n: number) => void; actions: CardActions }) {
  const [page, setPage] = useState(1);
  useEffect(() => { setPage(1); }, [rrfId, filters.dq, filters.status, filters.sort, filters.pageSize, filters.stage]);
  const query = useQuery({
    queryKey: ["apps", rrfId, "table", filters.dq, filters.status, filters.sort, filters.pageSize, filters.stage, page],
    queryFn: () => listApplications({ rrf_id: rrfId, stage: filters.stage || undefined, status: filters.status || undefined, q: filters.dq || undefined, sort: filters.sort, page, limit: filters.pageSize }),
    enabled: !!rrfId,
    placeholderData: keepPreviousData,
  });
  const items = query.data?.items ?? [];
  const total = query.data?.total ?? 0;
  const pages = Math.max(1, Math.ceil(total / filters.pageSize));
  useEffect(() => { if (page > pages) setPage(pages); }, [page, pages]);
  const showLoader = useDelayedFlag(query.isLoading);

  if (query.isLoading) {
    return <div className="card card-pad">{showLoader && <NeuralLoader label="Loading candidates" />}</div>;
  }

  return (
    <div className="card">
      <table className="dt">
        <thead><tr><th>Candidate</th><th>Stage</th><th>Status</th><th>Score</th><th>In stage</th><th>Actions</th></tr></thead>
        <tbody>
          {items.length === 0 ? <tr><td colSpan={6} className="muted" style={{ padding: 20 }}>No candidates match.</td></tr>
            : items.map((a) => {
              const badge = STATUS_BADGE[a.status] ?? { label: a.status, cls: "mut" };
              return (
                <tr key={a.application_id}>
                  <td>
                    <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                      <span className="pk-avatar sm">{initials(a.candidate_name)}</span>
                      <div><b>{a.candidate_name}</b><div className="muted" style={{ fontSize: ".72rem" }}>{[a.current_company, a.experience_years != null ? `${a.experience_years} yrs` : null].filter(Boolean).join(" · ")}</div></div>
                    </div>
                  </td>
                  <td>{LABEL[a.current_stage] ?? a.current_stage}</td>
                  <td><span className={`pk-status ${badge.cls}`}>{badge.label}</span></td>
                  <td><span className={`pk-score ${scoreCls(a.ai_screen_score)}`}>{a.ai_screen_score != null ? Math.round(a.ai_screen_score) : "—"}</span></td>
                  <td className="muted">{relDays(a.updated_at ?? a.created_at)}</td>
                  <td>
                    <div className="row" style={{ gap: 6 }}>
                      <Link className="linkbtn" to={`/candidates/${a.candidate_id}`}>Open</Link>
                      {INTERVIEW_STAGES.includes(a.current_stage) && a.current_round_feedback && <span className="pk-fbdone">✓ Feedback</span>}
                      {actions.canFeedback && a.status === "ACTIVE" && INTERVIEW_STAGES.includes(a.current_stage) && !a.current_round_feedback && <button className="pk-link strong" onClick={() => actions.setFeedback(a)}>Feedback</button>}
                      {actions.canWrite && a.status === "ACTIVE" && DEFAULT_NEXT[a.current_stage] && <button className="pk-link" onClick={() => actions.setModal({ app: a, action: "ADVANCE", label: "Advance" })}>Advance</button>}
                      {actions.canMarkJoined && a.status === "ACTIVE" && a.current_stage === "OFFER_ACCEPTED" && <button className="pk-link strong" onClick={() => actions.setModal({ app: a, action: "MARK_JOINED", label: "Mark joined", target: "JOINED" })}>Mark joined</button>}
                      {actions.canWrite && a.status === "ACTIVE" && <button className="pk-link neg" onClick={() => actions.setModal({ app: a, action: "REJECT", label: "Reject" })}>Reject</button>}
                    </div>
                  </td>
                </tr>
              );
            })}
        </tbody>
      </table>
      <div className="pk-table-foot">
        <div className="pk-pagesize inline">
          Rows {PAGE_SIZES.map((n) => <button key={n} className={filters.pageSize === n ? "on" : ""} onClick={() => setPageSize(n)}>{n}</button>)}
        </div>
        <div className="pk-pager">
          <button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>‹</button>
          <span>{total === 0 ? "0" : `${(page - 1) * filters.pageSize + 1}–${Math.min(page * filters.pageSize, total)}`} of {total}</span>
          <button disabled={page >= pages} onClick={() => setPage((p) => p + 1)}>›</button>
        </div>
      </div>
    </div>
  );
}

/* ---------- Add candidate ---------- */
function AddCandidate({ rrfId, onClose, onDone }: { rrfId: string; onClose: () => void; onDone: () => void }) {
  const candQ = useQuery({ queryKey: ["candidates"], queryFn: () => listCandidates({ limit: 100 }) });
  const options = candQ.data?.items ?? [];
  const [cid, setCid] = useState("");
  const [error, setError] = useState<string | null>(null);
  const m = useMutation({
    mutationFn: () => createApplication(rrfId, cid),
    onSuccess: onDone,
    onError: (e) => setError((e as { message?: string }).message ?? "Failed"),
  });
  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()}>
        <h3>Add candidate to requisition</h3>
        <label>Candidate</label>
        <select value={cid} onChange={(e) => setCid(e.target.value)}>
          <option value="">Select…</option>
          {options.map((c) => <option key={c.candidate_id} value={c.candidate_id}>{c.full_name} · {c.email}</option>)}
        </select>
        {error && <p className="error-text">{error}</p>}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 16 }}>
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button disabled={!cid || m.isPending} onClick={() => m.mutate()}>{m.isPending ? "Adding…" : "Add"}</button>
        </div>
      </div>
    </div>
  );
}
