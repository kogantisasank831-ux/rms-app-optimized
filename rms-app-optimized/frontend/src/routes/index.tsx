import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";
import { AppShell } from "../components/AppShell";
import { BrandLoader } from "../components/BrandLoader";
import { ProtectedRoute } from "../components/ProtectedRoute";

const Dashboard = lazy(() => import("../pages/Dashboard"));
const Login = lazy(() => import("../pages/Login"));
const AuditLog = lazy(() => import("../pages/admin/AuditLog"));
const SkillImport = lazy(() => import("../pages/admin/SkillImport"));
const Users = lazy(() => import("../pages/admin/Users"));
const CandidateDetail = lazy(() => import("../pages/candidates/Detail"));
const CandidateList = lazy(() => import("../pages/candidates/List"));
const CandidateUpload = lazy(() => import("../pages/candidates/Upload"));
const CandidateDashboard = lazy(() => import("../pages/careers/Dashboard"));
const CandidateLogin = lazy(() => import("../pages/careers/CandidateLogin"));
const JobDetail = lazy(() => import("../pages/careers/JobDetail"));
const Landing = lazy(() => import("../pages/careers/Landing"));
const Portal = lazy(() => import("../pages/careers/Portal"));
const Signup = lazy(() => import("../pages/careers/Signup"));
const InterviewDetail = lazy(() => import("../pages/interviews/InterviewDetail"));
const MyInterviews = lazy(() => import("../pages/interviews/MyInterviews"));
const OffersPage = lazy(() => import("../pages/offers/Detail"));
const Kanban = lazy(() => import("../pages/pipeline/Kanban"));
const RrfCreate = lazy(() => import("../pages/rrf/Create"));
const RrfDetail = lazy(() => import("../pages/rrf/Detail"));
const RrfList = lazy(() => import("../pages/rrf/List"));

const RRF_ROLES = ["ADMIN", "HR", "HIRING_MANAGER", "BU_HEAD"];
const HIRING_ROLES = ["ADMIN", "HR", "HIRING_MANAGER"];
const ADMIN_HR_ROLES = ["ADMIN", "HR"];

function staffPage(children: ReactNode, allowedRoles?: string[]) {
  return <ProtectedRoute allowedRoles={allowedRoles}>{children}</ProtectedRoute>;
}

/** Route tree. Pages are loaded on demand so the first screen does not download the whole ATS. */
export function AppRoutes() {
  return (
    <Suspense fallback={<BrandLoader />}>
      <Routes>
        <Route path="/login" element={<Login />} />
        <Route path="/careers" element={<Landing />} />
        <Route path="/careers/roles" element={<Portal />} />
        <Route path="/careers/jobs/:jobCode" element={<JobDetail />} />
        <Route path="/careers/login" element={<CandidateLogin />} />
        <Route path="/careers/signup" element={<Signup />} />
        <Route path="/careers/dashboard" element={<CandidateGuard><CandidateDashboard /></CandidateGuard>} />
        <Route element={<AppShell />}>
          <Route path="/" element={staffPage(<Dashboard />)} />
          <Route path="/rrfs" element={staffPage(<RrfList />, RRF_ROLES)} />
          <Route path="/rrfs/new" element={staffPage(<RrfCreate />, RRF_ROLES)} />
          <Route path="/rrfs/:rrfId" element={staffPage(<RrfDetail />, RRF_ROLES)} />
          <Route path="/candidates" element={staffPage(<CandidateList />, HIRING_ROLES)} />
          <Route path="/candidates/new" element={staffPage(<CandidateUpload />, HIRING_ROLES)} />
          <Route path="/candidates/:candidateId" element={staffPage(<CandidateDetail />, HIRING_ROLES)} />
          <Route path="/pipeline" element={staffPage(<Kanban />, HIRING_ROLES)} />
          <Route path="/interviews" element={staffPage(<MyInterviews />)} />
          <Route path="/interviews/:interviewId" element={staffPage(<InterviewDetail />)} />
          <Route path="/offers" element={staffPage(<OffersPage />, HIRING_ROLES)} />
          <Route path="/admin/users" element={staffPage(<Users />, ["ADMIN"])} />
          <Route path="/admin/skills" element={staffPage(<SkillImport />, ADMIN_HR_ROLES)} />
          <Route path="/admin/audit" element={staffPage(<AuditLog />, ADMIN_HR_ROLES)} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}

function CandidateGuard({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  if (loading) return <BrandLoader />;
  if (!user) return <Navigate to="/careers/login" replace />;
  if (user.role !== "CANDIDATE") return <Navigate to="/" replace />;
  return <>{children}</>;
}
