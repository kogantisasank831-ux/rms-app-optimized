"""dashboard_service — metrics (LLD 11.2), role-scoped, with a 60s in-process TTL cache.

Scope: HR/ADMIN see all; HM own RRFs; BU_HEAD own-BU RRFs (RRF-level only — no candidate
data, INV-07). Every scalar metric is returned as {value, description}.

Two surfaces, so the UI can render instantly and let the heavier bits stream in:
  * get_metrics()  — fast, DB-only core (KPIs, alerts, pipeline, schedule, risk lists).
                     The many counts are consolidated into a few round-trips (was ~15).
  * get_insights() — AI observability (agent-run tiles). HR/ADMIN only. Loaded in the
                     background by the client so it never blocks the core dashboard.
"""
from __future__ import annotations

import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User

_CACHE_TTL = 60.0
_cache: dict[str, tuple[float, dict]] = {}
_insights_cache: dict[str, tuple[float, dict]] = {}


def _rrf_filter(user: User) -> tuple[str, dict]:
    role = user.role_code
    if role in ("HR", "ADMIN"):
        return "", {}
    if role == "HIRING_MANAGER":
        return "AND r.created_by = :uid", {"uid": str(user.user_id)}
    if role == "BU_HEAD":
        return "AND r.bu_id IN (SELECT bu_id FROM business_units WHERE bu_head_user_id = :uid)", {"uid": str(user.user_id)}
    return "AND 1=0", {}  # no scope -> nothing


def _m(value, description: str) -> dict:
    return {"value": value, "description": description}


def _forward_fill(series: list) -> list:
    """Replace leading/intermediate Nones so a sparkline draws a continuous line.
    Leading Nones adopt the first known value; later Nones carry the previous one."""
    out: list = []
    last = None
    first_known = next((v for v in series if v is not None), None)
    for v in series:
        if v is None:
            out.append(last if last is not None else (first_known if first_known is not None else 0))
        else:
            out.append(v)
            last = v
    return out


def _trend_block(series: list, *, unit: str, up_is_good: bool) -> dict:
    """Sparkline points + a real period delta (first known -> last known over the window)."""
    known = [v for v in series if v is not None]
    delta = None
    if len(known) >= 2:
        first, last = known[0], known[-1]
        if unit == "pct":
            delta = round(((last - first) / first) * 100, 1) if first else (100.0 if last else 0.0)
        else:
            delta = round(last - first, 1)
    return {"spark": _forward_fill(series), "delta": delta, "unit": unit, "up_is_good": up_is_good}


