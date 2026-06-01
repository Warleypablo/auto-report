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
  gestor_travado: boolean;
  cup: CupInfo | null;
};

export type ClienteEditData = {
  nome?: string | null;
  categoria?: string | null;
  gestor?: string | null;
  gestor_travado?: boolean;
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
  ctr: number | null;
  frequency: number | null;
  hook_rate: number | null;
};

export type GoogleAd = {
  nome: string;
  investimento: number | null;
  faturamento: number | null;
  conversoes: number | null;
  cpa: number | null;
  roas: number | null;
  impressoes: number | null;
  ctr: number | null;
};

export type RedeAnuncio = "meta" | "google";
export type ThumbStatus = "pendente" | "ok" | "sem_imagem" | "erro";

export type CriativoAgregado = {
  criativo_id: string;
  cliente_slug: string;
  cliente_nome: string;
  categoria: string;
  gestor_nome: string | null;
  rede: RedeAnuncio;
  ad_id: string;
  nome: string | null;
  tipo: string | null;
  preview_link: string | null;
  thumb_url: string | null;
  thumb_status: ThumbStatus;
  investimento: number;
  faturamento: number;
  roas: number | null;
  ctr: number | null;
  cpa: number | null;
  cpl: number | null;
  impressoes: number;
  clicks: number;
  conversoes: number;
  leads: number | null;
  hook_rate: number | null;
  frequency: number | null;
};

export type TotaisCriativos = {
  criativos: number;
  investimento: number;
  faturamento: number;
  roas: number | null;
  conversoes: number;
  impressoes: number;
  clicks: number;
};

export type CriativosResponse = {
  items: CriativoAgregado[];
  total: number;
  totais: TotaisCriativos;
};

export type CriativosParams = {
  de: string; // YYYY-MM-DD
  ate: string; // YYYY-MM-DD
  rede?: "meta" | "google" | "todos";
  categoria?: Array<"ECOMMERCE" | "LEAD_COM_SITE" | "LEAD_SEM_SITE">;
  gestor?: string;
  cliente?: string; // slug
  fat_min?: number;
  fat_max?: number;
  inv_min?: number;
  inv_max?: number;
  cli_fat_min?: number;
  cli_fat_max?: number;
  cli_inv_min?: number;
  cli_inv_max?: number;
  order_by?: "roas" | "faturamento" | "investimento";
  limit?: number;
  offset?: number;
};

export type MetricasBreakdown = {
  meta_ads: MetaAd[];
  google_ads: GoogleAd[];
};

export type InteligenciaSinal = {
  tipo: string;
  severidade: "critico" | "atencao" | "oportunidade";
  titulo: string;
  metrica_principal: string;
  contexto: Record<string, unknown>;
};

export type InteligenciaAlerta = {
  cliente_slug: string;
  cliente_nome: string;
  cliente_categoria: string;
  severidade: "critico" | "atencao" | "oportunidade";
  sinais: InteligenciaSinal[];
  narrativa: string | null;
};

export type InteligenciaResponse = {
  mes: string;
  alertas: InteligenciaAlerta[];
};

