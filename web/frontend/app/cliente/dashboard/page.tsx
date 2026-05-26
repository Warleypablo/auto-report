"use client";

import { Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import {
  ApiError,
  Breakdown,
  ClientePublic,
  Highlight,
  TimelineItem,
  clienteApi,
} from "@/lib/api-cliente";

import CampaignBars from "@/components/CampaignBars";
import CreativeGallery from "@/components/CreativeGallery";
import DetailsDrawer from "@/components/DetailsDrawer";
import EvolutionChartHero from "@/components/EvolutionChartHero";
import HeroMonth from "@/components/HeroMonth";
import KpiRow from "@/components/KpiRow";
import WelcomeSplash from "@/components/WelcomeSplash";

const NOMES_MES = [
  "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
  "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
];

function mesLabel(mes: string): string {
  if (!mes) return "";
  const [a, m] = mes.split("-");
  return `${NOMES_MES[parseInt(m) - 1]} ${a}`;
}

const fmtBRL = (v: number | null) =>
  v == null ? "—" : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
const fmtInt = (v: number | null) => (v == null ? "—" : v.toLocaleString("pt-BR"));

export default function ClienteDashboardPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center">
          <p className="font-display text-xl italic text-[var(--muted)]">Carregando…</p>
        </main>
      }
    >
      <ClienteDashboardInner />
    </Suspense>
  );
}

function ClienteDashboardInner() {
  const router = useRouter();
  const search = useSearchParams();
  const wantIntro = search.get("intro") === "1";

  const fetchedRef = useRef(false);

  const [cliente, setCliente] = useState<ClientePublic | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [highlight, setHighlight] = useState<Highlight | null>(null);
  const [mesesDisponiveis, setMesesDisponiveis] = useState<string[]>([]);
  const [mes, setMes] = useState<string>("");
  const [breakdown, setBreakdown] = useState<Breakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [showSplash, setShowSplash] = useState(false);
  const [drawerMeta, setDrawerMeta] = useState(false);
  const [drawerGoogle, setDrawerGoogle] = useState(false);

  useEffect(() => {
    if (fetchedRef.current) return;
    fetchedRef.current = true;

    Promise.all([
      clienteApi.me(),
      clienteApi.timeline(12),
      clienteApi.mesesDisponiveis(),
      clienteApi.highlight().catch(() => ({ highlight: null })),
    ])
      .then(([me, tl, md, hl]) => {
        setCliente(me);
        setTimeline(tl.items);
        setMesesDisponiveis(md.meses);
        setHighlight(hl.highlight);
        if (md.meses.length > 0) setMes(md.meses[0]);

        if (wantIntro) {
          const today = new Date().toISOString().slice(0, 10);
          const key = `splash-seen-${today}`;
          if (typeof window !== "undefined" && !localStorage.getItem(key)) {
            setShowSplash(true);
            localStorage.setItem(key, "1");
          }
          // Limpa query param ?intro=1
          router.replace("/cliente/dashboard");
        }
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) {
          router.push("/cliente/login?expired=1");
          return;
        }
        setErr(e instanceof Error ? e.message : "Erro ao carregar dados.");
      })
      .finally(() => setLoading(false));
  }, [router, wantIntro]);

  useEffect(() => {
    if (!mes) return;
    clienteApi.breakdown(mes).then(setBreakdown).catch(() => setBreakdown(null));
  }, [mes]);

  const snapMes = useMemo(() => timeline.find((i) => i.mes === mes) ?? null, [timeline, mes]);

  // Sparks de 6 meses para KPIs secundários
  const last6 = useMemo(() => timeline.slice(-6), [timeline]);

  async function handleLogout() {
    await clienteApi.logout().catch(() => {});
    router.push("/cliente/login");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="font-display text-xl italic text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  if (err) {
    return (
      <main className="mx-auto max-w-md px-6 py-12">
        <p className="text-sm text-[var(--crimson)]">{err}</p>
      </main>
    );
  }

  const metaAds = breakdown?.meta_ads ?? [];
  const googleAds = breakdown?.google_ads ?? [];

  const kpis = snapMes
    ? [
        {
          label: "Investimento",
          value: fmtBRL(snapMes.investimento),
          spark: last6.map((p) => p.investimento ?? 0),
          varPct: null,
        },
        {
          label: "CPA",
          value: fmtBRL(snapMes.cpa),
          spark: last6.map((p) => p.cpa ?? 0),
          varPct: null,
        },
        {
          label: "Leads",
          value: fmtInt(snapMes.leads),
          spark: last6.map((p) => p.leads ?? 0),
          varPct: null,
        },
        {
          label: "Vendas",
          value: fmtInt(snapMes.vendas),
          spark: last6.map((p) => p.vendas ?? 0),
          varPct: null,
        },
      ]
    : [];

  return (
    <>
      {showSplash && cliente && (
        <WelcomeSplash
          nomeCliente={cliente.nome}
          highlight={highlight}
          mesLabel={mesLabel(mes)}
          onDismiss={() => setShowSplash(false)}
        />
      )}

      <main className="mx-auto max-w-6xl px-6 py-10">
        <header className="mb-12 flex items-start justify-between gap-4">
          <div className="flex items-center gap-3">
            {cliente?.logo_url && (
              // eslint-disable-next-line @next/next/no-img-element
              <img
                src={cliente.logo_url}
                alt={cliente.nome}
                className="h-9 w-9 rounded object-contain"
              />
            )}
            <div>
              <p className="font-display text-base text-[var(--ink)]">{cliente?.nome ?? "Cliente"}</p>
              <p className="eyebrow text-[10px] text-[var(--muted)]">
                {cliente?.setor ?? cliente?.categoria}
              </p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            {mesesDisponiveis.length > 0 && (
              <select
                aria-label="Mês"
                value={mes}
                onChange={(e) => setMes(e.target.value)}
                className="select font-display text-base"
              >
                {mesesDisponiveis.map((m) => (
                  <option key={m} value={m}>
                    {mesLabel(m)}
                  </option>
                ))}
              </select>
            )}
            <button
              onClick={handleLogout}
              className="rounded-full border border-[var(--rule-soft)] px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
            >
              Sair
            </button>
          </div>
        </header>

        {!snapMes ? (
          <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-12 text-center text-sm text-[var(--muted)]">
            Seus dados estão sendo processados. Volte em breve.
          </p>
        ) : (
          <HeroMonth
            mesLabel={mesLabel(mes)}
            faturamento={snapMes.faturamento}
            roas={snapMes.roas}
            varFaturamento={snapMes.faturamento_var_pct}
            varRoas={snapMes.roas_var_pct}
            timeline12m={timeline.map((p) => ({ mes: p.mes, faturamento: p.faturamento }))}
          />
        )}

        {kpis.length > 0 && <KpiRow kpis={kpis} />}

        {timeline.length >= 2 && <EvolutionChartHero timeline={timeline} />}

        <CreativeGallery criativos={metaAds} onSeeAll={() => setDrawerMeta(true)} />
        <CampaignBars campanhas={googleAds} onSeeAll={() => setDrawerGoogle(true)} />

        <footer className="mt-24 border-t border-[var(--rule-soft)] pt-6 text-center">
          <p className="eyebrow text-[10px] text-[var(--muted)]">
            Relatório gerado em {new Date().toLocaleDateString("pt-BR")}
          </p>
        </footer>
      </main>

      <DetailsDrawer
        open={drawerMeta}
        onClose={() => setDrawerMeta(false)}
        title={`Todos os criativos · Meta Ads · ${mesLabel(mes)}`}
      >
        <FullMetaTable ads={metaAds} />
      </DetailsDrawer>

      <DetailsDrawer
        open={drawerGoogle}
        onClose={() => setDrawerGoogle(false)}
        title={`Todas as campanhas · Google Ads · ${mesLabel(mes)}`}
      >
        <FullGoogleTable ads={googleAds} />
      </DetailsDrawer>
    </>
  );
}

