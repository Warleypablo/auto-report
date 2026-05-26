import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8765";

export async function proxyGet(
  req: NextRequest,
  backendPath: string,
  query?: URLSearchParams,
) {
  const token = req.cookies.get("cliente_token")?.value;
  if (!token) {
    return NextResponse.json({ detail: "Token ausente" }, { status: 401 });
  }
  const url = `${API_URL}${backendPath}${query ? `?${query.toString()}` : ""}`;
  const r = await fetch(url, { headers: { Authorization: `Bearer ${token}` } });
  const body = await r.text();
  return new NextResponse(body, {
    status: r.status,
    headers: { "Content-Type": r.headers.get("Content-Type") ?? "application/json" },
  });
}
