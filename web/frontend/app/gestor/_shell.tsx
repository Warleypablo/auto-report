"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname, useSearchParams } from "next/navigation";
import { gestorApi } from "@/lib/api-gestor";
import type { UsuarioInfo } from "@/lib/api-gestor";

const NAV: { href: string; label: string; icon: string; tab?: string }[] = [
  { href: "/gestor",              label: "Dashboard", icon: "◉" },
  { href: "/gestor?tab=reportes", label: "Reportes",  icon: "◈", tab: "reportes" },
  { href: "/gestor/performance",  label: "Criativos", icon: "◈" },
  { href: "/gestor/turbomax",     label: "TurboMax",  icon: "⚡" },
];

export default function GestorShell({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UsuarioInfo | null>(null);
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const currentTab = searchParams.get("tab");

  useEffect(() => {
    gestorApi.me().then(setUser).catch(() => {
      window.location.href = "/gestor/login";
    });
  }, []);

  async function handleLogout() {
    await gestorApi.logout();
    window.location.href = "/gestor/login";
  }

  return (
    <div className="flex min-h-screen">
      <aside className="sticky top-0 flex h-screen w-56 flex-shrink-0 flex-col border-r border-[var(--rule-soft)] bg-[var(--paper-soft)]">
        <div className="border-b border-[var(--rule-soft)] px-5 py-5">
          <p className="font-display text-lg font-medium leading-tight text-[var(--ink)]">Painel</p>
          <p className="text-xs text-[var(--muted)]">Gestores</p>
        </div>

        <nav className="flex-1 px-3 py-4">
          {NAV.map(({ href, label, icon, tab }) => {
            let active: boolean;
            if (tab) {
              active = pathname === "/gestor" && currentTab === tab;
            } else if (href === "/gestor") {
              active = pathname === "/gestor" && !currentTab;
            } else {
              active = pathname.startsWith(href);
            }
            return (
              <Link
                key={href}
                href={href}
                className={[
                  "mb-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition",
                  active
                    ? "bg-[var(--forest-soft)] font-medium text-[var(--forest)] shadow-[inset_2px_0_0_0_var(--forest)]"
                    : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
                ].join(" ")}
              >
                <span className="text-[10px] opacity-60">{icon}</span>
                {label}
              </Link>
            );
          })}
        </nav>

        <div className="border-t border-[var(--rule-soft)] px-3 pt-3 pb-1">
          <Link
            href="/gestor?tab=configuracoes"
            className={[
              "mb-1 flex w-full items-center gap-3 rounded-md px-3 py-2.5 text-left text-sm transition",
              currentTab === "configuracoes" && pathname === "/gestor"
                ? "bg-[var(--forest-soft)] font-medium text-[var(--forest)] shadow-[inset_2px_0_0_0_var(--forest)]"
                : "text-[var(--muted)] hover:bg-[var(--paper-deep)] hover:text-[var(--ink)]",
            ].join(" ")}
          >
            <span className="text-[10px] opacity-60">◎</span>
            Configurações
          </Link>
        </div>
        <div className="border-t border-[var(--rule-soft)] px-4 py-4">
          <p className="text-xs font-medium text-[var(--ink-soft)]">{user?.nome ?? "—"}</p>
          <p className="mb-3 truncate text-xs text-[var(--muted)]">{user?.email ?? ""}</p>
          {user?.is_admin && (
            <>
              <Link href="/gestor/admin/usuarios" className="mb-2 block text-xs text-[var(--forest)] hover:underline">
                Administração →
              </Link>
              <Link href="/gestor/admin/historico" className="mb-3 block text-xs text-[var(--forest)] hover:underline">
                Base histórica →
              </Link>
            </>
          )}
          <button
            onClick={handleLogout}
            className="text-xs text-[var(--muted)] transition hover:text-[var(--crimson)]"
          >
            Sair
          </button>
        </div>
      </aside>

      <div className="flex-1 overflow-y-auto">
        {children}
      </div>
    </div>
  );
}
