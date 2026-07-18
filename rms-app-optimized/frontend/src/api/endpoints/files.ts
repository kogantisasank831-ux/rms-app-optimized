import { api, type Envelope } from "../client";

export async function presign(objectKey: string): Promise<string> {
  const r = await api.get<Envelope<{ object_key: string; download_url: string; expires_in: number }>>("/files/presign", { params: { object_key: objectKey } });
  return r.data.data.download_url;
}
