import type { GoogleAd, MetaAd } from "@/lib/api-gestor";
import type { AdContext } from "../useAdContext";

type Variant = "meta" | "google";

function fmtPct(v: number | null, suffix = "%"): string {
  return v == null ? "—" : `${v.toFixed(1)}${suffix}`;
}
function fmtDecimal(v: number | null): string {
  return v == null ? "—" : v.toFixed(2);
}

function ComparisonArrow({ value, avg }: { value: number | null; avg: number | null }) {
  if (value == null || avg == null) return null;
  const above = value >= avg;
  return (
    <span className={`text-[10px] ${above ? "text-emerald-400" : "text-red-400"}`}>
      {above ? "↑" : "↓"} média {avg.toFixed(2)}
      {value < 1 || avg < 1 ? "" : "×"}
    </span>
  );
}

function FunilKpi({
  label,
  value,
  avg,
  formatFn,
  unavailableHint,
}: {
  label: string;
  value: number | null;
  avg: number | null;
  formatFn: (v: number | null) => string;
  unavailableHint?: string;
}) {
  return (
    <div className="flex-1">
      <p className="text-[10px] uppercase tracking-widest text-[var(--muted)]">{label}</p>
      <p className="mt-1 font-mono-num text-3xl text-[var(--ink)]">{formatFn(value)}</p>
      {value == null && unavailableHint && (
        <p className="mt-0.5 text-[9px] italic text-[var(--muted)]">{unavailableHint}</p>
      )}
      {value != null && <ComparisonArrow value={value} avg={avg} />}
    </div>
  );
}

export type FunilFadigaBlockProps = {
  ad: MetaAd | GoogleAd;
  ctx: AdContext;
  variant: Variant;
};

export function FunilFadigaBlock({ ad, ctx, variant }: FunilFadigaBlockProps) {
  const adAny = ad as MetaAd;
  const allUnavailable =
    variant === "meta"
      ? adAny.ctr == null && adAny.frequency == null && adAny.hook_rate == null
      : adAny.ctr == null;

  return (
    <div className="rounded-xl border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-6 py-5">
      <p className="mb-4 text-[10px] uppercase tracking-widest text-[var(--muted)]">
        Funil &amp; fadiga
      </p>
      <div className="flex gap-8">
        <FunilKpi
          label="CTR"
          value={adAny.ctr ?? null}
          avg={ctx.avgCtr}
          formatFn={(v) => fmtPct(v)}
        />
        {variant === "meta" && (
          <>
            <FunilKpi
              label="Hook rate"
              value={adAny.hook_rate ?? null}
              avg={ctx.avgHookRate}
              formatFn={(v) => fmtPct(v)}
              unavailableHint="Apenas vídeo"
            />
            <FunilKpi
              label="Frequency"
              value={adAny.frequency ?? null}
              avg={ctx.avgFrequency}
              formatFn={fmtDecimal}
            />
          </>
        )}
      </div>
      {allUnavailable && (
        <p className="mt-4 text-[10px] italic text-[var(--muted)]">
          Métricas de funil indisponíveis neste período. Disponíveis a partir do próximo ciclo de
          coleta.
        </p>
      )}
    </div>
  );
}
