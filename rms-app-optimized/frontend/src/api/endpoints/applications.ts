import { api, type Envelope, type Paged } from "../client";

export interface SkillCoverage { skill: string; present: boolean; evidence: string; }
export interface ScreeningResult {
  match_score?: number;
  experience_fit?: "BELOW" | "MEETS" | "EXCEEDS" | string;
  essential_skill_coverage?: SkillCoverage[];
  missing_essential_skills?: string[];
  desired_skills_found?: string[];
  strengths?: string[];
  risks?: string[];
  recommendation?: "SHORTLIST" | "REVIEW" | "REJECT" | string;
  rationale?: string;
}
export interface Application {
  application_id: string; rrf_id: string; rrf_code: string; candidate_id: string;
  candidate_name: string; current_stage: string; status: string;
  held_from_stage: string | null; ai_screen_score: number | null; created_at: string;
  updated_at?: string;
  current_company?: string | null;
  experience_years?: number | null;
  top_skills?: string[];
  current_round_feedback?: boolean;
  ai_screen_result?: ScreeningResult | null;
}

export interface PipelineStats {
  active_candidates: number;
  added_this_week: number;
  avg_days_in_stage: number | null;
  interview_conversion: number;
  offers_released: number;
  offers_pending: number;
  offer_acceptance: number;
}
export interface HistoryRow {
  history_id: number; from_stage: string | null; to_stage: string | null;
  action: string; comment: string; acted_by: string; acted_at: string;
}

export interface TransitionResult {
  application_id: string;
  from_stage: string;
  current_stage: string;
  status: string;
  action: string;
  history_id: number;
}

export async function listApplications(params?: { rrf_id?: string; stage?: string; status?: string; q?: string; sort?: string; page?: number; limit?: number }): Promise<Paged<Application>> {
  const r = await api.get<Envelope<Application[]>>("/applications", { params });
  return { items: r.data.data, total: r.data.meta?.total ?? r.data.data.length };
}

export async function getPipelineStats(rrfId: string): Promise<PipelineStats> {
  return (await api.get<Envelope<PipelineStats>>("/applications/pipeline-stats", { params: { rrf_id: rrfId } })).data.data;
}
export async function getApplication(id: string): Promise<Application> {
  return (await api.get<Envelope<Application>>(`/applications/${id}`)).data.data;
}
export async function getHistory(id: string): Promise<HistoryRow[]> {
  return (await api.get<Envelope<HistoryRow[]>>(`/applications/${id}/history`)).data.data;
}
export async function createApplication(rrf_id: string, candidate_id: string): Promise<Application> {
  return (await api.post<Envelope<Application>>("/applications", { rrf_id, candidate_id })).data.data;
}
export async function transitionApplication(id: string, action: string, comment: string, target_stage?: string): Promise<TransitionResult> {
  return (await api.post<Envelope<TransitionResult>>(`/applications/${id}/transition`, { action, comment, target_stage })).data.data;
}
export async function screenApplication(id: string) {
  return (await api.post<Envelope<Record<string, unknown>>>(`/applications/${id}/screen`)).data.data;
}

export interface RankedCandidate {
  candidate_id: string; score: number; matched_essential: string[];
  missing_essential: string[]; matched_desired: string[]; note: string;
}
export async function matchCandidates(rrfId: string): Promise<{ ranked: RankedCandidate[]; method_note: string }> {
  return (await api.get<Envelope<{ ranked: RankedCandidate[]; method_note: string }>>(`/rrfs/${rrfId}/match-candidates`)).data.data;
}
