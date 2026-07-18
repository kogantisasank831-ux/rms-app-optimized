import { useQuery } from "@tanstack/react-query";
import { Link, useNavigate, useParams } from "react-router-dom";

import { getJob } from "../../api/endpoints/careers";
import { useAuth } from "../../auth/AuthContext";
import { BrandLogo, Ic, Icon } from "../../components/brand";
import { InlineLoader } from "../../components/InlineLoader";
import { jobCategory, readJobCache, writeJobCache } from "./jobCache";

function fmtPosted(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `Posted ${d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" })}`;
}

export default function JobDetail() {
  const { jobCode = "" } = useParams();
  const navigate = useNavigate();
  const { user } = useAuth();
  // Hydrate instantly from the locally-cached copy (warmed on the careers dashboard),
  // then refresh from the DB in the background.
  const q = useQuery({
    queryKey: ["careers-job", jobCode],
    queryFn: () => getJob(jobCode).then((d) => { writeJobCache(jobCode, d); return d; }),
    enabled: !!jobCode,
    placeholderData: () => readJobCache(jobCode),
  });
  const job = q.data;

  // Same apply flow as the portal cards: signed-in candidates apply directly,
  // everyone else is routed to sign up first (job carried along).
  const onApply = () => {
    if (!job) return;
    if (user?.role === "CANDIDATE") navigate(`/careers/dashboard?apply=${job.rrf_id}`);
    else navigate(`/careers/signup?job=${job.rrf_id}`);
  };

  return (
    <div className="cp">
      <nav className="cp-nav anim">
        <div className="in">
          <Link to="/careers" style={{ textDecoration: "none" }}><BrandLogo tag="Careers" /></Link>
          <div className="links" />
          {user?.role === "CANDIDATE" ? (
            <Link to="/careers/dashboard" className="cp-btn-ghost">My Applications</Link>
          ) : (
            <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
              <Link to="/careers/login" className="cp-btn-solid">Candidate Sign in</Link>
              <Link to="/login" className="cp-btn-ghost">HR / Manager Login</Link>
            </div>
          )}
        </div>
      </nav>

      <main className="cp-main">
        <Link to={user?.role === "CANDIDATE" ? "/careers/dashboard" : "/careers/roles"} className="linkbtn" style={{ display: "inline-flex", alignItems: "center", gap: 6, margin: "8px 0 16px" }}>
          <span style={{ transform: "rotate(180deg)", display: "inline-flex" }}><Icon path={Ic.arrow} size={14} /></span> {user?.role === "CANDIDATE" ? "Back to my dashboard" : "Back to all roles"}
        </Link>

        {q.isLoading ? (
          <div className="job-card" style={{ display: "grid", placeItems: "center", padding: 40 }}><InlineLoader label="Loading Role" /></div>
        ) : q.isError || !job ? (
          <div className="job-card" style={{ textAlign: "center", padding: 48 }}>
            <h3>Role not found</h3>
            <p className="blurb">This role is no longer open, or the link is invalid.</p>
            <button className="apply" style={{ marginTop: 16 }} onClick={() => navigate("/careers/roles")}>Browse open roles</button>
          </div>
        ) : (
          <>
            {/* header band */}
            <div className="jd-head">
              <div className="jd-head-main">
                <div className="jd-chips">
                  <span className="t" style={{ background: "var(--skysoft)", color: "var(--navy)", fontWeight: 700 }}>{jobCategory(job)}</span>
                  {job.department && <span className="t">{job.department}</span>}
                </div>
                <h1 className="jd-title">{job.title}</h1>
                <div className="jd-posted">{fmtPosted(job.posted_at)}</div>
                <div className="meta jd-facts">
                  <span><Icon path={Ic.pin} size={15} />{job.location}{job.wfh_allowed ? " · WFH allowed" : ""}</span>
                  <span><Icon path={Ic.brief} size={15} />{job.employment_type} · {job.min_experience_years}+ yrs</span>
                  {job.openings > 0 && <span><Icon path={Ic.users} size={15} />{job.openings} opening{job.openings === 1 ? "" : "s"}</span>}
                  {job.salary_range && <span><Icon path={Ic.award} size={15} />{job.salary_range}</span>}
                  {job.needed_by_date && <span><Icon path={Ic.clock} size={15} />Closes {new Date(job.needed_by_date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</span>}
                </div>
              </div>
              <span className="code jd-code">{job.job_code}</span>
            </div>

            <div className="jd-layout">
              <div className="jd-main">
                <div className="jd-panel">
                  <Section icon={Ic.doc} title="Job description">
                    {job.description
                      ? <p className="blurb" style={{ whiteSpace: "pre-wrap", fontSize: ".9rem", lineHeight: 1.6 }}>{job.description}</p>
                      : <p className="blurb">No description provided.</p>}
                  </Section>

                  {job.responsibilities.length > 0 && (
                    <Section icon={Ic.spark} title="What you'll do">
                      <ul style={{ margin: 0, paddingLeft: 18, fontSize: ".9rem", lineHeight: 1.7, color: "var(--ink-soft)" }}>
                        {job.responsibilities.map((r, i) => <li key={i}>{r}</li>)}
                      </ul>
                    </Section>
                  )}

                  <Section icon={Ic.check} title="Required skills">
                    {job.essential_skills.length > 0
                      ? <div className="tags">{job.essential_skills.map((s) => <span key={s} className="t" style={{ background: "var(--pos-soft)", color: "var(--pos)", fontWeight: 700 }}>{s}</span>)}</div>
                      : <p className="blurb">No specific required skills listed.</p>}
                  </Section>

                  {job.desired_skills.length > 0 && (
                    <Section icon={Ic.spark} title="Optional / nice-to-have skills">
                      <div className="tags">{job.desired_skills.map((s) => <span key={s} className="t">{s}</span>)}</div>
                    </Section>
                  )}

                  {job.education_qualification && (
                    <Section icon={Ic.brief} title="Eligibility">
                      <p className="blurb" style={{ fontSize: ".9rem" }}>{job.education_qualification}</p>
                    </Section>
                  )}
                </div>
              </div>

              {/* sticky apply rail */}
              <aside className="jd-side">
                <div className="jd-apply">
                  <div className="jd-apply-h">Ready to apply?</div>
                  <ul className="jd-facts-list">
                    <li><Icon path={Ic.pin} size={15} /><span>{job.location}{job.wfh_allowed ? " · WFH allowed" : ""}</span></li>
                    <li><Icon path={Ic.brief} size={15} /><span>{job.employment_type} · {job.min_experience_years}+ yrs</span></li>
                    {job.openings > 0 && <li><Icon path={Ic.users} size={15} /><span>{job.openings} opening{job.openings === 1 ? "" : "s"}</span></li>}
                    {job.salary_range && <li><Icon path={Ic.award} size={15} /><span>{job.salary_range}</span></li>}
                    {job.needed_by_date && <li><Icon path={Ic.clock} size={15} /><span>Closes {new Date(job.needed_by_date).toLocaleDateString(undefined, { day: "numeric", month: "short" })}</span></li>}
                  </ul>
                  <button className="apply" style={{ width: "100%", justifyContent: "center" }} onClick={onApply}>
                    {user?.role === "CANDIDATE" ? "Apply for this role" : "Apply now"} <Icon path={Ic.arrow} size={15} sw={2.2} />
                  </button>
                  <p className="blurb" style={{ margin: "12px 0 0", fontSize: ".78rem", textAlign: "center" }}>Applications reviewed within 3 days.</p>
                </div>
              </aside>
            </div>
          </>
        )}
      </main>

      <footer className="cp-foot">
        <div className="in">
          <BrandLogo tag="Careers" />
          <span>© 2026 TCG Digital · DataAlchemists ATS</span>
        </div>
      </footer>
    </div>
  );
}

function Section({ icon, title, children }: { icon: React.ReactNode; title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 22 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
        <span style={{ display: "inline-grid", placeItems: "center", height: 26, width: 26, borderRadius: 8, background: "var(--skysoft)", color: "var(--navy)" }}>
          <Icon path={icon} size={14} />
        </span>
        <b style={{ fontSize: ".95rem" }}>{title}</b>
      </div>
      {children}
    </section>
  );
}
