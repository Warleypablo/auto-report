"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

type Status = "idle" | "loading" | "ok" | "error";

export default function TriggerColetaButton({ mes, label }: { mes: string; label: string }) {
  const router = useRouter();
  const [status, setStatus] = useState<Status>("idle");
  const [msg, setMsg] = useState<string | null>(null);

  async function disparar() {
    setStatus("loading");
    setMsg(null);
    try {
      const res = await fetch("/api/trigger-coleta", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ mes }),
      });
      const data = (await res.json().catch(() => null)) as
        | { ok: boolean; result?: { ok?: number; fail?: number; total?: number; skipped?: boolean }; error?: string }
        | null;
      if (!res.ok || !data?.ok) {
        setStatus("error");
        setMsg(data?.error ?? `Falhou (${res.status})`);
        return;
      }
      const r = data.result;
      if (r?.skipped) {
        setMsg("ETL já estava rodando — tente em alguns minutos.");
      } else if (r) {
        setMsg(`ok ${r.ok ?? 0} · fail ${r.fail ?? 0} · total ${r.total ?? 0}`);
      }
      setStatus("ok");
      router.refresh();
    } catch (err) {
      setStatus("error");
      setMsg(err instanceof Error ? err.message : "Erro desconhecido");
    }
  }

  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        onClick={disparar}
        disabled={status === "loading"}
        className={[
          "rounded-full border px-4 py-1.5 text-xs uppercase tracking-[0.18em] transition",
          status === "loading"
            ? "cursor-wait border-[var(--rule-soft)] text-[var(--muted)]"
            : "border-[var(--forest)] text-[var(--forest)] hover:bg-[var(--forest)] hover:text-[var(--paper)]",
        ].join(" ")}
      >
        {status === "loading" ? "Coletando…" : `Coletar ${label}`}
      </button>
      {msg && (
        <p
          className={
            status === "error"
              ? "text-xs text-[var(--crimson)]"
              : "text-xs text-[var(--ink-soft)]"
          }
        >
          {msg}
        </p>
      )}
    </div>
  );
}