// === Tabelas completas usadas dentro do Drawer ===

function FullMetaTable({ ads }: { ads: any[] }) {
  if (ads.length === 0) return <p className="text-xs text-[var(--muted)]">Sem dados.</p>;
  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 bg-[var(--paper)]">
        <tr className="border-b border-[var(--rule-soft)]">
          <th className="py-2 pr-3 text-left font-medium text-[var(--muted)]">Criativo</th>
          <th className="py-2 pr-3 text-left font-medium text-[var(--muted)]">Anúncio</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Invest.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Leads</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Conv.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Fat.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">ROAS</th>
          <th className="py-2 text-right font-medium text-[var(--muted)]">Impressões</th>
        </tr>
      </thead>
      <tbody>
        {ads.map((ad, i) => (
          <tr key={i} className="border-b border-[var(--rule-soft)]/40 hover:bg-[var(--paper-soft)]">
            <td className="py-2 pr-3">
              {ad.imagem_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img src={ad.imagem_url} alt={ad.nome} className="h-10 w-10 rounded object-cover" />
              ) : (
                <div className="h-10 w-10 rounded bg-[var(--paper-deep)]" />
              )}
            </td>
            <td className="py-2 pr-3 text-[var(--ink)]">{ad.nome}</td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.investimento == null ? "—" : ad.investimento.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })}
            </td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.leads ?? "—"}</td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.conversoes ?? "—"}</td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.faturamento == null ? "—" : ad.faturamento.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })}
            </td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.roas == null ? "—" : `${ad.roas.toFixed(2).replace(".", ",")}×`}
            </td>
            <td className="py-2 text-right font-mono-num text-[var(--ink)]">
              {ad.impressoes == null ? "—" : ad.impressoes.toLocaleString("pt-BR")}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function FullGoogleTable({ ads }: { ads: any[] }) {
  if (ads.length === 0) return <p className="text-xs text-[var(--muted)]">Sem dados.</p>;
  return (
    <table className="w-full text-xs">
      <thead className="sticky top-0 bg-[var(--paper)]">
        <tr className="border-b border-[var(--rule-soft)]">
          <th className="py-2 pr-3 text-left font-medium text-[var(--muted)]">Campanha</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Invest.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Conv.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">Fat.</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">CPA</th>
          <th className="py-2 pr-3 text-right font-medium text-[var(--muted)]">ROAS</th>
          <th className="py-2 text-right font-medium text-[var(--muted)]">Impressões</th>
        </tr>
      </thead>
      <tbody>
        {ads.map((ad, i) => (
          <tr key={i} className="border-b border-[var(--rule-soft)]/40 hover:bg-[var(--paper-soft)]">
            <td className="py-2 pr-3 text-[var(--ink)]">{ad.nome}</td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.investimento == null ? "—" : ad.investimento.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })}
            </td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.conversoes ?? "—"}</td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.faturamento == null ? "—" : ad.faturamento.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })}
            </td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.cpa == null ? "—" : ad.cpa.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 })}
            </td>
            <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
              {ad.roas == null ? "—" : `${ad.roas.toFixed(2).replace(".", ",")}×`}
            </td>
            <td className="py-2 text-right font-mono-num text-[var(--ink)]">
              {ad.impressoes == null ? "—" : ad.impressoes.toLocaleString("pt-BR")}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
