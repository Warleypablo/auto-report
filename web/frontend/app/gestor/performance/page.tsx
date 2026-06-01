"use client";

import { useEffect, useState } from "react";

import GestorShell from "../_shell";
import { gestorApi } from "@/lib/api-gestor";
import type { CriativoAgregado, TotaisCriativos } from "@/lib/api-gestor";
import {
  FiltrosBar,
  type GestorOpt,
  type ClienteOpt,
} from "@/components/performance/FiltrosBar";
import {
  montarCriativosParams,
  type FiltrosState,
} from "@/lib/criativos-filtros";
import { useDebouncedValue } from "@/lib/use-debounce";
import {
  fmtRoas,
  roasTier,
  TIER_TEXT,
  TIER_BAR,
} from "@/lib/roas-tier";
import {
  ScatterChart,
  Scatter,
  XAxis,
  YAxis,
  ZAxis,
  Cell,
  ReferenceLine,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

type RankedCriativo = CriativoAgregado & { rank: number; rankDelta: number | null };

function fmtK(v: number | null): string {
  if (v == null || v === 0) return "—";
  if (v >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1).replace(".", ",")}M`;
  if (v >= 1_000) return `R$${(v / 1_000).toFixed(1).replace(".", ",")}k`;
  return `R$${Math.round(v)}`;
}

const MEDAL = ["🥇", "🥈", "🥉"];

// ── Imagem com fallback ───────────────────────────────────────────────────────

const THUMB_GRADIENTS = [
  ["#0a2e3d", "#06181f"],
  ["#2a1f4a", "#160f28"],
  ["#1a2f4a", "#0d1a28"],
  ["#3d2a1a", "#22160d"],
  ["#1a3d3d", "#0d2222"],
  ["#2a1a3d", "#160d22"],
  ["#3d1a2a", "#220d16"],
];

function nameHash(s: string): number {
  let h = 0;
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) & 0xffff;
  return h;
}

function AdThumbnail({ src, alt, className, semImagem }: { src: string | null; alt: string; className?: string; semImagem?: boolean }) {
  const safeAlt = alt && alt.trim().length > 0 ? alt : "Criativo";
  const [from, to] = THUMB_GRADIENTS[nameHash(safeAlt) % THUMB_GRADIENTS.length];
  const initial = (safeAlt.trim()[0] ?? "?").toUpperCase();
  // Anúncio sem criativo visual (ex.: search/texto): placeholder explícito de "texto",
  // distinto do gradiente com inicial — deixa claro que não há foto por natureza, e
  // não dá a impressão de uma imagem que falhou ao carregar.
  if (!src && semImagem) {
    return (
      <div
        className={`relative flex items-center justify-center overflow-hidden select-none bg-[var(--paper-deep)] ${className ?? ""}`}
        title="Anúncio de texto — sem imagem"
      >
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2} strokeLinecap="round" className="h-1/2 w-1/2 text-[var(--muted)] opacity-50">
          <line x1="5" y1="7" x2="19" y2="7" />
          <line x1="5" y1="12" x2="19" y2="12" />
          <line x1="5" y1="17" x2="13" y2="17" />
        </svg>
      </div>
    );
  }
  return (
    <div
      className={`relative overflow-hidden select-none ${className ?? ""}`}
      style={{ background: `linear-gradient(135deg, ${from} 0%, ${to} 100%)` }}
    >
      <span className="absolute inset-0 flex items-center justify-center font-display font-bold text-white/[0.07]" style={{ fontSize: "9rem", transform: "rotate(-10deg)" }}>
        {initial}
      </span>
      {src && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt=""
          className="absolute inset-0 h-full w-full object-cover"
          onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
        />
      )}
    </div>
  );
}

const TH = "pb-2 pt-3 text-[10px] font-normal uppercase tracking-widest text-[var(--muted)] whitespace-nowrap";

// ── KPI strip ─────────────────────────────────────────────────────────────────

function KpiStrip({ items }: { items: { label: string; value: string; sub?: string; highlight?: boolean }[] }) {
  return (
    <div className="mb-8 grid grid-cols-4 gap-3">
      {items.map(({ label, value, sub, highlight }) => (
        <div key={label} className={`relative overflow-hidden rounded-xl border bg-[var(--paper-soft)] px-5 py-5 ${highlight ? "border-[var(--forest)]/40 shadow-[0_0_28px_-8px_var(--forest)]" : "border-[var(--rule-soft)]"}`}>
          <div className="absolute left-0 top-3 bottom-3 w-0.5 rounded-full bg-gradient-to-b from-[var(--forest)] to-[var(--forest-deep)]" />
          <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">{label}</p>
          <p className={`font-display text-3xl font-medium leading-none ${highlight ? "text-[var(--forest)]" : "text-[var(--ink)]"}`}>{value}</p>
          {sub && <p className="mt-1.5 text-[10px] text-[var(--muted)]">{sub}</p>}
        </div>
      ))}
    </div>
  );
}

function fmtCpm(inv: number | null, imp: number | null): string {
  if (!inv || !imp) return "—";
  const cpm = (inv / imp) * 1000;
  return `R$${cpm.toFixed(2).replace(".", ",")}`;
}

function fmtImp(v: number | null): string {
  if (!v) return "—";
  if (v >= 1_000_000) return `${(v / 1_000_000).toFixed(1).replace(".", ",")}M`;
  if (v >= 1_000) return `${(v / 1_000).toFixed(0)}k`;
  return String(v);
}

function median(arr: number[]): number {
  if (arr.length === 0) return 0;
  const sorted = [...arr].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

const TIER_SCATTER_COLORS: Record<string, string> = {
  high: "var(--forest)",
  mid: "var(--amber)",
  low: "var(--crimson)",
  none: "var(--muted)",
};

// ── "Ver anúncio" ───────────────────────────────────────────────────────────

function VerAnuncioButton({ href }: { href: string | null }) {
  if (!href) return null;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      onClick={(e) => e.stopPropagation()}
      className="inline-block rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-2 py-0.5 text-[10px] text-[var(--forest)] transition hover:underline"
    >
      Ver anúncio ↗
    </a>
  );
}

// ── Pódio top 3 ───────────────────────────────────────────────────────────────

function Podium({ ads, maxRoas, onSelect }: {
  ads: RankedCriativo[];
  maxRoas: number;
  onSelect: (ad: RankedCriativo) => void;
}) {
  const top = ads.slice(0, 3);
  return (
    <div className="mb-4 grid grid-cols-3 gap-4">
      {top.map((ad) => {
        const tier = roasTier(ad.roas);
        const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;
        return (
          <button
            key={ad.criativo_id}
            onClick={() => onSelect(ad)}
            className="group relative overflow-hidden rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] text-left transition hover:border-[var(--forest)] hover:shadow-md"
          >
            <div className="relative h-40 w-full overflow-hidden">
              <AdThumbnail
                src={ad.thumb_url}
                alt={ad.nome ?? ad.cliente_nome}
                semImagem={ad.thumb_status === "sem_imagem"}
                className="h-full w-full object-cover transition group-hover:scale-[1.02]"
              />
              <span className="absolute left-2.5 top-2.5 text-xl drop-shadow">{MEDAL[ad.rank] ?? `#${ad.rank + 1}`}</span>
              <span className={`absolute right-2.5 top-2.5 rounded-md bg-[var(--paper)] px-2 py-0.5 text-xs font-semibold shadow ${TIER_TEXT[tier]}`}>
                {fmtRoas(ad.roas)}
              </span>
            </div>
            <div className="px-3.5 py-3">
              <p className="mb-0.5 truncate text-xs font-medium text-[var(--ink)]" title={ad.nome ?? ""}>{ad.nome ?? "Sem nome"}</p>
              <p className="mb-2 truncate text-[10px] text-[var(--muted)]">{ad.cliente_nome} · {ad.rede === "meta" ? "Meta" : "Google"}</p>
              <div className="mb-3 h-1 w-full rounded-full bg-[var(--paper-deep)]">
                <div className={`h-1 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
              </div>
              <div className="mb-2 grid grid-cols-2 gap-x-3 gap-y-1.5">
                <div>
                  <p className="text-[9px] uppercase tracking-widest text-[var(--muted)]">Faturamento</p>
                  <p className="font-mono-num text-xs font-medium text-[var(--forest)]">{fmtK(ad.faturamento)}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-widest text-[var(--muted)]">Investimento</p>
                  <p className="font-mono-num text-xs text-[var(--ink)]">{fmtK(ad.investimento)}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-widest text-[var(--muted)]">CPM</p>
                  <p className="font-mono-num text-xs text-[var(--ink)]">{fmtCpm(ad.investimento, ad.impressoes)}</p>
                </div>
                <div>
                  <p className="text-[9px] uppercase tracking-widest text-[var(--muted)]">Impressões</p>
                  <p className="font-mono-num text-xs text-[var(--ink)]">{fmtImp(ad.impressoes)}</p>
                </div>
              </div>
              <VerAnuncioButton href={ad.preview_link} />
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ── Tabela compacta (#4+) ─────────────────────────────────────────────────────

function Tabela({ ads, maxRoas, onSelect }: {
  ads: RankedCriativo[];
  maxRoas: number;
  onSelect: (ad: RankedCriativo) => void;
}) {
  if (ads.length === 0) return null;
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--rule-soft)]">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
            <th className={`${TH} pl-4 pr-2 w-10 text-left`}>#</th>
            <th className={`${TH} px-3 text-left`}>Criativo</th>
            <th className={`${TH} px-3 text-left`}>Cliente</th>
            <th className={`${TH} px-3 text-left hidden md:table-cell`}>Rede</th>
            <th className={`${TH} px-3 text-right`}>ROAS</th>
            <th className={`${TH} px-3 text-right`}>Faturamento</th>
            <th className={`${TH} px-3 text-right hidden md:table-cell`}>Investimento</th>
            <th className={`${TH} px-3 text-right hidden lg:table-cell`}>CPM</th>
            <th className={`${TH} px-3 text-right hidden lg:table-cell`}>Impressões</th>
            <th className={`${TH} px-3 text-right hidden xl:table-cell`}>Conv.</th>
            <th className={`${TH} pl-3 pr-4 text-right hidden xl:table-cell`}>CPA/CPL</th>
            <th className="w-20 pr-3"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--rule-soft)]">
          {ads.map((ad) => {
            const tier = roasTier(ad.roas);
            const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;
            return (
              <tr
                key={ad.criativo_id}
                onClick={() => onSelect(ad)}
                className="group cursor-pointer bg-[var(--paper)] transition hover:bg-[var(--paper-soft)]"
              >
                <td className="py-3 pl-0 pr-2">
                  <div className="flex items-center gap-0">
                    <div className={`mr-3 h-8 w-0.5 rounded-full ${TIER_BAR[tier]}`} />
                    <span className="font-mono-num text-xs text-[var(--muted)]">{ad.rank + 1}</span>
                  </div>
                </td>
                <td className="max-w-[200px] px-3 py-3">
                  <div className="flex items-center gap-2.5">
                    <div className="h-9 w-14 flex-shrink-0 overflow-hidden rounded-md">
                      <AdThumbnail src={ad.thumb_url} alt={ad.nome ?? ad.cliente_nome} semImagem={ad.thumb_status === "sem_imagem"} className="h-full w-full object-cover" />
                    </div>
                    <span className="block truncate text-xs font-medium text-[var(--ink)]" title={ad.nome ?? ""}>{ad.nome ?? "Sem nome"}</span>
                  </div>
                </td>
                <td className="whitespace-nowrap px-3 py-3 text-xs text-[var(--muted)]">{ad.cliente_nome}</td>
                <td className="hidden whitespace-nowrap px-3 py-3 text-xs text-[var(--muted)] md:table-cell">{ad.rede === "meta" ? "Meta" : "Google"}</td>
                <td className="px-3 py-3 text-right">
                  <span className={`font-mono-num text-sm font-semibold ${TIER_TEXT[tier]}`}>{fmtRoas(ad.roas)}</span>
                  <div className="mt-1 h-0.5 w-full rounded-full bg-[var(--paper-deep)]">
                    <div className={`h-0.5 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
                  </div>
                </td>
                <td className="px-3 py-3 text-right font-mono-num text-xs text-[var(--forest)]">{fmtK(ad.faturamento)}</td>
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] md:table-cell">{fmtK(ad.investimento)}</td>
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] lg:table-cell">{fmtCpm(ad.investimento, ad.impressoes)}</td>
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] lg:table-cell">{fmtImp(ad.impressoes)}</td>
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] xl:table-cell">{ad.conversoes ?? "—"}</td>
                <td className="hidden pl-3 pr-4 py-3 text-right font-mono-num text-xs text-[var(--muted)] xl:table-cell">
                  {ad.cpa != null ? fmtK(ad.cpa) : fmtK(ad.cpl)}
                </td>
                <td className="pr-3 py-3 text-right">
                  <VerAnuncioButton href={ad.preview_link} />
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

