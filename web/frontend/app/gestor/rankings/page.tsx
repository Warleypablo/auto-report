"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { gestorApi } from "@/lib/api-gestor";
import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import { deslocarMes, mesUltimoFechado } from "@/lib/mes-utils";
import {
  fmtRoas,
  roasTier,
  sortByRoas,
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

const TH_L = "pb-2.5 pt-3 text-left text-[10px] font-normal uppercase tracking-widest text-[var(--muted)] whitespace-nowrap";
const TH_R = "pb-2.5 pt-3 text-right text-[10px] font-normal uppercase tracking-widest text-[var(--muted)] whitespace-nowrap";

export default function RankingsPage() {
  const router = useRouter();
  const [mes, setMes] = useState(mesUltimoFechado());
  const [loading, setLoading] = useState(true);
  const [rede, setRede] = useState<"meta" | "google">("meta");
  const [metaAds, setMetaAds] = useState<RankedMetaAd[]>([]);
  const [googleAds, setGoogleAds] = useState<RankedGoogleAd[]>([]);

  const mesOpcoes = useMemo(
    () => Array.from({ length: 12 }, (_, i) => deslocarMes(mesUltimoFechado(), -i)),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    console.log('[rankings] effect disparado, mes =', mes);
    setLoading(true);
    gestorApi
      .clientes()
      .then(({ items }) => {
        if (cancelled) { console.log('[rankings] cancelado após clientes()'); return null; }
        const ativos = items.filter((c) => c.ativo);
        console.log('[rankings] clientes ativos:', ativos.length, '| buscando breakdown para mes =', mes);
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
        if (!results || cancelled) { console.log('[rankings] cancelado ou sem resultados'); return; }
        const allMeta: RankedMetaAd[] = [];
        const allGoogle: RankedGoogleAd[] = [];
        console.log('[rankings] breakdowns recebidos:', results.length, '| primeiro google_ads:', results[0]?.bd?.google_ads);
        for (const { cliente, bd } of results) {
          if (!bd) continue;
          for (const ad of bd.meta_ads ?? []) {
            allMeta.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug });
          }
          for (const ad of bd.google_ads ?? []) {
            allGoogle.push({ ...ad, clienteNome: cliente.nome, clienteSlug: cliente.slug });
          }
        }
        console.log('[rankings] setando', allMeta.length, 'meta ads e', allGoogle.length, 'google ads para mes =', mes);
        setMetaAds(sortByRoas(allMeta));
        setGoogleAds(sortByRoas(allGoogle));
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
        <section>
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
                    {metaAds.map((ad, i) => {
                      const tier = roasTier(ad.roas);
                      return (
                        <tr
                          key={`${ad.clienteSlug}-${ad.nome}`}
                          onClick={() => router.push(`/gestor/${ad.clienteSlug}`)}
                          className="cursor-pointer transition hover:bg-[var(--paper-deep)]"
                        >
                          <td className={`py-2.5 pl-4 pr-2 font-mono-num text-xs ${rankColor(i)}`}>
                            #{i + 1}
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
        <section>
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
                    {googleAds.map((c, i) => {
                      const tier = roasTier(c.roas);
                      return (
                        <tr
                          key={`${c.clienteSlug}-${c.nome}`}
                          onClick={() => router.push(`/gestor/${c.clienteSlug}`)}
                          className="cursor-pointer transition hover:bg-[var(--paper-deep)]"
                        >
                          <td className={`py-2.5 pl-4 pr-2 font-mono-num text-xs ${rankColor(i)}`}>
                            #{i + 1}
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
    </main>
  );
}
