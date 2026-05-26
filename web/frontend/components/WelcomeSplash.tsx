"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";

import type { Highlight } from "@/lib/api-cliente";

type Props = {
  nomeCliente: string;
  highlight: Highlight | null;
  mesLabel: string;
  onDismiss: () => void;
};

const horaSaudacao = () => {
  const h = new Date().getHours();
  if (h < 12) return "Bom dia";
  if (h < 18) return "Boa tarde";
  return "Boa noite";
};

const dataExtenso = () => {
  const d = new Date();
  const meses = [
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
  ];
  return `${d.getDate()} de ${meses[d.getMonth()]} · ${d.getFullYear()}`;
};

export default function WelcomeSplash({ nomeCliente, highlight, mesLabel, onDismiss }: Props) {
  const [visible, setVisible] = useState(true);

  useEffect(() => {
    const t = setTimeout(() => setVisible(false), 3000);
    return () => clearTimeout(t);
  }, []);

  function handleDismiss() {
    setVisible(false);
  }

  return (
    <AnimatePresence onExitComplete={onDismiss}>
      {visible && (
        <motion.div
          className="fixed inset-0 z-50 flex flex-col items-center justify-center overflow-hidden bg-[var(--paper)] px-6"
          initial={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.4, ease: "easeInOut" }}
          onClick={handleDismiss}
          role="dialog"
          aria-label="Boas-vindas"
        >
          <div className="mesh-bg" />

          <motion.p
            className="eyebrow relative text-[10px] text-[var(--muted)]"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5, delay: 0.1 }}
          >
            {dataExtenso()} · {nomeCliente}
          </motion.p>

          <motion.h1
            className="font-display relative mt-3 max-w-4xl text-center font-light italic leading-[0.95] tracking-tight text-[var(--ink)] text-[56px] sm:text-[88px] lg:text-[128px]"
            initial={{ opacity: 0, y: 24 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.7, delay: 0.2, ease: [0.2, 0.7, 0.2, 1] }}
          >
            {horaSaudacao()}, {nomeCliente}.
          </motion.h1>

          <motion.p
            className="font-display relative mt-6 max-w-2xl text-center italic text-[var(--muted)] text-[18px] sm:text-[22px]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.6 }}
          >
            {highlight?.message ?? `Aqui está sua performance de ${mesLabel}.`}
          </motion.p>

          <motion.button
            type="button"
            onClick={handleDismiss}
            className="absolute bottom-10 right-10 text-[10px] uppercase tracking-[0.18em] text-[var(--forest)] hover:text-[var(--ink)]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.4, delay: 1.2 }}
          >
            Continuar →
          </motion.button>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
