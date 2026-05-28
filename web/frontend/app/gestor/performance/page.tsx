"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import GestorShell from "../_shell";
import { gestorApi } from "@/lib/api-gestor";
import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import { deslocarMes, mesUltimoFechado } from "@/lib/mes-utils";
import {
  fmtRoas,
  roasTier,
  sortByRoas,
  TIER_TEXT,
  TIER_BAR,
} from "@/lib/roas-tier";
import {
  ScatterChart,
  Scatter,
  ComposedChart,
  Bar,
  Line,
  XAxis,
  YAxis,
  ZAxis,
  Cell,
  ReferenceLine,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from "recharts";

type RankedMetaAd = MetaAd & { clienteNome: string; clienteSlug: string; gestorNome: string | null; rank: number; rankDelta: number | null };
type RankedGoogleAd = GoogleAd & { clienteNome: string; clienteSlug: string; gestorNome: string | null; rank: number; rankDelta: number | null };

type HistoryPoint = {
  mes: string;
  mesLabel: string;
  roas: number | null;
  cpm: number | null;
  investimento: number | null;
  faturamento: number | null;
};

const MES_ABBR: Record<string, string> = {
  "01": "Jan", "02": "Fev", "03": "Mar", "04": "Abr",
  "05": "Mai", "06": "Jun", "07": "Jul", "08": "Ago",
  "09": "Set", "10": "Out", "11": "Nov", "12": "Dez",
};

function detectFadiga(history: HistoryPoint[]): { label: string; kind: "fadiga" | "queda" | "saudavel" } | null {
  const withData = history.filter(p => p.roas !== null);
  if (withData.length < 2) return null;
  const prev = withData[withData.length - 2];
  const last = withData[withData.length - 1];
  if (
    prev.cpm !== null && last.cpm !== null &&
    last.cpm > prev.cpm * 1.15 &&
    prev.roas !== null && last.roas !== null &&
    last.roas < prev.roas * 0.85
  ) {
    return { label: "⚠️ Fadiga detectada", kind: "fadiga" };
  }
  if (prev.roas !== null && last.roas !== null && last.roas < prev.roas * 0.80) {
    return { label: "↘ Performance em queda", kind: "queda" };
  }
  return { label: "✓ Saudável", kind: "saudavel" };
}

function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]} ${ano}`;
}

function fmtK(v: number | null): string {
  if (v == null || v === 0) return "—";
  if (v >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1).replace(".", ",")}M`;
  if (v >= 1_000) return `R$${(v / 1_000).toFixed(1).replace(".", ",")}k`;
  return `R$${Math.round(v)}`;
}

function fmtPct(v: number): string {
  return `${v.toFixed(1).replace(".", ",")}%`;
}

const MEDAL = ["🥇", "🥈", "🥉"];

// ── Imagem com fallback ───────────────────────────────────────────────────────

