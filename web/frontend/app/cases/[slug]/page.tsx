import { notFound } from "next/navigation";

import { EvolutionChart } from "@/components/EvolutionChart";
import { FontDetail } from "@/components/FontDetail";
import { MetricGrid } from "@/components/MetricGrid";
import { getCase } from "@/lib/api";

export const revalidate = 3600;

export default async function CaseDetailPage({ params }: { params: { slug: string } }) {
  let detail;
  try {
    detail = await getCase(params.slug);
  } catch {
    notFound();
  }

  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <header className="mb-12 flex flex-col gap-6 sm:flex-row sm:items-center">
        {detail.logo_url ? (
          <img
            src={detail.logo_url}
            alt={detail.nome}
            className="h-20 w-20 rounded object-contain"
          />
        ) : (
          <div className="flex h-20 w-20 items-center justify-center rounded bg-neutral-100 text-xl font-bold text-neutral-500">
            {detail.nome.slice(0, 2).toUpperCase()}
          </div>
        )}
        <div>
          <h1 className="text-3xl font-bold text-neutral-900">{detail.nome}</h1>
          <p className="mt-1 text-sm text-neutral-500">
            {detail.categoria}
            {detail.setor ? ` · ${detail.setor}` : ""}
            {detail.porte ? ` · ${detail.porte}` : ""}
          </p>
          {detail.descricao_publica && (
            <p className="mt-3 max-w-2xl text-neutral-700">{detail.descricao_publica}</p>
          )}
        </div>
      </header>

      <section>
        <h2 className="mb-6 text-xl font-bold text-neutral-900">Métricas do último mês</h2>
        <MetricGrid snapshot={detail} />
      </section>

      <section className="mt-12">
        <h2 className="mb-6 text-xl font-bold text-neutral-900">Evolução dos últimos meses</h2>
        <EvolutionChart pontos={detail.evolucao} />
      </section>

      <FontDetail detalhes={detail.metricas_detalhadas} />
    </main>
  );
}
