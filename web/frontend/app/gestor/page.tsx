"use client";

import { useEffect, useMemo, useState } from "react";
import {
  gestorApi,
  ClienteGestor,
  ClienteCreateData,
  ClienteEditData,
  ClienteMetricas,
  MetricasDashboard,
  MetricasBreakdown,
  GestorCadastrado,
  UsuarioInfo,
  JobInfo,
} from "@/lib/api-gestor";
import Link from "next/link";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  Legend,
  Cell,
} from "recharts";

type Tab = "reportes" | "dashboard" | "configuracoes";
type ReportesTab = "reportes-clientes" | "reportes-meus";
type ConfigTab = "config-clientes" | "config-gestores";

const REPORTES_SUB_TABS: { id: ReportesTab; label: string }[] = [
  { id: "reportes-clientes", label: "Clientes" },
  { id: "reportes-meus",     label: "Meus reports" },
];

const CONFIG_SUB_TABS: { id: ConfigTab; label: string }[] = [
  { id: "config-clientes", label: "Clientes" },
  { id: "config-gestores", label: "Gestores" },
];

// ── Formatters ────────────────────────────────────────────────────────────────
function fmtBRL(v: number | null): string {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });
}
function fmtNum(v: number | null, decimals = 2): string {
  if (v == null) return "—";
  return v.toLocaleString("pt-BR", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
}
function fmtPct(v: number | null): string {
  if (v == null) return "—";
  const sign = v >= 0 ? "+" : "";
  return `${sign}${(v * 100).toFixed(1)}%`;
}
function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]} ${ano}`;
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }: { status: JobInfo["status"] }) {
  const map: Record<JobInfo["status"], { label: string; cls: string }> = {
    done:    { label: "Concluído", cls: "text-[var(--forest)]" },
    error:   { label: "Erro",      cls: "text-[var(--crimson)]" },
    running: { label: "Gerando…",  cls: "text-[var(--amber)]" },
    pending: { label: "Na fila",   cls: "text-[var(--muted)]" },
  };
  const { label, cls } = map[status];
  return <span className={`text-xs ${cls}`}>{label}</span>;
}

// ── Sidebar ───────────────────────────────────────────────────────────────────
const NAV_ITEMS: { id: Tab; label: string; icon: string }[] = [
  { id: "dashboard",     label: "Dashboard",    icon: "◉" },
  { id: "reportes",      label: "Reportes",     icon: "◈" },
  { id: "configuracoes", label: "Configurações", icon: "◎" },
];

function Sidebar({
  tab, setTab, reportesTab, setReportesTab, configTab, setConfigTab, user, onLogout,
}: {
  tab: Tab; setTab: (t: Tab) => void;
  reportesTab: ReportesTab; setReportesTab: (t: ReportesTab) => void;
  configTab: ConfigTab; setConfigTab: (t: ConfigTab) => void;
  user: UsuarioInfo | null; onLogout: () => void;
}) {
  return (
    <aside className="flex h-screen w-56 flex-shrink-0 flex-col border-r border-[var(--rule-soft)] bg-[var(--paper-soft)]">
      <div className="border-b border-[var(--rule-soft)] px-5 py-5">
        <p className="font-display text-lg font-medium leading-tight text-[var(--ink)]">Painel</p>
        <p className="text-xs text-[var(--muted)]">Gestores</p>
      </div>
      <nav className="flex-1 px-3 py-4">
        {NAV_ITEMS.map(({ id, label, icon }) => (
          <div key={id}>
            <button
              onClick={() => setTab(id)}
              className={[
                "mb-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition",
                tab === id
                  ? "bg-[var(--paper-deep)] font-medium text-[var(--ink)]"
                  : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
              ].join(" ")}
            >
              <span className="text-[10px] opacity-60">{icon}</span>
              {label}
            </button>
            {id === "reportes" && tab === "reportes" && (
              <div className="mb-1 ml-5 flex flex-col">
                {REPORTES_SUB_TABS.map(({ id: subId, label: subLabel }) => (
                  <button key={subId} onClick={() => setReportesTab(subId)}
                    className={["flex w-full items-center rounded-md px-3 py-1.5 text-left text-xs transition", reportesTab === subId ? "font-medium text-[var(--ink)]" : "text-[var(--muted)] hover:text-[var(--ink)]"].join(" ")}
                  >
                    <span className={["mr-2 text-[8px]", reportesTab === subId ? "opacity-100" : "opacity-0"].join(" ")}>▸</span>
                    {subLabel}
                  </button>
                ))}
              </div>
            )}
            {id === "configuracoes" && tab === "configuracoes" && (
              <div className="mb-1 ml-5 flex flex-col">
                {CONFIG_SUB_TABS.map(({ id: subId, label: subLabel }) => (
                  <button
                    key={subId}
                    onClick={() => setConfigTab(subId)}
                    className={[
                      "flex w-full items-center rounded-md px-3 py-1.5 text-left text-xs transition",
                      configTab === subId
                        ? "font-medium text-[var(--ink)]"
                        : "text-[var(--muted)] hover:text-[var(--ink)]",
                    ].join(" ")}
                  >
                    <span className={["mr-2 text-[8px]", configTab === subId ? "opacity-100" : "opacity-0"].join(" ")}>▸</span>
                    {subLabel}
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}
      </nav>
      <div className="border-t border-[var(--rule-soft)] px-4 py-4">
        <p className="text-xs font-medium text-[var(--ink-soft)]">{user?.nome ?? "—"}</p>
        <p className="mb-3 truncate text-xs text-[var(--muted)]">{user?.email ?? ""}</p>
        {user?.is_admin && (
          <Link href="/gestor/admin/usuarios" className="mb-2 block text-xs text-[var(--forest)] hover:underline">
            Administração →
          </Link>
        )}
        <button onClick={onLogout} className="text-xs text-[var(--muted)] transition hover:text-[var(--crimson)]">
          Sair
        </button>
      </div>
    </aside>
  );
}

// ── Filtro de gestor ───────────────────────────────────────────────────────────
function GestorFiltro({
  gestores,
  value,
  onChange,
}: {
  gestores: string[];
  value: string;
  onChange: (v: string) => void;
}) {
  if (gestores.length === 0) return null;
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-[var(--muted)]">Gestor</span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-2 py-1 text-xs text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
      >
        <option value="">Todos</option>
        {gestores.map((nome) => (
          <option key={nome} value={nome}>
            {nome}
          </option>
        ))}
      </select>
    </div>
  );
}

// ── Aba Clientes ──────────────────────────────────────────────────────────────
type DispatchedJob = {
  job_id: string;
  slug: string;
  nome: string;
  status: JobInfo["status"] | "dispatch_error";
  slides_url: string | null;
  erro: string | null;
  dispatched_at: number;  // Date.now() quando o disparo foi feito (client-side)
};

function formatElapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  if (s < 60) return `${s}s`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}min ${s % 60}s`;
  const h = Math.floor(m / 60);
  return `${h}h${m % 60 > 0 ? ` ${m % 60}min` : ""}`;
}

