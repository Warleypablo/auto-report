import { ClientesTable } from "@/components/ClientesTable";
import { listAllClientes } from "@/lib/api-internal";

export const dynamic = "force-dynamic";

export default async function ListaPage() {
  const data = await listAllClientes();

  const publicos = data.items.filter((i) => i.publicar_vitrine).length;
  const privados = data.total - publicos;
  const periodo = data.items.find((i) => i.periodo_fim)?.periodo_fim;

  return (
    <main className="mx-auto max-w-[1440px] px-8">
      <section className="grid gap-10 pb-8 pt-16 md:grid-cols-12">
        <div className="md:col-span-8">
          <div className="flex items-center gap-4 text-[var(--muted)]">
            <span className="eyebrow">Painel interno</span>
            <span className="block h-px w-12 bg-[var(--rule-soft)]" />
            <span className="eyebrow">Acesso restrito</span>
          </div>
          <h1 className="font-display mt-5 text-[clamp(2.5rem,5vw,4.5rem)] font-medium leading-[0.95] tracking-tight">
            Lista completa de clientes
          </h1>
          <p className="mt-5 max-w-2xl text-base leading-relaxed text-[var(--ink-soft)]">
            Inclui todos os clientes na base, sejam ou não publicados na
            vitrine. Cabeçalhos da tabela são clicáveis para ordenar; use os
            filtros para isolar segmentos.
          </p>
        </div>

        <aside className="md:col-span-4">
          <div className="grid grid-cols-3 gap-px bg-[var(--rule-soft)]">
            <div className="bg-[var(--paper)] p-4">
              <p className="eyebrow">Total</p>
              <p className="font-mono-num mt-2 text-2xl font-medium text-[var(--ink)]">
                {data.total}
              </p>
            </div>
            <div className="bg-[var(--paper)] p-4">
              <p className="eyebrow">Públicos</p>
              <p className="font-mono-num mt-2 text-2xl font-medium text-[var(--forest)]">
                {publicos}
              </p>
            </div>
            <div className="bg-[var(--paper)] p-4">
              <p className="eyebrow">Privados</p>
              <p className="font-mono-num mt-2 text-2xl font-medium text-[var(--amber)]">
                {privados}
              </p>
            </div>
          </div>
          {periodo && (
            <p className="mt-4 text-xs text-[var(--muted)]">
              Snapshots de referência:{" "}
              <span className="font-mono-num text-[var(--ink-soft)]">
                {new Date(periodo).toLocaleDateString("pt-BR", {
                  month: "long",
                  year: "numeric",
                })}
              </span>
            </p>
          )}
        </aside>
      </section>

      <ClientesTable items={data.items} />

      <p className="mt-8 text-xs text-[var(--muted)]">
        Dados extraídos diretamente do banco — não passam pelo filtro de
        publicação. Não compartilhar fora do time.
      </p>
    </main>
  );
}
