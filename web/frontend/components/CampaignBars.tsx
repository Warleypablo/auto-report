"use client";

import { motion } from "framer-motion";

import type { GoogleAd } from "@/lib/api-cliente";

import RevealOnView from "./RevealOnView";

type Props = {
  campanhas: GoogleAd[];
  onSeeAll: () => void;
};

const fmtBRL = (v: number | null) =>
  v == null
    ? "—"
    : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtRoas = (v: number | null) => (v == null ? "—" : `${v.toFixed(2).replace(".", ",")}×`);

export default function CampaignBars({ campanhas, onSeeAll }: Props) {
  if (campanhas.length === 0) {
    return (
      <RevealOnView className="mb-16">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Top campanhas · Google Ads</p>
        <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
          Sem campanhas detalhadas neste mês.
        </p>
      </RevealOnView>
    );
  }

  const top5 = campanhas.slice(0, 5);
  const maxInv = Math.max(...top5.map((c) => c.investimento ?? 0), 1);

  return (
    <RevealOnView className="mb-16">
      <div className="mb-4 flex items-end justify-between">
        <p className="eyebrow text-xs text-[var(--muted)]">Top campanhas · Google Ads</p>
        {campanhas.length > 5 && (
          <button
            type="button"
            onClick={onSeeAll}
            className="text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:underline"
          >
            Ver todas as {campanhas.length} →
          </button>
        )}
      </div>

      <div className="flex flex-col divide-y divide-[var(--rule-soft)] rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
        {top5.map((c, i) => {
          const pct = (c.investimento ?? 0) / maxInv;
          return (
            <div key={i} className="grid grid-cols-[1fr_auto] items-center gap-4 px-4 py-3">
              <div className="min-w-0">
                <p className="font-display truncate text-base text-[var(--ink)]">{c.nome}</p>
                <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[var(--paper-deep)]">
                  <motion.div
                    className="h-full origin-left bg-[var(--forest)]"
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
              <p className="font-mono-num text-base text-[var(--ink)]">{fmtRoas(c.roas)}</p>
            </div>
          );
        })}
      </div>
    </RevealOnView>
  );
}
