import { api, type Envelope, type Paged } from "../client";

export interface Skill { skill_id: number; skill_name: string; skill_category: string | null; aliases: string[]; }

export async function listSkills(params?: { q?: string; page?: number; limit?: number }): Promise<Paged<Skill>> {
  const r = await api.get<Envelope<Skill[]>>("/skills", { params });
  return { items: r.data.data, total: r.data.meta?.total ?? r.data.data.length };
}

export interface SkillPayload { skill_name: string; skill_category?: string | null; aliases: string[]; }

export async function createSkill(payload: SkillPayload): Promise<Skill> {
  const r = await api.post<Envelope<Skill>>("/skills", payload);
  return r.data.data;
}

export async function updateSkill(skillId: number, payload: SkillPayload): Promise<Skill> {
  const r = await api.patch<Envelope<Skill>>(`/skills/${skillId}`, payload);
  return r.data.data;
}

export async function importSkills(file: File): Promise<{ rows: number; inserted: number; updated: number }> {
  const fd = new FormData();
  fd.append("file", file);
  const r = await api.post<Envelope<{ rows: number; inserted: number; updated: number }>>("/skills/import", fd);
  return r.data.data;
}
