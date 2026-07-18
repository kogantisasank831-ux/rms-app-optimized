import { useQueryClient } from "@tanstack/react-query";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { type AuthUser, fetchMe, login as loginApi } from "../api/endpoints/auth";
import { type ApiError, tokenStore } from "../api/client";

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<AuthUser>;
  setSession: (token: string, user: AuthUser) => void;
  refreshUser: () => Promise<AuthUser | null>;
  logout: () => void;
}

const AuthContext = createContext<AuthState | undefined>(undefined);
const AUTH_ME_KEY = ["auth", "me"] as const;

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(() => !!tokenStore.get());

  const clearLocalSession = useCallback(() => {
    setUser(null);
    setLoading(false);
    // Query keys are intentionally shared throughout the app. Clearing on every
    // identity change prevents one user briefly seeing another user's cached data.
    queryClient.clear();
  }, [queryClient]);

  // Keep React auth state synchronized when the Axios interceptor expires a token.
  useEffect(() => tokenStore.subscribe((token) => {
    if (!token) clearLocalSession();
  }), [clearLocalSession]);

  // Hydrate once from an existing token. fetchQuery deduplicates React Strict Mode's
  // development remount, avoiding duplicate /auth/me requests.
  useEffect(() => {
    let active = true;
    if (!tokenStore.get()) {
      setLoading(false);
      return;
    }
    queryClient.fetchQuery({
      queryKey: AUTH_ME_KEY,
      queryFn: fetchMe,
      staleTime: 30_000,
      retry: false,
    })
      .then((nextUser) => {
        if (active) setUser(nextUser);
      })
      .catch((error: ApiError) => {
        // Only an authoritative 401 invalidates the saved session. A temporary
        // outage should not silently discard a valid token.
        if (error.status === 401) tokenStore.clear();
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [queryClient]);

  const login = useCallback(async (email: string, password: string) => {
    const result = await loginApi(email, password);
    queryClient.clear();
    tokenStore.set(result.access_token);
    queryClient.setQueryData(AUTH_ME_KEY, result.user);
    setUser(result.user);
    return result.user;
  }, [queryClient]);

  const setSession = useCallback((token: string, nextUser: AuthUser) => {
    queryClient.clear();
    tokenStore.set(token);
    queryClient.setQueryData(AUTH_ME_KEY, nextUser);
    setUser(nextUser);
  }, [queryClient]);

  const refreshUser = useCallback(async () => {
    if (!tokenStore.get()) return null;
    const nextUser = await fetchMe();
    queryClient.setQueryData(AUTH_ME_KEY, nextUser);
    setUser(nextUser);
    return nextUser;
  }, [queryClient]);

  const logout = useCallback(() => {
    tokenStore.clear();
    clearLocalSession();
  }, [clearLocalSession]);

  const value = useMemo<AuthState>(
    () => ({ user, loading, login, setSession, refreshUser, logout }),
    [user, loading, login, setSession, refreshUser, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
