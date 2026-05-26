import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8765";
const COOKIE_NAME = "cliente_token";
const EXPIRY_HOURS = 8;

export async function POST(req: NextRequest) {
  const { cnpj, senha } = await req.json();
  const r = await fetch(`${API_URL}/cliente/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cnpj, senha }),
  });

  if (!r.ok) {
    const data = await r.json().catch(() => ({ detail: "Erro inesperado" }));
    return NextResponse.json({ detail: data.detail ?? "Erro inesperado" }, { status: r.status });
  }

  const data = await r.json();
  const resp = NextResponse.json({ ok: true, cliente: data.cliente });
  resp.cookies.set({
    name: COOKIE_NAME,
    value: data.token,
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: EXPIRY_HOURS * 3600,
  });
  return resp;
}
