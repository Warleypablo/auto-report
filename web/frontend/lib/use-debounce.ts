"use client";

import { useEffect, useState } from "react";

/**
 * Retorna `value` atrasado em `delayMs`. Reinicia o timer a cada mudança.
 * Usado para evitar disparar um fetch a cada tecla nos filtros de faixa.
 */
export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState<T>(value);
  useEffect(() => {
    const t = setTimeout(() => setDebounced(value), delayMs);
    return () => clearTimeout(t);
  }, [value, delayMs]);
  return debounced;
}
