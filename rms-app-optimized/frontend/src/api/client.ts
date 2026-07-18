import axios, { type AxiosError } from "axios";

const TOKEN_KEY = "rms_token";
type TokenListener = (token: string | null) => void;
const tokenListeners = new Set<TokenListener>();

function notifyTokenListeners(token: string | null): void {
  tokenListeners.forEach((listener) => listener(token));
}

export const tokenStore = {
  get: (): string | null => localStorage.getItem(TOKEN_KEY),
  set: (token: string): void => {
    localStorage.setItem(TOKEN_KEY, token);
    notifyTokenListeners(token);
  },
  clear: (): void => {
    const hadToken = localStorage.getItem(TOKEN_KEY) !== null;
    localStorage.removeItem(TOKEN_KEY);
    if (hadToken) notifyTokenListeners(null);
  },
  subscribe: (listener: TokenListener): (() => void) => {
    tokenListeners.add(listener);
    return () => tokenListeners.delete(listener);
  },
};

/** Normalized error shape surfaced to callers (from the API error envelope). */
export interface ApiError {
  code: string;
  message: string;
  details?: unknown[];
  status?: number;
}

/** Standard success envelope + pagination shapes. */
export interface Envelope<T> {
  success: boolean;
  data: T;
  meta?: { page: number; limit: number; total: number };
}
export interface Paged<T> {
  items: T[];
  total: number;
}

export const api = axios.create({ baseURL: "/api/v1" });

// Attach the current JWT immediately before every request.
api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Normalize the API envelope. An expired authenticated request clears the shared
// session, while an ordinary bad login must not destroy a different open session.
api.interceptors.response.use(
  (resp) => resp,
  (error: AxiosError<{ error?: ApiError }>) => {
    const status = error.response?.status;
    const requestUrl = error.config?.url ?? "";
    if (status === 401 && !requestUrl.endsWith("/auth/login")) tokenStore.clear();
    const apiErr: ApiError = {
      ...(error.response?.data?.error ?? { code: "RMS-E-0000", message: error.message }),
      status,
    };
    return Promise.reject(apiErr);
  },
);
