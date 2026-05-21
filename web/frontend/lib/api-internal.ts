import "server-only";

import type { ClientesListResponse, PeriodosResponse } from "./types";

const BASE = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
const TOKEN = process.env.INTERNAL_API_TOKEN ?? "";

async function fetchInternal<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: { ...(init.headers ?? {}), "x-etl-token": TOKEN },
    cache: "no-store",
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${path} retornou ${res.status}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export function listAllClientes(de: string, ate: string): Promise<ClientesListResponse> {
  const qs = `?de=${encodeURIComponent(de)}&ate=${encodeURIComponent(ate)}`;
  return fetchInternal<ClientesListResponse>(`/internal/clientes${qs}`);
}

export function listPeriodos(): Promise<PeriodosResponse> {
  return fetchInternal<PeriodosResponse>("/internal/periodos");
}

export function triggerColetaMes(mes: string): Promise<unknown> {
  const qs = `?mes=${encodeURIComponent(mes)}&incluir_privados=true`;
  return fetchInternal(`/internal/etl/trigger${qs}`, { method: "POST" });
}
