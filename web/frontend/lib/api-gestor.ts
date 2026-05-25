export type UsuarioInfo = {
  id: string;
  email: string;
  nome: string;
  is_admin: boolean;
};

export type CupInfo = {
  status: string | null;
  responsavel: string | null;
  responsavel_geral: string | null;
  vendedor: string | null;
  squad: string | null;
  segmento: string | null;
  cluster: string | null;
  status_conta: string | null;
  motivo_cancelamento: string | null;
  contrato_servico: string | null;
  contrato_produto: string | null;
  contrato_plano: string | null;
  contrato_valor_recorrente: number | null;
  contrato_status: string | null;
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
  cup_task_id: string | null;
  ativo: boolean;
  cup: CupInfo | null;
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

export type GestorCadastrado = {
  id: string;
  nome: string;
  squad: string | null;
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

export type Frequencia = "MENSAL" | "SEMANAL";

export type JobInfo = {
  id: string;
  mes: string;
  frequencia: Frequencia;
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

export type MetaAd = {
  nome: string;
  investimento: number | null;
  leads: number | null;
  cpl: number | null;
  conversoes: number | null;
  faturamento: number | null;
  roas: number | null;
  cpa: number | null;
  impressoes: number | null;
  imagem_url: string | null;
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

export type MetricasBreakdown = {
  meta_ads: MetaAd[];
  google_ads: GoogleAd[];
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

  listGestoresCadastrados: () =>
    apiCall<{ items: GestorCadastrado[] }>("gestores-cadastrados"),

  createGestorCadastrado: (nome: string, squad: string | null) =>
    apiCall<GestorCadastrado>("gestores-cadastrados", "POST", { nome, squad }),

  deleteGestorCadastrado: (id: string) =>
    apiCall<void>(`gestores-cadastrados/${id}`, "DELETE"),

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

  syncGestoresFromClickup: () =>
    apiCall<{
      atualizados: number;
      total_ativos: number;
      com_match_nome: number;
      com_contrato_performance: number;
      com_responsavel: number;
    }>("clientes/sync-gestores", "POST"),

  listClientesSemVinculoCup: () =>
    apiCall<{
      total: number;
      items: Array<{
        cliente_id: string;
        cliente_nome: string;
        cliente_categoria: string;
        cliente_gestor: string | null;
        sugestoes: Array<{ task_id: string; nome: string; responsavel: string | null; score: number }>;
      }>;
    }>("clickup/sem-vinculo"),

  searchClickupTasks: (q: string) =>
    apiCall<{
      items: Array<{
        task_id: string;
        nome: string;
        responsavel: string | null;
        status: string | null;
        vinculado_a: { id: string; nome: string } | null;
      }>;
    }>(`clickup/tasks?q=${encodeURIComponent(q)}`),

  vincularCupTask: (clienteId: string, cupTaskId: string | null) =>
    apiCall<{ cliente_id: string; cup_task_id: string | null }>(
      `clientes/${clienteId}/cup-task`,
      "PATCH",
      { cup_task_id: cupTaskId },
    ),

  automatchClickup: (dryRun: boolean) =>
    apiCall<{
      dry_run: boolean;
      matches: Array<{ cliente_id: string; cliente_nome: string; task_id: string; cup_nome: string }>;
      aplicados: number;
      ambiguos: Array<{ cliente_id: string; cliente_nome: string; candidatos: Array<{ task_id: string; nome: string }> }>;
      sem_candidato: Array<{ cliente_id: string; cliente_nome: string }>;
      stats: {
        total_clientes_sem_vinculo: number;
        matches_propostos: number;
        ambiguos: number;
        sem_candidato: number;
      };
    }>(`clickup/automatch?dry_run=${dryRun}`, "POST"),

  triggerReport: (slug: string, mes: string, frequencia: Frequencia = "MENSAL") =>
    apiCall<{ job_id: string }>("reports/trigger", "POST", { slug, mes, frequencia }),

  getJob: (job_id: string) =>
    apiCall<JobInfo>(`reports/${job_id}`),

  listJobs: (slug?: string) =>
    apiCall<JobInfo[]>(`reports${slug ? `?slug=${slug}` : ""}`),

  metricas: () => apiCall<MetricasDashboard>("metricas"),

  metricasBreakdown: (slug: string) =>
    apiCall<MetricasBreakdown>(`metricas/${slug}/breakdown`),

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