const THUMB_GRADIENTS = [
  ["#1a3d2e", "#0d2019"],
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

function AdThumbnail({ src, alt, className }: { src: string | null; alt: string; className?: string }) {
  const [from, to] = THUMB_GRADIENTS[nameHash(alt) % THUMB_GRADIENTS.length];
  const initial = (alt.trim()[0] ?? "?").toUpperCase();
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

function RankDeltaBadge({ delta }: { delta: number | null }) {
  if (delta === null) return <span className="text-[9px] text-[var(--muted)] opacity-50">novo</span>;
  if (delta === 0) return null;
  const up = delta > 0;
  return (
    <span className={`text-[9px] font-semibold ${up ? "text-emerald-400" : "text-red-400"}`}>
      {up ? `▲${delta}` : `▼${Math.abs(delta)}`}
    </span>
  );
}

// ── KPI strip ─────────────────────────────────────────────────────────────────

function KpiStrip({ items }: { items: { label: string; value: string; sub?: string; highlight?: boolean }[] }) {
  return (
    <div className="mb-8 grid grid-cols-4 gap-3">
      {items.map(({ label, value, sub, highlight }) => (
        <div key={label} className="relative overflow-hidden rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-5 py-5">
          <div className="absolute left-0 top-3 bottom-3 w-0.5 rounded-full bg-[var(--forest)] opacity-30" />
          <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">{label}</p>
          <p className={`font-display text-3xl font-medium leading-none ${highlight ? "text-[var(--forest)]" : "text-[var(--ink)]"}`}>{value}</p>
          {sub && <p className="mt-1.5 text-[10px] text-[var(--muted)]">{sub}</p>}
        </div>
      ))}
    </div>
  );
}

// ── Pódio top 3 ───────────────────────────────────────────────────────────────

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
  high: "#34d399",
  mid: "#facc15",
  low: "#f87171",
  none: "#6b7280",
};

function PodiumMeta({ ads, maxRoas, onSelect }: {
  ads: RankedMetaAd[];
  maxRoas: number;
  onSelect: (ad: RankedMetaAd) => void;
}) {
  const top = ads.slice(0, 3);
  return (
    <div className="mb-4 grid grid-cols-3 gap-4">
      {top.map((ad) => {
        const tier = roasTier(ad.roas);
        const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;
        return (
          <button
            key={`${ad.clienteSlug}-${ad.nome}`}
            onClick={() => onSelect(ad)}
            className="group relative overflow-hidden rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] text-left transition hover:border-[var(--forest)] hover:shadow-md"
          >
            {/* Imagem */}
            <div className="relative h-40 w-full overflow-hidden">
              <AdThumbnail
                src={ad.imagem_url}
                alt={ad.nome}
                className="h-full w-full object-cover transition group-hover:scale-[1.02]"
              />
              <span className="absolute left-2.5 top-2.5 text-xl drop-shadow">{MEDAL[ad.rank]}</span>
              {(ad.rankDelta !== 0) && (
                <span className={`absolute left-2 bottom-2 rounded px-1.5 py-0.5 text-[9px] font-semibold backdrop-blur-sm ${
                  ad.rankDelta === null
                    ? "bg-black/30 text-white/50"
                    : ad.rankDelta > 0
                    ? "bg-emerald-900/60 text-emerald-300"
                    : "bg-red-900/60 text-red-300"
                }`}>
                  {ad.rankDelta === null ? "novo" : ad.rankDelta > 0 ? `▲${ad.rankDelta}` : `▼${Math.abs(ad.rankDelta)}`}
                </span>
              )}
              <span className={`absolute right-2.5 top-2.5 rounded-md bg-[var(--paper)] px-2 py-0.5 text-xs font-semibold shadow ${TIER_TEXT[tier]}`}>
                {fmtRoas(ad.roas)}
              </span>
            </div>

            {/* Info */}
            <div className="px-3.5 py-3">
              <p className="mb-0.5 truncate text-xs font-medium text-[var(--ink)]" title={ad.nome}>{ad.nome}</p>
              <p className="mb-3 truncate text-[10px] text-[var(--muted)]">{ad.clienteNome}</p>
              <div className="mb-3 h-1 w-full rounded-full bg-[var(--paper-deep)]">
                <div className={`h-1 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
              </div>
              <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
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
            </div>
          </button>
        );
      })}
    </div>
  );
}

function PodiumGoogle({ ads, maxRoas, onSelect }: {
  ads: RankedGoogleAd[];
  maxRoas: number;
  onSelect: (ad: RankedGoogleAd) => void;
}) {
  const top = ads.slice(0, 3);
  return (
    <div className="mb-4 grid grid-cols-3 gap-4">
      {top.map((ad) => {
        const tier = roasTier(ad.roas);
        const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;
        return (
          <button
            key={`${ad.clienteSlug}-${ad.nome}`}
            onClick={() => onSelect(ad)}
            className="group rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4 text-left transition hover:border-[var(--forest)] hover:shadow-md"
          >
            <div className="mb-3 flex items-start justify-between gap-2">
              <div className="flex items-center gap-2">
                <span className="text-xl">{MEDAL[ad.rank]}</span>
                {(ad.rankDelta !== 0) && (
                  <span className={`rounded px-1.5 py-0.5 text-[9px] font-semibold ${
                    ad.rankDelta === null
                      ? "bg-[var(--paper-deep)] text-[var(--muted)]"
                      : ad.rankDelta > 0
                      ? "bg-emerald-900/40 text-emerald-300"
                      : "bg-red-900/40 text-red-300"
                  }`}>
                    {ad.rankDelta === null ? "novo" : ad.rankDelta > 0 ? `▲${ad.rankDelta}` : `▼${Math.abs(ad.rankDelta)}`}
                  </span>
                )}
              </div>
              <span className={`rounded-md bg-[var(--paper)] px-2 py-0.5 text-xs font-semibold shadow ${TIER_TEXT[tier]}`}>
                {fmtRoas(ad.roas)}
              </span>
            </div>
            <p className="mb-0.5 line-clamp-2 text-xs font-medium leading-snug text-[var(--ink)]" title={ad.nome}>{ad.nome}</p>
            <p className="mb-3 truncate text-[10px] text-[var(--muted)]">{ad.clienteNome}</p>
            <div className="mb-3 h-1 w-full rounded-full bg-[var(--paper-deep)]">
              <div className={`h-1 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
            </div>
            <div className="grid grid-cols-2 gap-x-3 gap-y-1.5">
              <div>
                <p className="text-[9px] uppercase tracking-widest text-[var(--muted)]">Faturamento</p>
                <p className="font-mono-num text-xs font-medium text-[var(--forest)]">{fmtK(ad.faturamento)}</p>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-widest text-[var(--muted)]">Investimento</p>
                <p className="font-mono-num text-xs text-[var(--ink)]">{fmtK(ad.investimento)}</p>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-widest text-[var(--muted)]">Conv.</p>
                <p className="font-mono-num text-xs text-[var(--ink)]">{ad.conversoes ?? "—"}</p>
              </div>
              <div>
                <p className="text-[9px] uppercase tracking-widest text-[var(--muted)]">Impressões</p>
                <p className="font-mono-num text-xs text-[var(--ink)]">{fmtImp(ad.impressoes)}</p>
              </div>
            </div>
          </button>
        );
      })}
    </div>
  );
}

// ── Evolução temporal ─────────────────────────────────────────────────────────

function EvolucaoTooltip({ active, payload }: { active?: boolean; payload?: { payload: HistoryPoint }[] }) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1.5 font-medium text-[var(--ink)]">{d.mesLabel}</p>
      <p style={{ color: "#34d399" }}>ROAS: {d.roas != null ? `${d.roas.toFixed(2)}×` : "—"}</p>
      <p style={{ color: "#f59e0b" }}>CPM: {d.cpm != null ? fmtK(d.cpm) : "—"}</p>
      <p className="text-[var(--muted)]">Faturamento: {fmtK(d.faturamento)}</p>
      <p className="text-[var(--muted)]">Investimento: {fmtK(d.investimento)}</p>
    </div>
  );
}

