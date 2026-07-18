import { api, type Envelope, type Paged } from "../client";

export interface DirectoryUser {
  user_id: string; full_name: string; email: string;
  role: string; role_name: string; designation: string | null;
  is_active?: boolean;
  photo_icon_url?: string | null;
  photo_url?: string | null;
}

export interface RoleOption { role_code: string; role_name: string }

export async function listUsers(params?: { role?: string; q?: string; include_inactive?: boolean; page?: number; limit?: number }): Promise<Paged<DirectoryUser>> {
  const r = await api.get<Envelope<DirectoryUser[]>>("/users", { params });
  return { items: r.data.data, total: r.data.meta?.total ?? r.data.data.length };
}

export async function listRoles(): Promise<RoleOption[]> {
  const r = await api.get<Envelope<RoleOption[]>>("/users/roles");
  return r.data.data;
}

export async function createUser(payload: {
  full_name: string; email: string; role: string; designation?: string | null; password?: string | null;
}): Promise<DirectoryUser> {
  const r = await api.post<Envelope<DirectoryUser>>("/users", payload);
  return r.data.data;
}

export async function setUserActive(userId: string, isActive: boolean): Promise<DirectoryUser> {
  const r = await api.patch<Envelope<DirectoryUser>>(`/users/${userId}`, { is_active: isActive });
  return r.data.data;
}

export async function updateUser(userId: string, payload: {
  full_name?: string; email?: string; designation?: string | null; role?: string; is_active?: boolean;
}): Promise<DirectoryUser> {
  const r = await api.patch<Envelope<DirectoryUser>>(`/users/${userId}`, payload);
  return r.data.data;
}

/** ADMIN: upload/replace any user's profile photo. */
export async function uploadUserPhoto(userId: string, photo: File): Promise<DirectoryUser> {
  const fd = new FormData();
  fd.append("photo", photo);
  const r = await api.post<Envelope<DirectoryUser>>(`/users/${userId}/photo`, fd);
  return r.data.data;
}

/** Any signed-in user: upload/replace their own profile photo. */
export async function uploadMyPhoto(photo: File): Promise<DirectoryUser> {
  const fd = new FormData();
  fd.append("photo", photo);
  const r = await api.post<Envelope<DirectoryUser>>(`/users/me/photo`, fd);
  return r.data.data;
}
