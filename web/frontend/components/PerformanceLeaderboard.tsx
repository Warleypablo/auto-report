"use client";

import { useState } from "react";

import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import {
  fmtBRL,
  fmtRoas,
  roasTier,
  TIER_TEXT,
  TIER_BAR,
  sortByRoas,
} from "@/lib/roas-tier";
import AdThumb from "./AdThumb";

const INITIAL_LIMIT = 5;

const TH = "pb-2 pt-3 text-[10px] font-normal uppercase tracking-widest text-[var(--muted)] whitespace-nowrap";

function MetaLeaderboard({ ads }: { ads: MetaAd[] }) {
  const [showAll, setShowAll] = useState(false);
  const sorted = sortByRoas(ads);
  const visible = showAll ? sorted : sorted.slice(0, INITIAL_LIMIT);
  const maxRoas = sorted.length > 0 ? Math.max(...sorted.filter(a => a.roas != null).map(a => a.roas ?? 0)) : 0;

  if (ads.length === 0) {
    return (
      <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
        Sem criativos detalhados neste mês.
      </p>
    );
  }

  return (
    <div>
      <div className="overflow-hidden rounded-lg border border-[var(--rule-soft)]">
        <table className="w-full">
          <thead>
            <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
              <th className={`${TH} pl-4 pr-2 w-8 text-left`}>#</th>
              <th className={`${TH} px-3 text-left`}>Criativo</th>
              <th className={`${TH} px-3 text-right`}>ROAS</th>
              <th className={`${TH} px-3 text-right`}>Faturamento</th>
              <th className={`${TH} px-3 text-right hidden sm:table-cell`}>Investimento</th>
              <th className={`${TH} px-3 text-right hidden md:table-cell`}>Leads / Conv.</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[var(--rule-soft)]">
            {visible.map((ad, i) => {
              const tier = roasTier(ad.roas);
              const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;
              return (
                <tr key={ad.nome} className="bg-[var(--paper)] hover:bg-[var(--paper-soft)] transition">
                  <td className="py-3 pl-0 pr-2">
                    <div className="flex items-center">
                      <div className={`mr-3 h-8 w-0.5 rounded-full ${TIER_BAR[tier]}`} />
                      <span className="font-mono-num text-xs text-[var(--muted)]">{i + 1}</span>
                    </div>
                  </td>
                  <td className="px-3 py-3 max-w-[220px]">
                    <div className="flex items-center gap-2.5">
                      <AdThumb src={ad.imagem_url} name={ad.nome} className="h-9 w-14 flex-shrink-0 rounded" />
                      <span className="block truncate text-xs font-medium text-[var(--ink)]" title={ad.nome}>{ad.nome}</span>
                    </div>
                  </td>
                  <td className="px-3 py-3 text-right">
                    <span className={`font-mono-num text-sm font-semibold ${TIER_TEXT[tier]}`}>{fmtRoas(ad.roas)}</span>
                    <div className="mt-1 h-0.5 w-full rounded-full bg-[var(--paper-deep)]">
                      <div className={`h-0.5 rounded-full ${TIER_BAR[tier]}`} style={{ width: `${barPct}%` }} />
                    </div>
                  </td>
                  <td className="px-3 py-3 text-right font-mono-num text-xs text-[var(--forest)]">{fmtBRL(ad.faturamento)}</td>
                  <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] sm:table-cell">{fmtBRL(ad.investimento)}</td>
                  <td className="hidden px-3 py-3 text-right font-mono-num text-xs text-[var(--muted)] md:table-cell">
                    {ad.leads != null ? `${ad.leads.toLocaleString("pt-BR")} leads` : ad.conversoes != null ? `${ad.conversoes.toLocaleString("pt-BR")} conv.` : "—"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {ads.length > INITIAL_LIMIT && (
        <button
          type="button"
          aria-expanded={showAll}
          onClick={() => setShowAll((v) => !v)}
          className="mt-2 text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:underline"
        >
          {showAll ? "Mostrar só top 5" : `Ver todos os ${ads.length} →`}
        </button>
      )}
    </div>
  );
}

function GoogleLeaderboard({ ads }: { ads: GoogleAd[] }) {
  const [showAll, setShowAll] = useState(false);

  if (ads.length === 0) {
    return (
      <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
        Sem campanhas detalhadas neste mês.
      </p>
    );
  }

  const sorted = sortByRoas(ads);
  const visible = showAll ? sorted : sorted.slice(0, INITIAL_LIMIT);
  const maxInv = Math.max(...sorted.map((c) => c.investimento ?? 0), 1);

  return (
    <div>
      <div className="flex flex-col divide-y divide-[var(--rule-soft)] overflow-hidden rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
        {visible.map((c, i) => {
          const tier = roasTier(c.roas);
          const pct = (c.investimento ?? 0) / maxInv;
          return (
            <div
              key={c.nome}
              className="grid grid-cols-[2rem_1fr_auto] items-center gap-4 px-4 py-3"
            >
              <span className="font-mono-num text-xs text-[var(--muted)]">#{i + 1}</span>
              <div className="min-w-0">
                <p className="truncate text-sm text-[var(--ink)]" title={c.nome}>
                  {c.nome}
                </p>
                <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[var(--paper-deep)]">
                  <div
                    className={`h-full origin-left ${TIER_BAR[tier]}`}
                    style={{ width: `${pct * 100}%`, transition: "width 0.8s ease" }}
                  />
                </div>
                <p className="font-mono-num mt-1 text-[10px] text-[var(--muted)]">
                  Invest: {fmtBRL(c.investimento)}
                </p>
              </div>
              <p className={`font-mono-num text-base font-semibold ${TIER_TEXT[tier]}`}>
                {fmtRoas(c.roas)}
              </p>
            </div>
          );
        })}
      </div>
      {ads.length > INITIAL_LIMIT && (
        <button
          type="button"
          aria-expanded={showAll}
          onClick={() => setShowAll((v) => !v)}
          className="mt-2 text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:underline"
        >
          {showAll ? "Mostrar só top 5" : `Ver todas as ${ads.length} →`}
        </button>
      )}
    </div>
  );
}

type Props = {
  metaAds: MetaAd[];
  googleAds: GoogleAd[];
  loading: boolean;
};

export default function PerformanceLeaderboard({ metaAds, googleAds, loading }: Props) {
  if (loading) {
    return (
      <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
        Carregando…
      </p>
    );
  }

  if (metaAds.length === 0 && googleAds.length === 0) {
    return (
      <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
        Sem dados granulares para este mês.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      {metaAds.length > 0 && (
        <div>
          <p className="eyebrow mb-3 text-[10px] font-medium text-[var(--muted)]">
            Meta Ads — top criativos
          </p>
          <MetaLeaderboard ads={metaAds} />
        </div>
      )}
      {googleAds.length > 0 && (
        <div>
          <p className="eyebrow mb-3 text-[10px] font-medium text-[var(--muted)]">
            Google Ads — campanhas
          </p>
          <GoogleLeaderboard ads={googleAds} />
        </div>
      )}
    </div>
  );
}
