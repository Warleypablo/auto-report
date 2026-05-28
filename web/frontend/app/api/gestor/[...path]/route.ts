import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

const BACKEND = process.env.INTERNAL_API_URL ?? "http://localhost:8765";

function backendUrl(segments: string[], search: string): string {
  const path = segments.join("/");
  // /api/gestor/me → /auth/me
  if (path === "me") return `${BACKEND}/auth/me${search}`;
  // /api/gestor/clientes, /api/gestor/reports/*, /api/gestor/admin/* → /gestor/...
  return `${BACKEND}/gestor/${path}${search}`;
}

async function handler(
  req: NextRequest,
  { params }: { params: Promise<{ path: string[] }> },
) {
  const { path } = await params;
  const token = req.cookies.get("gestor_token")?.value ?? "";
  const search = req.nextUrl.search ?? "";
  const url = backendUrl(path, search);

  const headers: Record<string, string> = {
    "content-type": "application/json",
  };
  if (token) headers["authorization"] = `Bearer ${token}`;

  let body: string | undefined;
  if (req.method !== "GET" && req.method !== "DELETE") {
    body = await req.text().catch(() => undefined);
  }

  const backendRes = await fetch(url, {
    method: req.method,
    headers,
    body,
    cache: "no-store",
  });

  const contentType = backendRes.headers.get("content-type") ?? "";
  if (backendRes.status === 204 || !contentType.includes("application/json")) {
    return new NextResponse(null, { status: backendRes.status });
  }

  const data = await backendRes.json().catch(() => ({}));
  return NextResponse.json(data, {
    status: backendRes.status,
    headers: { "Cache-Control": "no-store" },
  });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
