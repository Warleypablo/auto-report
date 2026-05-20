import { CaseCard } from "@/components/CaseCard";
import { Filters } from "@/components/Filters";
import { listCases } from "@/lib/api";

export const revalidate = 3600;

type SearchParams = {
  categoria?: string;
  order_by?: "roas" | "faturamento" | "crescimento";
};

export default async function HomePage({ searchParams }: { searchParams: SearchParams }) {
  const data = await listCases({
    categoria: searchParams.categoria,
    orderBy: searchParams.order_by ?? "faturamento",
    limit: 50,
  });

  return (
    <main className="mx-auto max-w-7xl px-6 py-16">
      <header className="mb-12 max-w-3xl">
        <h1 className="text-4xl font-bold tracking-tight text-neutral-900 sm:text-5xl">
          Cases de sucesso
        </h1>
        <p className="mt-4 text-lg text-neutral-600">
          Resultados reais dos nossos clientes em mídia paga, analytics e
          e-commerce — números medidos, não promessas.
        </p>
      </header>

      <Filters />

      {data.items.length === 0 ? (
        <p className="text-neutral-500">
          Nenhum case encontrado para os filtros selecionados.
        </p>
      ) : (
        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {data.items.map((item) => (
            <CaseCard key={item.slug} item={item} />
          ))}
        </div>
      )}
    </main>
  );
}
