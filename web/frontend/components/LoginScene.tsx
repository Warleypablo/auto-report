"use client";

import { useEffect, useRef, useState } from "react";
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

export default function LoginScene() {
  const router = useRouter();
  const search = useSearchParams();
  const meshRef = useRef<HTMLDivElement | null>(null);
  const [cnpj, setCnpj] = useState("");
  const [senha, setSenha] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(
    search.get("expired") ? "Sua sessão expirou. Entre novamente." : null,
  );

  // Paralaxe sutil no mouse
  useEffect(() => {
    function onMove(e: MouseEvent) {
      if (!meshRef.current) return;
      const x = (e.clientX / window.innerWidth - 0.5) * 12;
      const y = (e.clientY / window.innerHeight - 0.5) * 12;
      meshRef.current.style.translate = `${x}px ${y}px`;
    }
    window.addEventListener("mousemove", onMove);
    return () => window.removeEventListener("mousemove", onMove);
  }, []);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setErr(null);
    try {
      await clienteApi.login(cnpj, senha);
      router.push("/cliente/dashboard?intro=1");
    } catch (e) {
      setErr(e instanceof ApiError ? e.detail : "Erro ao entrar.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden px-6">
      <div ref={meshRef} className="mesh-bg" style={{ transition: "translate 0.4s ease-out" }} />

      <div className="relative w-full max-w-sm">
        <h1 className="font-display mb-1 text-3xl font-light italic tracking-tight text-[var(--ink)]">
          Bem-vindo.
        </h1>
        <p className="mb-10 text-xs text-[var(--muted)]">
          Entre com o CNPJ para ver seus dados de performance.
        </p>

        <form onSubmit={onSubmit} className="flex flex-col gap-5">
          <label htmlFor="cnpj" className="flex flex-col gap-1.5">
            <span className="eyebrow text-[10px] text-[var(--muted)]">CNPJ</span>
            <input
              id="cnpj"
              inputMode="numeric"
              autoComplete="off"
              value={cnpj}
              onChange={(e) => setCnpj(maskCNPJ(e.target.value))}
              placeholder="00.000.000/0000-00"
              className="border-b border-[var(--rule-soft)] bg-transparent py-2 text-base text-[var(--ink)] placeholder:font-display placeholder:italic placeholder:text-[var(--muted)] focus:border-[var(--forest)] focus:outline-none"
            />
          </label>

          <label htmlFor="senha" className="flex flex-col gap-1.5">
            <span className="eyebrow text-[10px] text-[var(--muted)]">Senha</span>
            <input
              id="senha"
              type="password"
              autoComplete="current-password"
              value={senha}
              onChange={(e) => setSenha(e.target.value)}
              className="border-b border-[var(--rule-soft)] bg-transparent py-2 text-base text-[var(--ink)] focus:border-[var(--forest)] focus:outline-none"
            />
          </label>

          {err && (
            <p role="alert" className="text-xs text-[var(--crimson)]">
              {err}
            </p>
          )}

          <button
            type="submit"
            disabled={loading || cnpj.replace(/\D/g, "").length < 11 || senha.length === 0}
            className="mt-6 rounded-full border border-[var(--forest)] px-6 py-2.5 text-[11px] uppercase tracking-[0.18em] text-[var(--forest)] transition hover:bg-[var(--forest)] hover:text-[var(--paper)] disabled:cursor-not-allowed disabled:opacity-40"
          >
            {loading ? "Entrando…" : "Entrar"}
          </button>
        </form>
      </div>
    </main>
  );
}
