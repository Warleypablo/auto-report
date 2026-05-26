import { NextRequest, NextResponse } from "next/server";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8765";

export async function POST(req: NextRequest) {
  const token = req.cookies.get("cliente_token")?.value;
  if (token) {
    await fetch(`${API_URL}/cliente/auth/logout`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    }).catch(() => {});
  }
  const resp = NextResponse.json({ ok: true });
  resp.cookies.delete("cliente_token");
  return resp;
}
