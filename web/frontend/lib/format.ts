type MaybeNum = number | string | null | undefined;

function toNumber(v: MaybeNum): number | null {
  if (v === null || v === undefined || v === "") return null;
  const n = typeof v === "number" ? v : Number(v);
  return Number.isFinite(n) ? n : null;
}

const brlFmt = new Intl.NumberFormat("pt-BR", {
  style: "currency",
  currency: "BRL",
  minimumFractionDigits: 2,
});

const intFmt = new Intl.NumberFormat("pt-BR");

export function formatBRL(v: MaybeNum): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return brlFmt.format(n);
}

export function formatInt(v: MaybeNum): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return intFmt.format(n);
}

export function formatRoas(v: MaybeNum): string {
  const n = toNumber(v);
  if (n === null) return "—";
  return `${n.toFixed(1).replace(".", ",")}x`;
}

export function formatPct(v: MaybeNum): string {
  const n = toNumber(v);
  if (n === null) return "—";
  const sign = n > 0 ? "+" : "";
  return `${sign}${n.toFixed(1).replace(".", ",")}%`;
}
