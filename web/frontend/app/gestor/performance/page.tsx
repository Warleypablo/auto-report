"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";

import { gestorApi } from "@/lib/api-gestor";
import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import { deslocarMes, mesUltimoFechado } from "@/lib/mes-utils";
import {
  fmtRoas,
  roasTier,
  sortByRoas,
  TIER_TEXT,
} from "@/lib/roas-tier";

type RankedMetaAd = MetaAd & { clienteNome: string; clienteSlug: string; rank: number };
type RankedGoogleAd = GoogleAd & { clienteNome: string; clienteSlug: string; rank: number };

function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]} ${ano}`;
}

function rankColor(i: number): string {
  if (i === 0) return "text-[#d97706] font-bold";
  if (i === 1) return "text-[#6b7280] font-semibold";
  if (i === 2) return "text-[#92400e] font-semibold";
  return "text-[var(--muted)]";
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

const TH_L = "pb-2.5 pt-3 text-left text-[10px] font-normal uppercase tracking-widest text-[var(--muted)] whitespace-nowrap";
const TH_R = "pb-2.5 pt-3 text-right text-[10px] font-normal uppercase tracking-widest text-[var(--muted)] whitespace-nowrap";

// ── Drawer de detalhes ────────────────────────────────────────────────────────

function MetricRow({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 py-2 border-b border-[var(--rule-soft)] last:border-0">
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
        <div
          className="h-1.5 rounded-full bg-[var(--forest)] opacity-70"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

function MetaDrawer({
  ad,
  allAds,
  onClose,
}: {
  ad: RankedMetaAd;
  allAds: RankedMetaAd[];
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const tier = roasTier(ad.roas);

  const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0);
  const avgRoas = adsComRoas.length > 0
    ? adsComRoas.reduce((s, a) => s + (a.roas ?? 0), 0) / adsComRoas.length
    : null;
  const roasVsAvg = avgRoas && ad.roas ? ad.roas / avgRoas : null;

  const totalInv = allAds.reduce((s, a) => s + (a.investimento ?? 0), 0);
  const totalFat = allAds.reduce((s, a) => s + (a.faturamento ?? 0), 0);
  const shareInv = totalInv > 0 && ad.investimento ? (ad.investimento / totalInv) * 100 : null;
  const shareFat = totalFat > 0 && ad.faturamento ? (ad.faturamento / totalFat) * 100 : null;

  const cpm = ad.impressoes && ad.investimento && ad.impressoes > 0
    ? (ad.investimento / ad.impressoes) * 1000
    : null;

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]"
        onClick={onClose}
      />
      {/* Drawer */}
      <aside className="fixed right-0 top-0 z-50 flex h-full w-[360px] flex-col bg-[var(--paper)] shadow-2xl">
        {/* Header */}
        <div className="flex items-start justify-between gap-3 border-b border-[var(--rule-soft)] px-5 py-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-[var(--ink)]" title={ad.nome}>{ad.nome}</p>
            <p className="text-xs text-[var(--muted)]">{ad.clienteNome}</p>
          </div>
          <button onClick={onClose} className="mt-0.5 flex-shrink-0 text-[var(--muted)] transition hover:text-[var(--ink)]">
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {/* Imagem */}
          {ad.imagem_url && (
            <div className="mb-5 overflow-hidden rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-deep)]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={ad.imagem_url}
                alt={ad.nome}
                className="w-full object-cover"
                style={{ maxHeight: 200 }}
              />
            </div>
          )}

          {/* Rank badge */}
          <div className="mb-4 flex items-center gap-2">
            <span className={`font-mono-num text-lg ${rankColor(ad.rank)}`}>#{ad.rank + 1}</span>
            <span className="text-xs text-[var(--muted)]">no ranking geral · Meta Ads</span>
            <span className={`ml-auto rounded px-2 py-0.5 text-xs font-medium ${TIER_TEXT[tier]}`}>
              {fmtRoas(ad.roas)}
            </span>
          </div>

          {/* Métricas */}
          <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">Métricas</p>
          <div className="mb-5 rounded-lg border border-[var(--rule-soft)] px-3">
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

          {/* Contexto comparativo */}
          <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Contexto · carteira</p>

          {roasVsAvg != null && (
            <div className="mb-4 rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">ROAS vs. média da carteira</p>
              <p className={`mt-1 font-mono-num text-xl font-semibold ${roasVsAvg >= 1 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                {roasVsAvg >= 1 ? "+" : ""}{((roasVsAvg - 1) * 100).toFixed(0)}%
              </p>
              <p className="mt-0.5 text-[10px] text-[var(--muted)]">
                Média dos criativos: {avgRoas ? fmtRoas(avgRoas) : "—"}
              </p>
            </div>
          )}

          {(shareInv != null || shareFat != null) && (
            <div className="rounded-lg border border-[var(--rule-soft)] px-4 py-3">
              {shareInv != null && <ContextBar label="Share de investimento na carteira" pct={shareInv} />}
              {shareFat != null && <ContextBar label="Share de faturamento na carteira" pct={shareFat} />}
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="border-t border-[var(--rule-soft)] px-5 py-3">
          <Link
            href={`/gestor/${ad.clienteSlug}`}
            className="block text-center text-xs text-[var(--forest)] transition hover:underline"
          >
            Ver dashboard do cliente →
          </Link>
        </div>
      </aside>
    </>
  );
}

