import type { Job, JobDetail } from "../../api/endpoints/careers";

/**
 * Job-family categories for the careers filter, derived from the role title/skills
 * (there is no category column in the DB). First matching rule wins, so more specific
 * families are listed before broader ones (Data Scientist → AI, Data Engineer → Data,
 * Software Engineer → Engineering).
 */
const CATEGORY_RULES: { label: string; test: RegExp }[] = [
  { label: "Artificial Intelligence", test: /\b(a\.?i\.?|ml|machine learning|deep learning|nlp|llm|gen ?ai|data scien|computer vision)\b/i },
  { label: "Data", test: /\b(data engineer|data analyst|analytics|big data|etl|data warehouse|\bbi\b)\b/i },
  { label: "Engineering", test: /\b(engineer|developer|sde|dev ?ops|\bsre\b|back ?end|front ?end|full ?stack|software|\bqa\b|tester|architect|platform)\b/i },
  { label: "Business Analyst", test: /\b(business analyst|\bba\b|analyst|product owner|functional)\b/i },
  { label: "Product", test: /\b(product manager|product lead|\bpm\b|product owner)\b/i },
  { label: "Design", test: /\b(designer|\bux\b|\bui\b|creative)\b/i },
  { label: "HR", test: /\b(hr\b|human resource|recruit|talent acquisition|people ops)\b/i },
  { label: "Sales & Marketing", test: /\b(sales|marketing|growth|account executive)\b/i },
  { label: "Consulting", test: /\b(consultant|consulting|advisory)\b/i },
];

export function jobCategory(job: Pick<Job, "title" | "tags" | "project_name" | "department">): string {
  const hay = `${job.title} ${(job.tags ?? []).join(" ")} ${job.project_name ?? ""} ${job.department ?? ""}`;
  for (const r of CATEGORY_RULES) if (r.test.test(hay)) return r.label;
  return "Other";
}

/* ---- local-system cache of job detail pages, so a card opens instantly ---- */
const cacheKey = (jobCode: string) => `rms:job:${jobCode}`;

export function readJobCache(jobCode: string): JobDetail | undefined {
  try {
    const raw = localStorage.getItem(cacheKey(jobCode));
    return raw ? (JSON.parse(raw) as JobDetail) : undefined;
  } catch {
    return undefined;
  }
}

export function writeJobCache(jobCode: string, detail: JobDetail): void {
  try {
    localStorage.setItem(cacheKey(jobCode), JSON.stringify(detail));
  } catch {
    /* storage full / disabled — non-fatal, we just lose the instant-open optimisation */
  }
}
