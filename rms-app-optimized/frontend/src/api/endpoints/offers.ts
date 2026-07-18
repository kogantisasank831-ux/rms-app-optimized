import { api, type Envelope } from "../client";

export interface Offer {
  offer_id: string; offer_code: string; application_id: string;
  candidate_name: string | null; designation: string;
  ctc_annual: string; monthly_gross: string | null; joining_date: string; work_location: string;
  status: string; valid_until: string | null; letter_object_key: string | null; created_at: string;
}
export interface OfferCreatePayload {
  application_id: string; candidate_name?: string; designation: string; ctc_annual: string;
  monthly_gross?: string; joining_date: string; work_location: string; valid_until?: string;
}
export type OfferUpdatePayload = Partial<Omit<OfferCreatePayload, "application_id">>;

export interface OfferSummary { offer_id: string; application_id: string; offer_code: string; status: string; letter_ready: boolean; }
export async function listOffers(): Promise<OfferSummary[]> {
  return (await api.get<Envelope<OfferSummary[]>>("/offers")).data.data;
}

export async function getOffer(id: string): Promise<Offer> {
  return (await api.get<Envelope<Offer>>(`/offers/${id}`)).data.data;
}
export async function createOffer(payload: OfferCreatePayload): Promise<Offer> {
  return (await api.post<Envelope<Offer>>("/offers", payload)).data.data;
}
export async function updateOffer(id: string, payload: OfferUpdatePayload): Promise<Offer> {
  return (await api.patch<Envelope<Offer>>(`/offers/${id}`, payload)).data.data;
}
export async function generateLetter(id: string): Promise<{ letter_object_key: string; download_url: string; template_version: string }> {
  return (await api.post<Envelope<{ letter_object_key: string; download_url: string; template_version: string }>>(`/offers/${id}/generate-letter`)).data.data;
}
export async function transitionOffer(id: string, action: string, comment: string) {
  return (await api.post<Envelope<Record<string, unknown>>>(`/offers/${id}/transition`, { action, comment })).data.data;
}
