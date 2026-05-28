import AdThumb from "@/components/AdThumb";
import type { MetaAd } from "@/lib/api-gestor";

export type CriativoPreviewProps = {
  ad: MetaAd;
  mode: "drawer" | "fullscreen";
};

export function CriativoPreview({ ad, mode }: CriativoPreviewProps) {
  if (!ad.imagem_url) return null;
  const height = mode === "fullscreen" ? 400 : 220;
  return (
    <div
      className="mb-5 overflow-hidden rounded-xl border border-[var(--rule-soft)]"
      style={{ height }}
    >
      <AdThumb src={ad.imagem_url} name={ad.nome} className="h-full w-full object-cover" />
    </div>
  );
}
