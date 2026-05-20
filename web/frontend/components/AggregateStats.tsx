import type { CaseListItem } from "@/lib/types";

function sumDecimal(items: CaseListItem[], key: "faturamento" | "investimento") {
  return items.reduce((acc, it) => {
    const v = it[key];
    if (!v) return acc;
    return acc + Number(v);
  }, 0);
}

function avgDecimal(items: CaseListItem[], key: "roas") {
  const vals = items
    .map((it) => (it[key] != null ? Number(it[key]) : null))
    .filter((v): v is number => v != null && Number.isFinite(v));
  if (!vals.length) return 0;
  return vals.reduce((a, b) => a + b, 0) / vals.length;
}

function formatBigBRL(n: number): { num: string; unit: string } {
  if (n >= 1_000_000) return { num: (n / 1_000_000).toFixed(1).replace(".", ","), unit: "M" };
  if (n >= 1_000) return { num: (n / 1_000).toFixed(0), unit: "k" };
  return { num: n.toFixed(0), unit: "" };
}

export function AggregateStats({ items }: { items: CaseListItem[] }) {
  const ecommerce = items.filter((i) => i.categoria === "E-commerce");
  const leadgen = items.filter((i) => i.categoria !== "E-commerce");

  const faturamento = sumDecimal(ecommerce, "faturamento");
  const investimento = sumDecimal(items, "investimento");
  const roasMedio = avgDecimal(ecommerce, "roas");
  const totalLeads = leadgen.reduce((acc, i) => acc + (i.leads ?? 0), 0);

  const fatF = formatBigBRL(faturamento);
  const invF = formatBigBRL(investimento);

  const stats = [
    {
      eyebrow: "Faturamento agregado",
      num: `R$ ${fatF.num}`,
      unit: fatF.unit,
      caption: "Soma dos últimos meses fechados, e-commerce.",
    },
    {
      eyebrow: "Investimento gerenciado",
      num: `R$ ${invF.num}`,
      unit: invF.unit,
      caption: "Mídia paga no mesmo período, todas as contas.",
    },
    {
      eyebrow: "ROAS médio",
      num: roasMedio.toFixed(1).replace(".", ","),
      unit: "x",
      caption: "Média simples entre clientes de e-commerce.",
    },
    {
      eyebrow: "Leads gerados",
      num: totalLeads.toLocaleString("pt-BR"),
      unit: "",
      caption: "Volume mensal somado, geração de leads.",
    },
  ];

  return (
    <section className="mt-12 border-y border-[var(--rule)] py-12">
      <div className="mb-8 flex items-end justify-between">
        <div>
          <p className="eyebrow">Seção I</p>
          <h2 className="font-display mt-1 text-3xl tracking-tight">
            Em números, último mês fechado
          </h2>
        </div>
        <span className="hidden font-mono-num text-xs text-[var(--muted)] md:inline">
          n = {items.length}
        </span>
      </div>

      <div className="grid gap-px bg-[var(--rule-soft)] md:grid-cols-4">
        {stats.map((s) => (
          <div key={s.eyebrow} className="bg-[var(--paper)] p-7">
            <p className="eyebrow">{s.eyebrow}</p>
            <p className="mt-4 flex items-baseline gap-1">
              <span className="font-mono-num text-[2.75rem] font-medium leading-none tracking-tight text-[var(--ink)]">
                {s.num}
              </span>
              {s.unit && (
                <span className="font-display text-2xl text-[var(--forest)]">
                  {s.unit}
                </span>
              )}
            </p>
            <p className="mt-4 text-xs leading-relaxed text-[var(--muted)]">
              {s.caption}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
