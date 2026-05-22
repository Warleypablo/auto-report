import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Em produção o INTERNAL_API_URL aponta para o backend no Render
  // Em dev, as rotas /api/* já fazem proxy via route handlers para localhost:8765
  env: {
    INTERNAL_API_URL: process.env.INTERNAL_API_URL ?? "http://localhost:8765",
  },
};

export default nextConfig;
