// Shared brand chrome + icon set for the auth screens and career portal.
import type { ReactNode } from "react";

/**
 * Official TCG Digital site logo (gear-C + gold spark + "tcgdigital" wordmark),
 * sourced verbatim from tcgdigital.com. Full-color variant for light backgrounds;
 * pass `white` for dark backgrounds. Used in the careers navigation bars.
 */
export function TcgLogo({ white = false, className = "" }: { white?: boolean; className?: string }) {
  const src = white ? "/brand/tcg-logo-white.webp" : "/brand/tcg-logo-fullcolor.webp";
  return <img className={`tcg-site-logo ${className}`.trim()} src={src} alt="TCG Digital" />;
}

export function BrandLogo({ dark = false, tag = "Agentic ATS" }: { dark?: boolean; tag?: string }) {
  return (
    <div className={`brand-logo${dark ? " on-dark" : ""}`}>
      <div className="glyph">
        <svg viewBox="0 0 24 24" fill="none">
          <path d="M4 8l8-4 8 4-8 4-8-4z" fill="#39acff" />
          <path d="M4 8v8l8 4v-8L4 8z" fill="#ffffff" opacity=".9" />
          <path d="M20 8v8l-8 4v-8l8-4z" fill="#8ed1fc" />
        </svg>
      </div>
      <div>
        <div className="wm">DataAlchemists <span className="sky">ATS</span></div>
        <div className="tag">{tag}</div>
      </div>
    </div>
  );
}

export const Ic = {
  mail: <path d="M4 4h16a2 2 0 012 2v12a2 2 0 01-2 2H4a2 2 0 01-2-2V6a2 2 0 012-2zM22 6l-10 7L2 6" />,
  lock: <><path d="M19 11H5a2 2 0 00-2 2v7a2 2 0 002 2h14a2 2 0 002-2v-7a2 2 0 00-2-2z" /><path d="M7 11V7a5 5 0 0110 0v4" /></>,
  user: <><circle cx="12" cy="8" r="3.6" /><path d="M5 20a7 7 0 0114 0" /></>,
  eye: <><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" /></>,
  eyeOff: <><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19M14.12 14.12a3 3 0 11-4.24-4.24M1 1l22 22" /></>,
  arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
  users: <><path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2" /><circle cx="9" cy="7" r="4" /><path d="M23 21v-2a4 4 0 00-3-3.87M16 3.13a4 4 0 010 7.75" /></>,
  brief: <><rect x="2" y="7" width="20" height="14" rx="2" /><path d="M16 21V5a2 2 0 00-2-2h-4a2 2 0 00-2 2v16" /></>,
  doc: <><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" /><path d="M14 2v6h6M9 15h6M9 11h2" /></>,
  award: <><circle cx="12" cy="8" r="6" /><path d="M8.21 13.89L7 23l5-3 5 3-1.21-9.12" /></>,
  x: <path d="M18 6L6 18M6 6l12 12" />,
  spark: <path d="M12 3l1.9 5.7a1 1 0 00.63.63L20 11l-5.7 1.9a1 1 0 00-.63.63L12 19l-1.9-5.7a1 1 0 00-.63-.63L4 11l5.7-1.9a1 1 0 00.63-.63L12 3z" />,
  video: <><path d="M23 7l-7 5 7 5V7z" /><rect x="1" y="5" width="15" height="14" rx="2" /></>,
  pin: <><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0118 0z" /><circle cx="12" cy="10" r="3" /></>,
  clock: <><circle cx="12" cy="12" r="10" /><path d="M12 6v6l4 2" /></>,
  search: <><circle cx="11" cy="11" r="8" /><path d="M21 21l-4.35-4.35" /></>,
  check: <path d="M20 6L9 17l-5-5" />,
  upload: <><path d="M21 15v4a2 2 0 01-2 2H5a2 2 0 01-2-2v-4" /><path d="M17 8l-5-5-5 5M12 3v12" /></>,
};

export function Icon({ path, size = 18, sw = 1.8 }: { path: ReactNode; size?: number; sw?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor"
      strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round">{path}</svg>
  );
}

