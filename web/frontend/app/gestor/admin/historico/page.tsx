"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import GestorShell from "../../_shell";
import { gestorApi } from "@/lib/api-gestor";
import type { BackfillJobStatus, CoberturaResponse } from "@/lib/api-gestor";

function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]}/${ano.slice(2)}`;
}

function calcMesIntervalo(mesesAtras: number): { ini: string; fim: string } {
  const hoje = new Date();
  const fim = `${hoje.getFullYear()}-${String(hoje.getMonth() + 1).padStart(2, "0")}`;
  const d = new Date(hoje.getFullYear(), hoje.getMonth() - (mesesAtras - 1), 1);
  const ini = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}`;
  return { ini, fim };
}

export default function HistoricoAdminPage() {
  const [data, setData] = useState<CoberturaResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [mostrarInativos, setMostrarInativos] = useState(true);
  const [jobId, setJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<BackfillJobStatus | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const load = useCallback(() => {
    setLoading(true);
    setErro(null);
    gestorApi
      .cobertura()
      .then(setData)
      .catch((e: unknown) => setErro(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (!jobId) return;
    pollRef.current = setInterval(async () => {
      try {
        const status = await gestorApi.getBackfillJob(jobId);
        setJobStatus(status);
        if (status.status !== "running") {
          clearInterval(pollRef.current!);
          pollRef.current = null;
          if (status.status === "done") load();
        }
      } catch {
        clearInterval(pollRef.current!);
        pollRef.current = null;
      }
    }, 3000);
    return () => { if (pollRef.current) clearInterval(pollRef.current); };
  }, [jobId, load]);

  async function dispararBackfill(slug?: string, nome?: string) {
    const msg = slug
      ? `Iniciar backfill dos últimos 36 meses para "${nome}"?`
      : "Iniciar backfill completo dos últimos 36 meses para todos os clientes?";
    if (!confirm(msg)) return;
    const { ini, fim } = calcMesIntervalo(36);
    try {
      const res = await gestorApi.triggerBackfill({ mes_inicio: ini, mes_fim: fim, slug });
      setJobId(res.job_id);
      setJobStatus({
        job_id: res.job_id,
        status: "running",
        meses_total: res.meses,
        meses_concluidos: 0,
        erros: 0,
        pct: 0,
      });
    } catch (e: unknown) {
      setErro(e instanceof Error ? e.message : "Erro ao iniciar backfill");
    }
  }

  const meses24 = data?.meses.slice(-24) ?? [];
  const clientes = (data?.clientes ?? []).filter((c) => mostrarInativos || c.ativo);
  const rodando = jobStatus?.status === "running";

  return (
    <GestorShell>
      <main className="px-6 py-10">
        {/* Cabeçalho */}
        <div className="mb-8 flex items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-2xl font-medium tracking-tight text-[var(--ink)]">
              Base Histórica
            </h1>
            <p className="mt-1 text-sm text-[var(--muted)]">
              Cobertura de snapshots por cliente e mês
            </p>
          </div>
          <div className="flex items-center gap-3">
            <label className="flex cursor-pointer items-center gap-2 text-xs text-[var(--muted)]">
              <input
                type="checkbox"
                checked={mostrarInativos}
                onChange={(e) => setMostrarInativos(e.target.checked)}
                className="accent-[var(--forest)]"
              />
              Mostrar inativos
            </label>
            <button
              onClick={() => dispararBackfill()}
              disabled={rodando}
              className="rounded-lg border border-[var(--forest)] px-4 py-1.5 text-xs text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:opacity-40"
            >
              Backfill completo
            </button>
          </div>
        </div>

        {/* Barra de progresso */}
        {jobStatus && (
          <div className="mb-6 rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
            <div className="mb-2 flex items-center justify-between text-xs">
              <span className="text-[var(--ink)]">
                {jobStatus.status === "running"
                  ? "Backfill em andamento…"
                  : jobStatus.status === "done"
                  ? "Backfill concluído"
                  : "Backfill com erro"}
              </span>
              <span className="text-[var(--muted)]">
                {jobStatus.meses_concluidos} de {jobStatus.meses_total} meses
                {jobStatus.erros > 0 && ` · ${jobStatus.erros} erros`}
              </span>
            </div>
            <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
              <div
                className={`h-1.5 rounded-full transition-all ${
                  jobStatus.status === "error"
                    ? "bg-[var(--crimson)]"
                    : "bg-[var(--forest)]"
                }`}
                style={{ width: `${jobStatus.pct}%` }}
              />
            </div>
          </div>
        )}

        {erro && (
          <p className="mb-4 text-sm text-[var(--crimson)]">{erro}</p>
        )}

        {loading ? (
          <p className="text-sm text-[var(--muted)]">Carregando…</p>
        ) : !data ? null : (
          <div className="overflow-x-auto rounded-xl border border-[var(--rule-soft)]">
            <table className="min-w-full">
              <thead>
                <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                  <th className="sticky left-0 z-10 bg-[var(--paper-soft)] pb-2 pl-4 pr-6 pt-3 text-left text-[10px] font-normal uppercase tracking-widest text-[var(--muted)] whitespace-nowrap">
                    Cliente
                  </th>
                  {meses24.map((m) => (
                    <th
                      key={m}
                      className="pb-2 px-1 pt-3 text-center text-[10px] font-normal text-[var(--muted)] whitespace-nowrap"
                      style={{ minWidth: 38 }}
                    >
                      {mesLabel(m)}
                    </th>
                  ))}
                  <th className="pb-2 pl-2 pr-3 pt-3 w-8" />
                </tr>
              </thead>
              <tbody className="divide-y divide-[var(--rule-soft)]">
                {clientes.map((c) => {
                  const snaps = new Set(c.meses_com_snapshot);
                  const cobertura = meses24.filter((m) => snaps.has(m)).length;
                  return (
                    <tr key={c.id} className="group bg-[var(--paper)] hover:bg-[var(--paper-soft)]">
                      <td className="sticky left-0 z-10 bg-inherit py-2 pl-4 pr-6 whitespace-nowrap">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-medium text-[var(--ink)]">
                            {c.nome}
                          </span>
                          {!c.ativo && (
                            <span className="rounded border border-[var(--rule-soft)] bg-[var(--paper-deep)] px-1.5 py-0.5 text-[9px] uppercase tracking-wide text-[var(--muted)]">
                              inativo
                            </span>
                          )}
                          <span className="text-[10px] text-[var(--muted)]">
                            {cobertura}/{meses24.length}
                          </span>
                        </div>
                      </td>
                      {meses24.map((m) => (
                        <td key={m} className="px-1 py-2 text-center">
                          <span
                            className={`inline-block h-2 w-2 rounded-full ${
                              snaps.has(m)
                                ? "bg-[var(--forest)] opacity-70"
                                : "bg-[var(--paper-deep)]"
                            }`}
                          />
                        </td>
                      ))}
                      <td className="py-2 pl-2 pr-3">
                        <button
                          onClick={() => dispararBackfill(c.slug, c.nome)}
                          disabled={rodando}
                          title="Backfill deste cliente"
                          className="text-sm text-[var(--muted)] opacity-0 transition hover:text-[var(--forest)] group-hover:opacity-100 disabled:pointer-events-none"
                        >
                          ↺
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </main>
    </GestorShell>
  );
}
