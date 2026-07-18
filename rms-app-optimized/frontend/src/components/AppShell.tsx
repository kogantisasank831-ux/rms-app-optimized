import { useIsFetching, useIsMutating, useMutation, useQueryClient } from "@tanstack/react-query";
import { type ReactNode, useEffect, useRef, useState } from "react";
import { Link, Navigate, Outlet, useLocation } from "react-router-dom";

import { getInsights, getMetrics } from "../api/endpoints/dashboard";
import { uploadMyPhoto } from "../api/endpoints/users";
import { useAuth } from "../auth/AuthContext";
import { useObjectUrl } from "../hooks/useObjectUrl";
import { Avatar } from "./Avatar";
import { BrandLoader } from "./BrandLoader";

interface NavItem {
  to: string;
  label: string;
  icon: ReactNode;
  roles?: string[];
  count?: number;
  section: "Overview" | "Hiring" | "Administration";
}

const I = {
  grid: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9">
      <rect x="3" y="3" width="7" height="8" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" />
      <rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="15" width="7" height="6" rx="1.5" />
    </svg>
  ),
  doc: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><rect x="4" y="4" width="16" height="16" rx="2" /><path d="M8 9h8M8 13h8M8 17h5" /></svg>,
  user: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><circle cx="12" cy="8" r="3.6" /><path d="M5 20a7 7 0 0 1 14 0" /></svg>,
  pipe: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><path d="M4 5v14M9.5 5v14M15 5v14M20.5 5v14" /></svg>,
  cal: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><rect x="3" y="4" width="18" height="17" rx="2" /><path d="M8 2v4M16 2v4M3 10h18" /></svg>,
  offer: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><path d="M7 3h7l5 5v13H7z" /><path d="M14 3v5h5" /></svg>,
  star: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><path d="M12 3l2.5 5 5.5.8-4 3.9.9 5.5L12 15.9 7.1 18.2l.9-5.5-4-3.9 5.5-.8z" /></svg>,
  shield: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.9"><path d="M12 3l8 3v6c0 4.6-3.1 7.7-8 9-4.9-1.3-8-4.4-8-9V6z" /></svg>,
};

const NAV: NavItem[] = [
  { to: "/", label: "Dashboard", icon: I.grid, section: "Overview" },
  { to: "/rrfs", label: "Requisitions", icon: I.doc, section: "Hiring", roles: ["ADMIN", "HR", "HIRING_MANAGER", "BU_HEAD"] },
  { to: "/candidates", label: "Candidates", icon: I.user, section: "Hiring", roles: ["ADMIN", "HR", "HIRING_MANAGER"] },
  { to: "/pipeline", label: "Pipeline", icon: I.pipe, section: "Hiring", roles: ["ADMIN", "HR", "HIRING_MANAGER"] },
  { to: "/interviews", label: "Interviews", icon: I.cal, section: "Hiring" },
  { to: "/offers", label: "Offers", icon: I.offer, section: "Hiring", roles: ["ADMIN", "HR", "HIRING_MANAGER"] },
  { to: "/admin/users", label: "Employees", icon: I.user, section: "Administration", roles: ["ADMIN"] },
  { to: "/admin/skills", label: "Skill Master", icon: I.star, section: "Administration", roles: ["ADMIN", "HR"] },
  { to: "/admin/audit", label: "Audit & AI Runs", icon: I.shield, section: "Administration", roles: ["ADMIN", "HR"] },
];

export function AppShell() {
  const { user, loading } = useAuth();
  const [collapsed, setCollapsed] = useState(false);
  const [editingPhoto, setEditingPhoto] = useState(false);
  const loc = useLocation();

  // Warm the Dashboard (Command Center) cache in the background from any staff page, so that
  // landing on / — whether it's the first page opened or a later navigation — renders instantly.
  // Deferred to browser idle; prefetchQuery is a no-op if the data is already fresh/in-flight.
  const qc = useQueryClient();
  const role = user?.role;
  useEffect(() => {
    if (!role || role === "CANDIDATE") return;
    const run = () => {
      void qc.prefetchQuery({ queryKey: ["metrics"], queryFn: getMetrics, staleTime: 30_000 });
      void qc.prefetchQuery({ queryKey: ["insights"], queryFn: getInsights, staleTime: 60_000 });
    };
    const w = window as Window & { requestIdleCallback?: (cb: () => void, o?: { timeout: number }) => number; cancelIdleCallback?: (id: number) => void };
    if (w.requestIdleCallback) {
      const id = w.requestIdleCallback(run, { timeout: 2000 });
      return () => w.cancelIdleCallback?.(id);
    }
    const t = setTimeout(run, 400);
    return () => clearTimeout(t);
  }, [role, qc]);

  if (loading) return <BrandLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: `${loc.pathname}${loc.search}` }} />;
  if (user.role === "CANDIDATE") return <Navigate to="/careers/dashboard" replace />;

  const visible = NAV.filter((n) => !n.roles || n.roles.includes(user.role));
  const sections: NavItem["section"][] = ["Overview", "Hiring", "Administration"];

  return (
    <div className={`shell${collapsed ? " collapsed" : ""}`}>
      <aside className="app-aside">
        <div className="aside-top">
          <div className="aside-glyph">
            <svg viewBox="0 0 24 24" fill="none">
              <path d="M4 8l8-4 8 4-8 4-8-4z" fill="#39acff" />
              <path d="M4 8v8l8 4v-8L4 8z" fill="#ffffff" opacity=".9" />
              <path d="M20 8v8l-8 4v-8l8-4z" fill="#8ed1fc" />
            </svg>
          </div>
          <div className="txt"><div className="aside-name">DataAlchemists ATS</div><div className="aside-sub">TCG Digital · RMS</div></div>
          <button className="aside-collapse" onClick={() => setCollapsed((c) => !c)} title={collapsed ? "Expand sidebar" : "Collapse sidebar"} aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M15 6l-6 6 6 6" /></svg>
          </button>
        </div>
        <nav className="aside-nav">
          {sections.map((sec) => {
            const items = visible.filter((n) => n.section === sec);
            if (!items.length) return null;
            return (
              <div key={sec}>
                <div className="nav-sec">{sec}</div>
                {items.map((n) => <NavLink key={n.to} item={n} />)}
              </div>
            );
          })}
        </nav>
        <button className="aside-user" onClick={() => setEditingPhoto(true)} title="Edit your profile photo">
          <Avatar name={user.full_name} src={user.photo_icon_url} className="av" size={34} />
          <div className="txt"><div className="nm">{user.full_name}</div><div className="rl">{roleLabel(user.role)}</div></div>
        </button>
      </aside>

      <div className="app-main">
        <Topbar />
        {/* Keep the outlet mounted across parameter changes; forced remounts reset page state and refetch data. */}
        <div className="route-view">
          <Outlet />
        </div>
        <footer className="app-footline">
          <span>Developed by <b>Data Alchemists (T-07)</b> for Hackathon 2026</span>
          <span>Team Members: Ankit, Deepankar, Manish, Sasank</span>
          <span>Data Science Competency&nbsp;|&nbsp;TCG Digital</span>
        </footer>
      </div>

      {editingPhoto && <ProfilePhotoModal onClose={() => setEditingPhoto(false)} />}
    </div>
  );
}

