import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Cases de sucesso",
  description: "Resultados reais dos nossos clientes em marketing digital.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR">
      <body className="min-h-screen bg-neutral-50 text-neutral-900 antialiased">
        <header className="border-b border-neutral-200 bg-white">
          <div className="mx-auto flex max-w-7xl items-center justify-between px-6 py-4">
            <Link href="/" className="text-lg font-bold tracking-tight">
              Cases
            </Link>
            <nav className="text-sm text-neutral-600">
              <Link href="/" className="hover:text-neutral-900">
                Vitrine
              </Link>
            </nav>
          </div>
        </header>
        {children}
        <footer className="mt-24 border-t border-neutral-200 bg-white">
          <div className="mx-auto max-w-7xl px-6 py-8 text-sm text-neutral-500">
            © {new Date().getFullYear()} — Cases publicados com autorização dos clientes.
          </div>
        </footer>
      </body>
    </html>
  );
}