async def get_metrics(db: AsyncSession, user: User) -> dict:
    cache_key = f"{user.role_code}:{user.user_id}"
    now = time.monotonic()
    hit = _cache.get(cache_key)
    if hit and hit[0] > now:
        return hit[1]

    flt, p = _rrf_filter(user)
    role = user.role_code
    data: dict = {}

    # --- RRF-level counts (all roles) — one round-trip -----------------------
    row = (await db.execute(text(f"""
        SELECT
          (SELECT count(*) FROM rrf r WHERE r.status='APPROVED' {flt})                              AS open_rrfs,
          (SELECT count(*) FROM rrf r WHERE r.status='PENDING_APPROVAL' {flt})                       AS pending_approvals,
          (SELECT COALESCE(SUM(r.positions_filled),0) FROM rrf r WHERE r.status IN ('APPROVED','CLOSED') {flt}) AS positions_filled,
          (SELECT COALESCE(SUM(r.positions_count),0)  FROM rrf r WHERE r.status IN ('APPROVED','CLOSED') {flt}) AS positions_total,
          (SELECT count(*) FROM rrf r WHERE r.status='ON_HOLD' {flt})                                AS rrf_on_hold
    """), p)).mappings().one()

    filled = int(row["positions_filled"] or 0)
    total_pos = int(row["positions_total"] or 0)
    data["open_rrfs"] = _m(int(row["open_rrfs"] or 0), "RRFs currently open for hiring (APPROVED).")
    data["pending_approvals"] = _m(int(row["pending_approvals"] or 0), "RRFs awaiting BU Head approval.")
    data["positions_filled"] = _m(filled, "Positions filled across open+closed RRFs.")
    data["positions_total"] = _m(total_pos, "Total positions across open+closed RRFs.")
    data["positions_filled_ratio"] = _m(round(filled / total_pos, 3) if total_pos else 0.0, "Fraction of positions filled (hiring goal progress).")

    # --- candidate-level counts — excluded for BU_HEAD (INV-07) --------------
    if role != "BU_HEAD":
        c = (await db.execute(text(f"""
            SELECT
              (SELECT count(*) FROM applications a JOIN rrf r ON r.rrf_id=a.rrf_id WHERE a.status='ON_HOLD' {flt}) AS app_on_hold,
              (SELECT count(*) FROM interviews i JOIN applications a ON a.application_id=i.application_id JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE i.status='SCHEDULED' AND i.scheduled_start::date = current_date {flt}) AS interviews_today,
              (SELECT count(*) FROM interviews i JOIN applications a ON a.application_id=i.application_id JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE i.status='SCHEDULED' AND i.scheduled_start::date BETWEEN current_date AND current_date + 7 {flt}) AS interviews_week,
              (SELECT count(*) FROM offers o JOIN applications a ON a.application_id=o.application_id JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE o.status <> 'DRAFT' {flt}) AS offers_released,
              (SELECT count(*) FROM offers o JOIN applications a ON a.application_id=o.application_id JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE o.status='ACCEPTED' {flt}) AS offers_accepted,
              (SELECT count(*) FROM offers o JOIN applications a ON a.application_id=o.application_id JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE o.status='RELEASED' AND o.valid_until IS NOT NULL
                   AND o.valid_until BETWEEN current_date AND current_date + 7 {flt}) AS offers_expiring,
              (SELECT count(*) FROM applications a JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE a.status='ACTIVE' AND a.updated_at < now() - interval '7 days' {flt}) AS candidates_stalled,
              (SELECT count(*) FROM interviews i JOIN applications a ON a.application_id=i.application_id JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE (i.status='COMPLETED' OR (i.status='SCHEDULED' AND i.scheduled_end < now()))
                   AND NOT EXISTS (SELECT 1 FROM interview_feedback f WHERE f.interview_id=i.interview_id) {flt}) AS feedback_overdue,
              (SELECT count(*) FROM applications a JOIN rrf r ON r.rrf_id=a.rrf_id WHERE 1=1 {flt}) AS total_apps,
              (SELECT count(*) FROM applications a JOIN rrf r ON r.rrf_id=a.rrf_id WHERE a.status='REJECTED' {flt}) AS rejected,
              (SELECT AVG(EXTRACT(EPOCH FROM (h.acted_at - a.created_at))/86400)
                 FROM application_stage_history h JOIN applications a ON a.application_id=h.application_id
                 JOIN rrf r ON r.rrf_id=a.rrf_id WHERE h.to_stage='JOINED' {flt}) AS avg_tth
        """), p)).mappings().one()

        total_apps = int(c["total_apps"] or 0)
        released = int(c["offers_released"] or 0)
        accepted = int(c["offers_accepted"] or 0)
        data["on_hold_count"] = _m(int(c["app_on_hold"] or 0) + int(row["rrf_on_hold"] or 0), "Applications on hold plus RRFs on hold.")
        data["interviews_today"] = _m(int(c["interviews_today"] or 0), "Interviews scheduled for today.")
        data["interviews_week"] = _m(int(c["interviews_week"] or 0), "Interviews scheduled within the next 7 days.")
        data["offers_released"] = _m(released, "Offers released to candidates.")
        data["offers_accepted"] = _m(accepted, "Offers accepted.")
        data["offers_expiring"] = _m(int(c["offers_expiring"] or 0), "Released offers expiring within 7 days.")
        data["offer_acceptance_rate"] = _m(round(accepted / released, 3) if released else 0.0, "Accepted / released offers.")
        data["candidates_stalled"] = _m(int(c["candidates_stalled"] or 0), "Active candidates with no activity in 7+ days.")
        data["feedback_overdue"] = _m(int(c["feedback_overdue"] or 0), "Completed/past interviews still missing feedback.")
        data["rejection_rate"] = _m(round(int(c["rejected"] or 0) / total_apps, 3) if total_apps else 0.0, "Rejected / total applications.")
        att = c["avg_tth"]
        data["avg_time_to_hire_days"] = _m(round(float(att), 1) if att is not None else None, "Average days from application to JOINED.")

        # pipeline by (active) stage
        stage_rows = (await db.execute(text(
            f"SELECT a.current_stage, count(*) FROM applications a JOIN rrf r ON r.rrf_id=a.rrf_id "
            f"WHERE a.status='ACTIVE' {flt} GROUP BY a.current_stage"
        ), p)).all()
        data["pipeline_by_stage"] = _m({r[0]: r[1] for r in stage_rows}, "Active candidates per pipeline stage.")

        # cumulative hiring funnel — how many applications EVER reached each milestone
        # (from stage history, so rejected/withdrawn candidates still count toward the
        # furthest stage they got to). Monotonically non-increasing top→bottom.
        _SCREENED = "'SCREENING','SHORTLISTED','INTERVIEW_R1','INTERVIEW_R2','INTERVIEW_MGMT','OFFER','OFFER_ACCEPTED','JOINED'"
        _INTERVIEWED = "'INTERVIEW_R1','INTERVIEW_R2','INTERVIEW_MGMT','OFFER','OFFER_ACCEPTED','JOINED'"
        _OFFERED = "'OFFER','OFFER_ACCEPTED','JOINED'"
        fr = (await db.execute(text(f"""
            SELECT
              (SELECT count(*) FROM applications a JOIN rrf r ON r.rrf_id=a.rrf_id WHERE 1=1 {flt}) AS applied,
              (SELECT count(DISTINCT h.application_id) FROM application_stage_history h
                 JOIN applications a ON a.application_id=h.application_id JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE h.to_stage IN ({_SCREENED}) {flt}) AS screened,
              (SELECT count(DISTINCT h.application_id) FROM application_stage_history h
                 JOIN applications a ON a.application_id=h.application_id JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE h.to_stage IN ({_INTERVIEWED}) {flt}) AS interviewed,
              (SELECT count(DISTINCT h.application_id) FROM application_stage_history h
                 JOIN applications a ON a.application_id=h.application_id JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE h.to_stage IN ({_OFFERED}) {flt}) AS offered,
              (SELECT count(DISTINCT h.application_id) FROM application_stage_history h
                 JOIN applications a ON a.application_id=h.application_id JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE h.to_stage='JOINED' {flt}) AS joined
        """), p)).mappings().one()
        data["hiring_funnel"] = _m(
            {"applied": int(fr["applied"] or 0), "screened": int(fr["screened"] or 0),
             "interviewed": int(fr["interviewed"] or 0), "offered": int(fr["offered"] or 0),
             "joined": int(fr["joined"] or 0)},
            "Cumulative count of applications that reached each hiring milestone.",
        )

        # today's schedule (list)
        sched = (await db.execute(text(
            f"SELECT c.full_name, r.position_title, i.round, i.mode, i.scheduled_start, i.interview_id "
            f"FROM interviews i JOIN applications a ON a.application_id=i.application_id "
            f"JOIN rrf r ON r.rrf_id=a.rrf_id JOIN candidates c ON c.candidate_id=a.candidate_id "
            f"WHERE i.status='SCHEDULED' AND i.scheduled_start::date = current_date {flt} "
            f"ORDER BY i.scheduled_start LIMIT 8"
        ), p)).all()
        data["todays_schedule"] = _m(
            [{"candidate": s[0], "role": s[1], "round": s[2], "mode": s[3],
              "at": s[4].isoformat() if s[4] else None, "interview_id": str(s[5])} for s in sched],
            "Interviews scheduled for today.",
        )

    # --- requisitions at risk (list, all roles that see RRFs) ----------------
    risk_rows = (await db.execute(text(f"""
        SELECT r.position_title, r.job_code,
               (current_date - COALESCE(r.approved_at::date, r.created_at::date)) AS days_open,
               (SELECT count(*) FROM applications a WHERE a.rrf_id=r.rrf_id AND a.status='ACTIVE') AS active_apps,
               (SELECT count(*) FROM applications a WHERE a.rrf_id=r.rrf_id
                  AND a.current_stage IN ('SHORTLISTED','INTERVIEW_R1','INTERVIEW_R2','INTERVIEW_MGMT','OFFER')) AS advanced
        FROM rrf r WHERE r.status='APPROVED' {flt}
        ORDER BY days_open DESC NULLS LAST LIMIT 6
    """), p)).all()

    def _risk(days: int, active: int, advanced: int) -> tuple[str, str]:
        if advanced == 0 and active == 0:
            return "No candidates yet", "At Risk"
        if advanced == 0:
            return "No shortlisted candidates", "At Risk"
        if days is not None and days > 30:
            return "Aging requisition", "Needs Attention"
        if active <= 2:
            return "Low candidate volume", "Needs Attention"
        return "On track", "Monitor"

    risk_list = []
    for pt, jc, days, active, advanced in risk_rows:
        d = int(days) if days is not None else None
        issue, level = _risk(d or 0, int(active or 0), int(advanced or 0))
        risk_list.append({"role": pt, "job_code": jc, "days_open": d,
                          "active": int(active or 0), "issue": issue, "risk": level})
    # Only surface the ones that actually carry risk (not plain "Monitor/On track").
    at_risk = [r for r in risk_list if r["risk"] != "Monitor"]
    data["requisitions_at_risk"] = _m(at_risk, "Open requisitions flagged by a simple risk heuristic.")

    # --- 30-day KPI sparklines + period deltas (headline cards) --------------
    # Cheap correlated-subquery series over a generated day axis; scoped by the same filter.
    trends: dict = {}
    rrf_series = (await db.execute(text(f"""
        SELECT
          (SELECT count(*) FROM rrf r
             WHERE r.approved_at IS NOT NULL AND r.approved_at::date <= gs.day {flt}) AS v
        FROM generate_series((current_date - 29), current_date, interval '1 day') AS gs(day)
        ORDER BY gs.day
    """), p)).all()
    trends["open_rrfs"] = _trend_block(
        [int(r[0] or 0) for r in rrf_series], unit="abs", up_is_good=True
    )

    if role != "BU_HEAD":
        cand_series = (await db.execute(text(f"""
            SELECT
              (SELECT count(*) FROM applications a JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE a.created_at::date <= gs.day {flt}) AS apps,
              (SELECT AVG(EXTRACT(EPOCH FROM (h.acted_at - a.created_at))/86400)
                 FROM application_stage_history h JOIN applications a ON a.application_id=h.application_id
                 JOIN rrf r ON r.rrf_id=a.rrf_id
                 WHERE h.to_stage='JOINED' AND h.acted_at::date <= gs.day {flt}) AS tth
            FROM generate_series((current_date - 29), current_date, interval '1 day') AS gs(day)
            ORDER BY gs.day
        """), p)).all()
        trends["pipeline"] = _trend_block(
            [int(r[0] or 0) for r in cand_series], unit="pct", up_is_good=True
        )
        trends["avg_time_to_hire_days"] = _trend_block(
            [float(r[1]) if r[1] is not None else None for r in cand_series],
            unit="days", up_is_good=False,
        )

    data["kpi_trends"] = _m(trends, "30-day sparkline series and period delta per headline KPI.")

    _cache[cache_key] = (now + _CACHE_TTL, data)
    return data


