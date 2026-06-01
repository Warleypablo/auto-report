"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { gestorApi, UsuarioListItem } from "@/lib/api-gestor";

export default function AdminUsuariosPage() {
  const [usuarios, setUsuarios] = useState<UsuarioListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [erro, setErro] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ email: "", nome: "", senha: "", is_admin: false });
  const [criando, setCriando] = useState(false);
  const [formErro, setFormErro] = useState<string | null>(null);

  function load() {
    setLoading(true);
    gestorApi
      .listUsuarios()
      .then(({ items }) => setUsuarios(items))
      .catch((e) => setErro(e.message))
      .finally(() => setLoading(false));
  }

  useEffect(() => { load(); }, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    setFormErro(null);
    setCriando(true);
    try {
      await gestorApi.createUsuario(form);
      setShowForm(false);
      setForm({ email: "", nome: "", senha: "", is_admin: false });
      load();
    } catch (err) {
      setFormErro(err instanceof Error ? err.message : "Erro ao criar");
    } finally {
      setCriando(false);
    }
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
      <Link href="/gestor" className="mb-8 block text-xs text-[var(--muted)] hover:text-[var(--ink)] transition">
        ← Dashboard
      </Link>

      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-3xl font-medium tracking-tight text-[var(--ink)]">
          Gestores
        </h1>
        <button
          onClick={() => setShowForm((v) => !v)}
          className="rounded-full border border-[var(--forest)] px-4 py-1.5 text-xs uppercase tracking-[0.18em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)]"
        >
          {showForm ? "Cancelar" : "+ Novo gestor"}
        </button>
      </div>

      {erro && <p className="mb-4 text-sm text-[var(--crimson)]">{erro}</p>}

      {showForm && (
        <form
          onSubmit={handleCreate}
          className="mb-8 flex flex-col gap-3 rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4"
        >
          <p className="eyebrow text-xs text-[var(--muted)]">Novo gestor</p>
          {(["email", "nome", "senha"] as const).map((field) => (
            <input
              key={field}
              type={field === "senha" ? "password" : field === "email" ? "email" : "text"}
              placeholder={field}
              value={form[field]}
              onChange={(e) => setForm((f) => ({ ...f, [field]: e.target.value }))}
              required
              className="w-full rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
            />
          ))}
          <label className="flex items-center gap-2 text-sm text-[var(--ink-soft)]">
            <input
              type="checkbox"
              checked={form.is_admin}
              onChange={(e) => setForm((f) => ({ ...f, is_admin: e.target.checked }))}
            />
            Administrador
          </label>
          {formErro && <p className="text-xs text-[var(--crimson)]">{formErro}</p>}
          <button
            type="submit"
            disabled={criando}
            className="w-full rounded-md border border-[var(--forest)] py-2 text-xs uppercase tracking-[0.18em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:opacity-50"
          >
            {criando ? "Criando…" : "Criar"}
          </button>
        </form>
      )}

      <ul className="flex flex-col gap-2">
        {usuarios.map((u) => (
          <li key={u.id}>
            <Link
              href={`/gestor/admin/usuarios/${u.id}`}
              className="flex items-center justify-between rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-3 transition hover:border-[var(--forest)] hover:shadow-[0_0_18px_-6px_var(--forest)]"
            >
              <div>
                <p className="text-sm font-medium text-[var(--ink)]">
                  {u.nome}
                  {u.is_admin && (
                    <span className="ml-2 rounded-full border border-[var(--forest)]/40 bg-[var(--forest)]/10 px-2 py-0.5 text-[10px] uppercase tracking-wide text-[var(--forest)]">admin</span>
                  )}
                  {!u.ativo && (
                    <span className="ml-2 text-xs text-[var(--muted)]">(inativo)</span>
                  )}
                </p>
                <p className="text-xs text-[var(--muted)]">
                  {u.email} · {u.n_clientes} cliente{u.n_clientes !== 1 ? "s" : ""}
                </p>
              </div>
              <span className="text-xs text-[var(--muted)]">Editar →</span>
            </Link>
          </li>
        ))}
      </ul>
    </main>
  );
}