// ── Scatter view ─────────────────────────────────────────────────────────────

type ScatterDot = {
  x: number;
  y: number;
  z: number;
  nome: string;
  clienteNome: string;
  roas: number | null;
};

function ScatterTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: ScatterDot }> }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  const tier = roasTier(d.roas);
  return (
    <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2.5 text-xs shadow-xl">
      <p className="mb-0.5 max-w-[200px] truncate font-medium text-[var(--ink)]">{d.nome}</p>
      <p className="mb-2 text-[var(--muted)]">{d.clienteNome}</p>
      <p className={`font-mono-num font-semibold ${TIER_TEXT[tier]}`}>ROAS {fmtRoas(d.roas)}</p>
      <p className="font-mono-num text-[var(--forest)]">Fat. {fmtK(d.y)}</p>
      <p className="font-mono-num text-[var(--muted)]">Inv. {fmtK(d.x)}</p>
    </div>
  );
}

function ScatterView({ ads }: { ads: RankedCriativo[] }) {
  const data: ScatterDot[] = ads
    .filter((a) => a.investimento != null && a.faturamento != null && a.investimento > 0)
    .map((a) => ({
      x: a.investimento,
      y: a.faturamento,
      z: Math.max(a.impressoes ?? 300, 300),
      nome: a.nome ?? "Sem nome",
      clienteNome: a.cliente_nome,
      roas: a.roas,
    }));

  if (data.length === 0) {
    return (
      <p className="rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-12 text-center text-sm text-[var(--muted)]">
        Sem dados suficientes para o scatter.
      </p>
    );
  }

  const medInv = median(data.map((d) => d.x));
  const medFat = median(data.map((d) => d.y));

  return (
    <div className="rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-5">
      <div className="mb-4 flex flex-wrap items-center gap-x-6 gap-y-2">
        <p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Investimento × Faturamento</p>
        <div className="flex flex-wrap items-center gap-4">
          {(["high", "mid", "low"] as const).map((tier) => (
            <span key={tier} className="flex items-center gap-1.5 text-[9px] text-[var(--muted)]">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: TIER_SCATTER_COLORS[tier] }} />
              {tier === "high" ? "ROAS ≥ 3×" : tier === "mid" ? "1,5× – 3×" : "< 1,5×"}
            </span>
          ))}
          <span className="text-[9px] text-[var(--muted)] opacity-50">tamanho = impressões</span>
        </div>
      </div>
      <ResponsiveContainer width="100%" height={440}>
        <ScatterChart margin={{ top: 10, right: 30, bottom: 44, left: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="var(--rule-soft)" opacity={0.4} />
          <XAxis
            dataKey="x"
            type="number"
            name="Investimento"
            tickFormatter={(v: number) => fmtK(v)}
            tick={{ fontSize: 10, fill: "var(--muted)" }}
            label={{ value: "Investimento", position: "insideBottom", offset: -28, fontSize: 10, fill: "var(--muted)" }}
          />
          <YAxis
            dataKey="y"
            type="number"
            name="Faturamento"
            tickFormatter={(v: number) => fmtK(v)}
            tick={{ fontSize: 10, fill: "var(--muted)" }}
            label={{ value: "Faturamento", angle: -90, position: "insideLeft", offset: 20, fontSize: 10, fill: "var(--muted)" }}
          />
          <ZAxis dataKey="z" range={[30, 300]} name="Impressões" />
          <Tooltip cursor={{ strokeDasharray: "3 3" }} content={<ScatterTooltip />} />
          <ReferenceLine
            x={medInv}
            stroke="rgba(255,255,255,0.18)"
            strokeDasharray="5 4"
            label={{ value: "med.", position: "insideTopRight", fontSize: 8, fill: "rgba(255,255,255,0.3)" }}
          />
          <ReferenceLine
            y={medFat}
            stroke="rgba(255,255,255,0.18)"
            strokeDasharray="5 4"
            label={{ value: "med.", position: "insideTopRight", fontSize: 8, fill: "rgba(255,255,255,0.3)" }}
          />
          <Scatter data={data} isAnimationActive={false}>
            {data.map((d, i) => (
              <Cell
                key={`cell-${i}`}
                fill={TIER_SCATTER_COLORS[roasTier(d.roas)]}
                fillOpacity={0.8}
              />
            ))}
          </Scatter>
        </ScatterChart>
      </ResponsiveContainer>
      <p className="mt-2 text-[9px] text-[var(--muted)] opacity-50">
        Quadrante superior esquerdo = alto faturamento com baixo investimento — criativos mais eficientes da carteira. As linhas marcam a mediana.
      </p>
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

const PAGE_SIZE = 50;

function hojeIso(): string {
  const d = new Date();
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
}
function trintaDiasAtrasIso(): string {
  const d = new Date();
  d.setUTCDate(d.getUTCDate() - 29);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
}

const FILTROS_INICIAIS: FiltrosState = {
  de: trintaDiasAtrasIso(),
  ate: hojeIso(),
  rede: "todos",
  categorias: [],
  gestor: "",
  cliente: "",
  faixaScope: "criativo",
  fatMin: "",
  fatMax: "",
  invMin: "",
  invMax: "",
  orderBy: "roas",
};

// Ao selecionar um criativo, abre o preview_link em nova aba e limpa a seleção.
function SelectRedirect({ href, onDone }: { href: string; onDone: () => void }) {
  useEffect(() => {
    window.open(href, "_blank", "noopener,noreferrer");
    onDone();
  }, [href, onDone]);
  return null;
}

export default function RankingsPage() {
  const [filtros, setFiltros] = useState<FiltrosState>(FILTROS_INICIAIS);
  const [view, setView] = useState<"ranking" | "scatter">("ranking");
  const [ads, setAds] = useState<RankedCriativo[]>([]);
  const [total, setTotal] = useState(0);
  const [totais, setTotais] = useState<TotaisCriativos | null>(null);
  const [offset, setOffset] = useState(0);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [selected, setSelected] = useState<RankedCriativo | null>(null);
  const [gestores, setGestores] = useState<GestorOpt[]>([]);
  const [clientes, setClientes] = useState<ClienteOpt[]>([]);

  // Filtros debounceados: muda de identidade só 400ms após a última edição.
  const filtrosDeb = useDebouncedValue(filtros, 400);

  // Carrega opções de gestor/cliente (uma vez).
  useEffect(() => {
    let cancelled = false;
    gestorApi.clientes().then(({ items }) => {
      if (cancelled) return;
      const ativos = items.filter((c) => c.ativo);
      const gset = new Map<string, string>();
      for (const c of ativos) if (c.gestor) gset.set(c.gestor, c.gestor);
      setGestores(Array.from(gset.keys()).sort((a, b) => a.localeCompare(b)).map((g) => ({ value: g, label: g })));
      setClientes(
        ativos
          .map((c) => ({ slug: c.slug, nome: c.nome }))
          .sort((a, b) => a.nome.localeCompare(b.nome)),
      );
    }).catch(() => undefined);
    return () => { cancelled = true; };
  }, []);

  // Reset de paginação quando os filtros (debounceados) mudam.
  useEffect(() => {
    setOffset(0);
  }, [filtrosDeb]);

  // Fetch principal: refaz a cada mudança de filtro debounceado ou de offset.
  useEffect(() => {
    let cancelled = false;
    const primeiraPagina = offset === 0;
    if (primeiraPagina) setLoading(true);
    else setLoadingMore(true);

    const params = montarCriativosParams(filtrosDeb, PAGE_SIZE, offset);
    gestorApi
      .criativos(params)
      .then((res) => {
        if (cancelled) return;
        setTotal(res.total);
        setTotais(res.totais);
        const ranked: RankedCriativo[] = res.items.map((it, i) => ({
          ...it,
          rank: offset + i,
          rankDelta: null,
        }));
        setAds((prev) => (primeiraPagina ? ranked : [...prev, ...ranked]));
      })
      .catch(() => {
        if (!cancelled && primeiraPagina) {
          setAds([]);
          setTotal(0);
          setTotais(null);
        }
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
        setLoadingMore(false);
      });
    return () => { cancelled = true; };
  }, [filtrosDeb, offset]);

  // KPIs do PERÍODO inteiro (vêm do backend), não a soma da página carregada —
  // somar só a página (top-N por ROAS) subestima muito o investimento da carteira.
  const totalFat = totais?.faturamento ?? null;
  const totalInv = totais?.investimento ?? null;
  const roasMedio = totais?.roas ?? null;
  const maxRoas = ads.length > 0 ? Math.max(...ads.filter((a) => a.roas != null).map((a) => a.roas ?? 0)) : 0;
  const rest = ads.slice(3);
  const temMais = ads.length < total;

  return (
    <GestorShell>
    <main className="mx-auto max-w-6xl px-6 py-12">
      <div className="mb-8">
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
              Performance
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">Rankings de criativos da carteira</p>
          </div>
        </div>
        <FiltrosBar state={filtros} onChange={setFiltros} gestores={gestores} clientes={clientes} />
      </div>

      {/* Tabs de rede + view toggle */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <div className="flex gap-1.5">
          {(["todos", "meta", "google"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setFiltros((f) => ({ ...f, rede: r }))}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                filtros.rede === r
                  ? "bg-[var(--forest)] text-[var(--on-accent)] shadow-[0_0_16px_-4px_var(--forest)]"
                  : "bg-[var(--paper-soft)] text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]"
              }`}
            >
              {r === "todos" ? "Todos" : r === "meta" ? "Meta Ads" : "Google Ads"}
            </button>
          ))}
        </div>
        <div className="flex gap-1">
          {(["ranking", "scatter"] as const).map((v) => (
            <button
              key={v}
              onClick={() => setView(v)}
              title={v === "scatter" ? "Scatter: investimento × faturamento" : "Ranking por ROAS"}
              className={`rounded-md px-3 py-1.5 text-xs font-medium transition ${
                view === v
                  ? "bg-[var(--paper-deep)] text-[var(--forest)] ring-1 ring-[var(--forest)]/25"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
            >
              {v === "ranking" ? "Ranking" : "Scatter"}
            </button>
          ))}
        </div>
      </div>

      {loading ? (
        <div className="flex items-center justify-center py-24">
          <p className="text-sm text-[var(--muted)]">Carregando…</p>
        </div>
      ) : ads.length === 0 ? (
        <p data-testid="criativos-empty" className="rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-12 text-center text-sm text-[var(--muted)]">
          Nenhum criativo encontrado para os filtros selecionados.
        </p>
      ) : (
        <>
          <KpiStrip items={[
            { label: "Criativos", value: `${totais?.criativos ?? total}`, sub: "no período" },
            { label: "Faturamento total", value: totalFat != null ? fmtK(totalFat) : "—", sub: "no período", highlight: true },
            { label: "Investimento total", value: totalInv != null ? fmtK(totalInv) : "—", sub: "no período" },
            { label: "ROAS médio", value: roasMedio != null ? fmtRoas(roasMedio) : "—", sub: "ponderado · no período" },
          ]} />

          {view === "scatter" ? (
            <ScatterView ads={ads} />
          ) : (
            <>
              {ads.length >= 1 && (
                <div className="mb-2">
                  <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Top 3 criativos</p>
                  <Podium ads={ads} maxRoas={maxRoas} onSelect={setSelected} />
                </div>
              )}
              {rest.length > 0 && (
                <div className="mt-4" data-testid="criativos-tabela">
                  <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Demais criativos</p>
                  <Tabela ads={rest} maxRoas={maxRoas} onSelect={setSelected} />
                </div>
              )}
              {temMais && (
                <div className="mt-6 flex justify-center">
                  <button
                    onClick={() => setOffset((o) => o + PAGE_SIZE)}
                    disabled={loadingMore}
                    className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-5 py-2.5 text-xs font-medium text-[var(--ink)] transition hover:border-[var(--forest)] disabled:opacity-50"
                  >
                    {loadingMore ? "Carregando…" : `Carregar mais (${ads.length}/${total})`}
                  </button>
                </div>
              )}
            </>
          )}
        </>
      )}

      {selected && selected.preview_link && (
        <SelectRedirect href={selected.preview_link} onDone={() => setSelected(null)} />
      )}
    </main>
    </GestorShell>
  );
}
