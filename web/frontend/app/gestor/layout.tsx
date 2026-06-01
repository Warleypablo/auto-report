export const dynamic = "force-dynamic";

export default function GestorLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="gestor-turbo min-h-screen bg-[var(--paper)]">
      {children}
    </div>
  );
}
