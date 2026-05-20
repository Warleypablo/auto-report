import "server-only";

import type { ClientesListResponse } from "./types";

const BASE = process.env.INTERNAL_API_URL ?? "http://localhost:8000";
const TOKEN = process.env.INTERNAL_API_TOKEN ?? "";

async function fetchInternal<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "x-etl-token": TOKEN },
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`API ${path} retornou ${res.status}`);
  return res.json() as Promise<T>;
}

export function listAllClientes(): Promise<ClientesListResponse> {
  return fetchInternal<ClientesListResponse>("/internal/clientes");
}
