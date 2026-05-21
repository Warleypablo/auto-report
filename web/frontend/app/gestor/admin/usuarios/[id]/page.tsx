"use client";

import { useEffect, useState, use } from "react";
import Link from "next/link";
import { gestorApi, ClienteGestor } from "@/lib/api-gestor";

export default function EditUsuarioPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const [todosClientes, setTodosClientes] = useState<ClienteGestor[]>([]);
  const [atribuidos, setAtribuidos] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState(false);
  const [busca, setBusca] = useState("");

  useEffect(() => {
    Promise.all([gestorApi.clientes(), gestorApi.getUsuarioClientes(id)])
      .then(([todos, assigned]) => {
        setTodosClientes(todos.items);
        setAtribuidos(new Set(assigned.items.map((c) => c.slug)));
      })
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  async function handleSave() {
    setSalvando(true);
    setErro(null);
    setSucesso(false);
    try {
      // 1. Add newly assigned clients
      const clienteIds = todosClientes
        .filter((c) => atribuidos.has(c.slug))
        .map((c) => c.id);
      if (clienteIds.length > 0) {
        await gestorApi.assignClientes(id, clienteIds);
      }
      // 2. Remove unassigned clients
      const atual = await gestorApi.getUsuarioClientes(id);
      for (const c of atual.items) {
        if (!atribuidos.has(c.slug)) {
          await gestorApi.removeClienteFromUsuario(id, c.id);
        }
      }
      setSucesso(true);
    } catch (e) {
      setErro(e instanceof Error ? e.message : "Erro ao salvar");
    } finally {
      setSalvando(false);
    }
  }

  if (loading) {
    return (
      <main className="flex min-h-screen items-center justify-center">
        <p className="text-sm text-[var(--muted)]">Carregando…</p>
      </main>
    );
  }

  const filtered = todosClientes.filter(
    (c) =>
      c.nome.toLowerCase().includes(busca.toLowerCase()) ||
      c.slug.toLowerCase().includes(busca.toLowerCase()),
  );

  return (
    <main className="mx-auto max-w-2xl px-6 py-16">
      <Link
        href="/gestor/admin/usuarios"
        className="mb-8 block text-xs text-[var(--muted)] hover:text-[var(--ink)] transition"
      >
        ← Gestores
      </Link>

      <h1 className="font-display mb-2 text-3xl font-medium tracking-tight text-[var(--ink)]">
        Editar gestor
      </h1>
      <p className="mb-8 text-sm text-[var(--muted)]">ID: {id}</p>

      {erro && <p className="mb-4 text-sm text-[var(--crimson)]">{erro}</p>}
      {sucesso && (
        <p className="mb-4 text-sm text-[var(--forest)]">Atribuições salvas!</p>
      )}

      <div className="mb-8">
        <p className="eyebrow mb-3 text-xs text-[var(--muted)]">Atribuir clientes</p>
        <input
          type="text"
          placeholder="Buscar cliente…"
          value={busca}
          onChange={(e) => setBusca(e.target.value)}
          className="mb-3 w-full rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
        />

        <ul className="max-h-80 overflow-y-auto flex flex-col gap-1">
          {filtered.map((c) => {
            const checked = atribuidos.has(c.slug);
            return (
              <li key={c.slug}>
                <label className="flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 transition hover:bg-[var(--paper-soft)]">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() =>
                      setAtribuidos((prev) => {
                        const next = new Set(prev);
                        if (checked) next.delete(c.slug);
                        else next.add(c.slug);
                        return next;
                      })
                    }
                    className="h-4 w-4 accent-[var(--forest)]"
                  />
                  <div>
                    <p className="text-sm text-[var(--ink)]">{c.nome}</p>
                    <p className="text-xs text-[var(--muted)]">{c.categoria}</p>
                  </div>
                </label>
              </li>
            );
          })}
        </ul>

        <button
          onClick={handleSave}
          disabled={salvando}
          className={[
            "mt-3 w-full rounded-md border py-2.5 text-xs uppercase tracking-[0.18em] transition",
            salvando
              ? "cursor-wait border-[var(--rule-soft)] text-[var(--muted)]"
              : "border-[var(--forest)] text-[var(--forest)] hover:bg-[var(--forest)] hover:text-[var(--paper)]",
          ].join(" ")}
        >
          {salvando ? "Salvando…" : "Salvar atribuições"}
        </button>
      </div>
    </main>
  );
}
