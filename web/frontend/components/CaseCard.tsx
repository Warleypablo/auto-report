import Link from "next/link";

import type { CaseListItem } from "@/lib/types";
import { formatBRL, formatPct, formatRoas } from "@/lib/format";

export function CaseCard({ item }: { item: CaseListItem }) {
  return (
    <Link
      href={`/cases/${item.slug}`}
      className="group block rounded-xl border border-neutral-200 bg-white p-6 shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg"
    >
      <div className="flex items-center gap-4">
        {item.logo_url ? (
          <img src={item.logo_url} alt={item.nome} className="h-12 w-12 rounded object-contain" />
        ) : (
          <div className="flex h-12 w-12 items-center justify-center rounded bg-neutral-100 text-sm font-bold text-neutral-500">
            {item.nome.slice(0, 2).toUpperCase()}
          </div>
        )}
        <div className="min-w-0">
          <h3 className="truncate font-semibold text-neutral-900">{item.nome}</h3>
          <p className="text-xs text-neutral-500">
            {item.categoria}
            {item.setor ? ` · ${item.setor}` : ""}
          </p>
        </div>
        {item.destaque && (
          <span className="ml-auto rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
            Destaque
          </span>
        )}
      </div>

      {item.descricao_publica && (
        <p className="mt-4 line-clamp-2 text-sm text-neutral-600">{item.descricao_publica}</p>
      )}

      <div className="mt-5 grid grid-cols-2 gap-4 border-t border-neutral-100 pt-4">
        <div>
          <p className="text-xs uppercase tracking-wider text-neutral-500">ROAS</p>
          <p className="mt-1 text-2xl font-bold text-neutral-900">{formatRoas(item.roas)}</p>
        </div>
        <div>
          <p className="text-xs uppercase tracking-wider text-neutral-500">Faturamento</p>
          <p className="mt-1 text-base font-semibold text-neutral-900">
            {formatBRL(item.faturamento)}
          </p>
          {item.faturamento_var_pct && (
            <p className="text-xs font-medium text-emerald-600">
              {formatPct(item.faturamento_var_pct)}
            </p>
          )}
        </div>
      </div>
    </Link>
  );
}
