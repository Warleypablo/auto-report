// Tipos compartilhados com a API. Em produção, gerar via openapi-typescript.
// Aqui estão escritos à mão para evitar dependência de backend rodando em build time.

export type CaseListItem = {
  slug: string;
  nome: string;
  logo_url: string | null;
  categoria: string;
  setor: string | null;
  porte: string | null;
  descricao_publica: string | null;
  destaque: boolean;
  periodo_inicio: string;
  periodo_fim: string;
  faturamento: string | null;
  investimento: string | null;
  roas: string | null;
  cpa: string | null;
  leads: number | null;
  vendas: number | null;
  faturamento_var_pct: string | null;
  roas_var_pct: string | null;
};

export type CaseListResponse = {
  items: CaseListItem[];
  total: number;
};

export type PontoEvolucao = {
  periodo_inicio: string;
  periodo_fim: string;
  faturamento: string | null;
  investimento: string | null;
  roas: string | null;
};

export type CaseDetail = CaseListItem & {
  metricas_detalhadas: Record<string, Record<string, number | string>>;
  evolucao: PontoEvolucao[];
  data_coleta: string;
};

export type RankingItem = {
  slug: string;
  nome: string;
  logo_url: string | null;
  valor: string;
};

export type ClienteListItem = {
  slug: string;
  nome: string;
  categoria: string;
  setor: string | null;
  porte: string | null;
  publicar_vitrine: boolean;
  destaque: boolean;
  periodo_inicio: string | null;
  periodo_fim: string | null;
  data_coleta: string | null;
  faturamento: string | null;
  investimento: string | null;
  roas: string | null;
  cpa: string | null;
  leads: number | null;
  vendas: number | null;
  faturamento_var_pct: string | null;
  roas_var_pct: string | null;
};

export type ClientesListResponse = {
  items: ClienteListItem[];
  total: number;
};