function AbaClientes({ clientes }: { clientes: ClienteGestor[] }) {
  const [busca, setBusca] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [mes, setMes] = useState(() => new Date().toISOString().slice(0, 7));
  const [frequencia, setFrequencia] = useState<"MENSAL" | "SEMANAL">("MENSAL");
  const [gerando, setGerando] = useState(false);
  const [progresso, setProgresso] = useState<{ atual: number; total: number; ok: number; erro: number } | null>(null);
  const [dispatched, setDispatched] = useState<DispatchedJob[]>([]);
  const [now, setNow] = useState(() => Date.now());

  // Ticker de 1s para atualizar tempo decorrido enquanto há jobs incompletos
  useEffect(() => {
    const hasIncomplete = dispatched.some((j) => j.status === "pending" || j.status === "running");
    if (!hasIncomplete) return;
    const id = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(id);
  }, [dispatched]);

  // Contadores agregados para o painel de progresso
  const counts = useMemo(() => {
    const c = { done: 0, running: 0, pending: 0, error: 0 };
    for (const j of dispatched) {
      if (j.status === "done") c.done++;
      else if (j.status === "running") c.running++;
      else if (j.status === "pending") c.pending++;
      else c.error++;  // error + dispatch_error
    }
    return c;
  }, [dispatched]);
  const totalDispatched = dispatched.length;
  const concluidos = counts.done + counts.error;
  const progressPercent = totalDispatched > 0 ? (concluidos / totalDispatched) * 100 : 0;

  const filtrados = clientes.filter((c) =>
    c.nome.toLowerCase().includes(busca.toLowerCase()) ||
    c.categoria.toLowerCase().includes(busca.toLowerCase()),
  );
  const porCategoria = filtrados.reduce<Record<string, ClienteGestor[]>>((acc, c) => {
    (acc[c.categoria] ??= []).push(c);
    return acc;
  }, {});

  function toggle(slug: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      next.has(slug) ? next.delete(slug) : next.add(slug);
      return next;
    });
  }

  function toggleAll() {
    setSelected(
      selected.size === filtrados.length ? new Set() : new Set(filtrados.map((c) => c.slug))
    );
  }

  async function handleGerar() {
    if (!mes || gerando) return;
    const slugs = Array.from(selected);
    const total = slugs.length;
    setGerando(true);
    setDispatched([]);
    setProgresso({ atual: 0, total, ok: 0, erro: 0 });
    const results: DispatchedJob[] = [];
    let ok = 0, erro = 0;
    for (let i = 0; i < slugs.length; i++) {
      const slug = slugs[i];
      const nome = clientes.find((c) => c.slug === slug)?.nome ?? slug;
      const dispatched_at = Date.now();
      try {
        const { job_id } = await gestorApi.triggerReport(slug, mes, frequencia);
        ok++;
        results.push({ job_id, slug, nome, status: "pending", slides_url: null, erro: null, dispatched_at });
      } catch (e: any) {
        erro++;
        results.push({ job_id: "", slug, nome, status: "dispatch_error", slides_url: null, erro: e?.message ?? "Erro ao disparar", dispatched_at });
      }
      setProgresso({ atual: i + 1, total, ok, erro });
      await new Promise((r) => setTimeout(r, 120));
    }
    setGerando(false);
    setProgresso(null);
    setDispatched(results);
    setSelected(new Set());
  }

  // Polling: a cada 4s atualiza jobs ainda pendentes/rodando
  useEffect(() => {
    const incomplete = dispatched.filter((j) => j.job_id && (j.status === "pending" || j.status === "running"));
    if (incomplete.length === 0) return;
    let cancelled = false;
    const timer = setTimeout(async () => {
      if (cancelled) return;
      const results = await Promise.allSettled(incomplete.map((j) => gestorApi.getJob(j.job_id)));
      if (cancelled) return;
      setDispatched((prev) =>
        prev.map((j) => {
          const idx = incomplete.findIndex((inc) => inc.job_id === j.job_id);
          if (idx < 0) return j;
          const r = results[idx];
          if (r.status === "fulfilled")
            return { ...j, status: r.value.status, slides_url: r.value.slides_url, erro: r.value.erro };
          return j;
        }),
      );
    }, 4000);
    return () => { cancelled = true; clearTimeout(timer); };
  }, [dispatched]);

  const allChecked = filtrados.length > 0 && selected.size === filtrados.length;

  return (
    <div className="pb-24">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-2xl font-medium text-[var(--ink)]">Clientes</h1>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1 rounded-md border border-[var(--rule-soft)] p-0.5">
            {(["MENSAL", "SEMANAL"] as const).map((f) => (
              <button
                key={f}
                onClick={() => setFrequencia(f)}
                className={["rounded px-3 py-1 text-xs font-medium transition", frequencia === f ? "bg-[var(--forest)] text-white" : "text-[var(--muted)] hover:text-[var(--ink)]"].join(" ")}
              >
                {f === "MENSAL" ? "Mensal" : "Semanal"}
              </button>
            ))}
          </div>
          <span className="eyebrow text-xs text-[var(--muted)]">{clientes.length} total</span>
        </div>
      </div>

      <div className="mb-4 flex items-center gap-3">
        <input
          type="search"
          placeholder="Buscar cliente ou categoria…"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="flex-1 rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
        />
        {filtrados.length > 0 && (
          <button
            onClick={toggleAll}
            className="shrink-0 rounded-md border border-[var(--rule-soft)] px-3 py-2 text-xs text-[var(--muted)] transition hover:border-[var(--forest)] hover:text-[var(--ink)]"
          >
            {allChecked ? "Desmarcar todos" : "Selecionar todos"}
          </button>
        )}
      </div>

      {/* Painel de jobs disparados com polling de status */}
      {dispatched.length > 0 && (
        <div className="mb-6 overflow-hidden rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
          <div className="border-b border-[var(--rule-soft)] px-4 py-3">
            <div className="mb-2 flex items-center justify-between">
              <p className="text-xs font-medium text-[var(--ink)]">
                Reports disparados — {mesLabel(mes)} ({frequencia === "MENSAL" ? "Mensal" : "Semanal"})
              </p>
              <button onClick={() => setDispatched([])} className="text-xs text-[var(--muted)] hover:text-[var(--ink)]">✕</button>
            </div>
            {/* Barra de progresso */}
            <div className="mb-1.5 h-1.5 w-full overflow-hidden rounded-full bg-[var(--rule-soft)]">
              <div
                className="h-full bg-[var(--forest)] transition-all duration-300"
                style={{ width: `${progressPercent}%` }}
              />
            </div>
            {/* Contadores */}
            <p className="text-[10px] text-[var(--muted)]">
              <span className="font-medium text-[var(--ink)]">{concluidos}/{totalDispatched}</span> concluídos
              {counts.running > 0 && <> · <span className="text-[var(--amber)]">{counts.running} gerando</span></>}
              {counts.pending > 0 && <> · {counts.pending} na fila</>}
              {counts.done > 0 && <> · <span className="text-[var(--forest)]">{counts.done} ok</span></>}
              {counts.error > 0 && <> · <span className="text-[var(--crimson)]">{counts.error} erro{counts.error > 1 ? "s" : ""}</span></>}
            </p>
          </div>
          <ul>
            {dispatched.map((j, idx) => {
              const elapsed = j.status === "pending" || j.status === "running"
                ? formatElapsed(now - j.dispatched_at)
                : null;
              return (
                <li
                  key={j.slug}
                  className={["flex items-center gap-3 px-4 py-3", idx < dispatched.length - 1 ? "border-b border-[var(--rule-soft)]" : ""].join(" ")}
                >
                  {j.status === "pending" && <span className="w-3 text-center text-xs text-[var(--muted)]">◌</span>}
                  {j.status === "running" && <div className="h-3 w-3 shrink-0 animate-spin rounded-full border-2 border-[var(--rule-soft)] border-t-[var(--amber)]" />}
                  {j.status === "done" && <span className="w-3 text-center text-xs text-[var(--forest)]">✓</span>}
                  {(j.status === "error" || j.status === "dispatch_error") && <span className="w-3 text-center text-xs text-[var(--crimson)]">✗</span>}
                  <span className="flex-1 text-sm text-[var(--ink)]">{j.nome}</span>
                  {j.status === "pending" && (
                    <span className="text-xs text-[var(--muted)]">
                      Na fila… <span className="opacity-60">({elapsed})</span>
                    </span>
                  )}
                  {j.status === "running" && (
                    <span className="text-xs text-[var(--amber)]">
                      Gerando… <span className="opacity-60">({elapsed})</span>
                    </span>
                  )}
                  {j.status === "done" && j.slides_url && (
                    <a href={j.slides_url} target="_blank" rel="noopener noreferrer"
                      className="rounded-md bg-[var(--forest)] px-3 py-1 text-xs font-medium text-white transition hover:opacity-90">
                      Abrir report →
                    </a>
                  )}
                  {j.status === "done" && !j.slides_url && <span className="text-xs text-[var(--muted)]">Concluído</span>}
                  {(j.status === "error" || j.status === "dispatch_error") && (
                    <span className="max-w-xs truncate text-xs text-[var(--crimson)]" title={j.erro ?? ""}>{j.erro ?? "Erro desconhecido"}</span>
                  )}
                </li>
              );
            })}
          </ul>
        </div>
      )}

      {filtrados.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">{busca ? "Nenhum cliente encontrado." : "Nenhum cliente atribuído."}</p>
      ) : (
        Object.entries(porCategoria)
          .sort(([a], [b]) => a.localeCompare(b))
          .map(([cat, lista]) => (
            <div key={cat} className="mb-6">
              <p className="eyebrow mb-2 text-xs text-[var(--muted)]">{cat}</p>
              <ul className="flex flex-col gap-1">
                {lista.map((c) => (
                  <li key={c.slug} className="flex items-center gap-2">
                    <button
                      onClick={() => toggle(c.slug)}
                      className={[
                        "flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] transition",
                        selected.has(c.slug)
                          ? "border-[var(--forest)] bg-[var(--forest)] text-white"
                          : "border-[var(--rule-soft)] bg-[var(--paper)] text-transparent hover:border-[var(--forest)]",
                      ].join(" ")}
                      aria-label={`Selecionar ${c.nome}`}
                    >
                      ✓
                    </button>
                    <div
                      className={[
                        "flex flex-1 items-center justify-between rounded-md border bg-[var(--paper-soft)] px-4 py-3 transition",
                        selected.has(c.slug)
                          ? "border-[var(--forest)]"
                          : "border-[var(--rule-soft)] hover:border-[var(--forest)] hover:bg-[var(--paper-deep)]",
                      ].join(" ")}
                    >
                      <button onClick={() => toggle(c.slug)} className="flex-1 text-left">
                        <span className="text-sm font-medium text-[var(--ink)]">{c.nome}</span>
                        <span className="ml-2 text-xs text-[var(--muted)]">{c.categoria}</span>
                      </button>
                      <Link
                        href={`/gestor/${c.slug}`}
                        onClick={(e) => e.stopPropagation()}
                        className="text-xs text-[var(--forest)] hover:underline"
                      >
                        Abrir →
                      </Link>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          ))
      )}

      {/* Barra flutuante de ação em lote */}
      {selected.size > 0 && (
        <div className="fixed bottom-0 left-56 right-0 z-50 flex flex-col border-t border-[var(--rule-soft)] bg-[var(--paper-soft)] shadow-lg">
          {progresso && (
            <div className="px-8 pt-3">
              <div className="mb-1 flex items-center justify-between text-xs text-[var(--muted)]">
                <span>
                  Disparando reports… {progresso.atual}/{progresso.total}
                  {progresso.erro > 0 && <span className="ml-2 text-[var(--crimson)]">{progresso.erro} com erro</span>}
                </span>
                <span className="text-[var(--forest)]">{progresso.ok} ok</span>
              </div>
              <div className="h-1.5 w-full overflow-hidden rounded-full bg-[var(--paper-deep)]">
                <div
                  className="h-full rounded-full bg-[var(--forest)] transition-all duration-300"
                  style={{ width: `${(progresso.atual / progresso.total) * 100}%` }}
                />
              </div>
            </div>
          )}
          <div className="flex items-center gap-4 px-8 py-4">
          <span className="text-sm font-medium text-[var(--ink)]">
            {selected.size} cliente{selected.size > 1 ? "s" : ""} selecionado{selected.size > 1 ? "s" : ""}
          </span>
          <div className="flex items-center gap-2">
            <label className="text-xs text-[var(--muted)]">Mês</label>
            <input
              type="month"
              value={mes}
              onChange={(e) => setMes(e.target.value)}
              className="rounded border border-[var(--rule-soft)] bg-[var(--paper)] px-2 py-1 text-sm text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
            />
          </div>
          <button
            onClick={handleGerar}
            disabled={gerando}
            className="rounded-md bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50"
          >
            {gerando ? "Gerando…" : `Gerar ${selected.size} report${selected.size > 1 ? "s" : ""}`}
          </button>
          <button
            onClick={() => setSelected(new Set())}
            className="text-sm text-[var(--muted)] transition hover:text-[var(--ink)]"
          >
            Limpar
          </button>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Aba Meus Reports ──────────────────────────────────────────────────────────
function AbaMeusReports({ jobs, loading }: { jobs: JobInfo[]; loading: boolean }) {
  const [filtroStatus, setFiltroStatus] = useState<JobInfo["status"] | "">("");

  const filtrados = filtroStatus
    ? jobs.filter((j) => j.status === filtroStatus)
    : jobs;

  const sorted = [...filtrados].sort(
    (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
  );

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-2xl font-medium text-[var(--ink)]">Meus reports</h1>
        <div className="flex items-center gap-2">
          <span className="text-xs text-[var(--muted)]">Status</span>
          <select
            value={filtroStatus}
            onChange={(e) => setFiltroStatus(e.target.value as JobInfo["status"] | "")}
            className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-2 py-1 text-xs text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          >
            <option value="">Todos</option>
            <option value="done">Concluído</option>
            <option value="running">Gerando</option>
            <option value="pending">Na fila</option>
            <option value="error">Erro</option>
          </select>
        </div>
      </div>

      {loading ? (
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      ) : sorted.length === 0 ? (
        <p className="text-sm text-[var(--muted)]">Nenhum report encontrado.</p>
      ) : (
        <div className="overflow-hidden rounded-lg border border-[var(--rule-soft)]">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                {["Cliente", "Mês", "Tipo", "Status", "Gerado em", ""].map((h) => (
                  <th key={h} className="px-3 py-2 text-left font-medium text-[var(--muted)]">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {sorted.map((j, idx) => (
                <tr key={j.id} className={idx % 2 === 0 ? "bg-[var(--paper-soft)]" : "bg-[var(--paper)]"}>
                  <td className="px-3 py-2.5 font-medium text-[var(--ink)]">{j.cliente_nome}</td>
                  <td className="px-3 py-2.5 text-[var(--muted)]">{mesLabel(j.mes)}</td>
                  <td className="px-3 py-2.5 text-[var(--muted)]">{j.frequencia === "SEMANAL" ? "Semanal" : "Mensal"}</td>
                  <td className="px-3 py-2.5"><StatusBadge status={j.status} /></td>
                  <td className="px-3 py-2.5 text-[var(--muted)]">
                    {new Date(j.created_at).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit", year: "numeric" })}
                  </td>
                  <td className="px-3 py-2.5 text-right">
                    {j.status === "done" && j.slides_url && (
                      <a href={j.slides_url} target="_blank" rel="noopener noreferrer"
                        className="rounded-md bg-[var(--forest)] px-3 py-1 text-xs font-medium text-white transition hover:opacity-90">
                        Abrir →
                      </a>
                    )}
                    {j.status === "error" && j.erro && (
                      <span className="max-w-xs truncate text-xs text-[var(--crimson)]" title={j.erro}>{j.erro}</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

// ── Custom Tooltip ────────────────────────────────────────────────────────────
function TooltipBRL({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-[var(--ink)]">{label}</p>
      {payload.map((p: any) => (
        <p key={p.name} style={{ color: p.color }}>
          {p.name}: {fmtBRL(p.value)}
        </p>
      ))}
    </div>
  );
}
function TooltipRoas({ active, payload, label }: any) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-xs shadow-lg">
      <p className="mb-1 font-medium text-[var(--ink)]">{label}</p>
      <p style={{ color: payload[0].color }}>ROAS: {fmtNum(payload[0].value)}×</p>
    </div>
  );
}

// ── Aba Dashboard ─────────────────────────────────────────────────────────────
function AbaDashboard({
  clientes,
  jobs,
  loadingJobs,
  metricas,
  loadingMetricas,
  slugsFiltro,
}: {
  clientes: ClienteGestor[];
  jobs: JobInfo[];
  loadingJobs: boolean;
  metricas: MetricasDashboard | null;
  loadingMetricas: boolean;
  slugsFiltro: Set<string> | null;
}) {
  const [expandido, setExpandido] = useState<string | null>(null);
  const [breakdown, setBreakdown] = useState<Record<string, MetricasBreakdown>>({});
  const [loadingBreakdown, setLoadingBreakdown] = useState<Record<string, boolean>>({});
  const [verTodosMeta, setVerTodosMeta] = useState<Record<string, boolean>>({});
  const [verTodosGoogle, setVerTodosGoogle] = useState<Record<string, boolean>>({});

  async function toggleExpandir(slug: string) {
    if (expandido === slug) { setExpandido(null); return; }
    setExpandido(slug);
    if (breakdown[slug]) return;
    setLoadingBreakdown((p) => ({ ...p, [slug]: true }));
    try {
      const data = await gestorApi.metricasBreakdown(slug);
      setBreakdown((p) => ({ ...p, [slug]: data }));
    } catch { /* silencia */ } finally {
      setLoadingBreakdown((p) => ({ ...p, [slug]: false }));
    }
  }

  const mesAtual = new Date().toISOString().slice(0, 7);

  // Apply gestor filter to jobs and metrics
  const jobsFiltrados = slugsFiltro ? jobs.filter((j) => slugsFiltro.has(j.cliente_slug)) : jobs;
  const itens = metricas
    ? (slugsFiltro ? metricas.items.filter((i) => slugsFiltro.has(i.slug)) : metricas.items)
    : [];

  // Recompute totals from filtered items
  const totalFaturamento = itens.reduce((s, i) => s + (i.faturamento ?? 0), 0);
  const totalInvestimento = itens.reduce((s, i) => s + (i.investimento ?? 0), 0);
  const roasVals = itens.filter((i) => i.roas != null).map((i) => i.roas!);
  const mediaRoas = roasVals.length > 0 ? roasVals.reduce((s, v) => s + v, 0) / roasVals.length : null;
  const totalLeads = itens.reduce((s, i) => s + (i.leads ?? 0), 0);
  const totalVendas = itens.reduce((s, i) => s + (i.vendas ?? 0), 0);

  const jobsMes = jobsFiltrados.filter((j) => j.mes === mesAtual);
  const concluidos = jobsFiltrados.filter((j) => j.status === "done").length;
  const taxa = jobsFiltrados.length > 0 ? Math.round((concluidos / jobsFiltrados.length) * 100) : 0;
  const emAndamento = jobsFiltrados.filter((j) => j.status === "running" || j.status === "pending");

  // Top 10 por faturamento (para gráfico Fat × Inv)
  const topFaturamento = [...itens]
    .filter((i) => i.faturamento != null || i.investimento != null)
    .sort((a, b) => (b.faturamento ?? 0) - (a.faturamento ?? 0))
    .slice(0, 10)
    .map((i) => ({
      nome: i.nome.length > 14 ? i.nome.slice(0, 13) + "…" : i.nome,
      Faturamento: i.faturamento ?? 0,
      Investimento: i.investimento ?? 0,
    }));

  // Top 10 por ROAS
  const topRoas = [...itens]
    .filter((i) => i.roas != null)
    .sort((a, b) => (b.roas ?? 0) - (a.roas ?? 0))
    .slice(0, 10)
    .map((i) => ({
      nome: i.nome.length > 14 ? i.nome.slice(0, 13) + "…" : i.nome,
      roas: i.roas ?? 0,
    }));

  const hasMetricas = itens.some((i) => i.faturamento != null || i.roas != null || i.investimento != null);

  return (
    <div>
      <h1 className="font-display mb-6 text-2xl font-medium text-[var(--ink)]">Dashboard</h1>

      {/* ── Cards de resumo ── */}
      <div className="mb-8 grid grid-cols-3 gap-4 xl:grid-cols-6">
        {[
          { label: "Clientes",          value: clientes.length,                              sub: "ativos" },
          { label: "Reports este mês",  value: jobsMes.length,                               sub: mesLabel(mesAtual) },
          { label: "Taxa de sucesso",   value: `${taxa}%`,                                   sub: `${concluidos}/${jobsFiltrados.length}` },
          { label: "Faturamento total", value: metricas ? fmtBRL(totalFaturamento) : "—",    sub: "última coleta" },
          { label: "Investimento total",value: metricas ? fmtBRL(totalInvestimento) : "—",   sub: "última coleta" },
          { label: "ROAS médio",        value: mediaRoas != null ? `${fmtNum(mediaRoas)}×` : "—", sub: "carteira" },
        ].map(({ label, value, sub }) => (
          <div key={label} className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
            <p className="eyebrow mb-2 text-xs text-[var(--muted)]">{label}</p>
            <p className="font-mono-num text-2xl font-medium text-[var(--ink)]">{value}</p>
            <p className="mt-1 text-xs text-[var(--muted)]">{sub}</p>
          </div>
        ))}
      </div>

      {/* ── Gráficos ── */}
      {loadingMetricas ? (
        <div className="mb-8 rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-8 text-center">
          <p className="text-sm text-[var(--muted)]">Carregando métricas…</p>
        </div>
      ) : hasMetricas ? (
        <div className="mb-8 grid grid-cols-1 gap-6 xl:grid-cols-2">
          {/* Faturamento × Investimento */}
          <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-5">
            <p className="eyebrow mb-4 text-xs text-[var(--muted)]">Faturamento × Investimento — top 10</p>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topFaturamento} margin={{ top: 0, right: 0, left: 0, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--rule-soft)" vertical={false} />
                <XAxis
                  dataKey="nome"
                  tick={{ fontSize: 10, fill: "var(--muted)" }}
                  angle={-35}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "var(--muted)" }}
                  tickFormatter={(v) => `R$${(v / 1000).toFixed(0)}k`}
                  width={55}
                />
                <Tooltip content={<TooltipBRL />} />
                <Legend wrapperStyle={{ fontSize: 11, paddingTop: 8 }} />
                <Bar dataKey="Faturamento" fill="var(--forest)" radius={[3, 3, 0, 0]} />
                <Bar dataKey="Investimento" fill="var(--amber)" radius={[3, 3, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>

          {/* ROAS top 10 */}
          <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-5">
            <p className="eyebrow mb-4 text-xs text-[var(--muted)]">ROAS — top 10 clientes</p>
            <ResponsiveContainer width="100%" height={260}>
              <BarChart data={topRoas} margin={{ top: 0, right: 0, left: 0, bottom: 40 }}>
                <CartesianGrid strokeDasharray="3 3" stroke="var(--rule-soft)" vertical={false} />
                <XAxis
                  dataKey="nome"
                  tick={{ fontSize: 10, fill: "var(--muted)" }}
                  angle={-35}
                  textAnchor="end"
                  interval={0}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "var(--muted)" }}
                  tickFormatter={(v) => `${v}×`}
                  width={40}
                />
                <Tooltip content={<TooltipRoas />} />
                <Bar dataKey="roas" radius={[3, 3, 0, 0]}>
                  {topRoas.map((_, i) => (
                    <Cell
                      key={i}
                      fill={`color-mix(in srgb, var(--forest) ${100 - i * 8}%, var(--paper-deep))`}
                    />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      ) : (
        <div className="mb-8 rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-8 text-center">
          <p className="text-sm text-[var(--muted)]">Ainda sem métricas de performance. Colete os dados para visualizar os gráficos.</p>
        </div>
      )}

      {/* ── Tabela de clientes com KPIs ── */}
      {hasMetricas && (
        <div className="mb-8">
          <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Desempenho por cliente — última coleta</p>
          <div className="overflow-x-auto rounded-lg border border-[var(--rule-soft)]">
            <table className="w-full text-xs">
              <thead>
                <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                  {["","Cliente","Categoria","Faturamento","Investimento","ROAS","CPA","Leads","Vendas","Fat Δ%","ROAS Δ%"].map((h) => (
                    <th key={h} className="px-3 py-2 text-left font-medium text-[var(--muted)]">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {[...itens]
                  .filter((i) => i.faturamento != null || i.roas != null)
                  .sort((a, b) => (b.faturamento ?? 0) - (a.faturamento ?? 0))
                  .map((item, idx) => {
                    const isOpen = expandido === item.slug;
                    const bk = breakdown[item.slug];
                    const loadingBk = loadingBreakdown[item.slug];
                    const rowBg = idx % 2 === 0 ? "bg-[var(--paper-soft)]" : "bg-[var(--paper)]";
                    return (
                      <>
                        <tr key={item.slug} className={rowBg}>
                          <td className="px-2 py-2">
                            <button
                              onClick={() => toggleExpandir(item.slug)}
                              className="flex h-5 w-5 items-center justify-center rounded text-xs text-[var(--muted)] transition hover:text-[var(--ink)]"
                              title={isOpen ? "Recolher" : "Ver detalhes"}
                            >
                              {isOpen ? "▾" : "▸"}
                            </button>
                          </td>
                          <td className="px-3 py-2 font-medium text-[var(--ink)]">
                            <Link href={`/gestor/${item.slug}`} className="hover:text-[var(--forest)] hover:underline">
                              {item.nome}
                            </Link>
                          </td>
                          <td className="px-3 py-2 text-[var(--muted)]">{item.categoria}</td>
                          <td className="px-3 py-2 font-mono-num text-[var(--ink)]">{fmtBRL(item.faturamento)}</td>
                          <td className="px-3 py-2 font-mono-num text-[var(--ink)]">{fmtBRL(item.investimento)}</td>
                          <td className="px-3 py-2 font-mono-num text-[var(--ink)]">{item.roas != null ? `${fmtNum(item.roas)}×` : "—"}</td>
                          <td className="px-3 py-2 font-mono-num text-[var(--ink)]">{fmtBRL(item.cpa)}</td>
                          <td className="px-3 py-2 font-mono-num text-[var(--ink)]">{item.leads ?? "—"}</td>
                          <td className="px-3 py-2 font-mono-num text-[var(--ink)]">{item.vendas ?? "—"}</td>
                          <td className={`px-3 py-2 font-mono-num ${item.faturamento_var_pct != null && item.faturamento_var_pct >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                            {fmtPct(item.faturamento_var_pct)}
                          </td>
                          <td className={`px-3 py-2 font-mono-num ${item.roas_var_pct != null && item.roas_var_pct >= 0 ? "text-[var(--forest)]" : "text-[var(--crimson)]"}`}>
                            {fmtPct(item.roas_var_pct)}
                          </td>
                        </tr>
                        {isOpen && (
                          <tr key={`${item.slug}-detail`} className="border-b border-[var(--rule-soft)]">
                            <td colSpan={11} className="bg-[var(--paper-deep)] px-6 py-4">
                              {loadingBk ? (
                                <p className="text-xs text-[var(--muted)]">Carregando…</p>
                              ) : !bk || (bk.meta_ads.length === 0 && bk.google_ads.length === 0) ? (
                                <p className="text-xs text-[var(--muted)]">Sem dados granulares disponíveis para este cliente.</p>
                              ) : (
                                <div className="flex flex-col gap-5">
                                  {/* Meta Ads */}
                                  {bk.meta_ads.length > 0 && (() => {
                                    const slug = item.slug;
                                    const todosMeta = verTodosMeta[slug] ?? false;
                                    const visiveis = todosMeta ? bk.meta_ads : bk.meta_ads.slice(0, 5);
                                    const ocultos = bk.meta_ads.length - 5;
                                    return (
                                      <div>
                                        <p className="eyebrow mb-2 text-xs font-medium text-[var(--muted)]">Meta Ads — top anúncios</p>
                                        <table className="w-full text-xs">
                                          <thead>
                                            <tr className="border-b border-[var(--rule-soft)]">
                                              <th className="pb-1 pr-3 text-left font-medium text-[var(--muted)]">Criativo</th>
                                              <th className="pb-1 pr-3 text-left font-medium text-[var(--muted)]">Anúncio</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Invest.</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Leads</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Conv.</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Fat.</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">CPL/CPA</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">ROAS</th>
                                              <th className="pb-1 text-right font-medium text-[var(--muted)]">Impressões</th>
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {visiveis.map((ad, i) => (
                                              <tr key={i} className="border-b border-[var(--rule-soft)]/40">
                                                <td className="py-2 pr-3">
                                                  {ad.imagem_url ? (
                                                    <img src={ad.imagem_url} alt={ad.nome} className="h-10 w-10 rounded object-cover" />
                                                  ) : (
                                                    <div className="h-10 w-10 rounded bg-[var(--paper-soft)]" />
                                                  )}
                                                </td>
                                                <td className="py-2 pr-3 font-medium text-[var(--ink)]">{ad.nome}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.investimento)}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.leads ?? "—"}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.conversoes ?? "—"}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.faturamento)}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.cpl ?? ad.cpa)}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.roas != null ? `${fmtNum(ad.roas)}×` : "—"}</td>
                                                <td className="py-2 text-right font-mono-num text-[var(--muted)]">{ad.impressoes?.toLocaleString("pt-BR") ?? "—"}</td>
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                        {ocultos > 0 && (
                                          <button
                                            onClick={() => setVerTodosMeta((p) => ({ ...p, [slug]: !todosMeta }))}
                                            className="mt-2 text-xs text-[var(--accent)] hover:underline"
                                          >
                                            {todosMeta ? "Ver menos" : `Ver mais ${ocultos} anúncio${ocultos !== 1 ? "s" : ""}`}
                                          </button>
                                        )}
                                      </div>
                                    );
                                  })()}
                                  {/* Google Ads */}
                                  {bk.google_ads.length > 0 && (() => {
                                    const slug = item.slug;
                                    const todosGoogle = verTodosGoogle[slug] ?? false;
                                    const visiveis = todosGoogle ? bk.google_ads : bk.google_ads.slice(0, 5);
                                    const ocultos = bk.google_ads.length - 5;
                                    return (
                                      <div>
                                        <p className="eyebrow mb-2 text-xs font-medium text-[var(--muted)]">Google Ads — top campanhas</p>
                                        <table className="w-full text-xs">
                                          <thead>
                                            <tr className="border-b border-[var(--rule-soft)]">
                                              <th className="pb-1 pr-3 text-left font-medium text-[var(--muted)]">Campanha</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Invest.</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Faturamento</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">Conv.</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">CPA</th>
                                              <th className="pb-1 pr-3 text-right font-medium text-[var(--muted)]">ROAS</th>
                                              <th className="pb-1 text-right font-medium text-[var(--muted)]">Impressões</th>
                                            </tr>
                                          </thead>
                                          <tbody>
                                            {visiveis.map((ad, i) => (
                                              <tr key={i} className="border-b border-[var(--rule-soft)]/40">
                                                <td className="py-2 pr-3 font-medium text-[var(--ink)]">{ad.nome}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.investimento)}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.faturamento)}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.conversoes != null ? fmtNum(ad.conversoes) : "—"}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{fmtBRL(ad.cpa)}</td>
                                                <td className="py-2 pr-3 text-right font-mono-num text-[var(--ink)]">{ad.roas != null ? `${fmtNum(ad.roas)}×` : "—"}</td>
                                                <td className="py-2 text-right font-mono-num text-[var(--muted)]">{ad.impressoes?.toLocaleString("pt-BR") ?? "—"}</td>
                                              </tr>
                                            ))}
                                          </tbody>
                                        </table>
                                        {ocultos > 0 && (
                                          <button
                                            onClick={() => setVerTodosGoogle((p) => ({ ...p, [slug]: !todosGoogle }))}
                                            className="mt-2 text-xs text-[var(--accent)] hover:underline"
                                          >
                                            {todosGoogle ? "Ver menos" : `Ver mais ${ocultos} campanha${ocultos !== 1 ? "s" : ""}`}
                                          </button>
                                        )}
                                      </div>
                                    );
                                  })()}
                                </div>
                              )}
                            </td>
                          </tr>
                        )}
                      </>
                    );
                  })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* ── Jobs em andamento ── */}
      {emAndamento.length > 0 && (
        <div className="mb-6">
          <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Em andamento</p>
          <ul className="flex flex-col gap-2">
            {emAndamento.map((j) => (
              <li key={j.id} className="flex items-center justify-between rounded-md border border-[var(--amber)]/40 bg-[var(--paper-soft)] px-4 py-3">
                <div>
                  <p className="text-sm font-medium text-[var(--ink)]">{j.cliente_nome}</p>
                  <p className="text-xs text-[var(--muted)]">{mesLabel(j.mes)}</p>
                </div>
                <div className="flex items-center gap-2">
                  <div className="h-3 w-3 animate-spin rounded-full border-2 border-[var(--rule-soft)] border-t-[var(--amber)]" />
                  <StatusBadge status={j.status} />
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* ── Atividade recente ── */}
      <div>
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Atividade recente</p>
        {loadingJobs ? (
          <p className="text-sm text-[var(--muted)]">Carregando…</p>
        ) : jobsFiltrados.filter((j) => j.status === "done" || j.status === "error").length === 0 ? (
          <p className="text-sm text-[var(--muted)]">Nenhum report gerado ainda.</p>
        ) : (
          <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)]">
            {jobsFiltrados
              .filter((j) => j.status === "done" || j.status === "error")
              .slice(0, 15)
              .map((j, idx, arr) => (
                <div
                  key={j.id}
                  className={["flex items-center justify-between px-4 py-3", idx < arr.length - 1 ? "border-b border-[var(--rule-soft)]" : ""].join(" ")}
                >
                  <div>
                    <p className="text-sm text-[var(--ink)]">{j.cliente_nome}</p>
                    <p className="text-xs text-[var(--muted)]">{mesLabel(j.mes)}</p>
                  </div>
                  <div className="flex items-center gap-3">
                    <StatusBadge status={j.status} />
                    {j.status === "done" && j.slides_url && (
                      <a href={j.slides_url} target="_blank" rel="noopener noreferrer" className="text-xs text-[var(--forest)] underline underline-offset-2">
                        Abrir →
                      </a>
                    )}
                  </div>
                </div>
              ))}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Aba Configurações ─────────────────────────────────────────────────────────
type EditForm = {
  nome: string;
  categoria: string;
  gestor: string;
  id_google_ads: string;
  id_meta_ads: string;
  id_ga4: string;
  painel_url: string;
  pasta_url: string;
};

const CATEGORIAS = ["E-commerce", "Lead Com Site", "Lead Sem Site"] as const;

function emptyForm(c: ClienteGestor): EditForm {
  return {
    nome: c.nome,
    categoria: c.categoria,
    gestor: c.gestor ?? "",
    id_google_ads: c.id_google_ads ?? "",
    id_meta_ads: c.id_meta_ads ?? "",
    id_ga4: c.id_ga4 ?? "",
    painel_url: c.painel_url ?? "",
    pasta_url: c.pasta_url ?? "",
  };
}

function emptyCreateForm(): EditForm {
  return {
    nome: "",
    categoria: CATEGORIAS[0],
    gestor: "",
    id_google_ads: "",
    id_meta_ads: "",
    id_ga4: "",
    painel_url: "",
    pasta_url: "",
  };
}

function AbaConfiguracoes({
  clientes,
  todosClientes,
  configTab,
  onClienteUpdated,
  onClienteDeleted,
  onClienteCriado,
  onGestorRenomeado,
  onGestoresNormalizados,
}: {
  clientes: ClienteGestor[];
  todosClientes: ClienteGestor[];
  configTab: ConfigTab;
  onClienteUpdated: (c: ClienteGestor) => void;
  onClienteDeleted: (id: string) => void;
  onClienteCriado: (c: ClienteGestor) => void;
  onGestorRenomeado: (de: string, para: string) => void;
  onGestoresNormalizados: (mapeamento: { de: string; para: string }[]) => void;
}) {
  const [busca, setBusca] = useState("");
  const [editando, setEditando] = useState<ClienteGestor | null>(null);
  const [editForm, setEditForm] = useState<EditForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveErr, setSaveErr] = useState<string | null>(null);
  const [deletando, setDeletando] = useState<ClienteGestor | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [deleteErr, setDeleteErr] = useState<string | null>(null);
  const [criando, setCriando] = useState(false);
  const [criarForm, setCriarForm] = useState<EditForm>(emptyCreateForm());
  const [creating, setCreating] = useState(false);
  const [createErr, setCreateErr] = useState<string | null>(null);
  const [renomeandoGestor, setRenomeandoGestor] = useState<string | null>(null);
  const [novoNomeGestor, setNovoNomeGestor] = useState("");
  const [renamingGestor, setRenamingGestor] = useState(false);
  const [renameGestorErr, setRenameGestorErr] = useState<string | null>(null);
  const [normalizing, setNormalizing] = useState(false);
  const [normalizeMsg, setNormalizeMsg] = useState<string | null>(null);
  const [gestoresCadastrados, setGestoresCadastrados] = useState<GestorCadastrado[]>([]);
  const [loadingGestoresCad, setLoadingGestoresCad] = useState(true);
  const [addingGestor, setAddingGestor] = useState(false);
  const [newGestorNome, setNewGestorNome] = useState("");
  const [newGestorSquad, setNewGestorSquad] = useState("");
  const [savingGestor, setSavingGestor] = useState(false);
  const [saveGestorErr, setSaveGestorErr] = useState<string | null>(null);
  const [removingGestorId, setRemovingGestorId] = useState<string | null>(null);

  useEffect(() => {
    gestorApi.listGestoresCadastrados()
      .then((res) => setGestoresCadastrados(res.items))
      .catch(console.error)
      .finally(() => setLoadingGestoresCad(false));
  }, []);

  const filtrados = clientes.filter((c) =>
    c.nome.toLowerCase().includes(busca.toLowerCase()) ||
    c.categoria.toLowerCase().includes(busca.toLowerCase()),
  );

  function openEdit(c: ClienteGestor) {
    setEditando(c);
    setEditForm(emptyForm(c));
    setSaveErr(null);
  }

  function openDelete(c: ClienteGestor) {
    setDeletando(c);
    setDeleteErr(null);
  }

  async function handleSalvar(e: React.FormEvent) {
    e.preventDefault();
    if (!editando || !editForm) return;
    setSaving(true);
    setSaveErr(null);
    try {
      const payload: ClienteEditData = {
        nome: editForm.nome || null,
        categoria: editForm.categoria || null,
        gestor: editForm.gestor || null,
        id_google_ads: editForm.id_google_ads || null,
        id_meta_ads: editForm.id_meta_ads || null,
        id_ga4: editForm.id_ga4 || null,
        painel_url: editForm.painel_url || null,
        pasta_url: editForm.pasta_url || null,
      };
      const updated = await gestorApi.updateCliente(editando.id, payload);
      onClienteUpdated(updated);
      setEditando(null);
      setEditForm(null);
    } catch (err: unknown) {
      setSaveErr(err instanceof Error ? err.message : "Erro ao salvar");
    } finally {
      setSaving(false);
    }
  }

  async function handleDesativar() {
    if (!deletando) return;
    setDeleting(true);
    setDeleteErr(null);
    try {
      await gestorApi.deleteCliente(deletando.id);
      onClienteDeleted(deletando.id);
      setDeletando(null);
    } catch (err: unknown) {
      setDeleteErr(err instanceof Error ? err.message : "Erro ao desativar");
    } finally {
      setDeleting(false);
    }
  }

  async function handleNormalizar() {
    setNormalizing(true);
    setNormalizeMsg(null);
    try {
      const res = await gestorApi.normalizarGestores();
      onGestoresNormalizados(res.mapeamento);
      setNormalizeMsg(
        res.nomes_alterados === 0
          ? "Nenhum nome precisou de ajuste."
          : `${res.nomes_alterados} nome${res.nomes_alterados !== 1 ? "s" : ""} normalizado${res.nomes_alterados !== 1 ? "s" : ""}.`
      );
    } catch (err: unknown) {
      setNormalizeMsg(err instanceof Error ? err.message : "Erro ao normalizar");
    } finally {
      setNormalizing(false);
    }
  }

  async function handleCriar(e: React.FormEvent) {
    e.preventDefault();
    if (!criarForm.nome.trim() || !criarForm.categoria) return;
    setCreating(true);
    setCreateErr(null);
    try {
      const payload: ClienteCreateData = {
        nome: criarForm.nome.trim(),
        categoria: criarForm.categoria,
        gestor: criarForm.gestor || null,
        id_google_ads: criarForm.id_google_ads || null,
        id_meta_ads: criarForm.id_meta_ads || null,
        id_ga4: criarForm.id_ga4 || null,
        painel_url: criarForm.painel_url || null,
        pasta_url: criarForm.pasta_url || null,
      };
      const novo = await gestorApi.createCliente(payload);
      onClienteCriado(novo);
      setCriando(false);
      setCriarForm(emptyCreateForm());
    } catch (err: unknown) {
      setCreateErr(err instanceof Error ? err.message : "Erro ao criar cliente");
    } finally {
      setCreating(false);
    }
  }

  async function handleAddGestorCadastrado(e: React.FormEvent) {
    e.preventDefault();
    if (!newGestorNome.trim()) return;
    setSavingGestor(true);
    setSaveGestorErr(null);
    try {
      const novo = await gestorApi.createGestorCadastrado(newGestorNome.trim(), newGestorSquad.trim() || null);
      setGestoresCadastrados((prev) => [...prev, novo].sort((a, b) => a.nome.localeCompare(b.nome)));
      setNewGestorNome("");
      setNewGestorSquad("");
      setAddingGestor(false);
    } catch (err: unknown) {
      setSaveGestorErr(err instanceof Error ? err.message : "Erro ao adicionar");
    } finally {
      setSavingGestor(false);
    }
  }

  async function handleRemoveGestorCadastrado(id: string) {
    setRemovingGestorId(id);
    try {
      await gestorApi.deleteGestorCadastrado(id);
      setGestoresCadastrados((prev) => prev.filter((g) => g.id !== id));
    } catch (err: unknown) {
      console.error(err);
    } finally {
      setRemovingGestorId(null);
    }
  }

  async function handleRenomearGestor(e: React.FormEvent) {
    e.preventDefault();
    if (!renomeandoGestor || !novoNomeGestor.trim()) return;
    setRenamingGestor(true);
    setRenameGestorErr(null);
    try {
      await gestorApi.renameGestor(renomeandoGestor, novoNomeGestor.trim());
      onGestorRenomeado(renomeandoGestor, novoNomeGestor.trim());
      setRenomeandoGestor(null);
      setNovoNomeGestor("");
    } catch (err: unknown) {
      setRenameGestorErr(err instanceof Error ? err.message : "Erro ao renomear");
    } finally {
      setRenamingGestor(false);
    }
  }

  function renderField(
    label: string,
    value: string,
    onChange: (v: string) => void,
    type: "text" | "select" = "text",
    required = false,
  ) {
    const inputCls =
      "rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]";
    return (
      <label className="flex flex-col gap-1">
        <span className="eyebrow text-xs text-[var(--muted)]">
          {label}{required && <span className="ml-0.5 text-[var(--crimson)]">*</span>}
        </span>
        {type === "select" ? (
          <select
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className={inputCls}
            required={required}
          >
            {CATEGORIAS.map((c) => (
              <option key={c} value={c}>{c}</option>
            ))}
          </select>
        ) : (
          <input
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            className={inputCls}
            required={required}
          />
        )}
      </label>
    );
  }

  // Sub-aba: Clientes
  const subClientes = (
    <>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-2xl font-medium text-[var(--ink)]">Clientes</h1>
        <div className="flex items-center gap-3">
          <span className="eyebrow text-xs text-[var(--muted)]">{clientes.length} cliente{clientes.length !== 1 ? "s" : ""}</span>
          <button
            onClick={() => { setCriando(true); setCriarForm(emptyCreateForm()); setCreateErr(null); }}
            className="rounded-md bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90"
          >
            + Adicionar cliente
          </button>
        </div>
      </div>
      <div className="mb-4">
        <input
          type="search"
          placeholder="Buscar cliente ou categoria…"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="w-full max-w-xs rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
        />
      </div>
      <div className="overflow-x-auto rounded-lg border border-[var(--rule-soft)]">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
              {["Nome", "Categoria", "Gestor", "ID Google", "ID Meta", "ID GA4", ""].map((h) => (
                <th key={h} className="px-3 py-2 text-left font-medium text-[var(--muted)]">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {filtrados.length === 0 ? (
              <tr>
                <td colSpan={7} className="py-10 text-center text-sm text-[var(--muted)]">Nenhum cliente encontrado.</td>
              </tr>
            ) : (
              filtrados.map((c, idx) => (
                <tr key={c.id} className={idx % 2 === 0 ? "bg-[var(--paper-soft)]" : "bg-[var(--paper)]"}>
                  <td className="px-3 py-2 font-medium text-[var(--ink)]">{c.nome}</td>
                  <td className="px-3 py-2 text-[var(--muted)]">{c.categoria}</td>
                  <td className="px-3 py-2 text-[var(--muted)]">{c.gestor ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-[var(--muted)]">{c.id_google_ads ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-[var(--muted)]">{c.id_meta_ads ?? "—"}</td>
                  <td className="px-3 py-2 font-mono text-[var(--muted)]">{c.id_ga4 ?? "—"}</td>
                  <td className="px-3 py-2">
                    <div className="flex items-center gap-2">
                      <button onClick={() => openEdit(c)} className="rounded border border-[var(--rule-soft)] px-2 py-1 text-xs text-[var(--muted)] transition hover:border-[var(--forest)] hover:text-[var(--forest)]">Editar</button>
                      <button onClick={() => openDelete(c)} className="rounded border border-[var(--rule-soft)] px-2 py-1 text-xs text-[var(--muted)] transition hover:border-[var(--crimson)] hover:text-[var(--crimson)]">Desativar</button>
                    </div>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
    </>
  );

  // Sub-aba: Gestores — lista unificada (clientes + cadastro)
  const todosNomes = Array.from(
    new Set([
      ...todosClientes.map((c) => c.gestor).filter((g): g is string => !!g),
      ...gestoresCadastrados.map((g) => g.nome),
    ])
  ).sort();

  const mergedGestores = todosNomes.map((nome) => {
    const cadastro = gestoresCadastrados.find((g) => g.nome === nome) ?? null;
    const count = todosClientes.filter((c) => c.gestor === nome).length;
    return { nome, squad: cadastro?.squad ?? null, cadastroId: cadastro?.id ?? null, count };
  });

  const subGestores = (
    <>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-2xl font-medium text-[var(--ink)]">Gestores</h1>
        <div className="flex items-center gap-3">
          {normalizeMsg && <span className="text-xs text-[var(--muted)]">{normalizeMsg}</span>}
          <button onClick={handleNormalizar} disabled={normalizing} className="rounded-md border border-[var(--rule-soft)] px-3 py-1.5 text-xs text-[var(--muted)] transition hover:border-[var(--forest)] hover:text-[var(--forest)] disabled:opacity-50">
            {normalizing ? "Normalizando…" : "Normalizar capitalização"}
          </button>
          <button onClick={() => { setAddingGestor(true); setSaveGestorErr(null); }} className="rounded-md bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90">
            + Adicionar gestor
          </button>
        </div>
      </div>

      {addingGestor && (
        <div className="mb-4 rounded-lg border border-[var(--forest)]/40 bg-[var(--paper-soft)] p-4">
          <form onSubmit={handleAddGestorCadastrado} className="flex items-end gap-3">
            <label className="flex flex-1 flex-col gap-1">
              <span className="eyebrow text-xs text-[var(--muted)]">Nome<span className="ml-0.5 text-[var(--crimson)]">*</span></span>
              <input autoFocus type="text" value={newGestorNome} onChange={(e) => setNewGestorNome(e.target.value)} placeholder="Nome do gestor"
                className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]" required />
            </label>
            <label className="flex flex-1 flex-col gap-1">
              <span className="eyebrow text-xs text-[var(--muted)]">Squad</span>
              <input type="text" value={newGestorSquad} onChange={(e) => setNewGestorSquad(e.target.value)} placeholder="Ex: Growth"
                className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]" />
            </label>
            <button type="submit" disabled={savingGestor || !newGestorNome.trim()} className="rounded-md bg-[var(--forest)] px-4 py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50">
              {savingGestor ? "Adicionando…" : "Adicionar"}
            </button>
            <button type="button" onClick={() => { setAddingGestor(false); setSaveGestorErr(null); setNewGestorNome(""); setNewGestorSquad(""); }}
              className="rounded-md border border-[var(--rule-soft)] px-4 py-2 text-sm text-[var(--muted)] transition hover:border-[var(--ink)] hover:text-[var(--ink)]">Cancelar</button>
          </form>
          {saveGestorErr && <p className="mt-2 text-xs text-[var(--crimson)]">{saveGestorErr}</p>}
        </div>
      )}

      {mergedGestores.length === 0 ? (
        <div className="rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] py-8 text-center">
          <p className="text-sm text-[var(--muted)]">Nenhum gestor encontrado.</p>
        </div>
      ) : (
        <div className="overflow-hidden rounded-lg border border-[var(--rule-soft)]">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-[var(--rule-soft)] bg-[var(--paper-soft)]">
                <th className="px-3 py-2 text-left font-medium text-[var(--muted)]">Nome</th>
                <th className="px-3 py-2 text-left font-medium text-[var(--muted)]">Squad</th>
                <th className="px-3 py-2 text-left font-medium text-[var(--muted)]">Clientes</th>
                <th className="px-3 py-2" />
              </tr>
            </thead>
            <tbody>
              {mergedGestores.map(({ nome, squad, cadastroId, count }, idx) => {
                const isRenaming = renomeandoGestor === nome;
                return (
                  <tr key={nome} className={idx % 2 === 0 ? "bg-[var(--paper-soft)]" : "bg-[var(--paper)]"}>
                    {isRenaming ? (
                      <td colSpan={4} className="px-3 py-2">
                        <form onSubmit={handleRenomearGestor} className="flex items-center gap-2">
                          <input autoFocus type="text" value={novoNomeGestor} onChange={(e) => setNovoNomeGestor(e.target.value)}
                            className="flex-1 rounded-md border border-[var(--forest)] bg-[var(--paper)] px-3 py-1.5 text-sm text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]" />
                          {renameGestorErr && <span className="text-xs text-[var(--crimson)]">{renameGestorErr}</span>}
                          <button type="submit" disabled={renamingGestor || !novoNomeGestor.trim()}
                            className="rounded-md bg-[var(--forest)] px-3 py-1.5 text-xs font-medium text-white transition hover:opacity-90 disabled:opacity-50">
                            {renamingGestor ? "Salvando…" : "Salvar"}
                          </button>
                          <button type="button" onClick={() => { setRenomeandoGestor(null); setRenameGestorErr(null); }}
                            className="rounded-md border border-[var(--rule-soft)] px-3 py-1.5 text-xs text-[var(--muted)] transition hover:text-[var(--ink)]">Cancelar</button>
                        </form>
                      </td>
                    ) : (
                      <>
                        <td className="px-3 py-2.5 font-medium text-[var(--ink)]">{nome}</td>
                        <td className="px-3 py-2.5 text-[var(--muted)]">{squad ?? "—"}</td>
                        <td className="px-3 py-2.5 text-[var(--muted)]">{count}</td>
                        <td className="px-3 py-2.5">
                          <div className="flex items-center justify-end gap-2">
                            <button onClick={() => { setRenomeandoGestor(nome); setNovoNomeGestor(nome); setRenameGestorErr(null); }}
                              className="rounded border border-[var(--rule-soft)] px-2 py-1 text-xs text-[var(--muted)] transition hover:border-[var(--forest)] hover:text-[var(--forest)]">Renomear</button>
                            {cadastroId && (
                              <button onClick={() => handleRemoveGestorCadastrado(cadastroId)} disabled={removingGestorId === cadastroId}
                                className="rounded border border-[var(--rule-soft)] px-2 py-1 text-xs text-[var(--muted)] transition hover:border-[var(--crimson)] hover:text-[var(--crimson)] disabled:opacity-50">
                                {removingGestorId === cadastroId ? "Removendo…" : "Remover"}
                              </button>
                            )}
                          </div>
                        </td>
                      </>
                    )}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </>
  );

  return (
    <div className="pb-24">
      {configTab === "config-clientes" && subClientes}
      {configTab === "config-gestores" && subGestores}

      {/* Modais — sempre montados para não perder estado */}
      {editando && editForm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-lg border border-[var(--rule-soft)] bg-[var(--paper)] p-6 shadow-xl">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-display text-lg font-medium text-[var(--ink)]">Editar — {editando.nome}</h2>
              <button type="button" onClick={() => setEditando(null)} className="text-sm text-[var(--muted)] transition hover:text-[var(--ink)]">✕</button>
            </div>
            <form onSubmit={handleSalvar} className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                {renderField("Nome", editForm!.nome, (v) => setEditForm((f) => f && { ...f, nome: v }))}
                {renderField("Categoria", editForm!.categoria, (v) => setEditForm((f) => f && { ...f, categoria: v }), "select")}
                {renderField("Gestor", editForm!.gestor, (v) => setEditForm((f) => f && { ...f, gestor: v }))}
                {renderField("ID Google Ads", editForm!.id_google_ads, (v) => setEditForm((f) => f && { ...f, id_google_ads: v }))}
                {renderField("ID Meta Ads", editForm!.id_meta_ads, (v) => setEditForm((f) => f && { ...f, id_meta_ads: v }))}
                {renderField("ID GA4", editForm!.id_ga4, (v) => setEditForm((f) => f && { ...f, id_ga4: v }))}
              </div>
              {renderField("Link Painel de Controle", editForm!.painel_url, (v) => setEditForm((f) => f && { ...f, painel_url: v }))}
              {renderField("Link Pasta", editForm!.pasta_url, (v) => setEditForm((f) => f && { ...f, pasta_url: v }))}
              {saveErr && <p className="text-xs text-[var(--crimson)]">{saveErr}</p>}
              <div className="mt-1 flex gap-3">
                <button type="submit" disabled={saving} className="flex-1 rounded-md bg-[var(--forest)] py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50">{saving ? "Salvando…" : "Salvar"}</button>
                <button type="button" onClick={() => setEditando(null)} className="flex-1 rounded-md border border-[var(--rule-soft)] py-2 text-sm text-[var(--muted)] transition hover:border-[var(--ink)] hover:text-[var(--ink)]">Cancelar</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {criando && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-lg rounded-lg border border-[var(--rule-soft)] bg-[var(--paper)] p-6 shadow-xl">
            <div className="mb-5 flex items-center justify-between">
              <h2 className="font-display text-lg font-medium text-[var(--ink)]">Novo cliente</h2>
              <button type="button" onClick={() => setCriando(false)} className="text-sm text-[var(--muted)] transition hover:text-[var(--ink)]">✕</button>
            </div>
            <form onSubmit={handleCriar} className="flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-3">
                {renderField("Nome", criarForm.nome, (v) => setCriarForm((f) => ({ ...f, nome: v })), "text", true)}
                {renderField("Categoria", criarForm.categoria, (v) => setCriarForm((f) => ({ ...f, categoria: v })), "select", true)}
                {renderField("Gestor", criarForm.gestor, (v) => setCriarForm((f) => ({ ...f, gestor: v })))}
                {renderField("ID Google Ads", criarForm.id_google_ads, (v) => setCriarForm((f) => ({ ...f, id_google_ads: v })))}
                {renderField("ID Meta Ads", criarForm.id_meta_ads, (v) => setCriarForm((f) => ({ ...f, id_meta_ads: v })))}
                {renderField("ID GA4", criarForm.id_ga4, (v) => setCriarForm((f) => ({ ...f, id_ga4: v })))}
              </div>
              {renderField("Link Painel de Controle", criarForm.painel_url, (v) => setCriarForm((f) => ({ ...f, painel_url: v })))}
              {renderField("Link Pasta", criarForm.pasta_url, (v) => setCriarForm((f) => ({ ...f, pasta_url: v })))}
              {createErr && <p className="text-xs text-[var(--crimson)]">{createErr}</p>}
              <div className="mt-1 flex gap-3">
                <button type="submit" disabled={creating || !criarForm.nome.trim()} className="flex-1 rounded-md bg-[var(--forest)] py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50">{creating ? "Criando…" : "Criar cliente"}</button>
                <button type="button" onClick={() => setCriando(false)} className="flex-1 rounded-md border border-[var(--rule-soft)] py-2 text-sm text-[var(--muted)] transition hover:border-[var(--ink)] hover:text-[var(--ink)]">Cancelar</button>
              </div>
            </form>
          </div>
        </div>
      )}

      {deletando && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
          <div className="w-full max-w-sm rounded-lg border border-[var(--rule-soft)] bg-[var(--paper)] p-6 shadow-xl">
            <h2 className="font-display text-lg font-medium text-[var(--ink)]">Desativar cliente</h2>
            <p className="mt-2 text-sm text-[var(--ink-soft)]">
              Deseja desativar <strong>{deletando.nome}</strong>? O cliente não aparecerá mais nas listas, mas os dados históricos serão preservados.
            </p>
            {deleteErr && <p className="mt-2 text-xs text-[var(--crimson)]">{deleteErr}</p>}
            <div className="mt-4 flex gap-3">
              <button onClick={handleDesativar} disabled={deleting} className="flex-1 rounded-md bg-[var(--crimson,#c0392b)] py-2 text-sm font-medium text-white transition hover:opacity-90 disabled:opacity-50">{deleting ? "Desativando…" : "Desativar"}</button>
              <button onClick={() => setDeletando(null)} className="flex-1 rounded-md border border-[var(--rule-soft)] py-2 text-sm text-[var(--muted)] transition hover:border-[var(--ink)] hover:text-[var(--ink)]">Cancelar</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ── Página principal ──────────────────────────────────────────────────────────
export default function GestorDashboard() {
  const [user, setUser] = useState<UsuarioInfo | null>(null);
  const [clientes, setClientes] = useState<ClienteGestor[]>([]);
  const [jobs, setJobs] = useState<JobInfo[]>([]);
  const [metricas, setMetricas] = useState<MetricasDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingJobs, setLoadingJobs] = useState(true);
  const [loadingMetricas, setLoadingMetricas] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [tab, setTab] = useState<Tab>("dashboard");
  const [reportesTab, setReportesTab] = useState<ReportesTab>("reportes-clientes");
  const [configTab, setConfigTab] = useState<ConfigTab>("config-clientes");

  // Gestor filter — derived from client list (field comes from the central sheet)
  const [gestorFiltro, setGestorFiltro] = useState<string>("");

  useEffect(() => {
    Promise.all([gestorApi.me(), gestorApi.clientes()])
      .then(([u, c]) => { setUser(u); setClientes(c.items); })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));

    gestorApi.listJobs().then(setJobs).catch(console.error).finally(() => setLoadingJobs(false));
    gestorApi.metricas().then(setMetricas).catch(console.error).finally(() => setLoadingMetricas(false));
  }, []);

  // Unique gestor names from the loaded clients list
  const gestores: string[] = Array.from(
    new Set(clientes.map((c) => c.gestor).filter((g): g is string => !!g))
  ).sort();

  // Filtered client list and slug set for dashboard
  const clientesFiltrados = gestorFiltro
    ? clientes.filter((c) => c.gestor === gestorFiltro)
    : clientes;

  const slugsFiltro: Set<string> | null = gestorFiltro
    ? new Set(clientesFiltrados.map((c) => c.slug))
    : null;

  async function handleLogout() {
    await gestorApi.logout();
    window.location.href = "/gestor/login";
  }

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen">
      <Sidebar tab={tab} setTab={setTab} reportesTab={reportesTab} setReportesTab={setReportesTab} configTab={configTab} setConfigTab={setConfigTab} user={user} onLogout={handleLogout} />
      <main className="flex-1 overflow-y-auto">
        <div className="flex items-center justify-between border-b border-[var(--rule-soft)] bg-[var(--paper-soft)] px-8 py-4">
          <p className="text-xs text-[var(--muted)]">
            {NAV_ITEMS.find((n) => n.id === tab)?.label}
            {gestorFiltro && (
              <span className="ml-2 text-[var(--forest)]">
                · {gestorFiltro}
                {" "}({clientesFiltrados.length} cliente{clientesFiltrados.length !== 1 ? "s" : ""})
              </span>
            )}
          </p>
          {gestores.length > 0 && (
            <GestorFiltro
              gestores={gestores}
              value={gestorFiltro}
              onChange={setGestorFiltro}
            />
          )}
        </div>
        <div className="px-8 py-8">
          {erro && <p className="mb-6 text-sm text-[var(--crimson)]">{erro}</p>}
          {tab === "reportes" && reportesTab === "reportes-clientes" && <AbaClientes clientes={clientesFiltrados} />}
          {tab === "reportes" && reportesTab === "reportes-meus"     && <AbaMeusReports jobs={jobs} loading={loadingJobs} />}
          {tab === "dashboard"     && (
            <AbaDashboard
              clientes={clientesFiltrados}
              jobs={jobs}
              loadingJobs={loadingJobs}
              metricas={metricas}
              loadingMetricas={loadingMetricas}
              slugsFiltro={slugsFiltro}
            />
          )}
          {tab === "configuracoes" && (
            <AbaConfiguracoes
              clientes={clientesFiltrados}
              todosClientes={clientes}
              configTab={configTab}
              onClienteUpdated={(updated) =>
                setClientes((prev) => prev.map((c) => (c.id === updated.id ? updated : c)))
              }
              onClienteDeleted={(id) =>
                setClientes((prev) => prev.filter((c) => c.id !== id))
              }
              onClienteCriado={(novo) =>
                setClientes((prev) => [...prev, novo].sort((a, b) => a.nome.localeCompare(b.nome)))
              }
              onGestorRenomeado={(de, para) =>
                setClientes((prev) => prev.map((c) => c.gestor === de ? { ...c, gestor: para } : c))
              }
              onGestoresNormalizados={(mapeamento) =>
                setClientes((prev) => {
                  const map = new Map(mapeamento.map(({ de, para }) => [de, para]));
                  return prev.map((c) => ({ ...c, gestor: c.gestor ? (map.get(c.gestor) ?? c.gestor) : c.gestor }));
                })
              }
            />
          )}
        </div>
      </main>
    </div>
  );
}
