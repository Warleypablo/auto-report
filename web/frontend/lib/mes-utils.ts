const MESES_PT = [
  "Janeiro","Fevereiro","Março","Abril","Maio","Junho",
  "Julho","Agosto","Setembro","Outubro","Novembro","Dezembro",
];

const MESES_CURTOS = [
  "Jan","Fev","Mar","Abr","Mai","Jun",
  "Jul","Ago","Set","Out","Nov","Dez",
];

export function labelMes(mes: string): string {
  const [y, m] = mes.split("-");
  const idx = Number(m) - 1;
  return `${MESES_PT[idx] ?? m} ${y}`;
}

export function labelMesCurto(mes: string): string {
  const [, m] = mes.split("-");
  return MESES_CURTOS[Number(m) - 1] ?? m;
}

export function labelRange(de: string, ate: string): string {
  if (de === ate) return labelMes(de);
  return `${labelMesCurto(de)} ${de.slice(0, 4)} → ${labelMesCurto(ate)} ${ate.slice(0, 4)}`;
}

export function deslocarMes(mes: string, delta: number): string {
  const [y, m] = mes.split("-").map(Number);
  const d = new Date(Date.UTC(y, m - 1 + delta, 1));
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}

export function mesUltimoFechado(): string {
  const d = new Date();
  d.setUTCDate(1);
  d.setUTCMonth(d.getUTCMonth() - 1);
  return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}`;
}
