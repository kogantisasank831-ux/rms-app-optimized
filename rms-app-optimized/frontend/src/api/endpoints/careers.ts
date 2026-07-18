import { api, type Envelope } from "../client";
import type { AuthUser, LoginResult } from "./auth";

export interface Job {
  rrf_id: string; job_code: string; title: string;
  department: string | null; project_name: string; location: string;
  wfh_allowed: boolean; min_experience_years: number; employment_type: string;
  needed_by_date: string | null; posted_at: string | null; openings: number;
  tags: string[]; blurb: string | null; salary_range: string | null;
}

export interface JobDetail extends Job {
  base_location: string | null;
  shift_hours: string | null;
  education_qualification: string | null;
  description: string | null;
  responsibilities: string[];
  essential_skills: string[];   // required
  desired_skills: string[];     // optional / nice-to-have
}

export interface PortalOffer {
  offer_id: string; offer_code: string; status: string; designation: string;
  ctc_annual: string; work_location: string; joining_date: string | null;
  valid_until: string | null; letter_url: string | null;
}
export interface PortalInterview {
  interview_id: string; round: string; mode: string;
  scheduled_start: string | null; scheduled_end: string | null;
  location: string | null; join_link: string | null;
}
export interface PortalApplication {
  application_id: string; rrf_id: string; job_code: string; title: string; location: string;
  current_stage: string; status: string; applied_at: string | null;
  offer: PortalOffer | null; interviews: PortalInterview[];
}
export interface PortalData {
  profile: {
    full_name: string; email: string; candidate_id: string | null;
    photo_icon_url?: string | null; photo_url?: string | null;
  };
  applications: PortalApplication[];
}

export async function listJobs(): Promise<Job[]> {
  return (await api.get<Envelope<Job[]>>("/careers/jobs")).data.data;
}

export async function getJob(jobCode: string): Promise<JobDetail> {
  return (await api.get<Envelope<JobDetail>>(`/careers/jobs/${encodeURIComponent(jobCode)}`)).data.data;
}

export async function signupCandidate(form: {
  full_name: string; email: string; password: string; phone?: string; cv: File; photo?: File | null;
}): Promise<LoginResult & { user: AuthUser }> {
  const fd = new FormData();
  fd.append("full_name", form.full_name);
  fd.append("email", form.email);
  fd.append("password", form.password);
  if (form.phone) fd.append("phone", form.phone);
  fd.append("cv_file", form.cv);
  if (form.photo) fd.append("photo", form.photo);
  return (await api.post<Envelope<LoginResult>>("/careers/signup", fd)).data.data;
}

export async function applyToJob(rrfId: string): Promise<{ application_id: string; current_stage: string; status: string }> {
  return (await api.post<Envelope<{ application_id: string; current_stage: string; status: string }>>("/careers/apply", { rrf_id: rrfId })).data.data;
}

export async function myPortal(): Promise<PortalData> {
  return (await api.get<Envelope<PortalData>>("/careers/me")).data.data;
}

export async function respondToOffer(
  offerId: string,
  action: "ACCEPT" | "DECLINE",
  comment?: string,
): Promise<{ offer_id: string; status: string; action: string }> {
  return (
    await api.post<Envelope<{ offer_id: string; status: string; action: string }>>(
      `/careers/offers/${offerId}/respond`,
      { action, comment },
    )
  ).data.data;
}
