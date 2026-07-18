import { api, type Envelope } from "../client";

export interface Panelist { user_id: string; full_name: string; is_lead: boolean; }
export interface Interview {
  interview_id: string; application_id: string; round: string;
  scheduled_start: string; scheduled_end: string; mode: string;
  meeting_link: string | null; location: string | null; status: string;
  rescheduled_from: string | null; panelists: Panelist[]; candidate_name?: string;
  /** Present on schedule responses so the pipeline can reconcile auto-advance reliably. */
  application_stage?: string;
}
export type AssessmentCategory = "behavioural" | "technical" | "process_knowledge";
export interface CategoryAssessment {
  category: AssessmentCategory; rating: number | null; comments: string | null;
}
export interface PriorFeedback {
  round: string; overall_rating: number; recommendation: string;
  strengths: string | null; weaknesses: string | null;
  assessments?: CategoryAssessment[]; ai_summary: Record<string, unknown> | null;
}

export async function myInterviews(): Promise<(Interview & { candidate_name?: string })[]> {
  return (await api.get<Envelope<Interview[]>>("/interviews/my")).data.data;
}
export async function listByApplication(applicationId: string): Promise<Interview[]> {
  return (await api.get<Envelope<Interview[]>>("/interviews", { params: { application_id: applicationId } })).data.data;
}
export interface SchedulePayload {
  application_id: string; round: string; scheduled_start: string; scheduled_end: string;
  mode?: string; meeting_link?: string; location?: string;
  panelists: { user_id: string; is_lead: boolean }[];
}
export async function scheduleInterview(payload: SchedulePayload): Promise<Interview> {
  return (await api.post<Envelope<Interview>>("/interviews", payload)).data.data;
}
export async function patchInterview(id: string, body: { action: string; comment: string; scheduled_start?: string; scheduled_end?: string }) {
  return (await api.patch<Envelope<Interview>>(`/interviews/${id}`, body)).data.data;
}
export async function priorFeedback(id: string): Promise<PriorFeedback[]> {
  return (await api.get<Envelope<PriorFeedback[]>>(`/interviews/${id}/prior-feedback`)).data.data;
}
export interface Feedback {
  feedback_id: string; interview_id: string; overall_rating: number; recommendation: string;
  strengths: string | null; weaknesses: string | null; raw_notes: string | null;
  attributes: Record<string, unknown>; assessments?: CategoryAssessment[];
  ai_summary: Record<string, unknown> | null;
  skill_ratings: { skill_id: number; skill_name: string; rating: number; remarks: string | null }[];
  interview_status: string;
}
export async function getFeedback(id: string): Promise<Feedback | null> {
  return (await api.get<Envelope<Feedback | null>>(`/interviews/${id}/feedback`)).data.data;
}
export interface FeedbackPayload {
  overall_rating: number; recommendation: string; strengths?: string; weaknesses?: string;
  raw_notes?: string; attributes?: Record<string, unknown>;
  assessments?: { category: AssessmentCategory; rating: number | null; comments?: string }[];
  skill_ratings?: { skill_id: number; rating: number; remarks?: string }[];
}
export async function submitFeedback(id: string, payload: FeedbackPayload) {
  return (await api.post<Envelope<Record<string, unknown>>>(`/interviews/${id}/feedback`, payload)).data.data;
}
export async function summarizeFeedback(id: string) {
  return (await api.post<Envelope<Record<string, unknown>>>(`/interviews/${id}/feedback/summarize`)).data.data;
}

// --- suggested interview questions (AGENT-6) ---
export interface SuggestedQuestion {
  category: string; question: string; rationale: string; what_to_look_for: string;
}
export interface InterviewQuestions {
  focus_areas: string[]; questions: SuggestedQuestion[]; summary: string;
}
export interface InterviewDetail extends Interview {
  candidate: {
    candidate_id: string; full_name: string; email: string; phone: string | null;
    total_experience_years: number | null; current_company: string | null;
  };
  position_title: string;
  min_experience_years: number;
  ai_screen_score: number | null;
  ai_interview_questions: InterviewQuestions | null;
}
export async function getInterview(id: string): Promise<InterviewDetail> {
  return (await api.get<Envelope<InterviewDetail>>(`/interviews/${id}`)).data.data;
}
export async function generateQuestions(id: string): Promise<InterviewDetail> {
  return (await api.post<Envelope<InterviewDetail>>(`/interviews/${id}/questions`)).data.data;
}
