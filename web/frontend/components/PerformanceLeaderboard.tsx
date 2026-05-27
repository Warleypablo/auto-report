"use client";

import { motion } from "framer-motion";
import { useState } from "react";

import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import {
  fmtBRL,
  fmtRoas,
  type RoasTier,
  roasTier,
  TIER_TEXT,
  TIER_BAR,
  sortByRoas,
} from "@/lib/roas-tier";

function MetaLeaderboard({ ads }: { ads: MetaAd[] }) {
  const [showAll, setShowAll] = useState(false);
  const sorted = sortByRoas(ads);
  const top3 = sorted.slice(0, 3);
  const rest = sorted.slice(3);

  if (ads.length === 0) {
    return (
      <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
        Sem criativos detalhados neste mês.
      </p>
    );
  }

  return (
    <div>
      <div className="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-2 md:grid md:grid-cols-3 md:overflow-visible md:pb-0">
        {top3.map((ad, i) => {
          const tier = roasTier(ad.roas);
          return (
            <motion.div
              key={ad.nome}
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              whileInView={{ opacity: 1, y: 0, scale: 1 }}
              viewport={{ once: true, margin: "-10%" }}
              transition={{ duration: 0.5, delay: i * 0.08, ease: [0.2, 0.7, 0.2, 1] }}
              whileHover={{ scale: 1.02 }}
              className="group relative aspect-video min-w-[85%] snap-start overflow-hidden rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-deep)] md:min-w-0"
            >
              {ad.imagem_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={ad.imagem_url}
                  alt={ad.nome}
                  className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
                />
              ) : (
                <div className="h-full w-full bg-gradient-to-br from-[var(--paper-deep)] to-[var(--paper-soft)]" />
              )}

              <div className="absolute left-3 top-3 rounded-sm bg-black/55 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-white font-semibold">
                #{i + 1}
              </div>

              <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/50 to-transparent p-4">
                <p className="line-clamp-1 text-[11px] text-white/90" title={ad.nome}>
                  {ad.nome}
                </p>
                <div className="mt-1 flex items-baseline justify-between">
                  <span className={`font-mono-num text-lg font-semibold ${TIER_TEXT[tier]}`}>
                    {fmtRoas(ad.roas)}
                  </span>
                  <span className="font-mono-num text-[11px] text-white/60">
                    {fmtBRL(ad.investimento)}
                  </span>
                </div>
                <p className="font-mono-num mt-0.5 text-[10px] text-white/50">
                  {ad.leads != null
                    ? `${ad.leads.toLocaleString("pt-BR")} leads`
                    : ad.conversoes != null
                    ? `${ad.conversoes.toLocaleString("pt-BR")} conv.`
                    : ""}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>

      {rest.length > 0 && (
        <div className="mt-3">
          {showAll && (
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--rule-soft)]">
                  <th className="py-1.5 pr-3 text-left font-medium text-[var(--muted)]">#</th>
                  <th className="py-1.5 pr-3 text-left font-medium text-[var(--muted)]">Anúncio</th>
                  <th className="py-1.5 pr-3 text-right font-medium text-[var(--muted)]">ROAS</th>
                  <th className="py-1.5 pr-3 text-right font-medium text-[var(--muted)]">Invest.</th>
                  <th className="py-1.5 text-right font-medium text-[var(--muted)]">Leads / Conv.</th>
                </tr>
              </thead>
              <tbody>
                {rest.map((ad, i) => {
                  const tier = roasTier(ad.roas);
                  return (
                    <tr
                      key={ad.nome}
                      className="border-b border-[var(--rule-soft)]/40 hover:bg-[var(--paper-soft)]"
                    >
                      <td className="py-2 pr-3 text-[var(--muted)]">{i + 4}</td>
                      <td className="py-2 pr-3 max-w-[200px]" title={ad.nome}>
                        <span className="block truncate text-[var(--ink)]">{ad.nome}</span>
                      </td>
                      <td
                        className={`py-2 pr-3 text-right font-mono-num font-semibold ${TIER_TEXT[tier]}`}
                      >
                        {fmtRoas(ad.roas)}
                      </td>
                      <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                        {fmtBRL(ad.investimento)}
                      </td>
                      <td className="py-2 text-right font-mono-num text-[var(--ink)]">
                        {ad.leads != null
                          ? ad.leads.toLocaleString("pt-BR")
                          : ad.conversoes != null
                          ? ad.conversoes.toLocaleString("pt-BR")
                          : "—"}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          )}
          <button
            type="button"
            aria-expanded={showAll}
            onClick={() => setShowAll((v) => !v)}
            className="mt-2 text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:underline"
          >
            {showAll ? "Mostrar só top 3" : `Ver todos os ${ads.length} →`}
          </button>
        </div>
      )}
    </div>
  );
}

function GoogleLeaderboard({ ads }: { ads: GoogleAd[] }) {
  const [showAll, setShowAll] = useState(false);
  const INITIAL_LIMIT = 5;

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
    <div className="flex flex-col divide-y divide-[var(--rule-soft)] rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
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
                <motion.div
                  className={`h-full origin-left ${TIER_BAR[tier]}`}
                  initial={{ scaleX: 0 }}
                  whileInView={{ scaleX: pct }}
                  viewport={{ once: true, margin: "-15%" }}
                  transition={{ duration: 0.8, delay: i * 0.06, ease: "easeOut" }}
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

      {ads.length > INITIAL_LIMIT && (
        <div className="px-4 py-2">
          <button
            type="button"
            aria-expanded={showAll}
            onClick={() => setShowAll((v) => !v)}
            className="text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:underline"
          >
            {showAll ? "Mostrar só top 5" : `Ver todas as ${ads.length} →`}
          </button>
        </div>
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
