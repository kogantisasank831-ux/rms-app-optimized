import { api, type Envelope, type Paged } from "../client";

export interface CandidateListItem {
  candidate_id: string; full_name: string; email: string; source: string;
  total_experience_years: number | null; current_company: string | null;
  cv_file_name: string; created_at: string;
  photo_icon_url?: string | null;
}
export interface CandidateDetail extends CandidateListItem {
  phone: string | null; notice_period_days: number | null;
  current_ctc: string | null; expected_ctc: string | null;
  cv_object_key: string; cv_download_url: string | null; cv_text: string | null;
  parsed_cv: unknown; created_by: string;
  photo_url?: string | null;
}

export async function listCandidates(params?: { page?: number; limit?: number }): Promise<Paged<CandidateListItem>> {
  const r = await api.get<Envelope<CandidateListItem[]>>("/candidates", { params });
  return { items: r.data.data, total: r.data.meta?.total ?? r.data.data.length };
}

export async function getCandidate(id: string): Promise<CandidateDetail> {
  const r = await api.get<Envelope<CandidateDetail>>(`/candidates/${id}`);
  return r.data.data;
}

export interface CandidateCreatePayload {
  full_name: string; email: string; phone?: string;
  total_experience_years?: number; source?: string; notice_period_days?: number;
}
export async function createCandidate(payload: CandidateCreatePayload, cv: File): Promise<{ candidate_id: string; cv_object_key: string; cv_text_extracted: boolean }> {
  const fd = new FormData();
  fd.append("payload", JSON.stringify(payload));
  fd.append("cv_file", cv);
  const r = await api.post<Envelope<{ candidate_id: string; cv_object_key: string; cv_text_extracted: boolean }>>("/candidates", fd);
  return r.data.data;
}
