import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { listJobs } from "../../api/endpoints/careers";
import { useAuth } from "../../auth/AuthContext";
import { TcgLogo } from "../../components/brand";
import { CareersLoaderMark } from "./CareersLoaderMark";

/**
 * Public careers landing page.
 *
 * Shows the branded TCG Digital careers loader animation, then reveals a hero
 * with two entry points — "Search open roles" (the careers dashboard at
 * /careers/roles) and "Candidate login / Sign up". While the loader animates we
 * prefetch the open-roles list into the query cache, so the careers dashboard
 * ("this page") is already loading in the background and opens instantly.
 *
 * The loader SVG mark + its scoped keyframes are injected verbatim from the
 * approved mockup (mockups/tcgdigital-careers-loader.html).
 */

const MESSAGES = [
  "Preparing your career experience",
  "Discovering teams and opportunities",
  "Connecting talent with possibility",
  "Almost ready",
];

const MIN_DURATION = 900;
const EXIT_DURATION = 580;

export default function Landing() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { user } = useAuth();

  const [showIntro] = useState(() => sessionStorage.getItem("rms:careers-intro-seen") !== "1");
  const [ready, setReady] = useState(!showIntro); // hero revealed
  const [leaving, setLeaving] = useState(false); // loader fading out
  const [hidden, setHidden] = useState(!showIntro); // loader removed from flow
  const [msgIndex, setMsgIndex] = useState(0);
  const [swap, setSwap] = useState(false);

  useEffect(() => {
    void queryClient.prefetchQuery({ queryKey: ["careers-jobs"], queryFn: listJobs });
    if (!showIntro) return;

    sessionStorage.setItem("rms:careers-intro-seen", "1");
    let swapTimer: ReturnType<typeof setTimeout> | null = null;
    const rotation = setInterval(() => {
      setSwap(true);
      if (swapTimer) clearTimeout(swapTimer);
      swapTimer = setTimeout(() => {
        setMsgIndex((i) => (i + 1) % MESSAGES.length);
        setSwap(false);
      }, 200);
    }, 900);

    const revealT = setTimeout(() => {
      clearInterval(rotation);
      setLeaving(true);
      setReady(true);
    }, MIN_DURATION);
    const hideT = setTimeout(() => setHidden(true), MIN_DURATION + EXIT_DURATION + 40);

    return () => {
      clearInterval(rotation);
      clearTimeout(revealT);
      clearTimeout(hideT);
      if (swapTimer) clearTimeout(swapTimer);
    };
  }, [queryClient, showIntro]);

  const goRoles = () => navigate("/careers/roles");
  const goAuth = () => navigate(user?.role === "CANDIDATE" ? "/careers/dashboard" : "/careers/login");

  return (
    <div className="lp">
      {!hidden && (
        <div className={`lp-loader${leaving ? " leaving" : ""}`} role="status" aria-live="polite">
          <div className="lp-loader-inner">
            <CareersLoaderMark />
            <div className="lp-wordmark">tcg<span>digital</span></div>
            <h1 className="lp-title">Find work that moves ideas forward</h1>
            <div className="lp-msg-wrap">
              <p className={`lp-msg${swap ? " swap" : ""}`}>{MESSAGES[msgIndex]}</p>
            </div>
            <div className="lp-progress" aria-hidden="true" />
          </div>
          <span className="sr-only">Loading the TCG Digital careers experience</span>
        </div>
      )}

      <main className={`lp-app${ready ? " ready" : ""}`} aria-hidden={ready ? undefined : true}>
        <header className="lp-header">
          <Link to="/careers" className="lp-brand" aria-label="TCG Digital Careers home"><TcgLogo /><span className="lp-brand-tag">Careers</span></Link>
          <nav className="lp-nav">
            <Link to="/careers/roles">Open roles</Link>
            {user?.role === "CANDIDATE" ? (
              <Link to="/careers/dashboard" className="lp-nav-btn">My applications</Link>
            ) : (
              <>
                <Link to="/careers/login" className="lp-nav-btn ghost">Candidate sign in</Link>
                <Link to="/login" className="lp-nav-link">HR / Manager login</Link>
              </>
            )}
          </nav>
        </header>

        <section className="lp-hero">
          <div className="lp-hero-copy">
            <div className="lp-eyebrow">Build what comes next</div>
            <h1>Your ideas can shape intelligent enterprises.</h1>
            <p>
              Join people who turn data, engineering, and AI into meaningful outcomes for
              organizations around the world. Search live openings or sign in to track your journey.
            </p>
            <div className="lp-actions">
              <button className="lp-btn" onClick={goRoles}>Search open roles</button>
              <button className="lp-btn secondary" onClick={goAuth}>
                {user?.role === "CANDIDATE" ? "My applications" : "Candidate login / Sign up"}
              </button>
            </div>
          </div>

          <div className="lp-visual">
            <article className="lp-jobcard" role="button" tabIndex={0} onClick={goRoles}
              onKeyDown={(e) => { if (e.key === "Enter") goRoles(); }}>
              <small>FEATURED ROLE</small>
              <h3>AI Solutions Engineer</h3>
              <p>Design production-grade AI systems that connect enterprise context, data, and action.</p>
              <div className="lp-tags">
                <span>Generative AI</span><span>Python</span><span>Cloud</span>
              </div>
              <div className="lp-jobmeta">
                <span>Kolkata · Hybrid</span>
                <span>View role →</span>
              </div>
            </article>
          </div>
        </section>
      </main>
    </div>
  );
}
