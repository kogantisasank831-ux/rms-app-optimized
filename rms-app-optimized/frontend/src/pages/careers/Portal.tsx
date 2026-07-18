import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listJobs } from "../../api/endpoints/careers";
import { useAuth } from "../../auth/AuthContext";
import { BrandLogo, Ic, Icon } from "../../components/brand";
import { InlineLoader } from "../../components/InlineLoader";

function fmtPosted(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `Posted ${d.toLocaleDateString(undefined, { day: "numeric", month: "short" })}`;
}
function fmtDeadline(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  return `Closes ${d.toLocaleDateString(undefined, { day: "numeric", month: "short" })}`;
}

export default function Portal() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const q = useQuery({ queryKey: ["careers-jobs"], queryFn: listJobs });
  const jobs = q.data ?? [];
  const [query, setQuery] = useState("");
  const [loc, setLoc] = useState("All locations");
  const [dept, setDept] = useState("All roles");

  const depts = useMemo(() => ["All roles", ...Array.from(new Set(jobs.map((j) => j.department).filter(Boolean) as string[]))], [jobs]);
  const locations = useMemo(() => ["All locations", ...Array.from(new Set(jobs.map((j) => j.location).filter(Boolean)))], [jobs]);

  const filtered = useMemo(() => jobs.filter((j) =>
    (dept === "All roles" || j.department === dept) &&
    (loc === "All locations" || j.location === loc) &&
    (query.trim() === "" || `${j.title} ${j.tags.join(" ")} ${j.department ?? ""}`.toLowerCase().includes(query.trim().toLowerCase())),
  ), [jobs, dept, loc, query]);

  const onApply = (rrfId: string) => {
    if (user?.role === "CANDIDATE") navigate(`/careers/dashboard?apply=${rrfId}`);
    else navigate(`/careers/signup?job=${rrfId}`);
  };

  const openJob = (jobCode: string) => navigate(`/careers/jobs/${encodeURIComponent(jobCode)}`);

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

      <header className="cp-hero">
        <div className="ring" style={{ position: "absolute", width: 520, height: 520, right: -110, top: -110 }} />
        <div className="in">
          <div className="eyebrow anim"><i /> We're hiring <i /></div>
          <h1 className="anim" style={{ animationDelay: "120ms" }}>Do the best work of your career.<br /><span className="sky">Build what decides.</span></h1>
          <p className="anim" style={{ animationDelay: "200ms" }}>Join the team behind mcube — data science, engineering and consulting for the world's most demanding industries.</p>

          <div className="cp-search anim" style={{ animationDelay: "300ms" }}>
            <div className="cp-field f" style={{ borderRight: "1px solid var(--line-2)" }}>
              <Icon path={Ic.search} size={16} />
              <input placeholder="Search roles, skills…" value={query} onChange={(e) => setQuery(e.target.value)} />
            </div>
            <div className="f" style={{ maxWidth: 210 }}>
              <Icon path={Ic.pin} size={16} />
              <select value={loc} onChange={(e) => setLoc(e.target.value)}>{locations.map((l) => <option key={l}>{l}</option>)}</select>
            </div>
            <button className="go" onClick={() => { /* filter is live */ }}>Search</button>
          </div>

          <div className="cp-stats anim" style={{ animationDelay: "420ms" }}>
            <span><b>{jobs.length}</b>&nbsp;open roles</span>
            <span><b>{locations.length - 1}</b>&nbsp;locations</span>
            <span><b>{depts.length - 1}</b>&nbsp;teams</span>
          </div>
        </div>
      </header>

      <main className="cp-main">
        <div className="cp-filter anim" style={{ animationDelay: "480ms" }}>
          {depts.map((d) => (
            <button key={d} className={`chipbtn${dept === d ? " on" : ""}`} onClick={() => setDept(d)}>
              {d} <span style={{ opacity: .7, marginLeft: 4 }}>{d === "All roles" ? jobs.length : jobs.filter((j) => j.department === d).length}</span>
            </button>
          ))}
        </div>

        <div className="cp-count">
          <h2>{q.isLoading ? "Loading roles…" : `${filtered.length} open ${filtered.length === 1 ? "role" : "roles"}`}{dept !== "All roles" && <span style={{ color: "var(--ink-faint)" }}> · {dept}</span>}</h2>
          <span style={{ fontSize: ".78rem", color: "var(--ink-faint)" }}>Applications reviewed within <b style={{ color: "var(--ink-soft)" }}>3 days</b></span>
        </div>

        {q.isLoading ? (
          <div className="job-card" style={{ display: "grid", placeItems: "center", padding: 40 }}><InlineLoader label="Loading Roles" /></div>
        ) : filtered.length === 0 ? (
          <div className="job-card" style={{ textAlign: "center", padding: 48 }}>
            <h3>No roles match your search</h3>
            <p className="blurb">Try a different keyword, team or location — or check back soon.</p>
          </div>
        ) : (
          <div className="job-grid">
            {filtered.map((j) => (
              <div
                key={j.rrf_id}
                className="job-card"
                role="button"
                tabIndex={0}
                style={{ cursor: "pointer" }}
                onClick={() => openJob(j.job_code)}
                onKeyDown={(e) => { if (e.key === "Enter") openJob(j.job_code); }}
              >
                <div className="top">
                  <div>
                    {j.department && <span className="t" style={{ background: "var(--skysoft)", color: "var(--navy)", fontWeight: 700 }}>{j.department}</span>}
                    <h3>{j.title}</h3>
                    {j.blurb && <p className="blurb">{j.blurb}</p>}
                  </div>
                  <span className="code">{j.job_code}</span>
                </div>
                <div className="meta">
                  <span><Icon path={Ic.pin} size={14} />{j.location}{j.wfh_allowed ? " · WFH" : ""}</span>
                  <span><Icon path={Ic.brief} size={14} />{j.employment_type} · {j.min_experience_years}+ yrs</span>
                  {j.needed_by_date && <span><Icon path={Ic.clock} size={14} />{fmtDeadline(j.needed_by_date)}</span>}
                </div>
                {j.tags.length > 0 && <div className="tags">{j.tags.slice(0, 6).map((t) => <span key={t} className="t">{t}</span>)}</div>}
                <div className="foot">
                  <span className="posted">{fmtPosted(j.posted_at)}</span>
                  <div className="row" style={{ gap: 8 }}>
                    <button className="cp-btn-ghost" onClick={(e) => { e.stopPropagation(); openJob(j.job_code); }}>View details</button>
                    <button className="apply" onClick={(e) => { e.stopPropagation(); onApply(j.rrf_id); }}>Apply now <Icon path={Ic.arrow} size={14} sw={2.2} /></button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </main>

      <footer className="cp-foot">
        <div className="in">
          <BrandLogo tag="Careers" />
          <span>Sign up once — our agents screen your application and keep you posted at every step.</span>
          <span>© 2026 TCG Digital · DataAlchemists ATS</span>
        </div>
      </footer>
    </div>
  );
}
