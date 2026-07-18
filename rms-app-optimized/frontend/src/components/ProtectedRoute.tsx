import { type ReactNode } from "react";
import { Navigate, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { BrandLoader } from "./BrandLoader";

/**
 * Gates a route behind authentication and (optionally) a role allowlist.
 * UI gating only — the backend independently enforces RBAC (LLD 7.1).
 */
export function ProtectedRoute({
  children,
  allowedRoles,
}: {
  children: ReactNode;
  allowedRoles?: string[];
}) {
  const { user, loading } = useAuth();
  const location = useLocation();

  if (loading) return <BrandLoader />;
  if (!user) return <Navigate to="/login" replace state={{ from: `${location.pathname}${location.search}` }} />;
  if (allowedRoles && !allowedRoles.includes(user.role)) {
    return (
      <div className="center-screen">
        <div className="card" style={{ padding: 24 }}>
          <h3>Not authorized</h3>
          <p className="error-text">Your role ({user.role}) cannot view this page.</p>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
