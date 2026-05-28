import type { AdContext } from "../useAdContext";

function fmtRoas(roas: number | null): string {
  return roas == null ? "—" : `${roas.toFixed(2)}×`;
}
function fmtPct(p: number): string {
  return `${p.toFixed(1)}%`;
}

function ContextBar({ label, pct }: { label: string; pct: number }) {
  return (
    <div className="mb-3 last:mb-0">
      <div className="mb-1 flex justify-between text-[10px] text-[var(--muted)]">
        <span>{label}</span>
        <span>{fmtPct(pct)}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-[var(--paper-deep)]">
        <div
          className="h-1.5 rounded-full bg-[var(--forest)] opacity-70"
          style={{ width: `${Math.min(pct, 100)}%` }}
        />
      </div>
    </div>
  );
}

export type ContextBlockProps = {
  ctx: AdContext;
  mode: "drawer" | "fullscreen";
};

export function ContextBlock({ ctx, mode }: ContextBlockProps) {
  if (mode === "drawer") {
    return (
      <>
        <p className="mb-3 text-[10px] uppercase tracking-widest text-[var(--muted)]">
          Contexto · carteira
        </p>
        {ctx.roasVsAvg != null && (
          <div className="mb-4 rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3">
            <p className="text-xs text-[var(--muted)]">ROAS vs. média da carteira</p>
            <p
              className={`mt-1 font-mono-num text-2xl font-semibold ${
                ctx.roasVsAvg >= 1 ? "text-[var(--forest)]" : "text-[var(--crimson)]"
              }`}
            >
              {ctx.roasVsAvg >= 1 ? "+" : ""}
              {((ctx.roasVsAvg - 1) * 100).toFixed(0)}%
            </p>
            <p className="mt-0.5 text-[10px] text-[var(--muted)]">
              Média: {fmtRoas(ctx.avgRoas)}
            </p>
          </div>
        )}
        {(ctx.shareInv != null || ctx.shareFat != null) && (
          <div className="rounded-xl border border-[var(--rule-soft)] px-4 py-3">
            {ctx.shareInv != null && <ContextBar label="Share de investimento" pct={ctx.shareInv} />}
            {ctx.shareFat != null && <ContextBar label="Share de faturamento" pct={ctx.shareFat} />}
          </div>
        )}
      </>
    );
  }

  // fullscreen — horizontal, 3 colunas
  return (
    <div className="mt-6 rounded-xl border border-[var(--rule-soft)] px-6 py-5">
      <p className="mb-4 text-[10px] uppercase tracking-widest text-[var(--muted)]">
        Contexto · carteira
      </p>
      <div className="grid grid-cols-1 gap-6 md:grid-cols-3">
        {ctx.roasVsAvg != null && (
          <div>
            <p className="text-xs text-[var(--muted)]">ROAS vs. média</p>
            <p
              className={`mt-1 font-mono-num text-3xl font-semibold ${
                ctx.roasVsAvg >= 1 ? "text-[var(--forest)]" : "text-[var(--crimson)]"
              }`}
            >
              {ctx.roasVsAvg >= 1 ? "+" : ""}
              {((ctx.roasVsAvg - 1) * 100).toFixed(0)}%
            </p>
            <p className="mt-0.5 text-[10px] text-[var(--muted)]">Média: {fmtRoas(ctx.avgRoas)}</p>
          </div>
        )}
        {ctx.shareInv != null && (
          <div>
            <p className="text-xs text-[var(--muted)]">Share de investimento</p>
            <p className="mt-1 font-mono-num text-3xl text-[var(--ink)]">{fmtPct(ctx.shareInv)}</p>
          </div>
        )}
        {ctx.shareFat != null && (
          <div>
            <p className="text-xs text-[var(--muted)]">Share de faturamento</p>
            <p className="mt-1 font-mono-num text-3xl text-[var(--forest)]">{fmtPct(ctx.shareFat)}</p>
          </div>
        )}
      </div>
    </div>
  );
}
