import { type FormEvent, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import type { ApiError } from "../api/client";
import { useAuth } from "../auth/AuthContext";
import { Ic, Icon, StaffBrandPanel } from "../components/brand";

export default function Login() {
  const { login, user } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (user) return <Navigate to={user.role === "CANDIDATE" ? "/careers/dashboard" : "/"} replace />;

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      const u = await login(email, password);
      if (u.role === "CANDIDATE") { navigate("/careers/dashboard", { replace: true }); return; }
      const dest = (location.state as { from?: string } | null)?.from ?? "/";
      navigate(dest, { replace: true });
    } catch (err) {
      setError((err as ApiError).message ?? "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-split">
      <StaffBrandPanel />
      <div className="auth-panel">
        <div className="inner">
          <div className="auth-form">
            <div className="anim" style={{ animationDelay: "150ms" }}>
              <h2>Welcome back</h2>
              <p className="sub">One sign-in for the hiring team — HR, Hiring Managers, BU Heads, Interviewers and Admins.</p>
            </div>

            <form onSubmit={onSubmit} style={{ marginTop: 20 }}>
              <div className="anim" style={{ animationDelay: "320ms", marginBottom: 14 }}>
                <label>Work email</label>
                <div className="auth-field">
                  <Icon path={Ic.mail} size={16} />
                  <input type="text" value={email} autoComplete="username" placeholder="you@tcgdigital.com" onChange={(e) => setEmail(e.target.value)} required />
                </div>
              </div>
              <div className="anim" style={{ animationDelay: "400ms", marginBottom: 16 }}>
                <label>Password</label>
                <div className="auth-field">
                  <Icon path={Ic.lock} size={16} />
                  <input type={show ? "text" : "password"} value={password} autoComplete="current-password" placeholder="••••••••" onChange={(e) => setPassword(e.target.value)} required />
                  <button type="button" className="toggle" onClick={() => setShow(!show)} aria-label="Toggle password"><Icon path={show ? Ic.eyeOff : Ic.eye} size={16} /></button>
                </div>
              </div>

              {error && <p className="error-text" style={{ marginTop: 0 }}>{error}</p>}

              <button type="submit" className="auth-primary anim" style={{ animationDelay: "500ms" }} disabled={submitting}>
                {submitting ? "Signing in…" : <>Sign in to Dashboard <Icon path={Ic.arrow} size={16} sw={2.2} /></>}
              </button>
            </form>

            <div className="auth-sep anim" style={{ animationDelay: "580ms" }}><span /><b>or</b><span /></div>

            <p className="auth-alt anim" style={{ animationDelay: "640ms" }}>
              Looking for a job? <Link to="/careers/roles">Browse open roles →</Link><br />
              <span style={{ fontSize: ".78rem" }}>Candidate? <Link to="/careers/login">Sign in to your applications</Link></span>
            </p>
          </div>
        </div>
        <footer className="auth-footer">© 2026 TCG Digital · DataAlchemists ATS · AI recommends, humans decide</footer>
      </div>
    </div>
  );
}
