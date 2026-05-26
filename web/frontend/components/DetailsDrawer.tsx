"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect } from "react";

type Props = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: React.ReactNode;
};

export default function DetailsDrawer({ open, onClose, title, children }: Props) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  useEffect(() => {
    if (!open) return;
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = prev;
    };
  }, [open]);

  return (
    <AnimatePresence>
      {open && (
        <>
          <motion.div
            className="fixed inset-0 z-40 bg-black/30 backdrop-blur-sm"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
            onClick={onClose}
            aria-hidden
          />
          <motion.aside
            className="fixed inset-y-0 right-0 z-50 flex w-full max-w-[720px] flex-col bg-[var(--paper)] shadow-2xl"
            role="dialog"
            aria-label={title}
            initial={{ x: "100%" }}
            animate={{ x: 0 }}
            exit={{ x: "100%" }}
            transition={{ duration: 0.3, ease: [0.2, 0.7, 0.2, 1] }}
          >
            <header className="flex items-center justify-between border-b border-[var(--rule-soft)] px-6 py-4">
              <h2 className="font-display text-lg text-[var(--ink)]">{title}</h2>
              <button
                type="button"
                onClick={onClose}
                aria-label="Fechar"
                className="rounded-full border border-[var(--rule-soft)] px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-[var(--muted)] hover:border-[var(--ink)] hover:text-[var(--ink)]"
              >
                Fechar
              </button>
            </header>
            <div className="flex-1 overflow-y-auto px-6 py-4">{children}</div>
          </motion.aside>
        </>
      )}
    </AnimatePresence>
  );
}
