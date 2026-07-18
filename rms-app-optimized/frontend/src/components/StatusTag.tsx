/** Maps RMS statuses/stages to a design-system tag class. */
const CLASS: Record<string, string> = {
  APPROVED: "tag-ok", ACTIVE: "tag-ok", ACCEPTED: "tag-ok", HIRED: "tag-ok", RELEASED: "tag-ok",
  PENDING_APPROVAL: "tag-wait", CANCEL_REQUESTED: "tag-wait", DRAFT: "tag-wait", SCHEDULED: "tag-wait",
  ON_HOLD: "tag-hold",
  CLOSED: "tag-closed", COMPLETED: "tag-closed", OFFER_ACCEPTED: "tag-ok",
  REJECTED: "tag-neg", CANCELLED: "tag-neg", DECLINED: "tag-neg", WITHDRAWN: "tag-neg", NO_SHOW: "tag-neg",
};

export function StatusTag({ value }: { value: string }) {
  const cls = CLASS[value] ?? "tag-hold";
  return <span className={`tag ${cls}`}>{value.replace(/_/g, " ")}</span>;
}
