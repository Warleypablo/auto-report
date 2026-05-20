import type { CaseDetail, CaseListResponse, RankingItem } from "./types";

const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    next: { revalidate: 3600 },
  });
  if (!res.ok) throw new Error(`API ${path} retornou ${res.status}`);
  return res.json() as Promise<T>;
}

export type ListCasesParams = {
  categoria?: string;
  setor?: string;
  orderBy?: "roas" | "faturamento" | "crescimento";
  limit?: number;
  offset?: number;
};

export function listCases(params: ListCasesParams = {}): Promise<CaseListResponse> {
  const qs = new URLSearchParams();
  if (params.categoria) qs.set("categoria", params.categoria);
  if (params.setor) qs.set("setor", params.setor);
  if (params.orderBy) qs.set("order_by", params.orderBy);
  if (params.limit) qs.set("limit", String(params.limit));
  if (params.offset) qs.set("offset", String(params.offset));
  const suffix = qs.toString() ? `?${qs}` : "";
  return fetchJson<CaseListResponse>(`/api/cases${suffix}`);
}

export function getCase(slug: string): Promise<CaseDetail> {
  return fetchJson<CaseDetail>(`/api/cases/${slug}`);
}

export function getRanking(
  tipo: "roas" | "faturamento" | "crescimento",
  limit = 10,
): Promise<RankingItem[]> {
  return fetchJson<RankingItem[]>(`/api/rankings/${tipo}?limit=${limit}`);
}
