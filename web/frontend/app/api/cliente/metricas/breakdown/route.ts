import { NextRequest, NextResponse } from "next/server";

import { proxyGet } from "../../_proxy";

export async function GET(req: NextRequest) {
  const mes = req.nextUrl.searchParams.get("mes");
  if (!mes) {
    return NextResponse.json({ detail: "mes obrigatório" }, { status: 400 });
  }
  return proxyGet(req, "/cliente/metricas/breakdown", new URLSearchParams({ mes }));
}
