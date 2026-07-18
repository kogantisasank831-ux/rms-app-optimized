import { QueryClient } from "@tanstack/react-query";

import type { ApiError } from "../api/client";

// Single TanStack Query client for all server state (no other state libs, per LLD).
export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Retrying validation/auth/not-found responses only duplicates traffic and delays
      // the real error. Retry one transient network/server failure instead.
      retry: (failureCount, error) => {
        const status = (error as unknown as Partial<ApiError>)?.status;
        return failureCount < 1 && (status == null || status >= 500);
      },
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});
