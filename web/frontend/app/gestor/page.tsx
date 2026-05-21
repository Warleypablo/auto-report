"use client";

import { useEffect, useState } from "react";
import { gestorApi, ClienteGestor, UsuarioInfo } from "@/lib/api-gestor";
import Link from "next/link";

export default function GestorDashboard() {
  const [user, setUser] = useState<UsuarioInfo | null>(null);
  const [clientes, setClientes] = useState<ClienteGestor[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([gestorApi.me(), gestorApi.clientes()])
      .then(([u, c]) => {
        setUser(u);
        setClientes(c.items);
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, []);

  async function handleLogout() {
    await gestorApi.logout();
    window.location.href = "/gestor/login";
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <header className="mb-10 flex items-center justify-between">
        <div>
          <p className="text-xs text-[var(--muted)]">Olá, {user?.nome ?? "—"}</p>
          {user?.is_admin && (
            <Link
              href="/gestor/admin/usuarios"
              className="mt-1 block text-xs text-[var(--forest)] underline underline-offset-2"
            >
              Administração →
            </Link>
          )}
        </div>
        <button
          onClick={handleLogout}
          className="text-xs text-[var(--muted)] hover:text-[var(--ink)] transition"
        >
          Sair
        </button>
      </header>

      <h1 className="font-display mb-6 text-3xl font-medium leading-tight tracking-tight text-[var(--ink)]">
        Seus clientes
      </h1>

      {erro && <p className="mb-4 text-sm text-[var(--crimson)]">{erro}</p>}

      {clientes.length === 0 && !erro && (
        <p className="text-sm text-[var(--muted)]">
          Nenhum cliente atribuído. Peça ao administrador para configurar seu acesso.
        </p>
      )}

      <ul className="flex flex-col gap-2">
        {clientes.map((c) => (
          <li key={c.slug}>
            <Link
              href={`/gestor/${c.slug}`}
              className="flex items-center justify-between rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3 transition hover:border-[var(--forest)] hover:bg-[var(--paper-deep)]"
            >
              <div>
                <p className="text-sm font-medium text-[var(--ink)]">{c.nome}</p>
                <p className="text-xs text-[var(--muted)]">{c.categoria}</p>
              </div>
              <span className="text-xs text-[var(--forest)]">Gerar report →</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
