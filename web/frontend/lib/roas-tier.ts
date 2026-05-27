export const fmtBRL = (v: number | null): string =>
  v == null
    ? "—"
    : v.toLocaleString("pt-BR", { style: "currency", currency: "BRL", maximumFractionDigits: 0 });

export const fmtRoas = (v: number | null): string =>
  v == null ? "—" : `${v.toFixed(2).replace(".", ",")}×`;

export type RoasTier = "high" | "mid" | "low" | "none";

export function roasTier(v: number | null): RoasTier {
  if (v == null) return "none";
  if (v >= 3) return "high";
  if (v >= 1.5) return "mid";
  return "low";
}

export const TIER_TEXT: Record<RoasTier, string> = {
  high: "text-[var(--forest)]",
  mid: "text-[#f59e0b]",
  low: "text-[var(--crimson)]",
  none: "text-[var(--muted)]",
};

export const TIER_BAR: Record<RoasTier, string> = {
  high: "bg-[var(--forest)]",
  mid: "bg-[#f59e0b]",
  low: "bg-[var(--crimson)]",
  none: "bg-[var(--muted)]",
};

export function sortByRoas<T extends { roas: number | null }>(items: T[]): T[] {
  return [...items].sort((a, b) => {
    if (a.roas == null && b.roas == null) return 0;
    if (a.roas == null) return 1;
    if (b.roas == null) return -1;
    return b.roas - a.roas;
  });
}
