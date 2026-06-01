"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import Link from "next/link";
import {
  gestorApi,
  JobInfo,
  ClienteGestor,
  MetricasBreakdown,
  MetricasTimeline,
  TimelineItem,
} from "@/lib/api-gestor";
import { mesUltimoFechado, deslocarMes } from "@/lib/mes-utils";
import {
  LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from "recharts";
import PerformanceLeaderboard from "@/components/PerformanceLeaderboard";

function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]} ${ano}`;
}
function fmtBRL(v: number | null | undefined) {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}
function fmtNum(v: number | null | undefined, decimals = 2) {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { maximumFractionDigits: decimals });
}
function fmtPct(v: number | null | undefined) {
  if (v == null) return "—";
  const s = v > 0 ? "+" : "";
  return `${s}${v.toFixed(1)}%`;
}

export default function ClienteReportPage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [cliente, setCliente] = useState<ClienteGestor | null>(null);
  const [mes, setMes] = useState(mesUltimoFechado());
  const [timeline, setTimeline] = useState<MetricasTimeline | null>(null);
  const [breakdown, setBreakdown] = useState<MetricasBreakdown | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(true);
  const [activeJob, setActiveJob] = useState<JobInfo | null>(null);
  const [history, setHistory] = useState<JobInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Carga inicial: cliente + jobs + timeline (12 meses)
  useEffect(() => {
    Promise.all([gestorApi.clientes(), gestorApi.listJobs(slug)])
      .then(([{ items }, jobs]) => {
        const c = items.find((i) => i.slug === slug) ?? null;
        if (!c) setErro("Cliente não encontrado ou sem acesso");
        setCliente(c);
        setHistory(jobs);
        const running = jobs.find((j) => j.status === "running" || j.status === "pending");
        if (running) startPolling(running.id);
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));

    gestorApi.metricasTimeline(slug, 12)
      .then((tl) => {
        setTimeline(tl);
        // Se houver dados, ajusta o mês selecionado pro mais recente que tem snapshot
        if (tl.items.length > 0) {
          setMes(tl.items[tl.items.length - 1].mes);
        }
      })
      .catch(console.error);

    return () => stopPolling();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  // Carrega breakdown do mês selecionado
  useEffect(() => {
    setLoadingDetail(true);
    gestorApi.metricasBreakdown(slug, mes)
      .then(setBreakdown)
      .catch(() => setBreakdown(null))
      .finally(() => setLoadingDetail(false));
  }, [slug, mes]);

  function startPolling(jobId: string) {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const job = await gestorApi.getJob(jobId);
        setActiveJob(job);
        if (job.status === "done" || job.status === "error") {
          stopPolling();
          setHistory((prev) => {
            const idx = prev.findIndex((j) => j.id === jobId);
            if (idx >= 0) {
              const next = [...prev];
              next[idx] = job;
              return next;
            }
            return [job, ...prev];
          });
        }
      } catch {
        stopPolling();
      }
    }, 2000);
  }

  function stopPolling() {
    if (pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
  }

  async function handleTrigger() {
    setErro(null);
    setTriggering(true);
    try {
      const { job_id } = await gestorApi.triggerReport(slug, mes);
      const initialJob: JobInfo = {
        id: job_id,
        mes,
        frequencia: "MENSAL",
        status: "pending",
        slides_url: null,
        erro: null,
        created_at: new Date().toISOString(),
        finished_at: null,
        cliente_slug: slug,
        cliente_nome: cliente?.nome ?? slug,
      };
      setActiveJob(initialJob);
      setHistory((prev) => [initialJob, ...prev]);
      startPolling(job_id);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao disparar report");
    } finally {
      setTriggering(false);
    }
  }

  const isRunning = activeJob?.status === "running" || activeJob?.status === "pending";

  // Snapshot do mês selecionado (pra cards KPI)
  const snapMes: TimelineItem | null = useMemo(() => {
    if (!timeline) return null;
    return timeline.items.find((i) => i.mes === mes) ?? null;
  }, [timeline, mes]);

  // Opções do seletor: meses com snapshots + fallback de 12 meses retroativos
  const mesOpcoes = useMemo(() => {
    const fromSnaps = (timeline?.items ?? []).map((i) => i.mes);
    const fallback = Array.from({ length: 12 }, (_, i) => deslocarMes(mesUltimoFechado(), -i));
    const merged = Array.from(new Set([...fromSnaps, ...fallback])).sort().reverse();
    return merged;
  }, [timeline]);

  // Dados pro gráfico de evolução
  const chartData = useMemo(() => {
    if (!timeline) return [];
    return timeline.items.map((i) => ({
      mes: mesLabel(i.mes),
      Faturamento: i.faturamento ?? 0,
      Investimento: i.investimento ?? 0,
      ROAS: i.roas ?? 0,
    }));
  }, [timeline]);

  const metaAds = breakdown?.meta_ads ?? [];
  const googleAds = breakdown?.google_ads ?? [];

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <Link href="/gestor" className="mb-6 block text-xs text-[var(--muted)] hover:text-[var(--ink)] transition">
        ← Seus clientes
      </Link>

      <div className="mb-8 flex items-baseline justify-between gap-4">
        <div>
          <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
            {cliente?.nome ?? slug}
          </h1>
          <p className="mt-1 text-xs text-[var(--muted)]">
            {cliente?.categoria}
            {cliente?.gestor && <> · gestor: {cliente.gestor}</>}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label htmlFor="mes-ref" className="text-xs text-[var(--muted)]">Mês:</label>
          <select
            id="mes-ref"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            disabled={isRunning}
            className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-1.5 text-xs text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          >
            {mesOpcoes.map((m) => (
              <option key={m} value={m}>{mesLabel(m)}</option>
            ))}
          </select>
        </div>
      </div>

      {/* Seção: Gerar report */}
      <section className="mb-8 rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
        <div className="flex items-center justify-between gap-4">
          <div>
            <p className="text-sm font-medium text-[var(--ink)]">Gerar report do mês selecionado</p>
            <p className="text-xs text-[var(--muted)]">Cria slides no Google Drive — 1 a 2 minutos</p>
          </div>
          <button
            onClick={handleTrigger}
            disabled={isRunning || triggering}
            className={[
              "rounded-full border px-5 py-2 text-xs uppercase tracking-[0.18em] transition",
              isRunning || triggering
                ? "cursor-wait border-[var(--rule-soft)] text-[var(--muted)]"
                : "border-[var(--forest)] text-[var(--forest)] hover:bg-[var(--forest)] hover:text-[var(--paper)]",
            ].join(" ")}
          >
            {triggering ? "Disparando…" : isRunning ? "Gerando…" : "▶ Gerar report"}
          </button>
        </div>

        {activeJob && (
          <div className="mt-3 rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] p-3">
            {isRunning ? (
              <div className="flex items-center gap-3">
                <div className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--rule-soft)] border-t-[var(--forest)]" />
                <p className="text-xs text-[var(--ink-soft)]">Gerando slides…</p>
              </div>
            ) : activeJob.status === "done" ? (
              <div className="flex items-center justify-between">
                <p className="text-xs font-medium text-[var(--forest)]">Report gerado!</p>
                <a href={activeJob.slides_url ?? "#"} target="_blank" rel="noopener noreferrer" className="text-xs text-[var(--forest)] underline underline-offset-2">
                  → Abrir slides
                </a>
              </div>
            ) : (
              <p className="text-xs text-[var(--crimson)]">Erro: {activeJob.erro ?? "Falha desconhecida"}</p>
            )}
          </div>
        )}
        {erro && <p className="mt-3 text-xs text-[var(--crimson)]">{erro}</p>}
      </section>

      {/* KPIs do mês */}
      <section className="mb-8">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">KPIs · {mesLabel(mes)}</p>
        {!snapMes ? (
          <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-xs text-[var(--muted)]">
            Sem snapshot para este mês. Gere o report ou aguarde o ETL.
          </p>
        ) : (
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
            {[
              { label: "Faturamento", value: fmtBRL(snapMes.faturamento), var: snapMes.faturamento_var_pct },
              { label: "Investimento", value: fmtBRL(snapMes.investimento), var: null },
              { label: "ROAS", value: snapMes.roas != null ? `${fmtNum(snapMes.roas)}×` : "—", var: snapMes.roas_var_pct },
              { label: "CPA", value: fmtBRL(snapMes.cpa), var: null },
              { label: "Leads", value: snapMes.leads != null ? snapMes.leads.toLocaleString("pt-BR") : "—", var: null },
              { label: "Vendas", value: snapMes.vendas != null ? snapMes.vendas.toLocaleString("pt-BR") : "—", var: null },
            ].map((kpi) => (
              <div key={kpi.label} className="kpi-turbo relative overflow-hidden rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-3">
                <p className="eyebrow mb-1 text-[10px] text-[var(--muted)]">{kpi.label}</p>
                <p className="font-mono-num text-lg font-medium text-[var(--ink)]">{kpi.value}</p>
                {kpi.var != null && (
                  <p className={`font-mono-num text-[10px] ${kpi.var >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                    {fmtPct(kpi.var)} vs mês anterior
                  </p>
                )}
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Evolução histórica */}
      {chartData.length > 1 && (
        <section className="mb-8">
          <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Evolução · últimos {chartData.length} meses</p>
          <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
            <ResponsiveContainer width="100%" height={260}>
              <LineChart data={chartData}>
                <CartesianGrid stroke="var(--rule-soft)" strokeDasharray="3 3" />
                <XAxis dataKey="mes" tick={{ fill: "var(--muted)", fontSize: 11 }} />
                <YAxis yAxisId="left" tick={{ fill: "var(--muted)", fontSize: 11 }} tickFormatter={(v) => v >= 1000 ? `${(v / 1000).toFixed(0)}k` : v} />
                <YAxis yAxisId="right" orientation="right" tick={{ fill: "var(--muted)", fontSize: 11 }} />
                <Tooltip
                  contentStyle={{ background: "var(--paper)", border: "1px solid var(--rule-soft)", fontSize: 12 }}
                  formatter={(value, name) => {
                    const v = typeof value === "number" ? value : 0;
                    if (name === "ROAS") return [`${v.toFixed(2)}×`, name as string];
                    return [fmtBRL(v), name as string];
                  }}
                />
                <Legend wrapperStyle={{ fontSize: 11 }} />
                <Line yAxisId="left" type="monotone" dataKey="Faturamento" stroke="var(--forest)" strokeWidth={2} dot={{ r: 3 }} />
                <Line yAxisId="left" type="monotone" dataKey="Investimento" stroke="var(--amber)" strokeWidth={2} dot={{ r: 3 }} />
                <Line yAxisId="right" type="monotone" dataKey="ROAS" stroke="var(--crimson)" strokeWidth={2} dot={{ r: 3 }} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </section>
      )}

      {/* Breakdown de campanhas */}
      <section className="mb-8">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Campanhas · {mesLabel(mes)}</p>
        <PerformanceLeaderboard
          metaAds={metaAds}
          googleAds={googleAds}
          loading={loadingDetail}
        />
      </section>

      {/* ClickUp info */}
      {cliente?.cup && (
        <section className="mb-8 rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
          <p className="eyebrow mb-3 text-xs text-[var(--muted)]">ClickUp</p>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs sm:grid-cols-3">
            {[
              ["Status", cliente.cup.status],
              ["Status conta", cliente.cup.status_conta],
              ["Squad", cliente.cup.squad],
              ["Responsável", cliente.cup.responsavel],
              ["Vendedor", cliente.cup.vendedor],
              ["Segmento", cliente.cup.segmento],
              ["Cluster", cliente.cup.cluster],
              ["Serviço", cliente.cup.contrato_servico],
              ["Plano", cliente.cup.contrato_plano],
              ["Valor recorrente", cliente.cup.contrato_valor_recorrente != null
                ? `R$ ${cliente.cup.contrato_valor_recorrente.toLocaleString("pt-BR")}`
                : null],
              ["Status contrato", cliente.cup.contrato_status],
              cliente.cup.motivo_cancelamento ? ["Motivo cancel.", cliente.cup.motivo_cancelamento] : null,
            ]
              .filter((r): r is [string, string | null] => r !== null && r[1] != null && r[1] !== "")
              .map(([label, value]) => (
                <div key={label} className="flex flex-col gap-0.5">
                  <dt className="text-[var(--muted)]">{label}</dt>
                  <dd className="font-medium text-[var(--ink)]">{value}</dd>
                </div>
              ))}
          </dl>
        </section>
      )}

      {/* Histórico de reports */}
      {history.filter((j) => j.status === "done" || j.status === "error").length > 0 && (
        <section>
          <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Reports anteriores</p>
          <ul className="flex flex-col gap-px border-t border-[var(--rule-soft)]">
            {history
              .filter((j) => j.status === "done" || j.status === "error")
              .map((j) => (
                <li key={j.id} className="flex items-center justify-between border-b border-[var(--rule-soft)] py-2">
                  <span className="text-xs text-[var(--ink-soft)]">{mesLabel(j.mes)}</span>
                  {j.status === "done" && j.slides_url ? (
                    <a href={j.slides_url} target="_blank" rel="noopener noreferrer" className="text-xs text-[var(--forest)] underline underline-offset-2">
                      → Abrir slides
                    </a>
                  ) : (
                    <span className="text-xs text-[var(--crimson)]">Erro</span>
                  )}
                </li>
              ))}
          </ul>
        </section>
      )}
    </main>
  );
}
