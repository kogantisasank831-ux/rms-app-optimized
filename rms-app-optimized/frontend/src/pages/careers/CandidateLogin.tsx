import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import type { ApiError } from "../../api/client";
import { useAuth } from "../../auth/AuthContext";
import { CareersBrandPanel, Ic, Icon } from "../../components/brand";

export default function CandidateLogin() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const job = params.get("job");
  const { login, logout } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null); setSubmitting(true);
    try {
      const u = await login(email, password);
      if (u.role !== "CANDIDATE") { logout(); setError("This is the candidate portal. Please use the HR / Manager login."); return; }
      navigate(job ? `/careers/dashboard?apply=${job}` : "/careers/dashboard", { replace: true });
    } catch (err) {
      setError((err as ApiError).message ?? "Sign in failed");
    } finally { setSubmitting(false); }
  }

  return (
    <div className="auth-split">
      <CareersBrandPanel />
      <div className="auth-panel">
        <div className="inner">
          <div className="auth-form">
            <div className="anim">
              <h2>Welcome back</h2>
              <p className="sub">Sign in to track your applications, interviews and offers.</p>
            </div>

            <form onSubmit={onSubmit} style={{ marginTop: 20 }}>
              <div className="anim" style={{ marginBottom: 14 }}>
                <label>Email</label>
                <div className="auth-field"><Icon path={Ic.mail} size={16} />
                  <input type="email" value={email} autoComplete="username" onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required /></div>
              </div>
              <div className="anim" style={{ marginBottom: 16 }}>
                <label>Password</label>
                <div className="auth-field"><Icon path={Ic.lock} size={16} />
                  <input type={show ? "text" : "password"} value={password} autoComplete="current-password" onChange={(e) => setPassword(e.target.value)} placeholder="••••••••" required />
                  <button type="button" className="toggle" onClick={() => setShow(!show)}><Icon path={show ? Ic.eyeOff : Ic.eye} size={16} /></button></div>
              </div>

              {error && <p className="error-text" style={{ marginTop: 0 }}>{error}</p>}

              <button type="submit" className="auth-primary" disabled={submitting}>
                {submitting ? "Signing in…" : <>Sign in <Icon path={Ic.arrow} size={16} sw={2.2} /></>}
              </button>
            </form>

            <p className="auth-alt">New here? <Link to={`/careers/signup${job ? `?job=${job}` : ""}`}>Create a candidate account</Link></p>
            <p className="auth-alt" style={{ marginTop: 6 }}><Link to="/careers/roles">← Back to open roles</Link></p>
          </div>
        </div>
        <footer className="auth-footer">© 2026 TCG Digital · DataAlchemists ATS</footer>
      </div>
    </div>
  );
}
