import { formatBRL, formatInt, formatRoas } from "@/lib/format";

const FONTES = [
  { key: "meta", label: "Meta Ads", glyph: "M" },
  { key: "google", label: "Google Ads", glyph: "G" },
  { key: "ga4", label: "GA4", glyph: "A" },
  { key: "painel", label: "Painel interno", glyph: "P" },
];

type Detalhes = Record<string, Record<string, number | string>>;

function formatValor(chave: string, valor: number | string): string {
  if (chave === "roas") return formatRoas(valor);
  if (chave === "taxa_engajamento") return `${valor}%`;
  if (["faturamento", "investimento", "cpa"].includes(chave)) return formatBRL(valor);
  return formatInt(valor);
}

function prettyKey(k: string): string {
  return k.replace(/_/g, " ");
}

export function FontDetail({ detalhes }: { detalhes: Detalhes }) {
  const ativas = FONTES.filter((f) => detalhes[f.key]);
  if (ativas.length === 0) return null;

  return (
    <section className="mt-20">
      <div className="flex items-end justify-between border-b border-[var(--rule)] pb-5">
        <div>
          <p className="eyebrow">Anexo</p>
          <h2 className="font-display mt-1 text-3xl tracking-tight text-[var(--ink)]">
            Detalhamento por fonte
          </h2>
        </div>
        <span className="hidden text-xs text-[var(--muted)] md:inline">
          {ativas.length} {ativas.length === 1 ? "fonte" : "fontes"} consolidadas
        </span>
      </div>

      <div className="mt-8 grid gap-px bg-[var(--rule-soft)] md:grid-cols-2">
        {ativas.map((f) => (
          <div key={f.key} className="bg-[var(--paper-soft)] p-7">
            <div className="flex items-center gap-4">
              <div className="flex h-10 w-10 items-center justify-center border border-[var(--ink)] bg-[var(--ink)] font-display text-lg text-[var(--paper)]">
                {f.glyph}
              </div>
              <h3 className="font-display text-xl tracking-tight text-[var(--ink)]">
                {f.label}
              </h3>
            </div>
            <dl className="mt-6 divide-y divide-[var(--rule-soft)] text-sm">
              {Object.entries(detalhes[f.key]).map(([k, v]) => (
                <div key={k} className="flex items-baseline justify-between py-3">
                  <dt className="capitalize text-[var(--muted)]">{prettyKey(k)}</dt>
                  <dd className="font-mono-num text-base font-medium text-[var(--ink)]">
                    {formatValor(k, v)}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        ))}
      </div>
    </section>
  );
}
