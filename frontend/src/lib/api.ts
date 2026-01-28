// frontend/src/lib/api.ts
export type ModelRecord = {
  id: string,
  sha256: string,
  name: string,
  type: string,
  status: string,
  archived: boolean};

const API_BASE = "http://127.0.0.1:5173";

export async function getModels(): Promise<ModelRecord[]> {
  const res = await fetch(`${API_BASE}/models`);
  if (!res.ok) {
    throw new Error(`GET /models failed: ${res.status} ${res.statusText}`);
  }
  return await res.json();
}