function EvolucaoTab({
  clienteSlug,
  adNome,
  adType,
  mes,
}: {
  clienteSlug: string;
  adNome: string;
  adType: "meta" | "google";
  mes: string;
}) {
  const [history, setHistory] = useState<HistoryPoint[] | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const meses = Array.from({ length: 6 }, (_, i) => deslocarMes(mes, -i)).reverse();
    Promise.all(
      meses.map(m => gestorApi.metricasBreakdown(clienteSlug, m).catch(() => null))
    ).then(results => {
      const pts: HistoryPoint[] = meses.map((m, i) => {
        const bd = results[i];
        const ads = adType === "meta" ? (bd?.meta_ads ?? []) : (bd?.google_ads ?? []);
        const ad = ads.find(a => a.nome === adNome) ?? null;
        const cpm =
          ad?.investimento && ad?.impressoes && ad.impressoes > 0
            ? (ad.investimento / ad.impressoes) * 1000
            : null;
        return {
          mes: m,
          mesLabel: MES_ABBR[m.slice(5, 7)] ?? m.slice(5, 7),
          roas: ad?.roas ?? null,
          cpm,
          investimento: ad?.investimento ?? null,
          faturamento: ad?.faturamento ?? null,
        };
      });
      setHistory(pts);
      setLoading(false);
    }).catch(() => {
      setHistory([]);
      setLoading(false);
    });
  }, [clienteSlug, adNome, adType, mes]);

  if (loading) {
    return (
      <div className="mt-6 space-y-3 px-1">
        <div className="h-[180px] animate-pulse rounded-xl bg-[var(--paper-deep)]" />
        <div className="flex gap-2">
          {[78, 55, 90, 45, 70, 60].map((w, i) => (
            <div key={i} className="animate-pulse rounded bg-[var(--paper-deep)]" style={{ height: 4, width: `${w}px`, animationDelay: `${i * 80}ms` }} />
          ))}
        </div>
      </div>
    );
  }

  const hasAnyData = history?.some(p => p.roas !== null) ?? false;

  if (!hasAnyData) {
    return (
      <div className="mt-10 text-center text-xs text-[var(--muted)]">
        Sem histórico disponível para este criativo.
      </div>
    );
  }

  const diagnosis = detectFadiga(history!);

  return (
    <div className="mt-4">
      {diagnosis && (
        <div className={`mb-4 inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-xs font-medium ${
          diagnosis.kind === "fadiga"
            ? "bg-amber-900/30 text-amber-300"
            : diagnosis.kind === "queda"
            ? "bg-red-900/30 text-red-300"
            : "bg-emerald-900/30 text-emerald-300"
        }`}>
          {diagnosis.label}
        </div>
      )}

      <ResponsiveContainer width="100%" height={200}>
        <ComposedChart data={history!} margin={{ top: 4, right: 8, bottom: 0, left: -16 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
          <XAxis
            dataKey="mesLabel"
            tick={{ fontSize: 9, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            yAxisId="ratio"
            tick={{ fontSize: 9, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => `${v}×`}
          />
          <YAxis
            yAxisId="reais"
            orientation="right"
            tick={{ fontSize: 9, fill: "#6b7280" }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v: number) => fmtK(v)}
          />
          <Bar yAxisId="reais" dataKey="faturamento" fill="#34d399" opacity={0.22} radius={[2, 2, 0, 0]} />
          <Bar yAxisId="reais" dataKey="investimento" fill="#6b7280" opacity={0.18} radius={[2, 2, 0, 0]} />
          <Line
            yAxisId="ratio"
            type="monotone"
            dataKey="roas"
            stroke="#34d399"
            strokeWidth={2}
            dot={{ r: 3, fill: "#34d399", strokeWidth: 0 }}
            connectNulls={false}
          />
          <Line
            yAxisId="reais"
            type="monotone"
            dataKey="cpm"
            stroke="#f59e0b"
            strokeWidth={1.5}
            strokeDasharray="4 2"
            dot={{ r: 2, fill: "#f59e0b", strokeWidth: 0 }}
            connectNulls={false}
          />
          <Tooltip content={<EvolucaoTooltip />} />
        </ComposedChart>
      </ResponsiveContainer>

      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-[9px] text-[var(--muted)]">
        <span className="flex items-center gap-1">
          <span className="inline-block h-0.5 w-4 rounded" style={{ background: "#34d399" }} />
          ROAS
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block w-4 border-t-2 border-dashed" style={{ borderColor: "#f59e0b" }} />
          CPM
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "#34d399", opacity: 0.5 }} />
          Fat.
        </span>
        <span className="flex items-center gap-1">
          <span className="inline-block h-2.5 w-2.5 rounded-sm" style={{ background: "#6b7280", opacity: 0.4 }} />
          Inv.
        </span>
      </div>
    </div>
  );
}

// ── Drawer helpers ────────────────────────────────────────────────────────────

function MetricRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-[var(--rule-soft)] py-2 last:border-0">
      <span className="text-xs text-[var(--muted)]">{label}</span>
      <span className={`font-mono-num text-sm ${highlight ? "font-semibold text-[var(--forest)]" : "text-[var(--ink)]"}`}>
        {value}
      </span>
    </div>
  );
}

function ContextBar({ label, pct }: { label: string; pct: number }) {
  return (
    <div className="mb-3">
      <div className="mb-1 flex justify-between text-[10px] text-[var(--muted)]">
        <span>{label}</span>
        <span>{fmtPct(pct)}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
        <div className="h-1.5 rounded-full bg-[var(--forest)] opacity-70" style={{ width: `${Math.min(pct, 100)}%` }} />
      </div>
    </div>
  );
}

// ── Drawers ───────────────────────────────────────────────────────────────────

