"use client";

import { useEffect, useRef, useState } from "react";

type Props = {
  to: number;
  format?: (n: number) => string;
  duration?: number;
  /** Se true, renderiza o valor final imediatamente. */
  disabled?: boolean;
};

const easeOutExpo = (t: number) => (t === 1 ? 1 : 1 - Math.pow(2, -10 * t));

export default function Counter({ to, format, duration = 1200, disabled }: Props) {
  const [value, setValue] = useState<number>(disabled ? to : 0);
  const rafRef = useRef<number | null>(null);
  const startedAt = useRef<number | null>(null);

  useEffect(() => {
    if (disabled) {
      setValue(to);
      return;
    }
    const prefersReduced =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    if (prefersReduced) {
      setValue(to);
      return;
    }

    startedAt.current = null;
    const tick = (ts: number) => {
      if (startedAt.current === null) startedAt.current = ts;
      const elapsed = ts - startedAt.current;
      const t = Math.min(1, elapsed / duration);
      setValue(to * easeOutExpo(t));
      if (t < 1) rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current != null) cancelAnimationFrame(rafRef.current);
    };
  }, [to, duration, disabled]);

  return <>{format ? format(value) : Math.round(value).toLocaleString("pt-BR")}</>;
}
