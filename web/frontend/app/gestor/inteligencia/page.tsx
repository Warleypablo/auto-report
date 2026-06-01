"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { gestorApi } from "@/lib/api-gestor";
import type { InteligenciaAlerta, InteligenciaResponse } from "@/lib/api-gestor";
import { deslocarMes, mesUltimoFechado } from "@/lib/mes-utils";

function mesLabel(mes: string): string {
  const [ano, m] = mes.split("-");
  const nomes = ["Jan","Fev","Mar","Abr","Mai","Jun","Jul","Ago","Set","Out","Nov","Dez"];
  return `${nomes[parseInt(m) - 1]} ${ano}`;
}

const SEV_CONFIG = {
  critico:      { label: "Crítico",      dot: "bg-[var(--crimson)]", text: "text-[var(--crimson)]", badge: "border border-[var(--crimson)]/30 bg-[var(--crimson)]/15 text-[var(--crimson)]" },
  atencao:      { label: "Atenção",      dot: "bg-[var(--amber)]",   text: "text-[var(--amber)]",   badge: "border border-[var(--amber)]/30 bg-[var(--amber)]/15 text-[var(--amber)]" },
  oportunidade: { label: "Oportunidade", dot: "bg-[var(--forest)]",  text: "text-[var(--forest)]",  badge: "border border-[var(--forest)]/30 bg-[var(--forest)]/15 text-[var(--forest)]" },
} as const;

function SeveridadeBadge({ sev }: { sev: InteligenciaAlerta["severidade"] }) {
  const cfg = SEV_CONFIG[sev];
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[10px] font-medium ${cfg.badge}`}>
      <span className={`h-1.5 w-1.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}

function AlertaCard({ alerta }: { alerta: InteligenciaAlerta }) {
  const router = useRouter();
  const sinal_principal = alerta.sinais[0];

  return (
    <div
      onClick={() => router.push(`/gestor/${alerta.cliente_slug}`)}
      className="cursor-pointer rounded-lg border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4 transition hover:bg-[var(--paper-deep)]"
    >
      <div className="mb-2 flex items-start justify-between gap-3">
        <div>
          <p className="text-sm font-medium text-[var(--ink)]">{alerta.cliente_nome}</p>
          <p className="text-xs text-[var(--muted)]">{alerta.cliente_categoria}</p>
        </div>
        <SeveridadeBadge sev={alerta.severidade} />
      </div>

      {sinal_principal && (
        <p className="mb-1.5 text-xs font-medium text-[var(--ink-soft)]">
          {sinal_principal.titulo}
          <span className="ml-2 font-mono text-[var(--ink)]">{sinal_principal.metrica_principal}</span>
        </p>
      )}

      {alerta.sinais.length > 1 && (
        <p className="mb-1.5 text-[10px] text-[var(--muted)]">
          +{alerta.sinais.length - 1} sinal{alerta.sinais.length > 2 ? "is" : ""} adicional{alerta.sinais.length > 2 ? "is" : ""}
        </p>
      )}

      {alerta.narrativa && (
        <p className="line-clamp-3 text-xs leading-relaxed text-[var(--muted)]">
          {alerta.narrativa}
        </p>
      )}
    </div>
  );
}

export default function InteligenciaPage() {
  const [mes, setMes] = useState(mesUltimoFechado());
  const [loading, setLoading] = useState(true);
  const [data, setData] = useState<InteligenciaResponse | null>(null);

  const mesOpcoes = useMemo(
    () => Array.from({ length: 12 }, (_, i) => deslocarMes(mesUltimoFechado(), -i)),
    [],
  );

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    gestorApi
      .inteligencia(mes)
      .then((res) => { if (!cancelled) setData(res); })
      .catch(() => { if (!cancelled) setData(null); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [mes]);

  const alertas = data?.alertas ?? [];
  const n_critico = alertas.filter((a) => a.severidade === "critico").length;
  const n_atencao = alertas.filter((a) => a.severidade === "atencao").length;
  const n_oportunidade = alertas.filter((a) => a.severidade === "oportunidade").length;

  return (
    <main className="mx-auto max-w-3xl px-6 py-12">
      <Link
        href="/gestor"
        className="mb-6 block text-xs text-[var(--muted)] transition hover:text-[var(--ink)]"
      >
        ← Seus clientes
      </Link>

      <div className="mb-6 flex items-baseline justify-between gap-4">
        <h1 className="font-display text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
          Inteligência
        </h1>
        <div className="flex items-center gap-2">
          <label htmlFor="mes-ref" className="text-xs text-[var(--muted)]">Mês:</label>
          <select
            id="mes-ref"
            value={mes}
            onChange={(e) => setMes(e.target.value)}
            className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-1.5 text-xs text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          >
            {mesOpcoes.map((m) => (
              <option key={m} value={m}>{mesLabel(m)}</option>
            ))}
          </select>
        </div>
      </div>

      {!loading && data && alertas.length > 0 && (
        <div className="mb-6 flex gap-3">
          {n_critico > 0 && (
            <span className="rounded-full border border-[var(--crimson)]/30 bg-[var(--crimson)]/15 px-3 py-1 text-xs font-medium text-[var(--crimson)]">
              {n_critico} crítico{n_critico > 1 ? "s" : ""}
            </span>
          )}
          {n_atencao > 0 && (
            <span className="rounded-full border border-[var(--amber)]/30 bg-[var(--amber)]/15 px-3 py-1 text-xs font-medium text-[var(--amber)]">
              {n_atencao} atenção
            </span>
          )}
          {n_oportunidade > 0 && (
            <span className="rounded-full border border-[var(--forest)]/30 bg-[var(--forest)]/15 px-3 py-1 text-xs font-medium text-[var(--forest)]">
              {n_oportunidade} oportunidade{n_oportunidade > 1 ? "s" : ""}
            </span>
          )}
        </div>
      )}

      {loading ? (
        <p className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-12 text-center text-sm text-[var(--muted)]">
          Carregando…
        </p>
      ) : alertas.length === 0 ? (
        <div className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-8 text-center">
          <p className="text-sm text-[var(--ink)]">Nenhum insight gerado para este período.</p>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Acesse o painel de administração para gerar os insights deste mês.
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {alertas.map((alerta) => (
            <AlertaCard key={alerta.cliente_slug} alerta={alerta} />
          ))}
        </div>
      )}
    </main>
  );
}
