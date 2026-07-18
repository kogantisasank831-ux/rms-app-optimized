import { api, type Envelope, type Paged } from "../client";

export interface Metric { value: unknown; description: string; }
export type Metrics = Record<string, Metric>;

export async function getMetrics(): Promise<Metrics> {
  const r = await api.get<Envelope<Metrics>>("/dashboard/metrics");
  return r.data.data;
}

/** AI observability tiles — fetched separately so the core dashboard renders first. */
export async function getInsights(): Promise<Metrics> {
  const r = await api.get<Envelope<Metrics>>("/dashboard/insights");
  return r.data.data;
}

export interface AuditRow {
  audit_id: number; entity_type: string; entity_id: string; action: string;
  performed_by: string | null; after_state: unknown; created_at: string;
}
export async function listAudit(params?: { entity_type?: string; entity_id?: string; page?: number; limit?: number }): Promise<Paged<AuditRow>> {
  const r = await api.get<Envelope<AuditRow[]>>("/audit", { params });
  return { items: r.data.data, total: r.data.meta?.total ?? r.data.data.length };
}
