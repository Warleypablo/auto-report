"use client";

import { useEffect, useRef, useState } from "react";
import {
  deslocarMes,
  labelMes,
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

const ref_mes = mesUltimoFechado();
const anoAtual = Number(ref_mes.slice(0, 4));

const QUICK_FILTERS: Array<{ label: string; de: string; ate: string }> = [
  { label: "Últimos 3M", de: deslocarMes(ref_mes, -2), ate: ref_mes },
  { label: "Últimos 6M", de: deslocarMes(ref_mes, -5), ate: ref_mes },
  { label: "Últimos 12M", de: deslocarMes(ref_mes, -11), ate: ref_mes },
  { label: "Este ano", de: `${anoAtual}-01`, ate: ref_mes },
];

type Which = "de" | "ate" | null;

function ChevronDown() {
  return (
    <svg className="h-3 w-3 opacity-50" viewBox="0 0 12 12" fill="none">
      <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function MonthGrid({
  year,
  setYear,
  selected,
  inRange,
  snapshotCount,
  onPick,
}: {
  year: number;
  setYear: (y: number) => void;
  selected: string;
  inRange: (mes: string) => boolean;
  snapshotCount: Map<string, number>;
  onPick: (mes: string) => void;
}) {
  return (
    <div>
      {/* Year nav */}
      <div className="mb-3 flex items-center justify-between">
        <button
          type="button"
          onClick={() => setYear(year - 1)}
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
          onClick={() => setYear(year + 1)}
          className="rounded p-1.5 hover:bg-[var(--paper-soft)] transition"
          aria-label="Próximo ano"
        >
          <svg className="h-3 w-3" viewBox="0 0 12 12" fill="none">
            <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
        </button>
      </div>

      {/* Grid */}
      <div className="grid grid-cols-4 gap-1">
        {MESES_CURTOS.map((label, idx) => {
          const mes = ymParaMes(year, idx + 1);
          const isSelected = mes === selected;
          const highlighted = inRange(mes);
          const hasSnapshot = snapshotCount.has(mes);

          return (
            <button
              key={mes}
              type="button"
              onClick={() => onPick(mes)}
              className={[
                "rounded py-1.5 text-xs font-medium transition select-none",
                isSelected
                  ? "bg-[var(--ink)] text-[var(--paper)]"
                  : highlighted
                  ? "bg-[var(--paper-deep)] text-[var(--ink)]"
                  : "text-[var(--ink-soft)] hover:bg-[var(--paper-soft)] hover:text-[var(--ink)]",
                !hasSnapshot && !isSelected ? "opacity-40" : "",
              ].filter(Boolean).join(" ")}
              title={hasSnapshot ? `${snapshotCount.get(mes)} snapshot(s)` : "Sem snapshots"}
            >
              {label}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export default function PeriodPicker({ available, de, ate }: Props) {
  const [open, setOpen] = useState<Which>(null);
  const [yearDe, setYearDe] = useState(() => Number(de.slice(0, 4)));
  const [yearAte, setYearAte] = useState(() => Number(ate.slice(0, 4)));
  const containerRef = useRef<HTMLDivElement>(null);

  const snapshotCount = new Map(available.map((a) => [a.mes, a.com_snapshot]));
  const snapshotTotal = available.reduce((acc, a) => acc + a.com_snapshot, 0);

  useEffect(() => {
    if (!open) {
      setYearDe(Number(de.slice(0, 4)));
      setYearAte(Number(ate.slice(0, 4)));
    }
  }, [de, ate, open]);

  useEffect(() => {
    function onMouseDown(e: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(null);
      }
    }
    if (open) document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  function applyRange(newDe: string, newAte: string) {
    const [d, a] = newDe <= newAte ? [newDe, newAte] : [newAte, newDe];
    setOpen(null);
    window.location.href = `/lista?de=${encodeURIComponent(d)}&ate=${encodeURIComponent(a)}`;
  }

  function pickDe(mes: string) {
    // If new start is after current end, adjust end too
    applyRange(mes, mes > ate ? mes : ate);
  }

  function pickAte(mes: string) {
    // If new end is before current start, adjust start too
    applyRange(mes < de ? mes : de, mes);
  }

  return (
    <div ref={containerRef} className="rounded-md border border-[var(--rule-soft)] bg-[var(--paper-soft)] p-4">
      {/* Header */}
      <div className="mb-3 flex items-center justify-between">
        <p className="eyebrow">Período</p>
        <p className="text-xs text-[var(--muted)]">
          {snapshotTotal} snapshot(s) no intervalo
        </p>
      </div>

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

      {/* Two selectors */}
      <div className="relative flex items-center gap-2">
        {/* Início */}
        <div className="relative flex-1">
          <div className="mb-1">
            <span className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Início</span>
          </div>
          <button
            type="button"
            onClick={() => setOpen((v) => v === "de" ? null : "de")}
            className={[
              "flex w-full items-center justify-between rounded border px-3 py-2 text-sm transition",
              open === "de"
                ? "border-[var(--ink)] bg-[var(--paper)] text-[var(--ink)]"
                : "border-[var(--rule-soft)] bg-[var(--paper)] text-[var(--ink-soft)] hover:border-[var(--ink-soft)] hover:text-[var(--ink)]",
            ].join(" ")}
          >
            <span className="font-mono-num">{labelMes(de)}</span>
            <ChevronDown />
          </button>
          {open === "de" && (
            <div className="absolute left-0 top-full z-50 mt-1 w-56 rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] p-3 shadow-xl">
              <MonthGrid
                year={yearDe}
                setYear={setYearDe}
                selected={de}
                inRange={(mes) => mes >= de && mes <= ate}
                snapshotCount={snapshotCount}
                onPick={pickDe}
              />
            </div>
          )}
        </div>

        {/* Arrow */}
        <div className="mt-5 text-[var(--muted)]">→</div>

        {/* Fim */}
        <div className="relative flex-1">
          <div className="mb-1">
            <span className="text-[10px] uppercase tracking-widest text-[var(--muted)]">Fim</span>
          </div>
          <button
            type="button"
            onClick={() => setOpen((v) => v === "ate" ? null : "ate")}
            className={[
              "flex w-full items-center justify-between rounded border px-3 py-2 text-sm transition",
              open === "ate"
                ? "border-[var(--ink)] bg-[var(--paper)] text-[var(--ink)]"
                : "border-[var(--rule-soft)] bg-[var(--paper)] text-[var(--ink-soft)] hover:border-[var(--ink-soft)] hover:text-[var(--ink)]",
            ].join(" ")}
          >
            <span className="font-mono-num">{labelMes(ate)}</span>
            <ChevronDown />
          </button>
          {open === "ate" && (
            <div className="absolute left-0 top-full z-50 mt-1 w-56 rounded-md border border-[var(--rule-soft)] bg-[var(--paper)] p-3 shadow-xl">
              <MonthGrid
                year={yearAte}
                setYear={setYearAte}
                selected={ate}
                inRange={(mes) => mes >= de && mes <= ate}
                snapshotCount={snapshotCount}
                onPick={pickAte}
              />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
