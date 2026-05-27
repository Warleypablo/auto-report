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
  TIER_BAR,
} from "@/lib/roas-tier";

type RankedMetaAd = MetaAd & { clienteNome: string; clienteSlug: string; rank: number };
type RankedGoogleAd = GoogleAd & { clienteNome: string; clienteSlug: string; rank: number };

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

const TH = "pb-2 pt-3 text-[10px] font-normal uppercase tracking-widest text-[var(--muted)] whitespace-nowrap";

// ── KPI strip ─────────────────────────────────────────────────────────────────

function KpiStrip({ items }: { items: { label: string; value: string; sub?: string }[] }) {
  return (
    <div className="mb-8 grid grid-cols-3 gap-4">
      {items.map(({ label, value, sub }) => (
        <div key={label} className="rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-5 py-4">
          <p className="mb-1 text-[10px] uppercase tracking-widest text-[var(--muted)]">{label}</p>
          <p className="font-display text-2xl font-medium text-[var(--ink)]">{value}</p>
          {sub && <p className="mt-0.5 text-[10px] text-[var(--muted)]">{sub}</p>}
        </div>
      ))}
    </div>
  );
}

// ── Pódio top 3 ───────────────────────────────────────────────────────────────

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
            <div className="relative h-36 w-full bg-gradient-to-br from-[var(--paper-deep)] to-[var(--paper-soft)]">
              {ad.imagem_url && (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={ad.imagem_url}
                  alt={ad.nome}
                  className="h-full w-full object-cover transition group-hover:scale-[1.02]"
                  onError={(e) => e.currentTarget.remove()}
                />
              )}
              {/* Medal badge */}
              <span className="absolute left-2.5 top-2.5 text-xl drop-shadow">{MEDAL[ad.rank]}</span>
              {/* ROAS badge */}
              <span className={`absolute right-2.5 top-2.5 rounded-md bg-[var(--paper)] px-2 py-0.5 text-xs font-semibold shadow ${TIER_TEXT[tier]}`}>
                {fmtRoas(ad.roas)}
              </span>
            </div>

            {/* Info */}
            <div className="px-3.5 py-3">
              <p className="mb-0.5 truncate text-xs font-medium text-[var(--ink)]" title={ad.nome}>{ad.nome}</p>
              <p className="mb-3 truncate text-[10px] text-[var(--muted)]">{ad.clienteNome}</p>
              {/* ROAS bar */}
              <div className="mb-2 h-1 w-full rounded-full bg-[var(--paper-deep)]">
                <div className={`h-1 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
              </div>
              <div className="flex justify-between text-[10px] text-[var(--muted)]">
                <span>{fmtK(ad.faturamento)}</span>
                <span>{fmtK(ad.investimento)}</span>
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
              <span className="text-xl">{MEDAL[ad.rank]}</span>
              <span className={`rounded-md bg-[var(--paper)] px-2 py-0.5 text-xs font-semibold shadow ${TIER_TEXT[tier]}`}>
                {fmtRoas(ad.roas)}
              </span>
            </div>
            <p className="mb-0.5 line-clamp-2 text-xs font-medium leading-snug text-[var(--ink)]" title={ad.nome}>{ad.nome}</p>
            <p className="mb-3 truncate text-[10px] text-[var(--muted)]">{ad.clienteNome}</p>
            <div className="mb-2 h-1 w-full rounded-full bg-[var(--paper-deep)]">
              <div className={`h-1 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
            </div>
            <div className="flex justify-between text-[10px] text-[var(--muted)]">
              <span>{fmtK(ad.faturamento)}</span>
              <span>{fmtK(ad.investimento)}</span>
            </div>
          </button>
        );
      })}
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

