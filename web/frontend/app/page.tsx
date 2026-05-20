import { CaseCard } from "@/components/CaseCard";
import { Filters } from "@/components/Filters";
import { AggregateStats } from "@/components/AggregateStats";
import { listCases } from "@/lib/api";

export const revalidate = 3600;

type SearchParams = {
  categoria?: string;
  order_by?: "roas" | "faturamento" | "crescimento";
};

export default async function HomePage({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const [data, dataAll] = await Promise.all([
    listCases({
      categoria: searchParams.categoria,
      orderBy: searchParams.order_by ?? "faturamento",
      limit: 50,
    }),
    listCases({ limit: 200 }),
  ]);

  const hoje = new Date();
  const edicao = hoje
    .toLocaleDateString("pt-BR", { month: "long", year: "numeric" })
    .toUpperCase();

  return (
    <main className="mx-auto max-w-[1320px] px-8">
      {/* ───── Hero editorial ───── */}
      <section className="grid gap-12 pb-16 pt-16 md:grid-cols-12 md:pt-24">
        <div className="md:col-span-8">
          <div className="flex items-center gap-4 text-[var(--muted)]">
            <span className="eyebrow">Vol. I · Ed. {edicao}</span>
            <span className="block h-px w-12 bg-[var(--rule-soft)]" />
            <span className="eyebrow">Performance Reports</span>
          </div>

          <h1 className="font-display mt-6 text-[clamp(3rem,7vw,6.5rem)] font-medium leading-[0.92] tracking-tight text-[var(--ink)]">
            Números <em className="not-italic text-[var(--forest)]">medidos</em>,
            <br />
            não promessas.
          </h1>

          <p className="mt-8 max-w-xl text-lg leading-relaxed text-[var(--ink-soft)]">
            Cada case abaixo vem direto das contas de Meta Ads, Google Ads e GA4
            dos nossos clientes. Sem maquiagem. Sem print bonito de WhatsApp.
            Apenas o desempenho real, atualizado diariamente.
          </p>

          <div className="mt-10 flex flex-wrap items-center gap-4 text-sm text-[var(--ink-soft)]">
            <a
              href="#cases"
              className="border border-[var(--ink)] bg-[var(--ink)] px-5 py-3 font-medium text-[var(--paper)] transition-colors hover:bg-[var(--forest-deep)]"
            >
              Ver vitrine
            </a>
            <a
              href="#metodologia"
              className="border border-[var(--rule-soft)] px-5 py-3 transition-colors hover:border-[var(--ink)]"
            >
              Metodologia
            </a>
          </div>
        </div>

        {/* Right side — agregados / colofão */}
        <aside className="md:col-span-4">
          <div className="border-l border-[var(--rule-soft)] pl-8">
            <p className="eyebrow">Nesta edição</p>
            <p className="font-display mt-2 text-3xl tracking-tight">
              {dataAll.total} {dataAll.total === 1 ? "case" : "cases"}{" "}
              publicados
            </p>
            <p className="mt-4 text-sm leading-relaxed text-[var(--muted)]">
              Cobertura: e-commerce, geração de leads e marcas sem site
              próprio. Períodos mensais fechados, atualizados a cada manhã pelo
              ETL.
            </p>
            <dl className="mt-8 grid grid-cols-2 gap-y-5 text-sm">
              <dt className="text-[var(--muted)]">Verticais</dt>
              <dd className="font-mono-num text-right text-[var(--ink)]">
                {new Set(dataAll.items.map((i) => i.setor).filter(Boolean)).size}
              </dd>
              <dt className="text-[var(--muted)]">E-commerce</dt>
              <dd className="font-mono-num text-right text-[var(--ink)]">
                {dataAll.items.filter((i) => i.categoria === "E-commerce").length}
              </dd>
              <dt className="text-[var(--muted)]">Lead generation</dt>
              <dd className="font-mono-num text-right text-[var(--ink)]">
                {dataAll.items.filter((i) => i.categoria !== "E-commerce").length}
              </dd>
            </dl>
          </div>
        </aside>
      </section>

      {/* ───── Wall of numbers ───── */}
      <AggregateStats items={dataAll.items} />

      {/* ───── Vitrine ───── */}
      <section id="cases" className="pt-24">
        <div className="flex items-end justify-between border-b border-[var(--rule)] pb-6">
          <div>
            <p className="eyebrow">Seção II</p>
            <h2 className="font-display mt-1 text-4xl tracking-tight text-[var(--ink)]">
              Cases em destaque
            </h2>
          </div>
          <p className="hidden text-xs text-[var(--muted)] md:block">
            {data.total} {data.total === 1 ? "case" : "cases"} encontrados
          </p>
        </div>

        <div className="mt-8">
          <Filters />
        </div>

        {data.items.length === 0 ? (
          <div className="border border-dashed border-[var(--rule-soft)] py-24 text-center">
            <p className="font-display text-2xl text-[var(--muted)]">
              Nenhum case encontrado.
            </p>
            <p className="mt-2 text-sm text-[var(--muted)]">
              Ajuste os filtros para ver mais cases.
            </p>
          </div>
        ) : (
          <div className="mt-8 grid gap-px bg-[var(--rule-soft)] sm:grid-cols-2 lg:grid-cols-3">
            {data.items.map((item, i) => (
              <CaseCard key={item.slug} item={item} index={i} />
            ))}
          </div>
        )}
      </section>

      {/* ───── Metodologia ───── */}
      <section
        id="metodologia"
        className="mt-32 border-t border-[var(--rule)] py-16"
      >
        <div className="grid gap-12 md:grid-cols-12">
          <div className="md:col-span-4">
            <p className="eyebrow">Seção III</p>
            <h2 className="font-display mt-1 text-3xl tracking-tight">
              Como medimos
            </h2>
          </div>
          <div className="grid gap-10 md:col-span-8 md:grid-cols-2">
            {[
              {
                t: "Direto das fontes",
                d: "Toda métrica é extraída via API de Meta Ads, Google Ads e GA4. Nada é editado a mão — o ETL roda diariamente e sobrescreve.",
              },
              {
                t: "Período fechado",
                d: "Comparamos o mês fechado mais recente contra os 5 meses anteriores. A variação % mostrada é mês-contra-mês.",
              },
              {
                t: "Opt-in explícito",
                d: "Cada cliente que aparece autorizou a publicação dos seus números. Quem revoga sai da vitrine em até 1 hora.",
              },
              {
                t: "Sem cherry-picking",
                d: "Mostramos o mês fechado mais recente, não o melhor mês. ROAS e faturamento são absolutos, sem filtros.",
              },
            ].map((b) => (
              <div key={b.t}>
                <h3 className="font-display text-xl tracking-tight">{b.t}</h3>
                <p className="mt-2 text-sm leading-relaxed text-[var(--ink-soft)]">
                  {b.d}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </main>
  );
}
