import { api, type Envelope, type Paged } from "../client";

export interface AgentRun {
  run_id: string; agent_name: string; entity_type: string; entity_id: string;
  model: string; status: string; prompt_tokens: number | null;
  completion_tokens: number | null; latency_ms: number | null; created_at: string;
}

export async function listRuns(params?: { agent_name?: string; page?: number; limit?: number }): Promise<Paged<AgentRun>> {
  const r = await api.get<Envelope<AgentRun[]>>("/agents/runs", { params });
  return { items: r.data.data, total: r.data.meta?.total ?? r.data.data.length };
}
