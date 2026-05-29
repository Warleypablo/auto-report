import type { CriativosParams } from "@/lib/api-gestor";

// Chaves de chip exibidas na UI. "LEAD_AMBOS" é um atalho que expande
// para LEAD_COM_SITE + LEAD_SEM_SITE no payload da API.
export type CategoriaChave = "ECOMMERCE" | "LEAD_COM_SITE" | "LEAD_SEM_SITE" | "LEAD_AMBOS";

export type FaixaScope = "criativo" | "cliente";

export type OrderBy = "roas" | "faturamento" | "investimento";

export type FiltrosState = {
  de: string; // YYYY-MM-DD
  ate: string; // YYYY-MM-DD
  rede: "meta" | "google" | "todos";
  categorias: CategoriaChave[];
  gestor: string; // "" = todos
  cliente: string; // slug, "" = todos
  faixaScope: FaixaScope;
  fatMin: string; // texto do input; "" = sem filtro
  fatMax: string;
  invMin: string;
  invMax: string;
  orderBy: OrderBy;
};

export const CATEGORIA_LABELS: Record<CategoriaChave, string> = {
  ECOMMERCE: "E-commerce",
  LEAD_COM_SITE: "Lead com site",
  LEAD_SEM_SITE: "Lead sem site",
  LEAD_AMBOS: "Lead (ambos)",
};

// Ordem em que os chips aparecem na barra de filtros.
export const CATEGORIA_CHIPS: CategoriaChave[] = [
  "ECOMMERCE",
  "LEAD_COM_SITE",
  "LEAD_SEM_SITE",
  "LEAD_AMBOS",
];

function isoDia(d: Date): string {
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(
    d.getUTCDate(),
  ).padStart(2, "0")}`;
}

function somaDias(base: Date, dias: number): Date {
  const d = new Date(base.getTime());
  d.setUTCDate(d.getUTCDate() + dias);
  return d;
}

export type RangeData = { de: string; ate: string };

// Presets de date range. Recebem "hoje" (injetável p/ testes determinísticos)
// e retornam {de, ate} inclusivos em YYYY-MM-DD.
export const PRESETS_DATA: Record<string, (hoje?: Date) => RangeData> = {
  ultimos_30: (hoje = new Date()) => ({ de: isoDia(somaDias(hoje, -29)), ate: isoDia(hoje) }),
  ultimos_60: (hoje = new Date()) => ({ de: isoDia(somaDias(hoje, -59)), ate: isoDia(hoje) }),
  ultimos_90: (hoje = new Date()) => ({ de: isoDia(somaDias(hoje, -89)), ate: isoDia(hoje) }),
  este_mes: (hoje = new Date()) => {
    const ini = new Date(Date.UTC(hoje.getUTCFullYear(), hoje.getUTCMonth(), 1));
    return { de: isoDia(ini), ate: isoDia(hoje) };
  },
  mes_passado: (hoje = new Date()) => {
    const ini = new Date(Date.UTC(hoje.getUTCFullYear(), hoje.getUTCMonth() - 1, 1));
    const fim = new Date(Date.UTC(hoje.getUTCFullYear(), hoje.getUTCMonth(), 0));
    return { de: isoDia(ini), ate: isoDia(fim) };
  },
};

export const PRESET_LABELS: Array<{ key: string; label: string }> = [
  { key: "ultimos_30", label: "Últimos 30d" },
  { key: "ultimos_60", label: "Últimos 60d" },
  { key: "ultimos_90", label: "Últimos 90d" },
  { key: "este_mes", label: "Este mês" },
  { key: "mes_passado", label: "Mês passado" },
];

function parseNum(s: string): number | undefined {
  if (s.trim() === "") return undefined;
  const n = Number(s.replace(",", "."));
  return Number.isFinite(n) ? n : undefined;
}

// Expande os chips selecionados nas chaves reais da API (sem duplicar).
export function expandirCategorias(
  cats: CategoriaChave[],
): Array<"ECOMMERCE" | "LEAD_COM_SITE" | "LEAD_SEM_SITE"> {
  const out = new Set<"ECOMMERCE" | "LEAD_COM_SITE" | "LEAD_SEM_SITE">();
  for (const c of cats) {
    if (c === "LEAD_AMBOS") {
      out.add("LEAD_COM_SITE");
      out.add("LEAD_SEM_SITE");
    } else {
      out.add(c);
    }
  }
  return Array.from(out);
}

// Converte o estado da UI no payload do endpoint agregado.
export function montarCriativosParams(
  st: FiltrosState,
  limit: number,
  offset: number,
): CriativosParams {
  const cats = expandirCategorias(st.categorias);
  const fatMin = parseNum(st.fatMin);
  const fatMax = parseNum(st.fatMax);
  const invMin = parseNum(st.invMin);
  const invMax = parseNum(st.invMax);
  const porCliente = st.faixaScope === "cliente";

  return {
    de: st.de,
    ate: st.ate,
    rede: st.rede,
    categoria: cats.length > 0 ? cats : undefined,
    gestor: st.gestor || undefined,
    cliente: st.cliente || undefined,
    fat_min: porCliente ? undefined : fatMin,
    fat_max: porCliente ? undefined : fatMax,
    inv_min: porCliente ? undefined : invMin,
    inv_max: porCliente ? undefined : invMax,
    cli_fat_min: porCliente ? fatMin : undefined,
    cli_fat_max: porCliente ? fatMax : undefined,
    cli_inv_min: porCliente ? invMin : undefined,
    cli_inv_max: porCliente ? invMax : undefined,
    order_by: st.orderBy,
    limit,
    offset,
  };
}
