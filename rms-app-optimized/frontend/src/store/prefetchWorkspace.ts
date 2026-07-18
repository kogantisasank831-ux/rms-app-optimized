import type { QueryKey } from "@tanstack/react-query";
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef } from "react";

import { listApplications } from "../api/endpoints/applications";
import { listCandidates } from "../api/endpoints/candidates";
import { myInterviews } from "../api/endpoints/interviews";
import { listOffers } from "../api/endpoints/offers";
import { listRrfs } from "../api/endpoints/rrfs";

/**
 * Warm caches for the main workspace pages once the Command Center is up.
 * Each (key, fn) mirrors the target page's primary useQuery EXACTLY, so navigating
 * there hits a warm cache and renders instantly (default staleTime 30s → no refetch flash).
 * `roles` gates each target to the same audience as the sidebar nav, so we never fire
 * a request the user isn't authorized for.
 */
interface Target {
  key: QueryKey;
  fn: () => Promise<unknown>;
  roles: string[] | null; // null = every signed-in staff role
}

const TARGETS: Target[] = [
  // Requisitions list — also feeds the Pipeline RRF picker.
  { key: ["rrfs"], fn: () => listRrfs({ limit: 100 }), roles: ["ADMIN", "HR", "HIRING_MANAGER", "BU_HEAD"] },
  // Candidates list — also used by the Pipeline board.
  { key: ["candidates"], fn: () => listCandidates({ limit: 100 }), roles: ["ADMIN", "HR", "HIRING_MANAGER"] },
  // My Interviews.
  { key: ["my-interviews"], fn: () => myInterviews(), roles: null },
  // Offers page: eligible applications + released offers.
  { key: ["apps", "offer-eligible"], fn: () => listApplications({ limit: 100 }), roles: ["ADMIN", "HR", "HIRING_MANAGER"] },
  { key: ["offers"], fn: () => listOffers(), roles: ["ADMIN", "HR", "HIRING_MANAGER"] },
];

type IdleWindow = Window & {
  requestIdleCallback?: (cb: () => void, opts?: { timeout: number }) => number;
  cancelIdleCallback?: (id: number) => void;
};

/**
 * Kicks off the background prefetch once `ready` (Command Center data has loaded).
 * Deferred to browser idle time so it never competes with the dashboard's own load.
 */
export function usePrefetchWorkspace(ready: boolean, role: string) {
  const qc = useQueryClient();
  const started = useRef(false);

  useEffect(() => {
    if (!ready || started.current) return;

    const run = () => {
      if (started.current) return;
      started.current = true;
      for (const t of TARGETS) {
        if (t.roles && !t.roles.includes(role)) continue;
        // prefetchQuery is a no-op if fresh data is already cached; failures stay silent.
        void qc.prefetchQuery({ queryKey: t.key, queryFn: t.fn, staleTime: 30_000 });
      }
    };

    const w = window as IdleWindow;
    if (w.requestIdleCallback) {
      const id = w.requestIdleCallback(run, { timeout: 2000 });
      return () => w.cancelIdleCallback?.(id);
    }
    const t = setTimeout(run, 400);
    return () => clearTimeout(t);
  }, [ready, role, qc]);
}