async def get_insights(db: AsyncSession, user: User) -> dict:
    """AI observability tiles (agent runs). HR/ADMIN only; others get an empty set."""
    if user.role_code not in ("HR", "ADMIN"):
        return {}

    cache_key = user.role_code
    now = time.monotonic()
    hit = _insights_cache.get(cache_key)
    if hit and hit[0] > now:
        return hit[1]

    rows = (await db.execute(text(
        "SELECT agent_name, status, count(*) FROM ai_agent_runs GROUP BY agent_name, status"
    ))).all()
    usage: dict[str, dict[str, int]] = {}
    for name, st, cnt in rows:
        usage.setdefault(name, {})[st] = int(cnt)

    def ok(agent: str) -> int:
        return usage.get(agent, {}).get("SUCCESS", 0)

    total_runs = sum(sum(s.values()) for s in usage.values())
    failures = sum(s.get("FAILURE", 0) for s in usage.values())

    review_pending = (await db.execute(text(
        "SELECT count(*) FROM applications WHERE status='ACTIVE' AND current_stage='SCREENING'"
    ))).scalar() or 0

    resumes = ok("resume_screening")
    matches = ok("candidate_matching")
    jds = ok("jd_creation")
    summaries = ok("feedback_summarization")
    scheduled = ok("interview_scheduling")
    # Transparent, documented estimate — minutes saved per successful agent action.
    hours_saved = round((resumes * 12 + matches * 8 + jds * 30 + summaries * 15 + scheduled * 10) / 60, 1)

    data = {
        "resumes_screened": _m(resumes, "Resumes auto-screened by the AI agent (successful runs)."),
        "candidate_matches": _m(matches, "Candidate-to-role matches computed by the AI agent."),
        "jd_drafts": _m(jds, "Job descriptions drafted by the AI agent."),
        "feedback_summaries": _m(summaries, "Interview feedback summaries generated."),
        "interviews_scheduled_ai": _m(scheduled, "Interview scheduling assists."),
        "human_review_pending": _m(int(review_pending), "AI-screened candidates awaiting a human shortlist decision."),
        "hours_saved": _m(hours_saved, "Estimated hours saved (12/8/30/15/10 min per screen/match/JD/summary/schedule)."),
        "agent_runs_total": _m(total_runs, "Total AI agent runs logged (INV-12)."),
        "agent_failures": _m(failures, "AI agent runs that failed."),
        "agent_usage": _m(usage, "AI agent runs by agent and status."),
    }
    _insights_cache[cache_key] = (now + _CACHE_TTL, data)
    return data


def invalidate() -> None:
    """Called on transitions to drop cached metrics (LLD 11.2)."""
    _cache.clear()
    _insights_cache.clear()
