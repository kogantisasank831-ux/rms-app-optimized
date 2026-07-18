import { api } from "../client";

export interface AuthUser {
  user_id: string;
  full_name: string;
  email: string;
  role: string;
  designation?: string | null;
  photo_icon_url?: string | null; // small avatar shown throughout the app
  photo_url?: string | null;      // larger picture for the profile page
}

export interface LoginResult {
  access_token: string;
  token_type: string;
  expires_in: number;
  user: AuthUser;
}

interface Envelope<T> {
  success: boolean;
  data: T;
}

export async function login(email: string, password: string): Promise<LoginResult> {
  const resp = await api.post<Envelope<LoginResult>>("/auth/login", { email, password });
  return resp.data.data;
}

export async function fetchMe(): Promise<AuthUser> {
  const resp = await api.get<Envelope<AuthUser>>("/auth/me");
  return resp.data.data;
}
