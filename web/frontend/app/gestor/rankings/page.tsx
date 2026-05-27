"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";

import { gestorApi } from "@/lib/api-gestor";
import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import { deslocarMes, mesUltimoFechado } from "@/lib/mes-utils";
import {
  fmtBRL,
  fmtRoas,
  roasTier,
  sortByRoas,
  TIER_BAR,
  TIER_TEXT,
} from "@/lib/roas-tier";

type RankedMetaAd = MetaAd & { clienteNome: string; clienteSlug: string };
type RankedGoogleAd = GoogleAd & { clienteNome: string; clienteSlug: string };

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

export default function RankingsPage() {
  const [mes, setMes] = useState(mesUltimoFechado());
  const [loading, setLoading] = useState(true);
  const [metaAds, setMetaAds] = useState<RankedMetaAd[]>([]);
  const [googleAds, setGoogleAds] = useState<RankedGoogleAd[]>([]);

  const mesOpcoes = useMemo(
    () => Array.from({ length: 12 }, (_, i) => deslocarMes(mesUltimoFechado(), -i)),
    [],
  );

  useEffect(() => {
    setLoading(true);
    gestorApi
      .clientes()
      .then(({ items }) => {
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
        const allMeta: RankedMetaAd[] = [];
        const allGoogle: RankedGoogleAd[] = [];
        for (const { cliente, bd } of results) {
          if (!bd) continue;
          for (const ad of bd.meta_ads) {
            allMeta.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug });
          }
          for (const ad of bd.google_ads) {
            allGoogle.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug });
          }
        }
        setMetaAds(sortByRoas(allMeta));
        setGoogleAds(sortByRoas(allGoogle));
      })
      .finally(() => setLoading(false));
  }, [mes]);

  const maxInvGoogle = useMemo(
    () => googleAds.reduce((max, c) => Math.max(max, c.investimento ?? 0), 0) || 1,
    [googleAds],
  );

  return (
    <main className="mx-auto max-w-4xl px-6 py-12">
      <Link
        href="/gestor"
        className="mb-6 block text-xs text-[var(--muted)] transition hover:text-[var(--ink)]"
      >
        ← Seus clientes
      </Link>

      <div className="mb-8 flex items-baseline justify-between gap-4">
        <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
          Rankings
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

      {loading ? (
        <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-12 text-center text-sm text-[var(--muted)]">
          Carregando rankings…
        </p>
      ) : (
        <div className="flex flex-col gap-12">
          {/* Meta Ads */}
          <section>
            <p className="eyebrow mb-4 text-xs text-[var(--muted)]">
              Top criativos · Meta Ads · carteira
            </p>
            {metaAds.length === 0 ? (
              <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
                Nenhum dado disponível para este mês.
              </p>
            ) : (
              <div className="flex flex-col divide-y divide-[var(--rule-soft)] rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                {metaAds.map((ad, i) => {
                  const tier = roasTier(ad.roas);
                  return (
                    <Link
                      key={`${ad.clienteSlug}-${ad.nome}`}
                      href={`/gestor/${ad.clienteSlug}`}
                      className="grid grid-cols-[2rem_2rem_1fr_auto] items-start gap-3 px-4 py-3 transition hover:bg-[var(--paper-deep)]"
                    >
                      <span className={`font-mono-num pt-0.5 text-xs ${rankColor(i)}`}>#{i + 1}</span>
                      <div className="relative mt-0.5 h-5 w-7 flex-shrink-0">
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
                      <div className="min-w-0">
                        <p className="truncate text-sm text-[var(--ink)]" title={ad.nome}>
                          {ad.nome}
                        </p>
                        <p className="mb-1.5 text-[10px] text-[var(--muted)]">{ad.clienteNome}</p>
                        <div className="flex flex-wrap gap-x-3 gap-y-0.5">
                          {ad.faturamento != null && (
                            <span className="font-mono-num text-[10px] text-[var(--forest)]">
                              {fmtK(ad.faturamento)} fat
                            </span>
                          )}
                          {ad.conversoes != null && (
                            <span className="font-mono-num text-[10px] text-[var(--muted)]">
                              {ad.conversoes} conv
                            </span>
                          )}
                          {ad.leads != null && (
                            <span className="font-mono-num text-[10px] text-[var(--muted)]">
                              {ad.leads} leads
                            </span>
                          )}
                          {ad.cpa != null && (
                            <span className="font-mono-num text-[10px] text-[var(--muted)]">
                              CPA {fmtK(ad.cpa)}
                            </span>
                          )}
                          {ad.cpl != null && (
                            <span className="font-mono-num text-[10px] text-[var(--muted)]">
                              CPL {fmtK(ad.cpl)}
                            </span>
                          )}
                        </div>
                      </div>
                      <div className="text-right">
                        <p className={`font-mono-num text-base font-semibold ${TIER_TEXT[tier]}`}>
                          {fmtRoas(ad.roas)}
                        </p>
                        <p className="font-mono-num text-[10px] text-[var(--muted)]">
                          {fmtBRL(ad.investimento)}
                        </p>
                      </div>
                    </Link>
                  );
                })}
              </div>
            )}
          </section>

          {/* Google Ads */}
          <section>
            <p className="eyebrow mb-4 text-xs text-[var(--muted)]">
              Top campanhas · Google Ads · carteira
            </p>
            {googleAds.length === 0 ? (
              <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
                Nenhum dado disponível para este mês.
              </p>
            ) : (
              <div className="flex flex-col divide-y divide-[var(--rule-soft)] rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                {googleAds.map((c, i) => {
                  const tier = roasTier(c.roas);
                  const pct = (c.investimento ?? 0) / maxInvGoogle;
                  return (
                    <Link
                      key={`${c.clienteSlug}-${c.nome}`}
                      href={`/gestor/${c.clienteSlug}`}
                      className="grid grid-cols-[2rem_1fr_auto] items-center gap-4 px-4 py-3 transition hover:bg-[var(--paper-deep)]"
                    >
                      <span className={`font-mono-num text-xs ${rankColor(i)}`}>#{i + 1}</span>
                      <div className="min-w-0">
                        <p className="truncate text-sm text-[var(--ink)]" title={c.nome}>
                          {c.nome}
                        </p>
                        <p className="text-[10px] text-[var(--muted)]">{c.clienteNome}</p>
                        <div className="mt-1.5 h-1 w-full overflow-hidden rounded-full bg-[var(--paper-deep)]">
                          <motion.div
                            className={`h-full origin-left ${TIER_BAR[tier]}`}
                            initial={{ scaleX: 0 }}
                            whileInView={{ scaleX: pct }}
                            viewport={{ once: true, margin: "-15%" }}
                            transition={{ duration: 0.8, delay: i * 0.04, ease: "easeOut" }}
                          />
                        </div>
                        <p className="font-mono-num mt-1 text-[10px] text-[var(--muted)]">
                          Invest: {fmtBRL(c.investimento)}
                        </p>
                      </div>
                      <p className={`font-mono-num text-base font-semibold ${TIER_TEXT[tier]}`}>
                        {fmtRoas(c.roas)}
                      </p>
                    </Link>
                  );
                })}
              </div>
            )}
          </section>
        </div>
      )}
    </main>
  );
}