function MetaDrawer({ ad, allAds, onClose, mes }: { ad: RankedMetaAd; allAds: RankedMetaAd[]; onClose: () => void; mes: string }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const [drawerTab, setDrawerTab] = useState<"metricas" | "evolucao">("metricas");

  const tier = roasTier(ad.roas);
  const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0);
  const avgRoas = adsComRoas.length > 0 ? adsComRoas.reduce((s, a) => s + (a.roas ?? 0), 0) / adsComRoas.length : null;
  const roasVsAvg = avgRoas && ad.roas ? ad.roas / avgRoas : null;
  const maxRoas = adsComRoas.length > 0 ? Math.max(...adsComRoas.map((a) => a.roas ?? 0)) : 0;
  const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;
  const totalInv = allAds.reduce((s, a) => s + (a.investimento ?? 0), 0);
  const totalFat = allAds.reduce((s, a) => s + (a.faturamento ?? 0), 0);
  const shareInv = totalInv > 0 && ad.investimento ? (ad.investimento / totalInv) * 100 : null;
  const shareFat = totalFat > 0 && ad.faturamento ? (ad.faturamento / totalFat) * 100 : null;
  const cpm = ad.impressoes && ad.investimento && ad.impressoes > 0 ? (ad.investimento / ad.impressoes) * 1000 : null;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]" onClick={onClose} />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-[380px] flex-col bg-[var(--paper)] shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-[var(--rule-soft)] px-5 py-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-[var(--ink)]" title={ad.nome}>{ad.nome}</p>
            <p className="text-xs text-[var(--muted)]">{ad.clienteNome}</p>
          </div>
          <button onClick={onClose} className="mt-0.5 flex-shrink-0 text-lg leading-none text-[var(--muted)] transition hover:text-[var(--ink)]">×</button>
        </div>

        {/* Abas */}
        <div className="flex border-b border-[var(--rule-soft)] px-5">
          {(["metricas", "evolucao"] as const).map(t => (
            <button
              key={t}
              onClick={() => setDrawerTab(t)}
              className={`mr-5 pb-2 pt-2.5 text-xs transition ${
                drawerTab === t
                  ? "border-b-2 border-[var(--forest)] font-medium text-[var(--ink)]"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
            >
              {t === "metricas" ? "Métricas" : "Evolução"}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {drawerTab === "evolucao" ? (
            <EvolucaoTab
              clienteSlug={ad.clienteSlug}
              adNome={ad.nome}
              adType="meta"
              mes={mes}
            />
          ) : (
            <>
          {ad.imagem_url && (
            <div className="mb-5 overflow-hidden rounded-xl border border-[var(--rule-soft)]" style={{ height: 220 }}>
              <AdThumbnail src={ad.imagem_url} alt={ad.nome} className="h-full w-full object-cover" />
            </div>
          )}

          {/* Rank + ROAS */}
          <div className="mb-5 flex items-center gap-3">
            {ad.rank < 3 && <span className="text-2xl">{MEDAL[ad.rank]}</span>}
            {ad.rank >= 3 && <span className="font-mono-num text-sm text-[var(--muted)]">#{ad.rank + 1}</span>}
            <div className="flex-1 min-w-0">
              <div className="mb-1 flex items-center justify-between">
                <span className={`font-mono-num text-lg font-semibold ${TIER_TEXT[tier]}`}>{fmtRoas(ad.roas)}</span>
                <span className="text-[10px] text-[var(--muted)]">{adsComRoas.length} criativos</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
                <div className={`h-1.5 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
              </div>
            </div>
          </div>

          <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">Métricas</p>
          <div className="mb-5 rounded-xl border border-[var(--rule-soft)] px-4">
            <MetricRow label="Faturamento" value={fmtK(ad.faturamento)} highlight />
            <MetricRow label="Investimento" value={fmtK(ad.investimento)} />
            <MetricRow label="ROAS" value={fmtRoas(ad.roas)} highlight />
            {ad.conversoes != null && <MetricRow label="Conversões" value={String(ad.conversoes)} />}
            {ad.leads != null && <MetricRow label="Leads" value={String(ad.leads)} />}
            {ad.cpa != null && <MetricRow label="CPA" value={fmtK(ad.cpa)} />}
            {ad.cpl != null && <MetricRow label="CPL" value={fmtK(ad.cpl)} />}
            {ad.impressoes != null && <MetricRow label="Impressões" value={ad.impressoes.toLocaleString("pt-BR")} />}
            {cpm != null && <MetricRow label="CPM" value={fmtK(cpm)} />}
          </div>

          <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Contexto · carteira</p>

          {roasVsAvg != null && (
            <div className="mb-4 rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">ROAS vs. média da carteira</p>
              <p className={`mt-1 font-mono-num text-2xl font-semibold ${roasVsAvg >= 1 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                {roasVsAvg >= 1 ? "+" : ""}{((roasVsAvg - 1) * 100).toFixed(0)}%
              </p>
              <p className="mt-0.5 text-[10px] text-[var(--muted)]">Média: {avgRoas ? fmtRoas(avgRoas) : "—"}</p>
            </div>
          )}

          {(shareInv != null || shareFat != null) && (
            <div className="rounded-xl border border-[var(--rule-soft)] px-4 py-3">
              {shareInv != null && <ContextBar label="Share de investimento" pct={shareInv} />}
              {shareFat != null && <ContextBar label="Share de faturamento" pct={shareFat} />}
            </div>
          )}
            </>
          )}
        </div>

        <div className="border-t border-[var(--rule-soft)] px-5 py-3">
          <Link href={`/gestor/${ad.clienteSlug}`} className="block text-center text-xs text-[var(--forest)] transition hover:underline">
            Ver dashboard do cliente →
          </Link>
        </div>
      </aside>
    </>
  );
}

function GoogleDrawer({ ad, allAds, onClose, mes }: { ad: RankedGoogleAd; allAds: RankedGoogleAd[]; onClose: () => void; mes: string }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

  const [drawerTab, setDrawerTab] = useState<"metricas" | "evolucao">("metricas");

  const tier = roasTier(ad.roas);
  const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0);
  const avgRoas = adsComRoas.length > 0 ? adsComRoas.reduce((s, a) => s + (a.roas ?? 0), 0) / adsComRoas.length : null;
  const roasVsAvg = avgRoas && ad.roas ? ad.roas / avgRoas : null;
  const maxRoas = adsComRoas.length > 0 ? Math.max(...adsComRoas.map((a) => a.roas ?? 0)) : 0;
  const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;
  const totalInv = allAds.reduce((s, a) => s + (a.investimento ?? 0), 0);
  const totalFat = allAds.reduce((s, a) => s + (a.faturamento ?? 0), 0);
  const shareInv = totalInv > 0 && ad.investimento ? (ad.investimento / totalInv) * 100 : null;
  const shareFat = totalFat > 0 && ad.faturamento ? (ad.faturamento / totalFat) * 100 : null;
  const cpm = ad.impressoes && ad.investimento && ad.impressoes > 0 ? (ad.investimento / ad.impressoes) * 1000 : null;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]" onClick={onClose} />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-[380px] flex-col bg-[var(--paper)] shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-[var(--rule-soft)] px-5 py-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-[var(--ink)]" title={ad.nome}>{ad.nome}</p>
            <p className="text-xs text-[var(--muted)]">{ad.clienteNome}</p>
          </div>
          <button onClick={onClose} className="mt-0.5 flex-shrink-0 text-lg leading-none text-[var(--muted)] transition hover:text-[var(--ink)]">×</button>
        </div>

        {/* Abas */}
        <div className="flex border-b border-[var(--rule-soft)] px-5">
          {(["metricas", "evolucao"] as const).map(t => (
            <button
              key={t}
              onClick={() => setDrawerTab(t)}
              className={`mr-5 pb-2 pt-2.5 text-xs transition ${
                drawerTab === t
                  ? "border-b-2 border-[var(--forest)] font-medium text-[var(--ink)]"
                  : "text-[var(--muted)] hover:text-[var(--ink)]"
              }`}
            >
              {t === "metricas" ? "Métricas" : "Evolução"}
            </button>
          ))}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {drawerTab === "evolucao" ? (
            <EvolucaoTab
              clienteSlug={ad.clienteSlug}
              adNome={ad.nome}
              adType="google"
              mes={mes}
            />
          ) : (
            <>
          <div className="mb-5 flex items-center gap-3">
            {ad.rank < 3 && <span className="text-2xl">{MEDAL[ad.rank]}</span>}
            {ad.rank >= 3 && <span className="font-mono-num text-sm text-[var(--muted)]">#{ad.rank + 1}</span>}
            <div className="flex-1 min-w-0">
              <div className="mb-1 flex items-center justify-between">
                <span className={`font-mono-num text-lg font-semibold ${TIER_TEXT[tier]}`}>{fmtRoas(ad.roas)}</span>
                <span className="text-[10px] text-[var(--muted)]">{adsComRoas.length} campanhas</span>
              </div>
              <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
                <div className={`h-1.5 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
              </div>
            </div>
          </div>

          <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">Métricas</p>
          <div className="mb-5 rounded-xl border border-[var(--rule-soft)] px-4">
            <MetricRow label="Faturamento" value={fmtK(ad.faturamento)} highlight />
            <MetricRow label="Investimento" value={fmtK(ad.investimento)} />
            <MetricRow label="ROAS" value={fmtRoas(ad.roas)} highlight />
            {ad.conversoes != null && <MetricRow label="Conversões" value={String(ad.conversoes)} />}
            {ad.cpa != null && <MetricRow label="CPA" value={fmtK(ad.cpa)} />}
            {ad.impressoes != null && <MetricRow label="Impressões" value={ad.impressoes.toLocaleString("pt-BR")} />}
            {cpm != null && <MetricRow label="CPM" value={fmtK(cpm)} />}
          </div>

          <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Contexto · carteira</p>

          {roasVsAvg != null && (
            <div className="mb-4 rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">ROAS vs. média da carteira</p>
              <p className={`mt-1 font-mono-num text-2xl font-semibold ${roasVsAvg >= 1 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                {roasVsAvg >= 1 ? "+" : ""}{((roasVsAvg - 1) * 100).toFixed(0)}%
              </p>
              <p className="mt-0.5 text-[10px] text-[var(--muted)]">Média: {avgRoas ? fmtRoas(avgRoas) : "—"}</p>
            </div>
          )}

          {(shareInv != null || shareFat != null) && (
            <div className="rounded-xl border border-[var(--rule-soft)] px-4 py-3">
              {shareInv != null && <ContextBar label="Share de investimento" pct={shareInv} />}
              {shareFat != null && <ContextBar label="Share de faturamento" pct={shareFat} />}
            </div>
          )}
            </>
          )}
        </div>

        <div className="border-t border-[var(--rule-soft)] px-5 py-3">
          <Link href={`/gestor/${ad.clienteSlug}`} className="block text-center text-xs text-[var(--forest)] transition hover:underline">
            Ver dashboard do cliente →
          </Link>
        </div>
      </aside>
    </>
  );
}

// ── Tabela compacta (#4+) ─────────────────────────────────────────────────────

function TabelaMeta({ ads, maxRoas, onSelect }: {
  ads: RankedMetaAd[];
  maxRoas: number;
  onSelect: (ad: RankedMetaAd) => void;
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
            <th className={`${TH} px-3 text-right`}>ROAS</th>
            <th className={`${TH} px-3 text-right`}>Faturamento</th>
            <th className={`${TH} px-3 text-right hidden md:table-cell`}>Investimento</th>
            <th className={`${TH} px-3 text-right hidden lg:table-cell`}>CPM</th>
            <th className={`${TH} px-3 text-right hidden lg:table-cell`}>Impressões</th>
            <th className={`${TH} px-3 text-right hidden xl:table-cell`}>Conv.</th>
            <th className={`${TH} px-3 text-right hidden xl:table-cell`}>Leads</th>
            <th className={`${TH} pl-3 pr-4 text-right hidden xl:table-cell`}>CPA/CPL</th>
            <th className="w-4 pr-3"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--rule-soft)]">
          {ads.map((ad) => {
            const tier = roasTier(ad.roas);
            const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;
            return (
              <tr
                key={`${ad.clienteSlug}-${ad.nome}`}
                onClick={() => onSelect(ad)}
                className="group cursor-pointer bg-[var(--paper)] transition hover:bg-[var(--paper-soft)]"
              >
                {/* Tier accent + rank */}
                <td className="py-3 pl-0 pr-2">
                  <div className="flex items-center gap-0">
                    <div className={`mr-3 h-8 w-0.5 rounded-full ${TIER_BAR[tier]}`} />
                    <div className="flex flex-col items-start leading-none gap-0.5">
                      <span className="font-mono-num text-xs text-[var(--muted)]">{ad.rank + 1}</span>
                      <RankDeltaBadge delta={ad.rankDelta} />
                    </div>
                  </div>
                </td>
                <td className="max-w-[200px] px-3 py-3">
                  <div className="flex items-center gap-2.5">
                    <div className="h-9 w-14 flex-shrink-0 overflow-hidden rounded-md">
                      <AdThumbnail src={ad.imagem_url} alt="" className="h-full w-full object-cover" />
                    </div>
                    <span className="block truncate text-xs font-medium text-[var(--ink)]" title={ad.nome}>{ad.nome}</span>
                  </div>
                </td>
                <td className="whitespace-nowrap px-3 py-3 text-xs text-[var(--muted)]">{ad.clienteNome}</td>
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
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] xl:table-cell">{ad.leads ?? "—"}</td>
                <td className="hidden pl-3 pr-4 py-3 text-right font-mono-num text-xs text-[var(--muted)] xl:table-cell">
                  {ad.cpa != null ? fmtK(ad.cpa) : fmtK(ad.cpl)}
                </td>
                <td className="pr-3 py-3 text-[var(--muted)] opacity-0 transition group-hover:opacity-60">
                  <span className="text-xs">›</span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

function TabelaGoogle({ ads, maxRoas, onSelect }: {
  ads: RankedGoogleAd[];
  maxRoas: number;
  onSelect: (ad: RankedGoogleAd) => void;
}) {
  if (ads.length === 0) return null;
  return (
    <div className="overflow-hidden rounded-xl border border-[var(--rule-soft)]">
      <table className="w-full">
        <thead>
          <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
            <th className={`${TH} pl-4 pr-2 w-10 text-left`}>#</th>
            <th className={`${TH} px-3 text-left`}>Campanha</th>
            <th className={`${TH} px-3 text-left`}>Cliente</th>
            <th className={`${TH} px-3 text-right`}>ROAS</th>
            <th className={`${TH} px-3 text-right`}>Faturamento</th>
            <th className={`${TH} px-3 text-right hidden md:table-cell`}>Investimento</th>
            <th className={`${TH} px-3 text-right hidden lg:table-cell`}>Impressões</th>
            <th className={`${TH} px-3 text-right hidden xl:table-cell`}>Conv.</th>
            <th className={`${TH} pl-3 pr-4 text-right hidden xl:table-cell`}>CPA</th>
            <th className="w-4 pr-3"></th>
          </tr>
        </thead>
        <tbody className="divide-y divide-[var(--rule-soft)]">
          {ads.map((c) => {
            const tier = roasTier(c.roas);
            const barPct = maxRoas > 0 && c.roas ? (c.roas / maxRoas) * 100 : 0;
            return (
              <tr
                key={`${c.clienteSlug}-${c.nome}`}
                onClick={() => onSelect(c)}
                className="group cursor-pointer bg-[var(--paper)] transition hover:bg-[var(--paper-soft)]"
              >
                <td className="py-3 pl-0 pr-2">
                  <div className="flex items-center">
                    <div className={`mr-3 h-8 w-0.5 rounded-full ${TIER_BAR[tier]}`} />
                    <div className="flex flex-col items-start leading-none gap-0.5">
                      <span className="font-mono-num text-xs text-[var(--muted)]">{c.rank + 1}</span>
                      <RankDeltaBadge delta={c.rankDelta} />
                    </div>
                  </div>
                </td>
                <td className="max-w-[280px] px-3 py-3">
                  <span className="block truncate text-xs font-medium text-[var(--ink)]" title={c.nome}>{c.nome}</span>
                </td>
                <td className="whitespace-nowrap px-3 py-3 text-xs text-[var(--muted)]">{c.clienteNome}</td>
                <td className="px-3 py-3 text-right">
                  <span className={`font-mono-num text-sm font-semibold ${TIER_TEXT[tier]}`}>{fmtRoas(c.roas)}</span>
                  <div className="mt-1 h-0.5 w-full rounded-full bg-[var(--paper-deep)]">
                    <div className={`h-0.5 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
                  </div>
                </td>
                <td className="px-3 py-3 text-right font-mono-num text-xs text-[var(--forest)]">{fmtK(c.faturamento)}</td>
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] md:table-cell">{fmtK(c.investimento)}</td>
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] lg:table-cell">{fmtImp(c.impressoes)}</td>
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] xl:table-cell">{c.conversoes ?? "—"}</td>
                <td className="hidden pl-3 pr-4 py-3 text-right font-mono-num text-xs text-[var(--muted)] xl:table-cell">{fmtK(c.cpa)}</td>
                <td className="pr-3 py-3 text-[var(--muted)] opacity-0 transition group-hover:opacity-60">
                  <span className="text-xs">›</span>
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

function ScatterView({ ads }: { ads: (RankedMetaAd | RankedGoogleAd)[] }) {
  const data: ScatterDot[] = ads
    .filter((a) => a.investimento != null && a.faturamento != null && a.investimento > 0)
    .map((a) => ({
      x: a.investimento!,
      y: a.faturamento!,
      z: Math.max(a.impressoes ?? 300, 300),
      nome: a.nome,
      clienteNome: a.clienteNome,
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

export default function RankingsPage() {
  const [mes, setMes] = useState(mesUltimoFechado());
  const [loading, setLoading] = useState(true);
  const [rede, setRede] = useState<"meta" | "google">("meta");
  const [view, setView] = useState<"ranking" | "scatter">("ranking");
  const [metaAds, setMetaAds] = useState<RankedMetaAd[]>([]);
  const [googleAds, setGoogleAds] = useState<RankedGoogleAd[]>([]);
  const [selectedMeta, setSelectedMeta] = useState<RankedMetaAd | null>(null);
  const [selectedGoogle, setSelectedGoogle] = useState<RankedGoogleAd | null>(null);
  const [clienteFilter, setClienteFilter] = useState("");
  const [gestorFilter, setGestorFilter] = useState("");

  const mesOpcoes = useMemo(
    () => Array.from({ length: 12 }, (_, i) => deslocarMes(mesUltimoFechado(), -i)),
    [],
  );

  const gestoresDisponiveis = useMemo(() => {
    const nomes = new Set<string>();
    for (const a of [...metaAds, ...googleAds]) if (a.gestorNome) nomes.add(a.gestorNome);
    return Array.from(nomes).sort((a, b) => a.localeCompare(b));
  }, [metaAds, googleAds]);

  const clientesDisponiveis = useMemo(() => {
    const base = gestorFilter
      ? [...metaAds, ...googleAds].filter((a) => a.gestorNome === gestorFilter)
      : [...metaAds, ...googleAds];
    const slugs = new Map<string, string>();
    for (const a of base) slugs.set(a.clienteSlug, a.clienteNome);
    return Array.from(slugs.entries()).sort((a, b) => a[1].localeCompare(b[1]));
  }, [metaAds, googleAds, gestorFilter]);

  const filteredMeta = useMemo(() => {
    let ads = metaAds;
    if (gestorFilter) ads = ads.filter((a) => a.gestorNome === gestorFilter);
    if (clienteFilter) ads = ads.filter((a) => a.clienteSlug === clienteFilter);
    return ads;
  }, [metaAds, gestorFilter, clienteFilter]);

  const filteredGoogle = useMemo(() => {
    let ads = googleAds;
    if (gestorFilter) ads = ads.filter((a) => a.gestorNome === gestorFilter);
    if (clienteFilter) ads = ads.filter((a) => a.clienteSlug === clienteFilter);
    return ads;
  }, [googleAds, gestorFilter, clienteFilter]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setSelectedMeta(null);
    setSelectedGoogle(null);
    const mesPrev = deslocarMes(mes, -1);
    const sortByRoasAsc = (a: { roas: number | null }, b: { roas: number | null }) =>
      (b.roas ?? -1) - (a.roas ?? -1);

    gestorApi
      .clientes()
      .then(({ items }) => {
        if (cancelled) return null;
        const ativos = items.filter((c) => c.ativo);
        return Promise.all(
          ativos.map((c) =>
            Promise.all([
              gestorApi.metricasBreakdown(c.slug, mes).catch(() => null),
              gestorApi.metricasBreakdown(c.slug, mesPrev).catch(() => null),
            ]).then(([bd, bdPrev]) => ({ cliente: c, bd, bdPrev })),
          ),
        );
      })
      .then((results) => {
        if (!results || cancelled) return;

        // Build prev-month rank maps
        const prevMetaFlat: Array<{ key: string; roas: number | null }> = [];
        const prevGoogleFlat: Array<{ key: string; roas: number | null }> = [];
        for (const { cliente, bdPrev } of results) {
          if (!bdPrev) continue;
          for (const ad of bdPrev.meta_ads ?? [])
            prevMetaFlat.push({ key: `${cliente.slug}:${ad.nome}`, roas: ad.roas });
          for (const ad of bdPrev.google_ads ?? [])
            prevGoogleFlat.push({ key: `${cliente.slug}:${ad.nome}`, roas: ad.roas });
        }
        const prevMetaMap = new Map<string, number>(
          [...prevMetaFlat].sort(sortByRoasAsc).map((a, i) => [a.key, i]),
        );
        const prevGoogleMap = new Map<string, number>(
          [...prevGoogleFlat].sort(sortByRoasAsc).map((a, i) => [a.key, i]),
        );

        const allMeta: RankedMetaAd[] = [];
        const allGoogle: RankedGoogleAd[] = [];
        for (const { cliente, bd } of results) {
          if (!bd) continue;
          for (const ad of bd.meta_ads ?? [])
            allMeta.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug, gestorNome: cliente.gestor, rank: 0, rankDelta: null });
          for (const ad of bd.google_ads ?? [])
            allGoogle.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug, gestorNome: cliente.gestor, rank: 0, rankDelta: null });
        }

        setMetaAds(
          sortByRoas(allMeta).map((a, i) => {
            const prev = prevMetaMap.get(`${a.clienteSlug}:${a.nome}`);
            return { ...a, rank: i, rankDelta: prev !== undefined ? prev - i : null };
          }),
        );
        setGoogleAds(
          sortByRoas(allGoogle).map((a, i) => {
            const prev = prevGoogleMap.get(`${a.clienteSlug}:${a.nome}`);
            return { ...a, rank: i, rankDelta: prev !== undefined ? prev - i : null };
          }),
        );
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [mes]);

  const activeAds = rede === "meta" ? filteredMeta : filteredGoogle;
  const totalFat = activeAds.reduce((s, a) => s + (a.faturamento ?? 0), 0);
  const totalInv = activeAds.reduce((s, a) => s + (a.investimento ?? 0), 0);
  const roasMedio = totalInv > 0 ? totalFat / totalInv : null;
  const maxRoas = activeAds.length > 0 ? Math.max(...activeAds.filter(a => a.roas != null).map(a => a.roas ?? 0)) : 0;

  const restMeta = filteredMeta.slice(3);
  const restGoogle = filteredGoogle.slice(3);

  return (
    <GestorShell>
    <main className="mx-auto max-w-6xl px-6 py-12">
      {/* Header */}
      <div className="mb-8">
        <div className="mb-5 flex items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
              Performance
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">Rankings de criativos e campanhas da carteira</p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {gestoresDisponiveis.length > 0 && (
            <select
              value={gestorFilter}
              onChange={(e) => { setGestorFilter(e.target.value); setClienteFilter(""); }}
              className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-xs text-[var(--ink)] focus:border-[var(--forest)] focus:outline-none"
            >
              <option value="">Todos os gestores</option>
              {gestoresDisponiveis.map((g) => (
                <option key={g} value={g}>{g}</option>
              ))}
            </select>
          )}
          {clientesDisponiveis.length > 0 && (
            <select
              value={clienteFilter}
              onChange={(e) => setClienteFilter(e.target.value)}
              className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-xs text-[var(--ink)] focus:border-[var(--forest)] focus:outline-none"
            >
              <option value="">Todos os clientes</option>
              {clientesDisponiveis.map(([slug, nome]) => (
                <option key={slug} value={slug}>{nome}</option>
              ))}
            </select>
          )}
          <select
            id="mes-ref"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-xs text-[var(--ink)] focus:border-[var(--forest)] focus:outline-none"
          >
            {mesOpcoes.map((m) => (
              <option key={m} value={m}>{mesLabel(m)}</option>
            ))}
          </select>
          {(gestorFilter || clienteFilter) && (
            <button
              onClick={() => { setGestorFilter(""); setClienteFilter(""); }}
              className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-xs text-[var(--muted)] transition hover:text-[var(--ink)]"
            >
              Limpar filtros ×
            </button>
          )}
        </div>
      </div>

      {/* Tabs + view toggle */}
      <div className="mb-6 flex items-center justify-between gap-4">
        <div className="flex gap-1.5">
          {(["meta", "google"] as const).map((r) => (
            <button
              key={r}
              onClick={() => setRede(r)}
              className={`rounded-lg px-4 py-2 text-sm font-medium transition ${
                rede === r
                  ? "bg-[var(--ink)] text-[var(--paper)]"
                  : "bg-[var(--paper-soft)] text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]"
              }`}
            >
              {r === "meta" ? "Meta Ads" : "Google Ads"}
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
                  ? "bg-[var(--paper-deep)] text-[var(--ink)]"
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
      ) : activeAds.length === 0 ? (
        <p className="rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-12 text-center text-sm text-[var(--muted)]">
          Nenhum dado disponível para este mês.
        </p>
      ) : (
        <>
          <KpiStrip items={[
            { label: "Criativos", value: String(activeAds.length), sub: rede === "meta" ? "Meta Ads" : "Google Ads" },
            { label: "Faturamento total", value: fmtK(totalFat), sub: mesLabel(mes), highlight: true },
            { label: "Investimento total", value: fmtK(totalInv), sub: mesLabel(mes) },
            { label: "ROAS médio", value: roasMedio != null ? fmtRoas(roasMedio) : "—", sub: "ponderado por investimento" },
          ]} />

          {view === "scatter" ? (
            <ScatterView ads={rede === "meta" ? filteredMeta : filteredGoogle} />
          ) : (
            <>
              {/* Pódio top 3 */}
              {rede === "meta" && filteredMeta.length >= 1 && (
                <div className="mb-2">
                  <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Top 3 criativos</p>
                  <PodiumMeta ads={filteredMeta} maxRoas={maxRoas} onSelect={setSelectedMeta} />
                </div>
              )}
              {rede === "google" && filteredGoogle.length >= 1 && (
                <div className="mb-2">
                  <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Top 3 campanhas</p>
                  <PodiumGoogle ads={filteredGoogle} maxRoas={maxRoas} onSelect={setSelectedGoogle} />
                </div>
              )}

              {/* Resto da tabela */}
              {rede === "meta" && restMeta.length > 0 && (
                <div className="mt-4">
                  <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Demais criativos</p>
                  <TabelaMeta ads={restMeta} maxRoas={maxRoas} onSelect={setSelectedMeta} />
                </div>
              )}
              {rede === "google" && restGoogle.length > 0 && (
                <div className="mt-4">
                  <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Demais campanhas</p>
                  <TabelaGoogle ads={restGoogle} maxRoas={maxRoas} onSelect={setSelectedGoogle} />
                </div>
              )}
            </>
          )}
        </>
      )}

      {selectedMeta && <MetaDrawer ad={selectedMeta} allAds={metaAds} onClose={() => setSelectedMeta(null)} mes={mes} />}
      {selectedGoogle && <GoogleDrawer ad={selectedGoogle} allAds={googleAds} onClose={() => setSelectedGoogle(null)} mes={mes} />}
    </main>
    </GestorShell>
  );
}
