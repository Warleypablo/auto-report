import { ClientesTable } from "@/components/ClientesTable";
import PeriodPicker from "@/components/PeriodPicker";
import { labelRange, deslocarMes, mesUltimoFechado } from "@/lib/mes-utils";
import TriggerColetaButton from "@/components/TriggerColetaButton";
import { listAllClientes, listPeriodos } from "@/lib/api-internal";

export const dynamic = "force-dynamic";

function defaultRange(): { de: string; ate: string } {
  const ate = mesUltimoFechado();
  const de = deslocarMes(ate, -2);
  return { de, ate };
}

function isoToMes(iso: string): string {
  return iso.slice(0, 7);
}

type SearchParams = { mes?: string; de?: string; ate?: string };

export default async function ListaPage({
  searchParams,
}: {
  searchParams: Promise<SearchParams>;
}) {
  const params = await searchParams;
  const MES_RE = /^\d{4}-\d{2}$/;

  // Compat: ?mes= é tratado como de=mes&ate=mes
  let { de, ate } = defaultRange();
  if (params.de && MES_RE.test(params.de) && params.ate && MES_RE.test(params.ate)) {
    de = params.de;
    ate = params.ate;
    if (de > ate) [de, ate] = [ate, de];
  } else if (params.mes && MES_RE.test(params.mes)) {
    de = params.mes;
    ate = params.mes;
  }

  const [data, periodos] = await Promise.all([
    listAllClientes(de, ate),
    listPeriodos(),
  ]);

  const publicos = data.items.filter((i) => i.publicar_vitrine).length;
  const privados = data.total - publicos;
  const semSnapshotNoRange = data.total - data.com_snapshot;

  const disponiveis = periodos.items.map((p) => ({
    mes: isoToMes(p.periodo_inicio),
    com_snapshot: p.com_snapshot,
  }));

  const labelPeriodo = labelRange(de, ate);

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
            vitrine. Cabeçalhos da tabela são clicáveis para ordenar; use o
            seletor de período para mudar o intervalo de referência.
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
          <p className="mt-4 text-xs text-[var(--muted)]">
            Referência:{" "}
            <span className="font-mono-num text-[var(--ink-soft)]">
              {labelPeriodo}
            </span>
            {" · "}
            {data.com_snapshot} com snapshot, {semSnapshotNoRange} sem
          </p>
        </aside>
      </section>

      <section className="mb-6 flex flex-wrap items-center justify-between gap-4">
        <div className="w-full max-w-3xl">
          <PeriodPicker
            available={disponiveis}
            de={de}
            ate={ate}
          />
        </div>
        {data.com_snapshot === 0 && (
          <TriggerColetaButton mes={ate} label={labelPeriodo} />
        )}
      </section>

      <ClientesTable items={data.items} />

      <p className="mt-8 text-xs text-[var(--muted)]">
        Dados extraídos diretamente do banco — não passam pelo filtro de
        publicação. Não compartilhar fora do time.
      </p>
    </main>
  );
}
