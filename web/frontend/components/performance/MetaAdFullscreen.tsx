"use client";

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useEffect } from "react";

import type { MetaAd } from "@/lib/api-gestor";

import { useAdContext } from "./useAdContext";
import { useFocusTrap } from "./useFocusTrap";
import { ContextBlock } from "./blocks/ContextBlock";
import { CriativoPreview } from "./blocks/CriativoPreview";
import { EvolucaoChart } from "./EvolucaoChart";
import { FunilFadigaBlock } from "./blocks/FunilFadigaBlock";
import { KpiHeader } from "./blocks/KpiHeader";
import { MetricsRows } from "./blocks/MetricsRows";

type RankedMetaAd = MetaAd & {
  clienteNome: string;
  clienteSlug: string;
  gestorNome: string | null;
  rank: number;
  rankDelta: number | null;
};

export type MetaAdFullscreenProps = {
  ad: RankedMetaAd | null;
  allAds: RankedMetaAd[];
  onClose: () => void;
  mes: string;
};

export function MetaAdFullscreen({ ad, allAds, onClose, mes }: MetaAdFullscreenProps) {
  useEffect(() => {
    if (!ad) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [ad, onClose]);

  useEffect(() => {
    if (!ad) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [ad]);

  return (
    <AnimatePresence>
      {ad && <MetaAdFullscreenBody ad={ad} allAds={allAds} onClose={onClose} mes={mes} />}
    </AnimatePresence>
  );
}

function MetaAdFullscreenBody({
  ad,
  allAds,
  onClose,
  mes,
}: {
  ad: RankedMetaAd;
  allAds: RankedMetaAd[];
  onClose: () => void;
  mes: string;
}) {
  const ctx = useAdContext(ad, allAds);
  const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0).length;
  const trapRef = useFocusTrap<HTMLDivElement>(true);

  return (
    <motion.div
      ref={trapRef}
      className="fixed inset-0 z-50 flex flex-col overflow-y-auto bg-[var(--paper)]"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      role="dialog"
      aria-modal="true"
      aria-labelledby="fs-title"
    >
      {/* Header sticky */}
      <header className="sticky top-0 z-10 flex items-start justify-between border-b border-[var(--rule-soft)] bg-[var(--paper)] px-8 py-5">
        <div className="min-w-0">
          <h2 id="fs-title" className="truncate font-display text-xl text-[var(--ink)]" title={ad.nome}>
            {ad.nome}
          </h2>
          <p className="text-xs text-[var(--muted)]">{ad.clienteNome}</p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Fechar"
          className="rounded-full border border-[var(--rule-soft)] px-4 py-1.5 text-xs uppercase tracking-[0.18em] text-[var(--muted)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
        >
          Fechar ✕
        </button>
      </header>

      <div className="flex-1 px-8 py-8">
        <KpiHeader ad={ad} ctx={ctx} totalAdsComRoas={adsComRoas} mode="fullscreen" />

        <div className="grid grid-cols-1 gap-8 md:grid-cols-2">
          <div>
            <CriativoPreview ad={ad} mode="fullscreen" />
            <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">Métricas</p>
            <MetricsRows ad={ad} cpm={ctx.cpm} mode="fullscreen" />
          </div>

          <div className="space-y-6">
            <FunilFadigaBlock ad={ad} ctx={ctx} variant="meta" />
            <div className="rounded-xl border border-[var(--rule-soft)] px-6 py-5">
              <p className="mb-2 text-[10px] uppercase tracking-widest text-[var(--muted)]">
                Evolução · 6 meses
              </p>
              <EvolucaoChart
                clienteSlug={ad.clienteSlug}
                adNome={ad.nome}
                adType="meta"
                mes={mes}
                mode="fullscreen"
              />
            </div>
          </div>
        </div>

        <ContextBlock ctx={ctx} mode="fullscreen" />
      </div>

      <footer className="border-t border-[var(--rule-soft)] px-8 py-4">
        <Link
          href={`/gestor/${ad.clienteSlug}`}
          className="text-sm text-[var(--forest)] transition hover:underline"
        >
          → Ver dashboard do cliente
        </Link>
      </footer>
    </motion.div>
  );
}
