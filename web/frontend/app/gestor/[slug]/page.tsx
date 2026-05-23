"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { gestorApi, JobInfo, ClienteGestor } from "@/lib/api-gestor";
import { mesUltimoFechado, deslocarMes } from "@/lib/mes-utils";

function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]} ${ano}`;
}

export default function ClienteReportPage({ params }: { params: { slug: string } }) {
  const { slug } = params;
  const [cliente, setCliente] = useState<ClienteGestor | null>(null);
  const [mes, setMes] = useState(mesUltimoFechado());
  const [activeJob, setActiveJob] = useState<JobInfo | null>(null);
  const [history, setHistory] = useState<JobInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [triggering, setTriggering] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

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

    return () => stopPolling();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

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

  const isRunning =
    activeJob?.status === "running" || activeJob?.status === "pending";

  const mesesDisponiveis = Array.from({ length: 12 }, (_, i) =>
    deslocarMes(mesUltimoFechado(), -i),
  );

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-xl px-6 py-16">
      <Link
        href="/gestor"
        className="mb-8 block text-xs text-[var(--muted)] hover:text-[var(--ink)] transition"
      >
        ← Seus clientes
      </Link>

      <h1 className="font-display mb-8 text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
        {cliente?.nome ?? slug}
      </h1>

      {/* Month selector */}
      <div className="mb-4">
        <p className="eyebrow mb-2 text-xs text-[var(--muted)]">Mês de referência</p>
        <select
          value={mes}
          onChange={(e) => setMes(e.target.value)}
          disabled={isRunning}
          className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
        >
          {mesesDisponiveis.map((m) => (
            <option key={m} value={m}>
              {mesLabel(m)}
            </option>
          ))}
        </select>
      </div>

      {/* Trigger button */}
      <button
        onClick={handleTrigger}
        disabled={isRunning || triggering}
        className={[
          "mb-6 w-full rounded-md border py-3 text-xs uppercase tracking-[0.18em] transition",
          isRunning || triggering
            ? "cursor-wait border-[var(--rule-soft)] text-[var(--muted)]"
            : "border-[var(--forest)] text-[var(--forest)] hover:bg-[var(--forest)] hover:text-[var(--paper)]",
        ].join(" ")}
      >
        {triggering ? "Disparando…" : isRunning ? "Gerando slides…" : "▶ Gerar report"}
      </button>

      {/* Active job status */}
      {activeJob && (
        <div className="mb-8 rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
          {activeJob.status === "running" || activeJob.status === "pending" ? (
            <div className="flex items-center gap-3">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-[var(--rule-soft)] border-t-[var(--forest)]" />
              <div>
                <p className="text-sm text-[var(--ink)]">Gerando slides…</p>
                <p className="text-xs text-[var(--muted)]">Pode levar 1–2 minutos</p>
              </div>
            </div>
          ) : activeJob.status === "done" ? (
            <div>
              <p className="mb-2 text-sm font-medium text-[var(--forest)]">Report gerado!</p>
              <a
                href={activeJob.slides_url ?? "#"}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs text-[var(--forest)] underline underline-offset-2"
              >
                → Abrir slides
              </a>
            </div>
          ) : (
            <p className="text-sm text-[var(--crimson)]">
              Erro: {activeJob.erro ?? "Falha desconhecida"}
            </p>
          )}
        </div>
      )}

      {erro && <p className="mb-6 text-sm text-[var(--crimson)]">{erro}</p>}

      {/* ClickUp info */}
      {cliente?.cup && (
        <div className="mb-8 rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
          <p className="eyebrow mb-3 text-xs text-[var(--muted)]">ClickUp</p>
          <dl className="grid grid-cols-2 gap-x-6 gap-y-2 text-xs">
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
              cliente.cup.motivo_cancelamento
                ? ["Motivo cancel.", cliente.cup.motivo_cancelamento]
                : null,
            ]
              .filter((r): r is [string, string | null] => r !== null && r[1] != null && r[1] !== "")
              .map(([label, value]) => (
                <div key={label} className="flex flex-col gap-0.5">
                  <dt className="text-[var(--muted)]">{label}</dt>
                  <dd className="font-medium text-[var(--ink)]">{value}</dd>
                </div>
              ))}
          </dl>
        </div>
      )}

      {/* History */}
      {history.filter((j) => j.status === "done" || j.status === "error").length > 0 && (
        <div>
          <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Reports anteriores</p>
          <ul className="flex flex-col gap-px border-t border-[var(--rule-soft)]">
            {history
              .filter((j) => j.status === "done" || j.status === "error")
              .map((j) => (
                <li
                  key={j.id}
                  className="flex items-center justify-between border-b border-[var(--rule-soft)] py-3"
                >
                  <span className="text-xs text-[var(--ink-soft)]">{mesLabel(j.mes)}</span>
                  {j.status === "done" && j.slides_url ? (
                    <a
                      href={j.slides_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-[var(--forest)] underline underline-offset-2"
                    >
                      → Abrir slides
                    </a>
                  ) : (
                    <span className="text-xs text-[var(--crimson)]">Erro</span>
                  )}
                </li>
              ))}
          </ul>
        </div>
      )}
    </main>
  );
}
