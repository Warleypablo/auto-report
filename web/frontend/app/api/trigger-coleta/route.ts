import { NextResponse } from "next/server";

import { triggerColetaMes } from "@/lib/api-internal";

export const runtime = "nodejs";

export async function POST(request: Request) {
  const { mes } = (await request.json().catch(() => ({}))) as { mes?: string };
  if (!mes || !/^\d{4}-\d{2}$/.test(mes)) {
    return NextResponse.json({ error: "mes inválido (YYYY-MM)" }, { status: 400 });
  }
  try {
    const result = await triggerColetaMes(mes);
    return NextResponse.json({ ok: true, result });
  } catch (err) {
    const message = err instanceof Error ? err.message : "Erro desconhecido";
    return NextResponse.json({ ok: false, error: message }, { status: 502 });
  }
}
