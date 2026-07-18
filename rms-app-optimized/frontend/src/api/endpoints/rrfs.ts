// typed calls for /rrfs router (list/detail + T-203 JD versions)
import { api } from "../client";

interface Envelope<T> {
  success: boolean;
  data: T;
  meta?: { page: number; limit: number; total: number };
}

export interface RrfSkill {
  skill_id: number;
  skill_name: string;
  req_type: string;
  priority: number;
}

export interface RrfListItem {
  rrf_id: string;
  rrf_code: string;
  position_title: string;
  positions_count: number;
  status: string;
  project_name: string;
  bu_id: number;
  bu_name?: string | null;
  needed_by_date: string;
  created_at: string;
}

export interface RrfDetail extends RrfListItem {
  assignment_location: string;
  base_location?: string | null;
  justification: string;
  project_type: string;
  salary_range?: string | null;
  wfh_allowed: boolean;
  shift_hours?: string | null;
  reporting_to?: string | null;
  scope_of_work?: string | null;
  responsibilities?: string | null;
  education_qualification?: string | null;
  min_experience_years: number;
  created_by: string;
  hr_rep_user_id?: string | null;
  approved_by?: string | null;
  positions_filled: number;
  skills: RrfSkill[];
}

export interface JdVersion {
  jd_id: string;
  version_no: number;
  jd_markdown: string;
  generated_by_agent: boolean;
  created_by: string;
  created_at: string;
}

export interface JdGenerateResult {
  version: JdVersion;
  seo_title: string;
  keywords: string[];
}

export async function listRrfs(params?: {
  status?: string;
  page?: number;
  limit?: number;
}): Promise<{ items: RrfListItem[]; total: number }> {
  const resp = await api.get<Envelope<RrfListItem[]>>("/rrfs", { params });
  return { items: resp.data.data, total: resp.data.meta?.total ?? resp.data.data.length };
}

export async function getRrf(rrfId: string): Promise<RrfDetail> {
  const resp = await api.get<Envelope<RrfDetail>>(`/rrfs/${rrfId}`);
  return resp.data.data;
}

export async function getJdVersions(rrfId: string): Promise<JdVersion[]> {
  const resp = await api.get<Envelope<JdVersion[]>>(`/rrfs/${rrfId}/jd`);
  return resp.data.data;
}

export async function generateJd(rrfId: string): Promise<JdGenerateResult> {
  const resp = await api.post<Envelope<JdGenerateResult>>(`/rrfs/${rrfId}/jd/generate`);
  return resp.data.data;
}

export async function saveJd(rrfId: string, jdMarkdown: string): Promise<JdVersion> {
  const resp = await api.post<Envelope<JdVersion>>(`/rrfs/${rrfId}/jd`, {
    jd_markdown: jdMarkdown,
  });
  return resp.data.data;
}

export interface RrfSkillIn { skill_id: number; req_type: "ESSENTIAL" | "DESIRED"; priority?: number; }
export interface RrfCreatePayload {
  position_title: string; positions_count: number; assignment_location: string;
  justification: string; project_name: string; project_type: "T_AND_M" | "FIXED_FEE";
  needed_by_date: string; min_experience_years?: number; wfh_allowed?: boolean;
  base_location?: string; salary_range?: string; bu_id: number; skills: RrfSkillIn[];
}
export async function createRrf(payload: RrfCreatePayload): Promise<{ rrf_id: string; rrf_code: string; status: string }> {
  const r = await api.post<Envelope<{ rrf_id: string; rrf_code: string; status: string }>>("/rrfs", payload);
  return r.data.data;
}
export async function transitionRrf(rrfId: string, action: string, comment: string) {
  const r = await api.post<Envelope<Record<string, unknown>>>(`/rrfs/${rrfId}/transition`, { action, comment });
  return r.data.data;
}