function GoogleDrawer({
  ad,
  allAds,
  onClose,
}: {
  ad: RankedGoogleAd;
  allAds: RankedGoogleAd[];
  onClose: () => void;
}) {
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [onClose]);

  const tier = roasTier(ad.roas);

  const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0);
  const avgRoas = adsComRoas.length > 0
    ? adsComRoas.reduce((s, a) => s + (a.roas ?? 0), 0) / adsComRoas.length
    : null;
  const roasVsAvg = avgRoas && ad.roas ? ad.roas / avgRoas : null;

  const totalInv = allAds.reduce((s, a) => s + (a.investimento ?? 0), 0);
  const totalFat = allAds.reduce((s, a) => s + (a.faturamento ?? 0), 0);
  const shareInv = totalInv > 0 && ad.investimento ? (ad.investimento / totalInv) * 100 : null;
  const shareFat = totalFat > 0 && ad.faturamento ? (ad.faturamento / totalFat) * 100 : null;

  const cpm = ad.impressoes && ad.investimento && ad.impressoes > 0
    ? (ad.investimento / ad.impressoes) * 1000
    : null;

  return (
    <>
      <div className="fixed inset-0 z-40 bg-black/30 backdrop-blur-[1px]" onClick={onClose} />
      <aside className="fixed right-0 top-0 z-50 flex h-full w-[360px] flex-col bg-[var(--paper)] shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-[var(--rule-soft)] px-5 py-4">
          <div className="min-w-0">
            <p className="truncate text-sm font-medium text-[var(--ink)]" title={ad.nome}>{ad.nome}</p>
            <p className="text-xs text-[var(--muted)]">{ad.clienteNome}</p>
          </div>
          <button onClick={onClose} className="mt-0.5 flex-shrink-0 text-[var(--muted)] transition hover:text-[var(--ink)]">
            ✕
          </button>
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          <div className="mb-4 flex items-center gap-2">
            <span className={`font-mono-num text-lg ${rankColor(ad.rank)}`}>#{ad.rank + 1}</span>
            <span className="text-xs text-[var(--muted)]">no ranking geral · Google Ads</span>
            <span className={`ml-auto rounded px-2 py-0.5 text-xs font-medium ${TIER_TEXT[tier]}`}>
              {fmtRoas(ad.roas)}
            </span>
          </div>

          <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">Métricas</p>
          <div className="mb-5 rounded-lg border border-[var(--rule-soft)] px-3">
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
            <div className="mb-4 rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3">
              <p className="text-xs text-[var(--muted)]">ROAS vs. média da carteira</p>
              <p className={`mt-1 font-mono-num text-xl font-semibold ${roasVsAvg >= 1 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                {roasVsAvg >= 1 ? "+" : ""}{((roasVsAvg - 1) * 100).toFixed(0)}%
              </p>
              <p className="mt-0.5 text-[10px] text-[var(--muted)]">
                Média das campanhas: {avgRoas ? fmtRoas(avgRoas) : "—"}
              </p>
            </div>
          )}

          {(shareInv != null || shareFat != null) && (
            <div className="rounded-lg border border-[var(--rule-soft)] px-4 py-3">
              {shareInv != null && <ContextBar label="Share de investimento na carteira" pct={shareInv} />}
              {shareFat != null && <ContextBar label="Share de faturamento na carteira" pct={shareFat} />}
            </div>
          )}
        </div>

        <div className="border-t border-[var(--rule-soft)] px-5 py-3">
          <Link
            href={`/gestor/${ad.clienteSlug}`}
            className="block text-center text-xs text-[var(--forest)] transition hover:underline"
          >
            Ver dashboard do cliente →
          </Link>
        </div>
      </aside>
    </>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function RankingsPage() {
  const [mes, setMes] = useState(mesUltimoFechado());
  const [loading, setLoading] = useState(true);
  const [rede, setRede] = useState<"meta" | "google">("meta");
  const [metaAds, setMetaAds] = useState<RankedMetaAd[]>([]);
  const [googleAds, setGoogleAds] = useState<RankedGoogleAd[]>([]);
  const [selectedMeta, setSelectedMeta] = useState<RankedMetaAd | null>(null);
  const [selectedGoogle, setSelectedGoogle] = useState<RankedGoogleAd | null>(null);

  const mesOpcoes = useMemo(
    () => Array.from({ length: 12 }, (_, i) => deslocarMes(mesUltimoFechado(), -i)),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setSelectedMeta(null);
    setSelectedGoogle(null);
    gestorApi
      .clientes()
      .then(({ items }) => {
        if (cancelled) return null;
        const ativos = items.filter((c) => c.ativo);
        return Promise.all(
          ativos.map((c) =>
            gestorApi
              .metricasBreakdown(c.slug, mes)
              .then((bd) => ({ cliente: c, bd }))
              .catch(() => ({ cliente: c, bd: null })),
          ),
        );
      })
      .then((results) => {
        if (!results || cancelled) return;
        const allMeta: RankedMetaAd[] = [];
        const allGoogle: RankedGoogleAd[] = [];
        for (const { cliente, bd } of results) {
          if (!bd) continue;
          for (const ad of bd.meta_ads ?? []) {
            allMeta.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug, rank: 0 });
          }
          for (const ad of bd.google_ads ?? []) {
            allGoogle.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug, rank: 0 });
          }
        }
        const sortedMeta = sortByRoas(allMeta).map((a, i) => ({ ...a, rank: i }));
        const sortedGoogle = sortByRoas(allGoogle).map((a, i) => ({ ...a, rank: i }));
        setMetaAds(sortedMeta);
        setGoogleAds(sortedGoogle);
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [mes]);

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <Link
        href="/gestor"
        className="mb-6 block text-xs text-[var(--muted)] transition hover:text-[var(--ink)]"
      >
        ← Seus clientes
      </Link>

      <div className="mb-6 flex items-baseline justify-between gap-4">
        <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
          Performance
        </h1>
        <div className="flex items-center gap-2">
          <label htmlFor="mes-ref" className="text-xs text-[var(--muted)]">
            Mês:
          </label>
          <select
            id="mes-ref"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-1.5 text-xs text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          >
            {mesOpcoes.map((m) => (
              <option key={m} value={m}>
                {mesLabel(m)}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Tabs Meta / Google */}
      <div className="mb-6 flex gap-1 border-b border-[var(--rule-soft)]">
        {(["meta", "google"] as const).map((r) => (
          <button
            key={r}
            onClick={() => setRede(r)}
            className={`px-4 py-2 text-sm transition border-b-2 -mb-px ${
              rede === r
                ? "border-[var(--forest)] text-[var(--ink)] font-medium"
                : "border-transparent text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            {r === "meta" ? "Meta Ads" : "Google Ads"}
          </button>
        ))}
      </div>

      {loading ? (
        <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-12 text-center text-sm text-[var(--muted)]">
          Carregando rankings…
        </p>
      ) : rede === "meta" ? (
        <section key="meta">
            <p className="eyebrow mb-4 text-xs text-[var(--muted)]">
              Top criativos · Meta Ads · carteira
            </p>
            {metaAds.length === 0 ? (
              <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
                Nenhum dado disponível para este mês.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-[var(--rule-soft)]">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                      <th className={`${TH_L} pl-4 pr-2`}>#</th>
                      <th className={`${TH_L} px-2`}>Criativo</th>
                      <th className={`${TH_L} px-2`}>Cliente</th>
                      <th className={`${TH_R} px-2`}>ROAS</th>
                      <th className={`${TH_R} px-2`}>Faturamento</th>
                      <th className={`${TH_R} px-2`}>Investimento</th>
                      <th className={`${TH_R} px-2`}>Conv.</th>
                      <th className={`${TH_R} px-2`}>Leads</th>
                      <th className={`${TH_R} pl-2 pr-4`}>CPA/CPL</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--rule-soft)] bg-[var(--paper-soft)]">
                    {metaAds.map((ad) => {
                      const tier = roasTier(ad.roas);
                      return (
                        <tr
                          key={`${ad.clienteSlug}-${ad.nome}`}
                          onClick={() => setSelectedMeta(ad)}
                          className="cursor-pointer transition hover:bg-[var(--paper-deep)]"
                        >
                          <td className={`py-2.5 pl-4 pr-2 font-mono-num text-xs ${rankColor(ad.rank)}`}>
                            #{ad.rank + 1}
                          </td>
                          <td className="max-w-[220px] px-2 py-2.5">
                            <div className="flex items-center gap-2">
                              <div className="relative h-5 w-7 flex-shrink-0">
                                <div className="h-5 w-7 rounded bg-gradient-to-br from-[var(--paper-deep)] to-[var(--paper-soft)]" />
                                {ad.imagem_url && (
                                  // eslint-disable-next-line @next/next/no-img-element
                                  <img
                                    src={ad.imagem_url}
                                    alt=""
                                    className="absolute inset-0 h-full w-full rounded object-cover"
                                    onError={(e) => e.currentTarget.remove()}
                                  />
                                )}
                              </div>
                              <span
                                className="block truncate text-xs text-[var(--ink)]"
                                title={ad.nome}
                              >
                                {ad.nome}
                              </span>
                            </div>
                          </td>
                          <td className="whitespace-nowrap px-2 py-2.5 text-xs text-[var(--muted)]">
                            {ad.clienteNome}
                          </td>
                          <td className={`px-2 py-2.5 text-right font-mono-num font-semibold ${TIER_TEXT[tier]}`}>
                            {fmtRoas(ad.roas)}
                          </td>
                          <td className="px-2 py-2.5 text-right font-mono-num text-xs text-[var(--forest)]">
                            {fmtK(ad.faturamento)}
                          </td>
                          <td className="px-2 py-2.5 text-right font-mono-num text-xs text-[var(--muted)]">
                            {fmtK(ad.investimento)}
                          </td>
                          <td className="px-2 py-2.5 text-right font-mono-num text-xs text-[var(--muted)]">
                            {ad.conversoes ?? "—"}
                          </td>
                          <td className="px-2 py-2.5 text-right font-mono-num text-xs text-[var(--muted)]">
                            {ad.leads ?? "—"}
                          </td>
                          <td className="pl-2 pr-4 py-2.5 text-right font-mono-num text-xs text-[var(--muted)]">
                            {ad.cpa != null ? fmtK(ad.cpa) : fmtK(ad.cpl)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
        </section>
      ) : (
        <section key="google">
            <p className="eyebrow mb-4 text-xs text-[var(--muted)]">
              Top campanhas · Google Ads · carteira
            </p>
            {googleAds.length === 0 ? (
              <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
                Nenhum dado disponível para este mês.
              </p>
            ) : (
              <div className="overflow-x-auto rounded-lg border border-[var(--rule-soft)]">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                      <th className={`${TH_L} pl-4 pr-2`}>#</th>
                      <th className={`${TH_L} px-2`}>Campanha</th>
                      <th className={`${TH_L} px-2`}>Cliente</th>
                      <th className={`${TH_R} px-2`}>ROAS</th>
                      <th className={`${TH_R} px-2`}>Faturamento</th>
                      <th className={`${TH_R} px-2`}>Investimento</th>
                      <th className={`${TH_R} px-2`}>Conv.</th>
                      <th className={`${TH_R} pl-2 pr-4`}>CPA</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--rule-soft)] bg-[var(--paper-soft)]">
                    {googleAds.map((c) => {
                      const tier = roasTier(c.roas);
                      return (
                        <tr
                          key={`${c.clienteSlug}-${c.nome}`}
                          onClick={() => setSelectedGoogle(c)}
                          className="cursor-pointer transition hover:bg-[var(--paper-deep)]"
                        >
                          <td className={`py-2.5 pl-4 pr-2 font-mono-num text-xs ${rankColor(c.rank)}`}>
                            #{c.rank + 1}
                          </td>
                          <td className="max-w-[260px] px-2 py-2.5">
                            <span
                              className="block truncate text-xs text-[var(--ink)]"
                              title={c.nome}
                            >
                              {c.nome}
                            </span>
                          </td>
                          <td className="whitespace-nowrap px-2 py-2.5 text-xs text-[var(--muted)]">
                            {c.clienteNome}
                          </td>
                          <td className={`px-2 py-2.5 text-right font-mono-num font-semibold ${TIER_TEXT[tier]}`}>
                            {fmtRoas(c.roas)}
                          </td>
                          <td className="px-2 py-2.5 text-right font-mono-num text-xs text-[var(--forest)]">
                            {fmtK(c.faturamento)}
                          </td>
                          <td className="px-2 py-2.5 text-right font-mono-num text-xs text-[var(--muted)]">
                            {fmtK(c.investimento)}
                          </td>
                          <td className="px-2 py-2.5 text-right font-mono-num text-xs text-[var(--muted)]">
                            {c.conversoes ?? "—"}
                          </td>
                          <td className="pl-2 pr-4 py-2.5 text-right font-mono-num text-xs text-[var(--muted)]">
                            {fmtK(c.cpa)}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
        </section>
      )}

      {/* Drawers */}
      {selectedMeta && (
        <MetaDrawer ad={selectedMeta} allAds={metaAds} onClose={() => setSelectedMeta(null)} />
      )}
      {selectedGoogle && (
        <GoogleDrawer ad={selectedGoogle} allAds={googleAds} onClose={() => setSelectedGoogle(null)} />
      )}
    </main>
  );
}
