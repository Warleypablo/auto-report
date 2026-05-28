import { NextRequest, NextResponse } from "next/server";

export function middleware(req: NextRequest) {
  const { pathname } = req.nextUrl;

  if (pathname.startsWith("/cliente/")) {
    if (pathname === "/cliente/login") {
      return NextResponse.next();
    }
    const token = req.cookies.get("cliente_token")?.value;
    if (!token) {
      const loginUrl = req.nextUrl.clone();
      loginUrl.pathname = "/cliente/login";
      loginUrl.search = "";
      return NextResponse.redirect(loginUrl);
    }
    return NextResponse.next();
  }

  if (pathname === "/gestor/login") {
    return NextResponse.next();
  }

  if (pathname === "/gestor" || pathname.startsWith("/gestor/")) {
    const token = req.cookies.get("gestor_token")?.value;
    if (!token) {
      const loginUrl = req.nextUrl.clone();
      loginUrl.pathname = "/gestor/login";
      loginUrl.search = "";
      return NextResponse.redirect(loginUrl);
    }
    return NextResponse.next();
  }

  return NextResponse.next();
}

export const config = {
  matcher: [
    "/((?!_next/static|_next/image|favicon\\.ico|api/).*)",
  ],
};
