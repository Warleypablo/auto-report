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

  // Forward If-None-Match so the backend can respond with 304 when applicable.
  const ifNoneMatch = req.headers.get("if-none-match");
  if (ifNoneMatch) headers["if-none-match"] = ifNoneMatch;

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

  const status = backendRes.status;
  const contentType = backendRes.headers.get("content-type") ?? "";

  // 204 No Content and 304 Not Modified: no body to forward.
  if (status === 204 || status === 304) {
    const resHeaders: Record<string, string> = {};
    const etag = backendRes.headers.get("etag");
    if (etag) resHeaders["ETag"] = etag;
    return new NextResponse(null, { status, headers: resHeaders });
  }

  // JSON responses: parse and re-serialise (existing behaviour).
  if (contentType.includes("application/json")) {
    const data = await backendRes.json().catch(() => ({}));
    return NextResponse.json(data, {
      status,
      headers: { "Cache-Control": "no-store" },
    });
  }

  // Binary / non-JSON responses (e.g. image/jpeg for thumb endpoints):
  // stream the raw body with relevant headers preserved.
  const buffer = await backendRes.arrayBuffer();
  const resHeaders: Record<string, string> = {
    "Content-Type": contentType || "application/octet-stream",
  };
  const cacheControl = backendRes.headers.get("cache-control");
  if (cacheControl) resHeaders["Cache-Control"] = cacheControl;
  const etag = backendRes.headers.get("etag");
  if (etag) resHeaders["ETag"] = etag;
  const contentLength = backendRes.headers.get("content-length");
  if (contentLength) resHeaders["Content-Length"] = contentLength;

  return new NextResponse(buffer, { status, headers: resHeaders });
}

export { handler as GET, handler as POST, handler as PATCH, handler as DELETE };
