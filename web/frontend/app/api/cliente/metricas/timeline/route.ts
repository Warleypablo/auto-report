import { NextRequest } from "next/server";

import { proxyGet } from "../../_proxy";

export async function GET(req: NextRequest) {
  const meses = req.nextUrl.searchParams.get("meses") ?? "12";
  return proxyGet(req, "/cliente/metricas/timeline", new URLSearchParams({ meses }));
}
