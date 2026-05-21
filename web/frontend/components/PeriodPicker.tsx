"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import {
  deslocarMes,
  labelMesCurto,
  labelRange,
  mesUltimoFechado,
} from "@/lib/mes-utils";

const MESES_CURTOS = [
  "Jan","Fev","Mar","Abr","Mai","Jun",
  "Jul","Ago","Set","Out","Nov","Dez",
];

type Props = {
  available: Array<{ mes: string; com_snapshot: number }>;
  de: string;
  ate: string;
};

function ymParaMes(y: number, m: number): string {
  return `${y}-${String(m).padStart(2, "0")}`;
}

function clampRange(a: string, b: string): [string, string] {
  return a <= b ? [a, b] : [b, a];
}

const ref_mes = mesUltimoFechado();
const anoAtual = Number(ref_mes.slice(0, 4));

const QUICK_FILTERS: Array<{ label: string; de: string; ate: string }> = [
  { label: "Últimos 3M", de: deslocarMes(ref_mes, -2), ate: ref_mes },
  { label: "Últimos 6M", de: deslocarMes(ref_mes, -5), ate: ref_mes },
  { label: "Últimos 12M", de: deslocarMes(ref_mes, -11), ate: ref_mes },
  { label: "Este ano", de: `${anoAtual}-01`, ate: ref_mes },
];

export default function PeriodPicker({ available, de, ate }: Props) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [open, setOpen] = useState(false);
  const [year, setYear] = useState(() => Number(ate.slice(0, 4)));
  const [picking, setPicking] = useState<string | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  const snapshotCount = new Map(available.map((a) => [a.mes, a.com_snapshot]));

  useEffect(() => {
    if (!open) setYear(Number(ate.slice(0, 4)));
  }, [ate, open]);

  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
        setPicking(null);
      }
    }
    if (open) document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  function applyRange(newDe: string, newAte: string) {
    const [d, a] = clampRange(newDe, newAte);
    const next = new URLSearchParams(searchParams);
    next.set("de", d);
    next.set("ate", a);
    next.delete("mes");
    router.push(`?${next.toString()}`);
    setOpen(false);
    setPicking(null);
    setHovered(null);
  }

  function handleClickMes(mes: string) {
    if (!picking) {
      setPicking(mes);
    } else {
      applyRange(picking, mes);
    }
  }

  const snapshotTotal = available.reduce((acc, a) => acc + a.com_snapshot, 0);

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger */}
      <div className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
        <div className="flex items-center justify-between">
          <button
            type="button"
            onClick={() => { setOpen((v) => !v); setPicking(null); }}
            className="flex items-center gap-2 group"
          >
            <p className="eyebrow group-hover:text-[var(--ink)] transition">Período</p>
            <svg className="h-3 w-3 text-[var(--muted)] group-hover:text-[var(--ink-soft)] transition" viewBox="0 0 12 12" fill="none">
              <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </button>
          <p className="text-xs text-[var(--muted)]">
            {snapshotTotal} snapshot(s) ·{" "}
            <span className="font-mono-num text-[var(--ink-soft)]">{labelRange(de, ate)}</span>
          </p>
        </div>
      </div>

      {/* Popover */}
      {open && (
        <div className="absolute left-0 top-full z-50 mt-2 w-72 rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] p-4 shadow-xl">
          {/* Quick filters */}
          <div className="mb-4 flex flex-wrap gap-1.5">
            {QUICK_FILTERS.map((f) => {
              const active = f.de === de && f.ate === ate;
              return (
                <button
                  key={f.label}
                  type="button"
                  onClick={() => applyRange(f.de, f.ate)}
                  className={[
                    "rounded-full border px-2.5 py-0.5 text-[11px] transition",
                    active
                      ? "border-[var(--ink)] bg-[var(--ink)] text-[var(--paper)]"
                      : "border-[var(--rule-soft)] text-[var(--ink-soft)] hover:border-[var(--ink-soft)] hover:text-[var(--ink)]",
                  ].join(" ")}
                >
                  {f.label}
                </button>
              );
            })}
          </div>

          {/* Year navigation */}
          <div className="mb-3 flex items-center justify-between">
            <button
              type="button"
              onClick={() => setYear((y) => y - 1)}
              className="rounded p-1.5 hover:bg-[var(--paper-soft)] transition"
              aria-label="Ano anterior"
            >
              <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
                <path d="M8 2L4 6l4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
            <span className="font-mono-num text-sm font-medium">{year}</span>
            <button
              type="button"
              onClick={() => setYear((y) => y + 1)}
              className="rounded p-1.5 hover:bg-[var(--paper-soft)] transition"
              aria-label="Próximo ano"
            >
              <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
                <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>
          </div>

          {/* Month grid */}
          <div className="grid grid-cols-4 gap-1">
            {MESES_CURTOS.map((label, idx) => {
              const mes = ymParaMes(year, idx + 1);
              const isSelected = mes === de || mes === ate;
              const isPicking = mes === picking;
              const inCurrentRange = mes >= de && mes <= ate;
              const [cA, cB] = picking && hovered ? clampRange(picking, hovered) : ["", ""];
              const inCandidateRange = cA && cB && mes >= cA && mes <= cB;
              const hasSnapshot = snapshotCount.has(mes);

              return (
                <button
                  key={mes}
                  type="button"
                  onClick={() => handleClickMes(mes)}
                  onMouseEnter={() => picking && setHovered(mes)}
                  onMouseLeave={() => picking && setHovered(null)}
                  className={[
                    "rounded py-1.5 text-xs font-medium transition select-none",
                    isSelected || isPicking
                      ? "bg-[var(--ink)] text-[var(--paper)]"
                      : inCurrentRange || inCandidateRange
                      ? "bg-[var(--paper-deep)] text-[var(--ink)]"
                      : "text-[var(--ink-soft)] hover:bg-[var(--paper-soft)] hover:text-[var(--ink)]",
                    !hasSnapshot && !isSelected && !isPicking ? "opacity-40" : "",
                  ].filter(Boolean).join(" ")}
                  title={hasSnapshot ? `${snapshotCount.get(mes)} snapshot(s)` : "Sem snapshots"}
                >
                  {label}
                </button>
              );
            })}
          </div>

          {/* Hint */}
          <p className="mt-3 text-center text-[10px] text-[var(--muted)]">
            {picking
              ? `Início: ${labelMesCurto(picking)} — clique no mês final`
              : "Clique no mês inicial do período"}
          </p>
        </div>
      )}
    </div>
  );
}