const FEED = [
  { icon: Ic.doc, name: "JD Agent", line: "Drafted JD + rubric for Req #211" },
  { icon: Ic.spark, name: "Matcher Agent", line: "Ranked 118 applicants · 3 ready to shortlist" },
  { icon: Ic.video, name: "Evaluation Agent", line: "Interview feedback ready for Sneha Das" },
];

// Feature + trust glyphs for the candidate panel (kept local so the marketing FEED stays separate).
const CIc = {
  doc: <><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6z" /><path d="M14 2v6h6M9 15h6M9 11h4" /></>,
  chart: <><path d="M3 3v18h18" /><path d="M7 15l4-5 3 3 5-7" /></>,
  bell: <><path d="M18 8a6 6 0 00-12 0c0 7-3 9-3 9h18s-3-2-3-9" /><path d="M13.7 21a2 2 0 01-3.4 0" /></>,
  shield: <path d="M12 2l8 3v6c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V5l8-3z" />,
  shieldCheck: <><path d="M12 2l8 3v6c0 5-3.4 8.5-8 10-4.6-1.5-8-5-8-10V5l8-3z" /><path d="M9 12l2 2 4-4" /></>,
  userPlus: <><circle cx="9" cy="8" r="3.4" /><path d="M3 20a6 6 0 0112 0" /><path d="M18 8v6M15 11h6" /></>,
};

const CAREER_FEATURES = [
  { icon: CIc.doc, title: "Apply with ease", line: "Find and apply to roles that match your skills." },
  { icon: CIc.chart, title: "Track your progress", line: "Monitor your applications in real time." },
  { icon: CIc.bell, title: "Stay updated", line: "Get notified about interviews, offers and updates." },
];

const CAREER_TRUST = [
  { icon: CIc.shield, top: "Secure &", bot: "Private" },
  { icon: CIc.shieldCheck, top: "Trusted by", bot: "Top Companies" },
  { icon: CIc.userPlus, top: "100% Free to", bot: "Create Account" },
];

/**
 * Candidate-facing brand panel. No mention of internal AI agents / recruiter tooling —
 * the messaging is about the applicant's own journey. A full-bleed animated SVG scene
 * (city skyline, glowing path, a figure walking toward an open doorway) sits behind the copy.
 */
