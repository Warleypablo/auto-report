export type UsuarioInfo = {
  id: string;
  email: string;
  nome: string;
  is_admin: boolean;
};

export type ClienteGestor = {
  id: string;
  slug: string;
  nome: string;
  categoria: string;
  gestor: string | null;
  id_google_ads: string | null;
  id_meta_ads: string | null;
  id_ga4: string | null;
  painel_url: string | null;
  pasta_url: string | null;
  ativo: boolean;
};

export type ClienteEditData = {
  nome?: string | null;
  categoria?: string | null;
  gestor?: string | null;
  id_google_ads?: string | null;
  id_meta_ads?: string | null;
  id_ga4?: string | null;
  painel_url?: string | null;
  pasta_url?: string | null;
};

export type ClienteCreateData = {
  nome: string;
  categoria: string;
  gestor?: string | null;
  id_google_ads?: string | null;
  id_meta_ads?: string | null;
  id_ga4?: string | null;
  painel_url?: string | null;
  pasta_url?: string | null;
};

export type JobStatus = "pending" | "running" | "done" | "error";

export type JobInfo = {
  id: string;
  mes: string;
  status: JobStatus;
  slides_url: string | null;
  erro: string | null;
  created_at: string;
  finished_at: string | null;
  cliente_slug: string;
  cliente_nome: string;
};

export type ClienteMetricas = {
  slug: string;
  nome: string;
  categoria: string;
  periodo_inicio: string | null;
  periodo_fim: string | null;
  faturamento: number | null;
  investimento: number | null;
  roas: number | null;
  cpa: number | null;
  leads: number | null;
  vendas: number | null;
  faturamento_var_pct: number | null;
  roas_var_pct: number | null;
};

export type MetricasDashboard = {
  items: ClienteMetricas[];
  total_faturamento: number;
  total_investimento: number;
  media_roas: number | null;
  total_leads: number;
  total_vendas: number;
};

export type UsuarioListItem = {
  id: string;
  email: string;
  nome: string;
  is_admin: boolean;
  ativo: boolean;
  n_clientes: number;
};

async function apiCall<T>(
  path: string,
  method: string = "GET",
  body?: object,
): Promise<T> {
  const res = await fetch(`/api/gestor/${path}`, {
    method,
    headers: { "content-type": "application/json" },
    ...(body ? { body: JSON.stringify(body) } : {}),
  });
  if (res.status === 204) return undefined as unknown as T;
  const data = await res.json().catch(() => ({}));
  if (!res.ok) {
    throw new Error(data?.detail ?? `Erro ${res.status}`);
  }
  return data as T;
}

export const gestorApi = {
  login: (email: string, senha: string) =>
    apiCall<{ usuario: UsuarioInfo }>("login", "POST", { email, senha }),

  logout: () => apiCall<void>("logout", "POST"),

  me: () => apiCall<UsuarioInfo>("me"),

  clientes: () =>
    apiCall<{ items: ClienteGestor[] }>("clientes"),

  gestores: () =>
    apiCall<{ items: string[] }>("gestores"),

  renameGestor: (de: string, para: string) =>
    apiCall<{ de: string; para: string; atualizados: number }>(`gestores`, "PATCH", { de, para }),

  normalizarGestores: () =>
    apiCall<{ mapeamento: { de: string; para: string; atualizados: number }[]; nomes_alterados: number }>(
      `gestores/normalizar`, "POST"
    ),

  createCliente: (data: ClienteCreateData) =>
    apiCall<ClienteGestor>(`clientes`, "POST", data),

  updateCliente: (id: string, data: ClienteEditData) =>
    apiCall<ClienteGestor>(`clientes/${id}`, "PATCH", data),

  deleteCliente: (id: string) =>
    apiCall<void>(`clientes/${id}`, "DELETE"),

  triggerReport: (slug: string, mes: string) =>
    apiCall<{ job_id: string }>("reports/trigger", "POST", { slug, mes }),

  getJob: (job_id: string) =>
    apiCall<JobInfo>(`reports/${job_id}`),

  listJobs: (slug?: string) =>
    apiCall<JobInfo[]>(`reports${slug ? `?slug=${slug}` : ""}`),

  metricas: () => apiCall<MetricasDashboard>("metricas"),

  // Admin
  listUsuarios: () =>
    apiCall<{ items: UsuarioListItem[] }>("admin/usuarios"),

  createUsuario: (data: { email: string; nome: string; senha: string; is_admin: boolean }) =>
    apiCall<UsuarioInfo>("admin/usuarios", "POST", data),

  deactivateUsuario: (id: string) =>
    apiCall<void>(`admin/usuarios/${id}`, "DELETE"),

  getUsuarioClientes: (id: string) =>
    apiCall<{ items: ClienteGestor[] }>(`admin/usuarios/${id}/clientes`),

  assignClientes: (id: string, cliente_ids: string[]) =>
    apiCall<void>(`admin/usuarios/${id}/clientes`, "POST", { cliente_ids }),

  removeClienteFromUsuario: (usuario_id: string, cliente_id: string) =>
    apiCall<void>(`admin/usuarios/${usuario_id}/clientes/${cliente_id}`, "DELETE"),
};