function ProfilePhotoModal({ onClose }: { onClose: () => void }) {
  const { user, refreshUser } = useAuth();
  const fileRef = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const preview = useObjectUrl(file);
  const [error, setError] = useState<string | null>(null);

  const m = useMutation({
    mutationFn: () => uploadMyPhoto(file!),
    onSuccess: async () => { await refreshUser(); onClose(); },
    onError: (e) => setError((e as { message?: string }).message ?? "Could not update your photo."),
  });

  function pick(f: File | null) {
    setError(null);
    setFile(f);
  }

  return (
    <div className="modal-overlay" onMouseDown={onClose}>
      <div className="modal" onMouseDown={(e) => e.stopPropagation()} style={{ maxWidth: 380 }}>
        <h3>Your profile photo</h3>
        <div className="sub" style={{ marginBottom: 16 }}>Shown as your avatar across the app. JPEG, PNG or WebP.</div>
        <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 14 }}>
          <Avatar name={user?.full_name ?? "U"} src={preview ?? user?.photo_url ?? user?.photo_icon_url} size={112} radius={20} />
          <button className="btn-ghost" onClick={() => fileRef.current?.click()}>{file ? "Choose a different photo" : "Choose a photo"}</button>
          <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" style={{ display: "none" }} onChange={(e) => pick(e.target.files?.[0] ?? null)} />
          {file && <div className="muted" style={{ fontSize: ".78rem" }}>{file.name}</div>}
        </div>
        {error && <p className="error-text">{error}</p>}
        <div className="row" style={{ justifyContent: "flex-end", marginTop: 18 }}>
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
          <button disabled={!file || m.isPending} onClick={() => m.mutate()}>{m.isPending ? "Saving…" : "Save photo"}</button>
        </div>
      </div>
    </div>
  );
}

function NavLink({ item }: { item: NavItem }) {
  const loc = useLocation();
  const active = item.to === "/" ? loc.pathname === "/" : loc.pathname.startsWith(item.to);
  return (
    <Link to={item.to} className={`nav-i${active ? " on" : ""}`}>
      {item.icon}
      <span className="lbl">{item.label}</span>
      {item.count != null && <span className="count">{item.count}</span>}
    </Link>
  );
}

function Topbar() {
  const { user, logout } = useAuth();
  return (
    <div className="app-topbar">
      <div className="app-topbar-in">
        <label className="app-search">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="11" cy="11" r="7" /><path d="M21 21l-4-4" /></svg>
          <input placeholder="Global search coming soon" disabled aria-label="Global search is not available yet" />
        </label>
        <div className="app-tright">
          <BackgroundActivity />
          <span className="badge">{user?.role}</span>
          <button className="iconbtn" title="Notifications are not available yet" disabled aria-label="Notifications are not available yet">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M6 8a6 6 0 0 1 12 0c0 7 3 8 3 8H3s3-1 3-8" /><path d="M10 21h4" /></svg>
          </button>
          <button className="iconbtn" onClick={logout} title="Log out">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8"><path d="M16 17l5-5-5-5M21 12H9M12 19H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2h7" /></svg>
          </button>
        </div>
      </div>
    </div>
  );
}

function BackgroundActivity() {
  // Mutations (agent runs, transitions, saves) get an explicit label;
  // background query refetches show a lighter "Syncing" state.
  const mutating = useIsMutating();
  const fetching = useIsFetching();
  if (mutating > 0) {
    return <span className="bg-activity"><span className="spin" />Working…</span>;
  }
  if (fetching > 0) {
    return <span className="bg-activity" style={{ background: "transparent" }}><span className="spin" />Syncing</span>;
  }
  return null;
}

function roleLabel(role: string): string {
  const m: Record<string, string> = {
    ADMIN: "Administrator", HR: "HR Recruiter", HIRING_MANAGER: "Hiring Manager",
    BU_HEAD: "BU Head", INTERVIEWER: "Interviewer", CANDIDATE: "Candidate",
  };
  return m[role] ?? role;
}