function MetaDrawer({ ad, allAds, onClose }: { ad: RankedMetaAd; allAds: RankedMetaAd[]; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

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

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {ad.imagem_url && (
            <div className="mb-5 overflow-hidden rounded-xl border border-[var(--rule-soft)]">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={ad.imagem_url} alt={ad.nome} className="w-full object-cover" style={{ maxHeight: 220 }} />
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

function GoogleDrawer({ ad, allAds, onClose }: { ad: RankedGoogleAd; allAds: RankedGoogleAd[]; onClose: () => void }) {
  useEffect(() => {
    const h = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [onClose]);

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

        <div className="flex-1 overflow-y-auto px-5 py-4">
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
            <th className={`${TH} px-3 text-right`}>Investimento</th>
            <th className={`${TH} px-3 text-right hidden lg:table-cell`}>Conv.</th>
            <th className={`${TH} px-3 text-right hidden lg:table-cell`}>Leads</th>
            <th className={`${TH} pl-3 pr-4 text-right hidden lg:table-cell`}>CPA/CPL</th>
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
                    <span className="font-mono-num text-xs text-[var(--muted)]">{ad.rank + 1}</span>
                  </div>
                </td>
                <td className="max-w-[200px] px-3 py-3">
                  <div className="flex items-center gap-2.5">
                    <div className="relative h-9 w-14 flex-shrink-0 overflow-hidden rounded-md bg-gradient-to-br from-[var(--paper-deep)] to-[var(--paper-soft)]">
                      {ad.imagem_url && (
                        // eslint-disable-next-line @next/next/no-img-element
                        <img src={ad.imagem_url} alt="" className="absolute inset-0 h-full w-full object-cover" onError={(e) => e.currentTarget.remove()} />
                      )}
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
                <td className="px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)]">{fmtK(ad.investimento)}</td>
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] lg:table-cell">{ad.conversoes ?? "—"}</td>
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] lg:table-cell">{ad.leads ?? "—"}</td>
                <td className="hidden pl-3 pr-4 py-3 text-right font-mono-num text-xs text-[var(--muted)] lg:table-cell">
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
            <th className={`${TH} px-3 text-right`}>Investimento</th>
            <th className={`${TH} px-3 text-right hidden lg:table-cell`}>Conv.</th>
            <th className={`${TH} pl-3 pr-4 text-right hidden lg:table-cell`}>CPA</th>
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
                    <span className="font-mono-num text-xs text-[var(--muted)]">{c.rank + 1}</span>
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
                <td className="px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)]">{fmtK(c.investimento)}</td>
                <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] lg:table-cell">{c.conversoes ?? "—"}</td>
                <td className="hidden pl-3 pr-4 py-3 text-right font-mono-num text-xs text-[var(--muted)] lg:table-cell">{fmtK(c.cpa)}</td>
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
            gestorApi.metricasBreakdown(c.slug, mes)
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
          for (const ad of bd.meta_ads ?? [])
            allMeta.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug, rank: 0 });
          for (const ad of bd.google_ads ?? [])
            allGoogle.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug, rank: 0 });
        }
        setMetaAds(sortByRoas(allMeta).map((a, i) => ({ ...a, rank: i })));
        setGoogleAds(sortByRoas(allGoogle).map((a, i) => ({ ...a, rank: i })));
      })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [mes]);

  const activeAds = rede === "meta" ? metaAds : googleAds;
  const totalFat = activeAds.reduce((s, a) => s + (a.faturamento ?? 0), 0);
  const totalInv = activeAds.reduce((s, a) => s + (a.investimento ?? 0), 0);
  const roasMedio = totalInv > 0 ? totalFat / totalInv : null;
  const maxRoas = activeAds.length > 0 ? Math.max(...activeAds.filter(a => a.roas != null).map(a => a.roas ?? 0)) : 0;

  const restMeta = metaAds.slice(3);
  const restGoogle = googleAds.slice(3);

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <Link href="/gestor" className="mb-8 block text-xs text-[var(--muted)] transition hover:text-[var(--ink)]">
        ← Seus clientes
      </Link>

      {/* Header */}
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
            Performance
          </h1>
          <p className="mt-1 text-sm text-[var(--muted)]">Rankings de criativos e campanhas da carteira</p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="mes-ref" className="text-xs text-[var(--muted)]">Mês</label>
          <select
            id="mes-ref"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-1.5 text-xs text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          >
            {mesOpcoes.map((m) => (
              <option key={m} value={m}>{mesLabel(m)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Tabs */}
      <div className="mb-6 flex gap-1.5">
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
            { label: "Faturamento total", value: fmtK(totalFat), sub: mesLabel(mes) },
            { label: "ROAS médio", value: roasMedio != null ? fmtRoas(roasMedio) : "—", sub: "ponderado por investimento" },
          ]} />

          {/* Pódio top 3 */}
          {rede === "meta" && metaAds.length >= 1 && (
            <div className="mb-2">
              <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Top 3 criativos</p>
              <PodiumMeta ads={metaAds} maxRoas={maxRoas} onSelect={setSelectedMeta} />
            </div>
          )}
          {rede === "google" && googleAds.length >= 1 && (
            <div className="mb-2">
              <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">Top 3 campanhas</p>
              <PodiumGoogle ads={googleAds} maxRoas={maxRoas} onSelect={setSelectedGoogle} />
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

      {selectedMeta && <MetaDrawer ad={selectedMeta} allAds={metaAds} onClose={() => setSelectedMeta(null)} />}
      {selectedGoogle && <GoogleDrawer ad={selectedGoogle} allAds={googleAds} onClose={() => setSelectedGoogle(null)} />}
    </main>
  );
}
