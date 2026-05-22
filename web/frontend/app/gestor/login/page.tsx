"use client";

import { useState, FormEvent } from "react";
import { gestorApi } from "@/lib/api-gestor";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setErro(null);
    setLoading(true);
    try {
      await gestorApi.login(email, senha);
      window.location.href = "/gestor";
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Erro ao entrar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm">
        <div className="mb-8 text-center">
          <p className="font-display text-2xl font-medium tracking-tight text-[var(--ink)]">
            CASES
          </p>
          <p className="eyebrow mt-1 text-xs text-[var(--muted)]">Painel de Gestores</p>
        </div>

        <form onSubmit={handleSubmit} className="flex flex-col gap-4">
          <input
            type="email"
            placeholder="email@agencia.com"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="w-full rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-2.5 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          />
          <input
            type="password"
            placeholder="••••••••"
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            required
            className="w-full rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] px-4 py-2.5 text-sm text-[var(--ink)] placeholder:text-[var(--muted)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          />

          {erro && (
            <p className="text-xs text-[var(--crimson)]">{erro}</p>
          )}

          <button
            type="submit"
            disabled={loading}
            className={[
              "w-full rounded-md border py-2.5 text-xs uppercase tracking-[0.18em] transition",
              loading
                ? "cursor-wait border-[var(--rule-soft)] text-[var(--muted)]"
                : "border-[var(--forest)] text-[var(--forest)] hover:bg-[var(--forest)] hover:text-[var(--paper)]",
            ].join(" ")}
          >
            {loading ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
