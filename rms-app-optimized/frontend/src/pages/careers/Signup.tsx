import { type FormEvent, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

import type { ApiError } from "../../api/client";
import { signupCandidate } from "../../api/endpoints/careers";
import { useAuth } from "../../auth/AuthContext";
import { Avatar } from "../../components/Avatar";
import { CareersBrandPanel, CareersTrustRow, Ic, Icon } from "../../components/brand";
import { useObjectUrl } from "../../hooks/useObjectUrl";

export default function Signup() {
  const navigate = useNavigate();
  const [params] = useSearchParams();
  const job = params.get("job");
  const { setSession } = useAuth();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [cv, setCv] = useState<File | null>(null);
  const [photo, setPhoto] = useState<File | null>(null);
  const photoUrl = useObjectUrl(photo);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  function pickPhoto(f: File | null) {
    setPhoto(f);
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    if (!cv) { setError("Please attach your resume (PDF or DOCX)."); return; }
    setError(null); setSubmitting(true);
    try {
      const res = await signupCandidate({ full_name: fullName, email, password, phone: phone || undefined, cv, photo });
      setSession(res.access_token, res.user);
      navigate(job ? `/careers/dashboard?apply=${job}` : "/careers/dashboard", { replace: true });
    } catch (err) {
      setError((err as ApiError).message ?? "Could not create your account.");
    } finally { setSubmitting(false); }
  }

  return (
    <div className="auth-split">
      <CareersBrandPanel />
      <div className="auth-panel">
        <div className="inner">
          <div className="auth-form">
            <div className="anim">
              <h2>Create your candidate account</h2>
              <p className="sub">{job ? "One quick step, then your application goes straight in." : "It takes less than a minute."}</p>
            </div>

            <form onSubmit={onSubmit} style={{ marginTop: 20 }}>
              <div className="anim" style={{ display: "flex", alignItems: "center", gap: 14, marginBottom: 14 }}>
                <Avatar name={fullName || "You"} src={photoUrl} size={58} radius={16} />
                <div style={{ minWidth: 0 }}>
                  <label style={{ marginBottom: 4 }}>Profile photo (optional)</label>
                  <label style={{ cursor: "pointer", display: "inline-flex", alignItems: "center", gap: 7, fontSize: ".82rem", fontWeight: 600, color: "var(--accent)" }}>
                    <Icon path={Ic.upload} size={15} />{photo ? "Change photo" : "Add a photo"}
                    <input type="file" accept="image/png,image/jpeg,image/webp" style={{ display: "none" }} onChange={(e) => pickPhoto(e.target.files?.[0] ?? null)} />
                  </label>
                  {photo && <div style={{ fontSize: ".74rem", color: "var(--ink-faint)", marginTop: 2, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{photo.name}</div>}
                </div>
              </div>
              <div className="anim" style={{ marginBottom: 12 }}>
                <label>Full name</label>
                <div className="auth-field"><Icon path={Ic.user} size={16} />
                  <input value={fullName} onChange={(e) => setFullName(e.target.value)} placeholder="Enter your full name" required /></div>
              </div>
              <div className="anim" style={{ marginBottom: 12 }}>
                <label>Email</label>
                <div className="auth-field"><Icon path={Ic.mail} size={16} />
                  <input type="email" value={email} autoComplete="username" onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" required /></div>
              </div>
              <div className="anim" style={{ marginBottom: 12 }}>
                <label>Phone (optional)</label>
                <div className="auth-field"><Icon path={Ic.brief} size={16} />
                  <input value={phone} onChange={(e) => setPhone(e.target.value)} placeholder="+91 12345 67890" /></div>
              </div>
              <div className="anim" style={{ marginBottom: 12 }}>
                <label>Password</label>
                <div className="auth-field"><Icon path={Ic.lock} size={16} />
                  <input type={show ? "text" : "password"} value={password} autoComplete="new-password" onChange={(e) => setPassword(e.target.value)} placeholder="At least 6 characters" required />
                  <button type="button" className="toggle" onClick={() => setShow(!show)}><Icon path={show ? Ic.eyeOff : Ic.eye} size={16} /></button></div>
              </div>
              <div className="anim" style={{ marginBottom: 14 }}>
                <label>Resume (PDF or DOCX)</label>
                <label className="auth-field" style={{ cursor: "pointer" }}>
                  <Icon path={Ic.upload} size={16} />
                  <span style={{ fontSize: ".86rem", color: cv ? "var(--ink)" : "var(--ink-faint)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{cv ? cv.name : "Attach your resume…"}</span>
                  <input type="file" accept=".pdf,.docx" style={{ display: "none" }} onChange={(e) => setCv(e.target.files?.[0] ?? null)} />
                </label>
              </div>

              {error && <p className="error-text" style={{ marginTop: 0 }}>{error}</p>}

              <button type="submit" className="auth-primary" disabled={submitting}>
                {submitting ? "Creating account…" : <>Create account & continue <Icon path={Ic.arrow} size={16} sw={2.2} /></>}
              </button>
            </form>

            <p className="auth-alt">Already have an account? <Link to={`/careers/login${job ? `?job=${job}` : ""}`}>Sign in</Link></p>
            <p className="auth-alt" style={{ marginTop: 6 }}><Link to="/careers/roles">← Back to open roles</Link></p>
            <CareersTrustRow />
          </div>
        </div>
        <footer className="auth-footer">© 2026 TCG Digital · DataAlchemists ATS</footer>
      </div>
    </div>
  );
}
