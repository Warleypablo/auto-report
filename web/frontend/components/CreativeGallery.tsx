"use client";

import { useState } from "react";
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

const GRAD_PAIRS = [
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

function CreativeCard({ ad, index }: { ad: MetaAd; index: number }) {
  const [broken, setBroken] = useState(false);
  const showFallback = !ad.imagem_url || broken;
  const [from, to] = GRAD_PAIRS[nameHash(ad.nome) % GRAD_PAIRS.length];
  const initial = (ad.nome.trim()[0] ?? "?").toUpperCase();

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.98 }}
      whileInView={{ opacity: 1, y: 0, scale: 1 }}
      viewport={{ once: true, margin: "-10%" }}
      transition={{ duration: 0.5, delay: index * 0.08, ease: [0.2, 0.7, 0.2, 1] }}
      whileHover={{ scale: 1.02 }}
      className="group relative aspect-video min-w-[85%] snap-start overflow-hidden rounded-lg border border-[var(--rule-soft)] md:min-w-0"
    >
      {showFallback ? (
        <div
          className="flex h-full w-full items-center justify-center select-none"
          style={{ background: `linear-gradient(135deg, ${from} 0%, ${to} 100%)` }}
        >
          <span className="font-bold text-white/20" style={{ fontSize: "clamp(2rem, 25%, 5rem)" }}>
            {initial}
          </span>
        </div>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={ad.imagem_url!}
          alt={ad.nome}
          className="h-full w-full object-cover transition-transform duration-500 group-hover:scale-105"
          onError={() => setBroken(true)}
        />
      )}

      <div className="absolute left-3 top-3 rounded-sm bg-black/55 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-white">
        #{index + 1}
      </div>

      <div className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-black/85 via-black/50 to-transparent p-4">
        <p className="line-clamp-1 text-[11px] text-white/90">{ad.nome}</p>
        <div className="mt-1 flex items-baseline justify-between">
          <span className="font-mono-num text-lg text-white">{fmtRoas(ad.roas)}</span>
          <span className="font-mono-num text-[11px] text-white/80">{fmtBRL(ad.investimento)}</span>
        </div>
      </div>
    </motion.div>
  );
}

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
          <CreativeCard key={i} ad={ad} index={i} />
        ))}
      </div>
    </RevealOnView>
  );
}
