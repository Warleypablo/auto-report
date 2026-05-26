"use client";

import { motion } from "framer-motion";

import type { MetaAd } from "@/lib/api-cliente";

import RevealOnView from "./RevealOnView";

type Props = {
  criativos: MetaAd[];
  onSeeAll: () => void;
};

const fmtBRL = (v: number | null) =>
  v == null
    ? "—"
    : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtRoas = (v: number | null) => (v == null ? "—" : `${v.toFixed(2).replace(".", ",")}×`);

export default function CreativeGallery({ criativos, onSeeAll }: Props) {
  if (criativos.length === 0) {
    return (
      <RevealOnView className="mb-16">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Top criativos · Meta Ads</p>
        <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
          Sem criativos detalhados neste mês.
        </p>
      </RevealOnView>
    );
  }

  const top3 = criativos.slice(0, 3);

  return (
    <RevealOnView className="mb-16">
      <div className="mb-4 flex items-end justify-between">
        <p className="eyebrow text-xs text-[var(--muted)]">Top criativos · Meta Ads</p>
        {criativos.length > 3 && (
          <button
            type="button"
            onClick={onSeeAll}
            className="text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:underline"
          >
            Ver todos os {criativos.length} →
          </button>
        )}
      </div>

      <div className="flex gap-3 overflow-x-auto snap-x snap-mandatory pb-2 md:grid md:grid-cols-3 md:overflow-visible md:pb-0">
        {top3.map((ad, i) => (
          <motion.div
            key={i}
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
              <div className="flex h-full w-full items-center justify-center text-[10px] uppercase tracking-[0.18em] text-[var(--muted)]">
                sem imagem
              </div>
            )}

            <div className="absolute left-3 top-3 rounded-sm bg-black/55 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-white">
              #{i + 1}
            </div>

            <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/50 to-transparent p-4">
              <p className="line-clamp-1 text-[11px] text-white/90">{ad.nome}</p>
              <div className="mt-1 flex items-baseline justify-between">
                <span className="font-mono-num text-lg text-white">{fmtRoas(ad.roas)}</span>
                <span className="font-mono-num text-[11px] text-white/80">{fmtBRL(ad.investimento)}</span>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </RevealOnView>
  );
}