export type InteligenciaGenerateResponse = {
  mes: string;
  gerados: number;
  sem_sinais: number;
  sem_dados: number;
  erros: number;
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

export type MetricasTimeline = {
  cliente: { slug: string; nome: string; categoria: string; gestor: string | null };
  items: TimelineItem[];
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

export type CoberturaCliente = {
  id: string;
  slug: string;
  nome: string;
  ativo: boolean;
  meses_com_snapshot: string[];
};

export type CoberturaResponse = {
  meses: string[];
  clientes: CoberturaCliente[];
};

export type BackfillJobStatus = {
  job_id: string;
  status: "running" | "done" | "error";
  meses_total: number;
  meses_concluidos: number;
  erros: number;
  pct: number;
};

export type ChatMessage = {
  role: "user" | "assistant";
  content: string;
};

export type ChatResponse = {
  reply: string;
};

async function apiCall<T>(
  path: string,
  method: string = "GET",
  body?: object,
): Promise<T> {
  const res = await fetch(`/api/gestor/${path}`, {
    method,
    headers: { "content-type": "application/json" },
    cache: "no-store",
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

  cleanupGestores: () =>
    apiCall<{
      normalizacoes: { de: string; para: string; atualizados: number }[];
      cadastrados: string[];
      ja_cadastrados: string[];
      total_no_dropdown: number;
    }>(`admin/cleanup-gestores`, "POST"),

  createCliente: (data: ClienteCreateData) =>
    apiCall<ClienteGestor>(`clientes`, "POST", data),

  updateCliente: (id: string, data: ClienteEditData) =>
    apiCall<ClienteGestor>(`clientes/${id}`, "PATCH", data),

  deleteCliente: (id: string) =>
    apiCall<void>(`clientes/${id}`, "DELETE"),

  syncGestoresFromClickup: () =>
    apiCall<{
      atualizados: number;
      a_atualizar: number;
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

  triggerReport: (slug: string, mes: string, frequencia: Frequencia = "MENSAL", semana_inicio?: string) =>
    apiCall<{ job_id: string }>("reports/trigger", "POST", { slug, mes, frequencia, semana_inicio }),

  getJob: (job_id: string) =>
    apiCall<JobInfo>(`reports/${job_id}`),

  listJobs: (slug?: string) =>
    apiCall<JobInfo[]>(`reports${slug ? `?slug=${slug}` : ""}`),

  metricas: (mes?: string) =>
    apiCall<MetricasDashboard>(`metricas${mes ? `?mes=${encodeURIComponent(mes)}` : ""}`),

  metricasMesesDisponiveis: () =>
    apiCall<{ meses: string[] }>("metricas/meses-disponiveis"),

  metricasBreakdown: (slug: string, mes?: string) =>
    apiCall<MetricasBreakdown>(
      `metricas/${slug}/breakdown${mes ? `?mes=${encodeURIComponent(mes)}` : ""}`,
    ),

  metricasTimeline: (slug: string, meses?: number) =>
    apiCall<MetricasTimeline>(`metricas/${slug}/timeline${meses ? `?meses=${meses}` : ""}`),

  criativos: (params: CriativosParams) => {
    const qs = new URLSearchParams();
    qs.set("de", params.de);
    qs.set("ate", params.ate);
    if (params.rede) qs.set("rede", params.rede);
    (params.categoria ?? []).forEach((c) => qs.append("categoria", c));
    if (params.gestor) qs.set("gestor", params.gestor);
    if (params.cliente) qs.set("cliente", params.cliente);
    for (const k of [
      "fat_min", "fat_max", "inv_min", "inv_max",
      "cli_fat_min", "cli_fat_max", "cli_inv_min", "cli_inv_max",
      "limit", "offset",
    ] as const) {
      const v = params[k];
      if (v !== undefined && v !== null) qs.set(k, String(v));
    }
    if (params.order_by) qs.set("order_by", params.order_by);
    return apiCall<CriativosResponse>(`criativos?${qs.toString()}`);
  },

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

  inteligencia: (mes: string, gestor?: string) =>
    apiCall<InteligenciaResponse>(
      `inteligencia?mes=${encodeURIComponent(mes)}${gestor ? `&gestor=${encodeURIComponent(gestor)}` : ""}`,
    ),

  generateInteligencia: (mes: string) =>
    apiCall<InteligenciaGenerateResponse>(
      `inteligencia/generate?mes=${encodeURIComponent(mes)}`,
      "POST",
    ),

  triggerBackfill: (params: { mes_inicio: string; mes_fim: string; slug?: string }) =>
    apiCall<{ job_id: string; meses: number; clientes: number }>(
      "admin/etl/backfill",
      "POST",
      params,
    ),

  getBackfillJob: (job_id: string) =>
    apiCall<BackfillJobStatus>(`admin/etl/backfill/${job_id}`),

  cobertura: () =>
    apiCall<CoberturaResponse>("admin/cobertura"),

  chat: (messages: ChatMessage[], clienteSlug?: string) =>
    apiCall<ChatResponse>("turbomax/chat", "POST", {
      messages,
      cliente_slug: clienteSlug ?? "",
    }),
};
