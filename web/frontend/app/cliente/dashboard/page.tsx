"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  ApiError,
  Breakdown,
  ClientePublic,
  TimelineItem,
  clienteApi,
} from "@/lib/api-cliente";

const NOMES_MES = ["Jan", "Fev", "Mar", "Abr", "Mai", "Jun", "Jul", "Ago", "Set", "Out", "Nov", "Dez"];

function mesLabel(mes: string): string {
  const [a, m] = mes.split("-");
  return `${NOMES_MES[parseInt(m) - 1]} ${a}`;
}
function fmtBRL(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}
function fmtNum(v: number | null | undefined, d = 2) {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { maximumFractionDigits: d });
}
function fmtPct(v: number | null | undefined) {
  if (v == null) return "—";
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(1)}%`;
}

export default function ClienteDashboardPage() {
  const router = useRouter();
  const [cliente, setCliente] = useState<ClientePublic | null>(null);
  const [timeline, setTimeline] = useState<TimelineItem[]>([]);
  const [mesesDisponiveis, setMesesDisponiveis] = useState<string[]>([]);
  const [mes, setMes] = useState<string>("");
  const [breakdown, setBreakdown] = useState<Breakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingBreakdown, setLoadingBreakdown] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [verTodosMeta, setVerTodosMeta] = useState(false);
  const [verTodosGoogle, setVerTodosGoogle] = useState(false);

  useEffect(() => {
    Promise.all([
      clienteApi.me(),
      clienteApi.timeline(12),
      clienteApi.mesesDisponiveis(),
    ])
      .then(([me, tl, md]) => {
        setCliente(me);
        setTimeline(tl.items);
        setMesesDisponiveis(md.meses);
        if (md.meses.length > 0) setMes(md.meses[0]);
      })
      .catch((e) => {
        if (e instanceof ApiError && e.status === 401) {
          router.push("/cliente/login?expired=1");
          return;
        }
        setErr(e instanceof Error ? e.message : "Erro ao carregar dados.");
      })
      .finally(() => setLoading(false));
  }, [router]);

  useEffect(() => {
    if (!mes) return;
    setLoadingBreakdown(true);
    clienteApi
      .breakdown(mes)
      .then(setBreakdown)
      .catch(() => setBreakdown(null))
      .finally(() => setLoadingBreakdown(false));
  }, [mes]);

  const snapMes = useMemo(
    () => timeline.find((i) => i.mes === mes) ?? null,
    [timeline, mes],
  );

  const chartData = useMemo(
    () =>
      timeline.map((i) => ({
        mes: mesLabel(i.mes),
        Faturamento: i.faturamento ?? 0,
        Investimento: i.investimento ?? 0,
        ROAS: i.roas ?? 0,
      })),
    [timeline],
  );

  async function handleLogout() {
    await clienteApi.logout().catch(() => {});
    router.push("/cliente/login");
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
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

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-8 flex items-start justify-between gap-4">
        <div className="flex items-center gap-3">
          {cliente?.logo_url && (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={cliente.logo_url}
              alt={cliente.nome}
              className="h-10 w-10 rounded object-contain"
            />
          )}
          <div>
            <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
              {cliente?.nome ?? "Cliente"}
            </h1>
            <p className="mt-1 text-xs text-[var(--muted)]">
              {cliente?.setor ?? cliente?.categoria}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          {mesesDisponiveis.length > 0 && (
            <>
              <label htmlFor="mes" className="text-xs text-[var(--muted)]">
                Mês:
              </label>
              <select
                id="mes"
                value={mes}
                onChange={(e) => setMes(e.target.value)}
                className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-1.5 text-xs text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
              >
                {mesesDisponiveis.map((m) => (
                  <option key={m} value={m}>
                    {mesLabel(m)}
                  </option>
                ))}
              </select>
            </>
          )}
          <button
            onClick={handleLogout}
            className="rounded-full border border-[var(--rule-soft)] px-3 py-1.5 text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
          >
            Sair
          </button>
        </div>
      </header>

      {/* KPIs */}
      <section className="mb-8">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">
          KPIs {mes && `· ${mesLabel(mes)}`}
        </p>
        {!snapMes ? (
          <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
            Seus dados ainda estão sendo processados. Volte em breve.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {[
              {
                label: "Faturamento",
                value: fmtBRL(snapMes.faturamento),
                var: snapMes.faturamento_var_pct,
              },
              { label: "Investimento", value: fmtBRL(snapMes.investimento), var: null },
              {
                label: "ROAS",
                value: snapMes.roas != null ? `${fmtNum(snapMes.roas)}×` : "—",
                var: snapMes.roas_var_pct,
              },
              { label: "CPA", value: fmtBRL(snapMes.cpa), var: null },
              {
                label: "Leads",
                value: snapMes.leads != null ? snapMes.leads.toLocaleString("pt-BR") : "—",
                var: null,
              },
              {
                label: "Vendas",
                value: snapMes.vendas != null ? snapMes.vendas.toLocaleString("pt-BR") : "—",
                var: null,
              },
            ].map((kpi) => (
              <div
                key={kpi.label}
                className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-3"
              >
                <p className="eyebrow mb-1 text-[10px] text-[var(--muted)]">{kpi.label}</p>
                <p className="font-mono-num text-lg font-medium text-[var(--ink)]">{kpi.value}</p>
                {kpi.var != null && (
                  <p
                    className={`font-mono-num text-[10px] ${kpi.var >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}
                  >
                    {fmtPct(kpi.var)} vs mês anterior
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Evolução */}
      {chartData.length > 1 && (
        <section className="mb-8">
          <p className="eyebrow mb-3 text-xs text-[var(--muted)]">
            Evolução · últimos {chartData.length} meses
          </p>
          <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="var(--rule-soft)" strokeDasharray="3 3" />
                <XAxis dataKey="mes" tick={{ fill: "var(--muted)", fontSize: 11 }} />
                <YAxis
                  yAxisId="left"
                  tick={{ fill: "var(--muted)", fontSize: 11 }}
                  tickFormatter={(v) => (v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v)}
                />
                <YAxis
                  yAxisId="right"
                  orientation="right"
                  tick={{ fill: "var(--muted)", fontSize: 11 }}
                />
                <Tooltip
                  contentStyle={{
                    background: "var(--paper)",
                    border: "1px solid var(--rule-soft)",
                    fontSize: 12,
                  }}
                  formatter={(value, name) => {
                    const v = typeof value === "number" ? value : 0;
                    if (name === "ROAS") return [`${v.toFixed(2)}×`, name as string];
                    return [fmtBRL(v), name as string];
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="Faturamento"
                  stroke="var(--forest)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
                <Line
                  yAxisId="left"
                  type="monotone"
                  dataKey="Investimento"
                  stroke="var(--amber)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
                <Line
                  yAxisId="right"
                  type="monotone"
                  dataKey="ROAS"
                  stroke="var(--crimson)"
                  strokeWidth={2}
                  dot={{ r: 3 }}
                />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Campanhas */}
      <section className="mb-8">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">
          Campanhas {mes && `· ${mesLabel(mes)}`}
        </p>
        {loadingBreakdown ? (
          <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
            Carregando…
          </p>
        ) : !breakdown || (metaAds.length === 0 && googleAds.length === 0) ? (
          <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
            Sem detalhamento de campanhas neste mês.
          </p>
        ) : (
          <div className="flex flex-col gap-5">
            {metaAds.length > 0 && (
              <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
                <p className="eyebrow mb-2 text-[10px] font-medium text-[var(--muted)]">
                  Meta Ads — top anúncios
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-[var(--rule-soft)]">
                        <th className="pb-1 pr-3 text-left font-medium text-[var(--muted)]">
                          Criativo
                        </th>
                        <th className="pb-1 pr-3 text-left font-medium text-[var(--muted)]">
                          Anúncio
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          Invest.
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          Leads
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          Conv.
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          Fat.
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          CPL/CPA
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          ROAS
                        </th>
                        <th className="pb-1 text-right font-medium text-[var(--muted)]">
                          Impressões
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {(verTodosMeta ? metaAds : metaAds.slice(0, 5)).map((ad, i) => (
                        <tr key={i} className="border-b border-[var(--rule-soft)]/40">
                          <td className="py-2 pr-3">
                            {ad.imagem_url ? (
                              // eslint-disable-next-line @next/next/no-img-element
                              <img
                                src={ad.imagem_url}
                                alt={ad.nome}
                                className="h-10 w-10 rounded object-cover"
                              />
                            ) : (
                              <div className="h-10 w-10 rounded bg-[var(--paper)]" />
                            )}
                          </td>
                          <td className="py-2 pr-3 font-medium text-[var(--ink)]">{ad.nome}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {fmtBRL(ad.investimento)}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {ad.leads ?? "—"}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {ad.conversoes ?? "—"}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {fmtBRL(ad.faturamento)}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {fmtBRL(ad.cpl ?? ad.cpa)}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {ad.roas != null ? `${fmtNum(ad.roas)}×` : "—"}
                          </td>
                          <td className="py-2 text-right font-mono-num text-[var(--ink)]">
                            {ad.impressoes != null
                              ? ad.impressoes.toLocaleString("pt-BR")
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {metaAds.length > 5 && (
                  <button
                    onClick={() => setVerTodosMeta((v) => !v)}
                    className="mt-2 text-[10px] text-[var(--forest)] hover:underline"
                  >
                    {verTodosMeta ? "Mostrar só top 5" : `Ver todos os ${metaAds.length}`}
                  </button>
                )}
              </div>
            )}

            {googleAds.length > 0 && (
              <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
                <p className="eyebrow mb-2 text-[10px] font-medium text-[var(--muted)]">
                  Google Ads — top campanhas
                </p>
                <div className="overflow-x-auto">
                  <table className="w-full text-xs">
                    <thead>
                      <tr className="border-b border-[var(--rule-soft)]">
                        <th className="pb-1 pr-3 text-left font-medium text-[var(--muted)]">
                          Campanha
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          Invest.
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          Conv.
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          Fat.
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          CPA
                        </th>
                        <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">
                          ROAS
                        </th>
                        <th className="pb-1 text-right font-medium text-[var(--muted)]">
                          Impressões
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {(verTodosGoogle ? googleAds : googleAds.slice(0, 5)).map((ad, i) => (
                        <tr key={i} className="border-b border-[var(--rule-soft)]/40">
                          <td className="py-2 pr-3 font-medium text-[var(--ink)]">{ad.nome}</td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {fmtBRL(ad.investimento)}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {ad.conversoes ?? "—"}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {fmtBRL(ad.faturamento)}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {fmtBRL(ad.cpa)}
                          </td>
                          <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">
                            {ad.roas != null ? `${fmtNum(ad.roas)}×` : "—"}
                          </td>
                          <td className="py-2 text-right font-mono-num text-[var(--ink)]">
                            {ad.impressoes != null
                              ? ad.impressoes.toLocaleString("pt-BR")
                              : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                {googleAds.length > 5 && (
                  <button
                    onClick={() => setVerTodosGoogle((v) => !v)}
                    className="mt-2 text-[10px] text-[var(--forest)] hover:underline"
                  >
                    {verTodosGoogle ? "Mostrar só top 5" : `Ver todas as ${googleAds.length}`}
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </section>
    </main>
  );
}