export function CareersBrandPanel() {
  return (
    <div className="auth-brand careers-brand">
      <CareersJourneyScene />
      <div className="cb-scrim" />

      <div className="anim" style={{ position: "relative", zIndex: 1 }}><BrandLogo dark tag="Careers" /></div>

      <div style={{ position: "relative", zIndex: 1, maxWidth: "26rem" }}>
        <h1 className="anim" style={{ animationDelay: "160ms" }}>
          Your career journey<br /><span className="sky">starts here.</span>
        </h1>
        <p className="lede anim" style={{ animationDelay: "260ms" }}>
          Create your candidate profile, track your applications, and get one step closer to your dream role.
        </p>

        <div className="cb-features">
          {CAREER_FEATURES.map((f, i) => (
            <div key={f.title} className="cb-feat anim" style={{ animationDelay: `${380 + i * 120}ms` }}>
              <span className="cb-feat-ic"><Icon path={f.icon} size={18} sw={1.8} /></span>
              <div>
                <div className="cb-feat-t">{f.title}</div>
                <div className="cb-feat-l">{f.line}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ position: "relative", zIndex: 1, display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 18, flexWrap: "wrap" }}>
        <div className="cb-privacy anim" style={{ animationDelay: "820ms" }}>
          <Icon path={CIc.shield} size={18} sw={1.7} />
          <span>Your data is secure with us.<br />We respect your privacy.</span>
        </div>
        <div className="cb-quote anim" style={{ animationDelay: "760ms" }}>
          <span className="cb-quote-mark">“</span>
          <p>Opportunities don't happen.<br />You create them.</p>
        </div>
      </div>
    </div>
  );
}

const TEAM_FEATURES = [
  { icon: CIc.doc, title: "Manage requisitions", line: "Create, approve and track open roles end to end." },
  { icon: CIc.chart, title: "Move candidates forward", line: "Screen, shortlist and advance applicants in one pipeline." },
  { icon: CIc.bell, title: "Interview & decide", line: "Schedule panels, capture feedback and release offers." },
];

/**
 * Staff brand panel — ONE sign-in for the whole hiring team (HR, Hiring Manager, BU Head,
 * Interviewer, Admin). Reuses the animated journey scene with team-oriented copy.
 */
export function StaffBrandPanel() {
  return (
    <div className="auth-brand careers-brand">
      <CareersJourneyScene />
      <div className="cb-scrim" />

      <div className="anim" style={{ position: "relative", zIndex: 1 }}><BrandLogo dark tag="Hiring Team" /></div>

      <div style={{ position: "relative", zIndex: 1, maxWidth: "26rem" }}>
        <h1 className="anim" style={{ animationDelay: "160ms" }}>
          Hiring, all in<br /><span className="sky">one place.</span>
        </h1>
        <p className="lede anim" style={{ animationDelay: "260ms" }}>
          One sign-in for the whole hiring team — requisitions, candidates, interviews and offers, with every decision audited.
        </p>

        <div className="cb-features">
          {TEAM_FEATURES.map((f, i) => (
            <div key={f.title} className="cb-feat anim" style={{ animationDelay: `${380 + i * 120}ms` }}>
              <span className="cb-feat-ic"><Icon path={f.icon} size={18} sw={1.8} /></span>
              <div>
                <div className="cb-feat-t">{f.title}</div>
                <div className="cb-feat-l">{f.line}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div style={{ position: "relative", zIndex: 1, display: "flex", alignItems: "flex-end", justifyContent: "space-between", gap: 18, flexWrap: "wrap" }}>
        <div className="cb-privacy anim" style={{ animationDelay: "820ms" }}>
          <Icon path={CIc.shieldCheck} size={18} sw={1.7} />
          <span>Role-based access.<br />Every action audited.</span>
        </div>
        <div className="cb-quote anim" style={{ animationDelay: "760ms" }}>
          <span className="cb-quote-mark">“</span>
          <p>AI recommends.<br />Humans decide.</p>
        </div>
      </div>
    </div>
  );
}

/** Trust-badge row for candidate forms (matches the reference footer). */
export function CareersTrustRow() {
  return (
    <div className="cb-trust-row anim" style={{ animationDelay: "500ms" }}>
      {CAREER_TRUST.map((t) => (
        <div key={t.bot} className="cb-trust-i">
          <Icon path={t.icon} size={16} sw={1.7} />
          <span>{t.top}<br />{t.bot}</span>
        </div>
      ))}
    </div>
  );
}

/**
 * Animated hero scene (pure SVG + SMIL, no external assets):
 * twinkling stars, a city skyline, a glowing winding path leading to an open doorway,
 * a backpacked figure walking the path, glowing footsteps and floating job badges.
 * Rendered full-bleed behind the panel content.
 */
function CareersJourneyScene() {
  const SKY = "#39acff";
  const LIGHT = "#bfe4ff";
  // Hand-placed stars so we don't depend on Math.random.
  const stars = [
    [70, 60], [140, 40], [210, 90], [300, 50], [360, 120], [430, 70], [500, 140],
    [540, 60], [110, 150], [260, 30], [470, 200], [560, 240], [90, 250], [520, 320],
    [40, 120], [330, 180], [560, 30], [180, 210], [400, 40], [250, 130],
  ];
  const steps = [
    [258, 560], [286, 512], [320, 468], [354, 428], [388, 392], [416, 360],
  ];
  return (
    <svg className="cb-scene" viewBox="0 0 600 720" preserveAspectRatio="xMidYMid slice"
      role="img" aria-label="A figure walking a glowing path toward an open doorway over a city skyline">
      <defs>
        <linearGradient id="cb-door" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0" stopColor="#ffffff" /><stop offset="1" stopColor={SKY} />
        </linearGradient>
        <linearGradient id="cb-path" x1="0" y1="1" x2="0" y2="0">
          <stop offset="0" stopColor="rgba(57,172,255,.05)" />
          <stop offset="1" stopColor="rgba(150,215,255,.55)" />
        </linearGradient>
        <radialGradient id="cb-glow" cx="0.5" cy="0.5" r="0.5">
          <stop offset="0" stopColor="rgba(150,215,255,.9)" />
          <stop offset="1" stopColor="rgba(57,172,255,0)" />
        </radialGradient>
        <filter id="cb-blur" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="6" />
        </filter>
      </defs>

      {/* stars */}
      {stars.map(([x, y], i) => (
        <circle key={i} cx={x} cy={y} r={i % 3 === 0 ? 1.6 : 1} fill="#dff0ff">
          <animate attributeName="opacity" values="0.15;1;0.15" dur={`${2.4 + (i % 5) * 0.6}s`}
            begin={`${(i % 7) * 0.4}s`} repeatCount="indefinite" />
        </circle>
      ))}

      {/* city skyline */}
      <g fill="#0c2440" opacity=".85">
        {[[70, 260, 40], [115, 220, 46], [165, 300, 34], [205, 190, 52], [262, 250, 44],
          [312, 210, 60], [378, 268, 40], [424, 224, 54], [482, 300, 40], [524, 246, 56]]
          .map(([x, h, w], i) => <rect key={i} x={x} y={330 - h} width={w} height={h + 60} />)}
      </g>
      <line x1="0" y1="330" x2="600" y2="330" stroke="rgba(57,172,255,.18)" />

      {/* doorway + glow */}
      <ellipse cx="373" cy="255" rx="70" ry="90" fill="url(#cb-glow)" filter="url(#cb-blur)">
        <animate attributeName="opacity" values="0.55;0.95;0.55" dur="3.4s" repeatCount="indefinite" />
      </ellipse>
      <path d="M352 330 V196 a21 21 0 0 1 42 0 V330 Z" fill="#07182b" stroke="rgba(150,215,255,.5)" strokeWidth="2" />
      <path d="M373 330 V188 a17 17 0 0 1 17 8 V330 Z" fill="url(#cb-door)">
        <animate attributeName="opacity" values="0.8;1;0.8" dur="3.4s" repeatCount="indefinite" />
      </path>
      {/* light beam onto the path */}
      <path d="M360 330 L250 720 L470 720 L392 330 Z" fill="rgba(150,215,255,.10)">
        <animate attributeName="opacity" values="0.06;0.16;0.06" dur="3.4s" repeatCount="indefinite" />
      </path>

      {/* glowing path ribbon */}
      <path d="M236 720 C 250 610 300 545 352 495 C 398 450 420 405 424 336 L 452 336
               C 452 402 452 470 476 545 C 504 625 372 660 340 720 Z"
        fill="url(#cb-path)" stroke="rgba(150,215,255,.35)" strokeWidth="1" />
      {/* flowing centerline */}
      <path d="M300 716 C 310 620 350 560 388 512 C 420 470 436 420 438 340"
        fill="none" stroke={LIGHT} strokeWidth="2.4" strokeLinecap="round" opacity=".7"
        strokeDasharray="10 14">
        <animate attributeName="stroke-dashoffset" from="48" to="0" dur="1.6s" repeatCount="indefinite" />
      </path>

      {/* footsteps */}
      {steps.map(([x, y], i) => (
        <ellipse key={i} cx={x} cy={y} rx="7" ry="3.4" fill={LIGHT}
          transform={`rotate(-32 ${x} ${y})`}>
          <animate attributeName="opacity" values="0.15;0.9;0.15" dur="2.4s"
            begin={`${i * 0.35}s`} repeatCount="indefinite" />
        </ellipse>
      ))}

      {/* walking figure with backpack */}
      <g transform="translate(300 496)">
        <animateTransform attributeName="transform" type="translate" values="300 496; 300 492; 300 496"
          dur="1.2s" repeatCount="indefinite" additive="sum" />
        {/* backpack */}
        <rect x="-9" y="10" width="15" height="22" rx="6" fill="#0a2036" stroke="rgba(150,215,255,.35)" strokeWidth="1" />
        {/* legs (subtle stride) */}
        <rect x="4" y="34" width="6.5" height="30" rx="3.2" fill="#08182a">
          <animateTransform attributeName="transform" type="rotate" values="8 7 36;-10 7 36;8 7 36" dur="1.2s" repeatCount="indefinite" />
        </rect>
        <rect x="11" y="34" width="6.5" height="30" rx="3.2" fill="#0a2036">
          <animateTransform attributeName="transform" type="rotate" values="-10 14 36;8 14 36;-10 14 36" dur="1.2s" repeatCount="indefinite" />
        </rect>
        {/* torso + head */}
        <rect x="3" y="8" width="15" height="30" rx="7" fill="#0b2138" stroke="rgba(150,215,255,.4)" strokeWidth="1" />
        <circle cx="11" cy="0" r="8.5" fill="#0b2138" stroke="rgba(150,215,255,.4)" strokeWidth="1" />
        {/* arm */}
        <rect x="14" y="12" width="5.5" height="20" rx="2.75" fill="#08182a">
          <animateTransform attributeName="transform" type="rotate" values="-12 16 14;10 16 14;-12 16 14" dur="1.2s" repeatCount="indefinite" />
        </rect>
        {/* rim light */}
        <path d="M11 -8 a8.5 8.5 0 0 1 0 17 M18 10 v26" fill="none" stroke={LIGHT} strokeWidth="1.4" strokeLinecap="round" opacity=".55" />
      </g>

      {/* floating job badges */}
      {[[200, 372, 4], [452, 418, 5.2], [356, 300, 4.6]].map(([cx, cy, dur], i) => (
        <g key={i}>
          <animateTransform attributeName="transform" type="translate" values="0 0;0 -9;0 0"
            dur={`${dur}s`} begin={`${i * 0.5}s`} repeatCount="indefinite" additive="sum" />
          <circle cx={cx} cy={cy} r="21" fill="rgba(12,36,64,.85)" stroke="rgba(57,172,255,.4)" strokeWidth="1.4" />
          {i === 1 ? (
            <g transform={`translate(${cx - 8} ${cy - 8})`} fill="none" stroke={LIGHT} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="6" cy="5" r="3" /><path d="M1 15a5 5 0 0 1 10 0" /><path d="M12 3.5a3 3 0 0 1 0 5M11 15a5 5 0 0 0-3-4.6" />
            </g>
          ) : (
            <g transform={`translate(${cx - 8} ${cy - 7})`} fill="none" stroke={LIGHT} strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
              <rect x="0.5" y="4" width="15" height="11" rx="2" /><path d="M5 4V2.5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2V4" />
            </g>
          )}
        </g>
      ))}
    </svg>
  );
}

export function BrandPanel() {
  return (
    <div className="auth-brand">
      <div className="ring" style={{ width: 480, height: 480, right: -96, top: -96 }} />
      <div className="ring" style={{ width: 360, height: 360, left: -120, bottom: -120 }} />
      <div className="anim" style={{ position: "relative" }}><BrandLogo dark /></div>

      <div style={{ position: "relative", maxWidth: "30rem" }}>
        <div className="eyebrow anim" style={{ animationDelay: "120ms" }}><i /> Recruitment Intelligence</div>
        <h1 className="anim" style={{ animationDelay: "200ms" }}>
          Hiring that runs itself.<br /><span className="sky">Decisions that stay yours.</span>
        </h1>
        <p className="lede anim" style={{ animationDelay: "300ms" }}>
          Five AI agents parse, score, schedule and draft across your entire hiring funnel —
          pausing for your approval at every decision that matters.
        </p>
        <div className="agent-feed">
          {FEED.map((a, i) => (
            <div key={a.name} className="agent-row anim" style={{ animationDelay: `${480 + i * 120}ms` }}>
              <span className="ic"><Icon path={a.icon} size={16} sw={2} /></span>
              <div style={{ minWidth: 0 }}>
                <div className="nm">{a.name} <span className="dot pulse-dot" /></div>
                <div className="ln">{a.line}</div>
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="foot anim" style={{ animationDelay: "860ms" }}>
        <span>Every AI decision audited</span><span>·</span><span>AI recommends, humans decide</span>
      </div>
    </div>
  );
}
