import Link from "next/link";
import ThemeToggle from "../../components/ThemeToggle";

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  return (
    <>
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
            <Link
              href="/lista"
              className="border-l border-[var(--rule-soft)] pl-8 hover:text-[var(--ink)]"
            >
              Lista interna
            </Link>
            <ThemeToggle />
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
    </>
  );
}
