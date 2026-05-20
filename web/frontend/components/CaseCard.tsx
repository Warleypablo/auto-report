import Link from "next/link";

import type { CaseListItem } from "@/lib/types";
import { formatBRL, formatPct, formatRoas } from "@/lib/format";
import { CaseMark } from "./CaseMark";

export function CaseCard({ item, index }: { item: CaseListItem; index: number }) {
  const numero = String(index + 1).padStart(2, "0");
  const isEcommerce = item.categoria === "E-commerce";

  return (
    <Link
      href={`/cases/${item.slug}`}
      className="group relative block border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-7 transition-all duration-300 hover:bg-[var(--paper-deep)] hover:shadow-[8px_8px_0_var(--ink)]"
      style={{ animationDelay: `${index * 60}ms` }}
    >
      {item.destaque && (
        <span className="absolute -right-px -top-px bg-[var(--forest)] px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.18em] text-[var(--paper)]">
          Destaque
        </span>
      )}

      <div className="flex items-start justify-between">
        <span className="font-mono-num text-xs text-[var(--muted)]">№ {numero}</span>
        <span className="eyebrow">{item.categoria}</span>
      </div>

      <div className="mt-6 flex items-center gap-4">
        <CaseMark slug={item.slug} size={56} />
        <div className="min-w-0">
          <h3 className="font-display text-2xl leading-tight tracking-tight text-[var(--ink)]">
            {item.nome}
          </h3>
          <p className="mt-0.5 text-xs text-[var(--muted)]">
            {item.setor}
            {item.porte ? ` · ${item.porte}` : ""}
          </p>
        </div>
      </div>

      {item.descricao_publica && (
        <p className="mt-5 line-clamp-3 text-sm leading-relaxed text-[var(--ink-soft)]">
          {item.descricao_publica}
        </p>
      )}

      <div className="mt-7 border-t border-[var(--rule-soft)] pt-5">
        {isEcommerce ? (
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="eyebrow">Faturamento</p>
              <p className="font-mono-num mt-1.5 text-2xl font-medium text-[var(--ink)]">
                {formatBRL(item.faturamento)}
              </p>
              {item.faturamento_var_pct && (
                <p className="font-mono-num mt-1 text-xs text-[var(--forest)]">
                  ↗ {formatPct(item.faturamento_var_pct)}
                </p>
              )}
            </div>
            <div>
              <p className="eyebrow">ROAS</p>
              <p className="font-mono-num mt-1.5 text-2xl font-medium text-[var(--ink)]">
                {formatRoas(item.roas)}
              </p>
              {item.roas_var_pct && (
                <p className="font-mono-num mt-1 text-xs text-[var(--forest)]">
                  ↗ {formatPct(item.roas_var_pct)}
                </p>
              )}
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-2 gap-6">
            <div>
              <p className="eyebrow">Leads / mês</p>
              <p className="font-mono-num mt-1.5 text-2xl font-medium text-[var(--ink)]">
                {item.leads ? item.leads.toLocaleString("pt-BR") : "—"}
              </p>
            </div>
            <div>
              <p className="eyebrow">CPL</p>
              <p className="font-mono-num mt-1.5 text-2xl font-medium text-[var(--ink)]">
                {formatBRL(item.cpa)}
              </p>
            </div>
          </div>
        )}
      </div>

      <div className="mt-7 flex items-center justify-between text-xs">
        <span className="text-[var(--muted)]">
          {new Date(item.periodo_fim).toLocaleDateString("pt-BR", {
            month: "long",
            year: "numeric",
          })}
        </span>
        <span className="font-medium text-[var(--ink)] underline decoration-[var(--rule-soft)] underline-offset-4 transition-colors group-hover:decoration-[var(--ink)]">
          Ver case →
        </span>
      </div>
    </Link>
  );
}
