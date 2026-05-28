import type { GoogleAd, MetaAd } from "@/lib/api-gestor";

function fmtRoas(roas: number | null): string {
  return roas == null ? "—" : `${roas.toFixed(2)}×`;
}
function fmtK(v: number | null): string {
  if (v == null) return "—";
  if (Math.abs(v) >= 1_000_000) return `R$${(v / 1_000_000).toFixed(1)}M`;
  if (Math.abs(v) >= 1_000) return `R$${(v / 1_000).toFixed(0)}k`;
  return `R$${v.toFixed(0)}`;
}

function Row({ label, value, highlight }: { label: string; value: string; highlight?: boolean }) {
  return (
    <div className="flex items-baseline justify-between gap-4 border-b border-[var(--rule-soft)] py-2 last:border-0">
      <span className="text-xs text-[var(--muted)]">{label}</span>
      <span
        className={`font-mono-num text-sm ${
          highlight ? "font-semibold text-[var(--forest)]" : "text-[var(--ink)]"
        }`}
      >
        {value}
      </span>
    </div>
  );
}

export type MetricsRowsProps = {
  ad: MetaAd | GoogleAd;
  cpm: number | null;
  mode: "drawer" | "fullscreen";
};

export function MetricsRows({ ad, cpm, mode }: MetricsRowsProps) {
  const isMeta = "leads" in ad;
  const padding = mode === "fullscreen" ? "px-6" : "px-4";

  return (
    <div className={`mb-5 rounded-xl border border-[var(--rule-soft)] ${padding}`}>
      <Row label="Faturamento" value={fmtK(ad.faturamento)} highlight />
      <Row label="Investimento" value={fmtK(ad.investimento)} />
      <Row label="ROAS" value={fmtRoas(ad.roas)} highlight />
      {ad.conversoes != null && <Row label="Conversões" value={String(ad.conversoes)} />}
      {isMeta && (ad as MetaAd).leads != null && <Row label="Leads" value={String((ad as MetaAd).leads)} />}
      {ad.cpa != null && <Row label="CPA" value={fmtK(ad.cpa)} />}
      {isMeta && (ad as MetaAd).cpl != null && <Row label="CPL" value={fmtK((ad as MetaAd).cpl)} />}
      {ad.impressoes != null && <Row label="Impressões" value={ad.impressoes.toLocaleString("pt-BR")} />}
      {cpm != null && <Row label="CPM" value={fmtK(cpm)} />}
    </div>
  );
}
