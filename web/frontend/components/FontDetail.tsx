import { formatBRL, formatInt, formatRoas } from "@/lib/format";

const FONTES = [
  { key: "meta", label: "Meta Ads" },
  { key: "google", label: "Google Ads" },
  { key: "ga4", label: "GA4" },
  { key: "painel", label: "Painel" },
];

type Detalhes = Record<string, Record<string, number | string>>;

function formatValor(chave: string, valor: number | string): string {
  if (chave === "roas") return formatRoas(valor);
  if (["faturamento", "investimento", "cpa"].includes(chave)) return formatBRL(valor);
  return formatInt(valor);
}

export function FontDetail({ detalhes }: { detalhes: Detalhes }) {
  const fontesAtivas = FONTES.filter((f) => detalhes[f.key]);
  if (fontesAtivas.length === 0) return null;

  return (
    <section className="mt-12">
      <h2 className="text-xl font-bold text-neutral-900">Detalhamento por fonte</h2>
      <div className="mt-6 grid gap-4 md:grid-cols-2">
        {fontesAtivas.map((f) => (
          <div key={f.key} className="rounded-lg border border-neutral-200 bg-white p-5">
            <h3 className="font-semibold text-neutral-900">{f.label}</h3>
            <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
              {Object.entries(detalhes[f.key]).map(([k, v]) => (
                <div key={k} className="contents">
                  <dt className="text-neutral-500">{k}</dt>
                  <dd className="text-right font-medium text-neutral-900">{formatValor(k, v)}</dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </section>
  );
}
