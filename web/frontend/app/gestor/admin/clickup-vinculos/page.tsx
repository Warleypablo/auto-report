"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { gestorApi } from "@/lib/api-gestor";

type Sugestao = {
  task_id: string;
  nome: string;
  responsavel: string | null;
  score: number;
};

type ClienteSemVinculo = {
  cliente_id: string;
  cliente_nome: string;
  cliente_categoria: string;
  cliente_gestor: string | null;
  sugestoes: Sugestao[];
};

type SearchResult = {
  task_id: string;
  nome: string;
  responsavel: string | null;
  status: string | null;
  vinculado_a: { id: string; nome: string } | null;
};

export default function ClickupVinculosPage() {
  const [items, setItems] = useState<ClienteSemVinculo[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  // Por cliente: estado da busca manual e vinculação em andamento
  const [busca, setBusca] = useState<Record<string, string>>({});
  const [resultados, setResultados] = useState<Record<string, SearchResult[]>>({});
  const [buscando, setBuscando] = useState<Record<string, boolean>>({});
  const [vinculando, setVinculando] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<Record<string, { ok: boolean; msg: string }>>({});

  // Estado do automatch (preview + confirmação)
  const [automatching, setAutomatching] = useState(false);
  const [automatchPreview, setAutomatchPreview] = useState<{
    matches: Array<{ cliente_id: string; cliente_nome: string; task_id: string; cup_nome: string }>;
    ambiguos: Array<{ cliente_id: string; cliente_nome: string; candidatos: Array<{ task_id: string; nome: string }> }>;
    stats: { total_clientes_sem_vinculo: number; matches_propostos: number; ambiguos: number; sem_candidato: number };
  } | null>(null);
  const [automatchErro, setAutomatchErro] = useState<string | null>(null);

  // Estado da sincronização de gestores
  const [syncing, setSyncing] = useState(false);
  const [syncResult, setSyncResult] = useState<{
    atualizados: number;
    sem_vinculo: number;
    sem_contrato_performance: number;
    sem_responsavel_no_contrato: number;
  } | null>(null);
  const [syncErro, setSyncErro] = useState<string | null>(null);

  async function syncGestores() {
    if (!confirm("Atribuir gestores do ClickUp aos clientes do sistema?\n\nIsso vai sobrescrever clientes.gestor com o responsavel do contrato 'Performance' (cup_contratos) para todos os clientes vinculados.")) return;
    setSyncing(true);
    setSyncResult(null);
    setSyncErro(null);
    try {
      const r = await gestorApi.syncGestoresFromClickup();
      setSyncResult(r);
    } catch (e) {
      setSyncErro(e instanceof Error ? e.message : "Erro ao sincronizar");
    } finally {
      setSyncing(false);
    }
  }

  async function rodarAutomatchDryRun() {
    setAutomatchErro(null);
    setAutomatching(true);
    try {
      const r = await gestorApi.automatchClickup(true);
      setAutomatchPreview({ matches: r.matches, ambiguos: r.ambiguos, stats: r.stats });
    } catch (e) {
      setAutomatchErro(e instanceof Error ? e.message : "Erro no preview");
    } finally {
      setAutomatching(false);
    }
  }

  async function aplicarAutomatch() {
    setAutomatchErro(null);
    setAutomatching(true);
    try {
      const r = await gestorApi.automatchClickup(false);
      setAutomatchPreview(null);
      // Recarrega a lista — os matches aplicados devem sumir
      load();
      alert(`${r.aplicados} clientes vinculados automaticamente.`);
    } catch (e) {
      setAutomatchErro(e instanceof Error ? e.message : "Erro ao aplicar");
    } finally {
      setAutomatching(false);
    }
  }

  function load() {
    setLoading(true);
    setErro(null);
    gestorApi
      .listClientesSemVinculoCup()
      .then(({ items }) => setItems(items))
      .catch((e) => setErro(e instanceof Error ? e.message : "Erro ao carregar"))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function executarBusca(clienteId: string, q: string) {
    setBusca((b) => ({ ...b, [clienteId]: q }));
    if (q.trim().length < 2) {
      setResultados((r) => ({ ...r, [clienteId]: [] }));
      return;
    }
    setBuscando((b) => ({ ...b, [clienteId]: true }));
    try {
      const { items } = await gestorApi.searchClickupTasks(q);
      setResultados((r) => ({ ...r, [clienteId]: items }));
    } catch (e) {
      // Erros de busca não bloqueiam a UI, só somem
    } finally {
      setBuscando((b) => ({ ...b, [clienteId]: false }));
    }
  }

  async function vincular(clienteId: string, taskId: string, taskNome: string) {
    setVinculando(clienteId);
    setFeedback((f) => ({ ...f, [clienteId]: { ok: true, msg: "" } }));
    try {
      await gestorApi.vincularCupTask(clienteId, taskId);
      setFeedback((f) => ({ ...f, [clienteId]: { ok: true, msg: `Vinculado a "${taskNome}"` } }));
      // Remove o cliente da lista (já foi vinculado)
      setTimeout(() => {
        setItems((prev) => prev.filter((it) => it.cliente_id !== clienteId));
      }, 1200);
    } catch (e) {
      setFeedback((f) => ({
        ...f,
        [clienteId]: { ok: false, msg: e instanceof Error ? e.message : "Erro ao vincular" },
      }));
    } finally {
      setVinculando(null);
    }
  }

  const stats = useMemo(() => {
    const total = items.length;
    const comSugestaoBoa = items.filter((it) => it.sugestoes.some((s) => s.score >= 0.7)).length;
    return { total, comSugestaoBoa };
  }, [items]);

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-4xl px-6 py-16">
      <Link href="/gestor" className="mb-8 block text-xs text-[var(--muted)] hover:text-[var(--ink)] transition">
        ← Dashboard
      </Link>

      <div className="mb-2 flex items-center justify-between">
        <h1 className="font-display text-3xl font-medium tracking-tight text-[var(--ink)]">
          Vínculos ClickUp
        </h1>
        <button
          onClick={load}
          className="text-xs text-[var(--muted)] hover:text-[var(--ink)] transition"
        >
          ↻ Recarregar
        </button>
      </div>
      <p className="mb-8 text-sm text-[var(--muted)]">
        {stats.total} cliente{stats.total !== 1 ? "s" : ""} sem cup_task_id ·{" "}
        {stats.comSugestaoBoa} com sugestão automática boa
      </p>

      {erro && <p className="mb-4 text-sm text-[var(--crimson)]">{erro}</p>}

      {/* Match automático em lote */}
      {items.length > 0 && (
        <section className="mb-6 rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
          <div className="flex items-center justify-between gap-4">
            <div className="flex-1">
              <p className="text-sm font-medium text-[var(--ink)]">Match automático em lote</p>
              <p className="text-xs text-[var(--muted)]">
                Normaliza nomes (remove sufixos como LTDA, ME, S.A., acentos e pontuação) e vincula
                apenas onde há candidato único no ClickUp.
              </p>
            </div>
            <button
              onClick={rodarAutomatchDryRun}
              disabled={automatching}
              className="rounded-full border border-[var(--forest)] px-4 py-1.5 text-xs uppercase tracking-[0.18em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:opacity-50"
            >
              {automatching ? "Processando…" : "Visualizar match"}
            </button>
          </div>
          {automatchErro && <p className="mt-3 text-xs text-[var(--crimson)]">{automatchErro}</p>}
        </section>
      )}

      {/* Sincronizar gestores do contrato Performance */}
      <section className="mb-6 rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
        <div className="flex items-center justify-between gap-4">
          <div className="flex-1">
            <p className="text-sm font-medium text-[var(--ink)]">Sincronizar gestores do ClickUp</p>
            <p className="text-xs text-[var(--muted)]">
              Atribui clientes.gestor = responsavel do contrato cujo produto contém &ldquo;Performance&rdquo;
              (cup_contratos), para todos os clientes vinculados.
            </p>
          </div>
          <button
            onClick={syncGestores}
            disabled={syncing}
            className="rounded-full border border-[var(--forest)] px-4 py-1.5 text-xs uppercase tracking-[0.18em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:opacity-50"
          >
            {syncing ? "Sincronizando…" : "Sincronizar"}
          </button>
        </div>
        {syncResult && (
          <p className="mt-3 text-xs text-[var(--ink-soft)]">
            <span className="text-[var(--forest)]">{syncResult.atualizados} atualizados</span>
            {" · "}
            {syncResult.sem_vinculo} sem cup_task_id
            {" · "}
            {syncResult.sem_contrato_performance} sem contrato Performance
            {" · "}
            {syncResult.sem_responsavel_no_contrato} sem responsável no contrato
          </p>
        )}
        {syncErro && <p className="mt-3 text-xs text-[var(--crimson)]">{syncErro}</p>}
      </section>

      {/* Modal de preview do automatch */}
      {automatchPreview && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-6">
          <div className="max-h-[80vh] w-full max-w-2xl overflow-hidden rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] shadow-xl">
            <div className="border-b border-[var(--rule-soft)] px-5 py-3">
              <h2 className="font-display text-lg font-medium text-[var(--ink)]">
                Preview do match automático
              </h2>
              <p className="text-xs text-[var(--muted)]">
                {automatchPreview.stats.matches_propostos} ser{automatchPreview.stats.matches_propostos !== 1 ? "ão" : "á"} vinculado{automatchPreview.stats.matches_propostos !== 1 ? "s" : ""} · {automatchPreview.stats.ambiguos} ambíguo{automatchPreview.stats.ambiguos !== 1 ? "s" : ""} (precisam vínculo manual) · {automatchPreview.stats.sem_candidato} sem candidato
              </p>
            </div>
            <div className="max-h-[60vh] overflow-y-auto px-5 py-4">
              {automatchPreview.matches.length > 0 ? (
                <>
                  <p className="eyebrow mb-2 text-xs text-[var(--forest)]">Matches a aplicar</p>
                  <ul className="mb-4 flex flex-col gap-1">
                    {automatchPreview.matches.map((m) => (
                      <li key={m.cliente_id} className="flex items-baseline justify-between gap-3 text-xs">
                        <span className="font-medium text-[var(--ink)]">{m.cliente_nome}</span>
                        <span className="text-[var(--muted)]">→</span>
                        <span className="flex-1 text-right text-[var(--ink-soft)]">{m.cup_nome}</span>
                      </li>
                    ))}
                  </ul>
                </>
              ) : (
                <p className="text-xs text-[var(--muted)]">Nenhum match automático encontrado.</p>
              )}
              {automatchPreview.ambiguos.length > 0 && (
                <>
                  <p className="eyebrow mb-2 mt-4 text-xs text-[var(--amber)]">Ambíguos (não vinculados)</p>
                  <ul className="flex flex-col gap-1">
                    {automatchPreview.ambiguos.map((a) => (
                      <li key={a.cliente_id} className="text-xs">
                        <span className="font-medium text-[var(--ink)]">{a.cliente_nome}</span>
                        <span className="ml-2 text-[var(--muted)]">
                          ({a.candidatos.length} candidatos: {a.candidatos.map((c) => c.nome).join(", ")})
                        </span>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </div>
            <div className="flex items-center justify-end gap-2 border-t border-[var(--rule-soft)] px-5 py-3">
              <button
                onClick={() => setAutomatchPreview(null)}
                disabled={automatching}
                className="rounded-full px-4 py-1.5 text-xs uppercase tracking-[0.18em] text-[var(--muted)] hover:text-[var(--ink)] disabled:opacity-50"
              >
                Cancelar
              </button>
              <button
                onClick={aplicarAutomatch}
                disabled={automatching || automatchPreview.matches.length === 0}
                className="rounded-full border border-[var(--forest)] bg-[var(--forest)] px-4 py-1.5 text-xs uppercase tracking-[0.18em] text-[var(--paper)] transition hover:opacity-90 disabled:opacity-50"
              >
                {automatching ? "Aplicando…" : `Aplicar ${automatchPreview.matches.length} vínculo${automatchPreview.matches.length !== 1 ? "s" : ""}`}
              </button>
            </div>
          </div>
        </div>
      )}

      {items.length === 0 ? (
        <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6 text-center text-sm text-[var(--muted)]">
          Todos os clientes ativos estão vinculados ao ClickUp. ✓
        </p>
      ) : (
        <ul className="flex flex-col gap-3">
          {items.map((it) => {
            const fb = feedback[it.cliente_id];
            const sugTop = it.sugestoes.filter((s) => s.score >= 0.5);
            const searchQ = busca[it.cliente_id] ?? "";
            const searchRes = resultados[it.cliente_id] ?? [];

            return (
              <li
                key={it.cliente_id}
                className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4"
              >
                <div className="mb-3 flex items-baseline justify-between">
                  <div>
                    <p className="text-sm font-medium text-[var(--ink)]">{it.cliente_nome}</p>
                    <p className="text-xs text-[var(--muted)]">
                      {it.cliente_categoria}
                      {it.cliente_gestor && <> · gestor: {it.cliente_gestor}</>}
                    </p>
                  </div>
                  {fb && (
                    <span className={`text-xs ${fb.ok ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                      {fb.msg}
                    </span>
                  )}
                </div>

                {/* Sugestões automáticas */}
                {sugTop.length > 0 && (
                  <div className="mb-3">
                    <p className="eyebrow mb-1 text-[10px] text-[var(--muted)]">Sugestões automáticas</p>
                    <ul className="flex flex-col gap-1">
                      {sugTop.map((s) => (
                        <li key={s.task_id} className="flex items-center justify-between gap-3 text-xs">
                          <span className="flex-1 text-[var(--ink-soft)]">
                            {s.nome}
                            {s.responsavel && (
                              <span className="ml-2 text-[var(--muted)]">↳ {s.responsavel}</span>
                            )}
                            <span className="ml-2 text-[10px] text-[var(--muted)]">
                              ({Math.round(s.score * 100)}% match)
                            </span>
                          </span>
                          <button
                            onClick={() => vincular(it.cliente_id, s.task_id, s.nome)}
                            disabled={vinculando === it.cliente_id}
                            className="rounded-full border border-[var(--forest)] px-3 py-0.5 text-[10px] uppercase tracking-[0.15em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:opacity-50"
                          >
                            Vincular
                          </button>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}

                {/* Busca manual */}
                <div>
                  <p className="eyebrow mb-1 text-[10px] text-[var(--muted)]">Buscar manualmente no ClickUp</p>
                  <input
                    type="text"
                    placeholder="digite o nome..."
                    value={searchQ}
                    onChange={(e) => executarBusca(it.cliente_id, e.target.value)}
                    className="w-full rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-1.5 text-xs text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
                  />
                  {buscando[it.cliente_id] && (
                    <p className="mt-1 text-[10px] text-[var(--muted)]">buscando…</p>
                  )}
                  {searchRes.length > 0 && (
                    <ul className="mt-1 flex flex-col gap-1">
                      {searchRes.map((r) => (
                        <li key={r.task_id} className="flex items-center justify-between gap-3 rounded-sm border border-[var(--rule-soft)] bg-[var(--paper)] px-2 py-1 text-xs">
                          <span className="flex-1 text-[var(--ink-soft)]">
                            {r.nome}
                            {r.responsavel && (
                              <span className="ml-2 text-[var(--muted)]">↳ {r.responsavel}</span>
                            )}
                            {r.vinculado_a && (
                              <span className="ml-2 text-[10px] text-[var(--amber)]">
                                já vinculado a {r.vinculado_a.nome}
                              </span>
                            )}
                          </span>
                          <button
                            onClick={() => vincular(it.cliente_id, r.task_id, r.nome)}
                            disabled={vinculando === it.cliente_id || !!r.vinculado_a}
                            className="rounded-full border border-[var(--forest)] px-3 py-0.5 text-[10px] uppercase tracking-[0.15em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:opacity-30"
                          >
                            Vincular
                          </button>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      )}
    </main>
  );
}
