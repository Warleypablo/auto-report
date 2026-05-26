"use client";

import { motion } from "framer-motion";
import { useId } from "react";

type Option<T extends string> = { value: T; label: string };

type Props<T extends string> = {
  options: Option<T>[];
  value: T;
  onChange: (v: T) => void;
};

export default function MetricToggle<T extends string>({ options, value, onChange }: Props<T>) {
  const layoutId = useId();
  return (
    <div className="flex gap-6 text-[10px] uppercase tracking-[0.18em]">
      {options.map((opt) => {
        const active = opt.value === value;
        return (
          <button
            key={opt.value}
            type="button"
            onClick={() => onChange(opt.value)}
            className={`relative pb-1 transition-colors ${
              active ? "text-[var(--forest)]" : "text-[var(--muted)] hover:text-[var(--ink)]"
            }`}
          >
            {opt.label}
            {active && (
              <motion.span
                layoutId={`metric-underline-${layoutId}`}
                className="absolute inset-x-0 -bottom-px h-px bg-[var(--forest)]"
                transition={{ type: "spring", stiffness: 380, damping: 30 }}
              />
            )}
          </button>
        );
      })}
    </div>
  );
}
