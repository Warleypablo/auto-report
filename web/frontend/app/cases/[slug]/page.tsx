import Link from "next/link";
import { notFound } from "next/navigation";

import { CaseMark } from "@/components/CaseMark";
import { EvolutionChart } from "@/components/EvolutionChart";
import { FontDetail } from "@/components/FontDetail";
import { MetricGrid } from "@/components/MetricGrid";
import { getCase } from "@/lib/api";

export const revalidate = 3600;

export default async function CaseDetailPage({
  params,
}: {
  params: { slug: string };
}) {
  let detail;
  try {
    detail = await getCase(params.slug);
  } catch {
    notFound();
  }

  const periodo = new Date(detail.periodo_fim).toLocaleDateString("pt-BR", {
    month: "long",
    year: "numeric",
  });

  return (
    <main className="mx-auto max-w-[1320px] px-8">
      {/* Breadcrumb */}
      <div className="border-b border-[var(--rule-soft)] py-5 text-sm">
        <Link
          href="/"
          className="text-[var(--muted)] underline decoration-[var(--rule-soft)] underline-offset-4 hover:text-[var(--ink)] hover:decoration-[var(--ink)]"
        >
          ← Voltar à vitrine
        </Link>
      </div>

      {/* ───── Hero do case ───── */}
      <section className="grid gap-10 pb-12 pt-16 md:grid-cols-12">
        <div className="md:col-span-8">
          <div className="flex items-center gap-4">
            <span className="eyebrow">Estudo de caso</span>
            <span className="block h-px w-12 bg-[var(--rule-soft)]" />
            <span className="eyebrow">{detail.categoria}</span>
          </div>

          <h1 className="font-display mt-5 text-[clamp(2.75rem,6vw,5rem)] font-medium leading-[0.95] tracking-tight">
            {detail.nome}
          </h1>

          {detail.descricao_publica && (
            <p className="mt-6 max-w-2xl font-display text-xl leading-snug text-[var(--ink-soft)]">
              {detail.descricao_publica}
            </p>
          )}

          <dl className="mt-10 grid max-w-xl grid-cols-3 gap-px bg-[var(--rule-soft)]">
            <div className="bg-[var(--paper)] p-4">
              <dt className="eyebrow">Setor</dt>
              <dd className="font-mono-num mt-2 text-sm text-[var(--ink)]">
                {detail.setor ?? "—"}
              </dd>
            </div>
            <div className="bg-[var(--paper)] p-4">
              <dt className="eyebrow">Porte</dt>
              <dd className="font-mono-num mt-2 text-sm text-[var(--ink)]">
                {detail.porte ?? "—"}
              </dd>
            </div>
            <div className="bg-[var(--paper)] p-4">
              <dt className="eyebrow">Referência</dt>
              <dd className="font-mono-num mt-2 text-sm capitalize text-[var(--ink)]">
                {periodo}
              </dd>
            </div>
          </dl>
        </div>

        <aside className="md:col-span-4">
          <div className="flex h-full flex-col justify-between border-l border-[var(--rule-soft)] pl-8">
            <CaseMark slug={detail.slug} size={120} />
            <div>
              <p className="eyebrow">Atualizado</p>
              <p className="font-mono-num mt-2 text-sm text-[var(--ink)]">
                {new Date(detail.data_coleta).toLocaleString("pt-BR", {
                  day: "2-digit",
                  month: "short",
                  year: "numeric",
                  hour: "2-digit",
                  minute: "2-digit",
                })}
              </p>
            </div>
          </div>
        </aside>
      </section>

      {/* ───── Métricas ───── */}
      <section className="border-t border-[var(--rule)] pt-12">
        <div className="flex items-end justify-between pb-6">
          <div>
            <p className="eyebrow">Seção I</p>
            <h2 className="font-display mt-1 text-3xl tracking-tight">
              Performance no mês fechado
            </h2>
          </div>
          <span className="hidden font-mono-num text-xs text-[var(--muted)] md:inline">
            Período: {periodo}
          </span>
        </div>
        <MetricGrid snapshot={detail} />
      </section>

      {/* ───── Evolução ───── */}
      {detail.evolucao.length > 1 && (
        <section className="mt-20">
          <div className="flex items-end justify-between border-b border-[var(--rule)] pb-5">
            <div>
              <p className="eyebrow">Seção II</p>
              <h2 className="font-display mt-1 text-3xl tracking-tight">
                Evolução do faturamento
              </h2>
            </div>
            <span className="hidden text-xs text-[var(--muted)] md:inline">
              últimos {detail.evolucao.length} meses
            </span>
          </div>
          <div className="mt-8 border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-6">
            <EvolutionChart pontos={detail.evolucao} />
          </div>
        </section>
      )}

      {/* ───── Por fonte ───── */}
      <FontDetail detalhes={detail.metricas_detalhadas} />

      {/* Nav fim */}
      <div className="mt-20 border-t border-[var(--rule)] py-8">
        <Link
          href="/"
          className="font-display text-2xl tracking-tight text-[var(--ink)] underline decoration-[var(--rule-soft)] underline-offset-8 hover:decoration-[var(--ink)]"
        >
          Ver outros cases →
        </Link>
      </div>
    </main>
  );
}
