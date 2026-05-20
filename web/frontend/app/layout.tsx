import type { Metadata } from "next";
import { Fraunces, Manrope, JetBrains_Mono } from "next/font/google";
import Link from "next/link";

import "./globals.css";

const fraunces = Fraunces({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-fraunces",
  axes: ["SOFT", "WONK", "opsz"],
});

const manrope = Manrope({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  display: "swap",
  variable: "--font-geist",
});

const jetbrains = JetBrains_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "700"],
  display: "swap",
  variable: "--font-jetbrains",
});

export const metadata: Metadata = {
  title: "Cases — desempenho medido",
  description:
    "Relatórios anuais de performance de clientes: ROAS, faturamento gerado, evolução mês a mês. Números medidos, não promessas.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html
      lang="pt-BR"
      className={`${fraunces.variable} ${manrope.variable} ${jetbrains.variable}`}
    >
      <body className="paper-grain min-h-screen">
        <header className="relative z-10 border-b border-[var(--rule)]/15">
          <div className="mx-auto flex max-w-[1320px] items-center justify-between px-8 py-5">
            <Link href="/" className="flex items-baseline gap-3">
              <span className="font-display text-2xl font-medium tracking-tight text-[var(--ink)]">
                Cases
              </span>
              <span className="eyebrow hidden sm:inline">
                Vitrine de performance
              </span>
            </Link>
            <nav className="flex items-center gap-8 text-sm text-[var(--ink-soft)]">
              <Link href="/" className="hover:text-[var(--ink)]">
                Vitrine
              </Link>
              <a
                href="#metodologia"
                className="hidden border-l border-[var(--rule-soft)] pl-8 hover:text-[var(--ink)] md:inline"
              >
                Metodologia
              </a>
            </nav>
          </div>
        </header>

        <div className="relative z-10">{children}</div>

        <footer className="relative z-10 mt-32 border-t border-[var(--rule)]/15">
          <div className="mx-auto max-w-[1320px] px-8 py-12">
            <div className="grid gap-12 md:grid-cols-3">
              <div>
                <p className="eyebrow">Sobre os cases</p>
                <p className="mt-3 max-w-sm text-sm leading-relaxed text-[var(--ink-soft)]">
                  Todos os números são extraídos diretamente das contas de Meta
                  Ads, Google Ads e GA4 dos clientes — sem maquiagem. Cada case
                  é publicado com autorização explícita.
                </p>
              </div>
              <div>
                <p className="eyebrow">Atualização</p>
                <p className="mt-3 text-sm text-[var(--ink-soft)]">
                  Snapshots diários. Período de referência: mês fechado mais
                  recente.
                </p>
              </div>
              <div className="md:text-right">
                <p className="eyebrow">Edição</p>
                <p className="mt-3 font-display text-xl text-[var(--ink)]">
                  №{" "}
                  {new Date().toLocaleDateString("pt-BR", {
                    month: "long",
                    year: "numeric",
                  })}
                </p>
              </div>
            </div>
            <p className="mt-12 border-t border-[var(--rule-soft)] pt-6 text-xs text-[var(--muted)]">
              © {new Date().getFullYear()} — Cases publicados com autorização
              dos clientes.
            </p>
          </div>
        </footer>
      </body>
    </html>
  );
}
