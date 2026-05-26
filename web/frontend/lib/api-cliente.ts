export type ClientePublic = {
  id: string;
  slug: string;
  nome: string;
  categoria: string;
  logo_url: string | null;
  setor: string | null;
};

export type TimelineItem = {
  mes: string;
  periodo_inicio: string;
  periodo_fim: string;
  faturamento: number | null;
  investimento: number | null;
  roas: number | null;
  cpa: number | null;
  leads: number | null;
  vendas: number | null;
  faturamento_var_pct: number | null;
  roas_var_pct: number | null;
};

export type MetaAd = {
  nome: string;
  imagem_url: string | null;
  investimento: number | null;
  leads: number | null;
  cpl: number | null;
  conversoes: number | null;
  faturamento: number | null;
  roas: number | null;
  cpa: number | null;
  impressoes: number | null;
};

export type GoogleAd = {
  nome: string;
  investimento: number | null;
  faturamento: number | null;
  conversoes: number | null;
  cpa: number | null;
  roas: number | null;
  impressoes: number | null;
};

export type Breakdown = { meta_ads: MetaAd[]; google_ads: GoogleAd[] };

class ApiError extends Error {
  constructor(public status: number, public detail: string) {
    super(detail);
  }
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const r = await fetch(`/api/cliente${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
  });
  if (!r.ok) {
    let detail = `HTTP ${r.status}`;
    try {
      detail = (await r.json()).detail ?? detail;
    } catch {
      // ignore
    }
    throw new ApiError(r.status, detail);
  }
  if (r.status === 204) return undefined as T;
  return r.json();
}

export const clienteApi = {
  login: (cnpj: string) =>
    call<{ ok: true; cliente: ClientePublic }>("/login", {
      method: "POST",
      body: JSON.stringify({ cnpj }),
    }),
  logout: () => call<void>("/logout", { method: "POST" }),
  me: () => call<ClientePublic>("/me"),
  timeline: (meses = 12) =>
    call<{ items: TimelineItem[] }>(`/metricas/timeline?meses=${meses}`),
  breakdown: (mes: string) => call<Breakdown>(`/metricas/breakdown?mes=${mes}`),
  mesesDisponiveis: () => call<{ meses: string[] }>("/metricas/meses-disponiveis"),
};

export { ApiError };
