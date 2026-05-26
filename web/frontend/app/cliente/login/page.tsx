"use client";

import { Suspense } from "react";

import LoginScene from "@/components/LoginScene";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <main className="flex min-h-screen items-center justify-center">
          <p className="text-sm text-[var(--muted)]">Carregando…</p>
        </main>
      }
    >
      <LoginScene />
    </Suspense>
  );
}
