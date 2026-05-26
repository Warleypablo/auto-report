"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { ApiError, clienteApi } from "@/lib/api-cliente";

function maskCNPJ(v: string): string {
  const d = v.replace(/\D/g, "").slice(0, 14);
  if (d.length <= 2) return d;
  if (d.length <= 5) return `${d.slice(0, 2)}.${d.slice(2)}`;
  if (d.length <= 8) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5)}`;
  if (d.length <= 12) return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8)}`;
  return `${d.slice(0, 2)}.${d.slice(2, 5)}.${d.slice(5, 8)}/${d.slice(8, 12)}-${d.slice(12)}`;
}

export default function LoginPage() {
  const router = useRouter();
  const search = useSearchParams();
  const [cnpj, setCnpj] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(
    search.get("expired") ? "Sua sessão expirou. Entre novamente." : null,
  );

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      await clienteApi.login(cnpj);
      router.push("/cliente/dashboard");
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : "Erro ao entrar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center px-6">
      <h1 className="font-display mb-1 text-2xl font-medium tracking-tight text-[var(--ink)]">
        Área do Cliente
      </h1>
      <p className="mb-8 text-xs text-[var(--muted)]">
        Entre com o CNPJ para ver seus dados de performance.
      </p>

      <form onSubmit={onSubmit} className="flex flex-col gap-4">
        <label htmlFor="cnpj" className="flex flex-col gap-1">
          <span className="text-xs text-[var(--muted)]">CNPJ</span>
          <input
            id="cnpj"
            inputMode="numeric"
            autoComplete="off"
            value={cnpj}
            onChange={(e) => setCnpj(maskCNPJ(e.target.value))}
            placeholder="00.000.000/0000-00"
            className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] px-3 py-2 text-sm text-[var(--ink)] focus:outline-none focus:ring-1 focus:ring-[var(--forest)]"
          />
        </label>

        {err && (
          <p role="alert" className="text-xs text-[var(--crimson)]">
            {err}
          </p>
        )}

        <button
          type="submit"
          disabled={loading || cnpj.replace(/\D/g, "").length < 11}
          className="rounded-full border border-[var(--forest)] px-5 py-2 text-xs uppercase tracking-[0.18em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {loading ? "Entrando…" : "Entrar"}
        </button>
      </form>
    </main>
  );
}
