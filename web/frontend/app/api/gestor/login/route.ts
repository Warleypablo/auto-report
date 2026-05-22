import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";

const BACKEND = process.env.INTERNAL_API_URL ?? "http://localhost:8765";

export async function POST(req: NextRequest) {
  const body = await req.json().catch(() => null);
  if (!body?.email || !body?.senha) {
    return NextResponse.json({ error: "email e senha obrigatórios" }, { status: 400 });
  }

  const backendRes = await fetch(`${BACKEND}/auth/login`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(body),
  });

  const data = await backendRes.json().catch(() => ({}));

  if (!backendRes.ok) {
    return NextResponse.json(data, { status: backendRes.status });
  }

  const response = NextResponse.json({ usuario: data.usuario });
  response.cookies.set("gestor_token", data.token, {
    httpOnly: true,
    path: "/",
    maxAge: 8 * 60 * 60,
    sameSite: "lax",
  });
  return response;
}
