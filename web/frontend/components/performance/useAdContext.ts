import { useMemo } from "react";
import type { GoogleAd, MetaAd } from "@/lib/api-gestor";

type RoasTier = "alto" | "medio" | "baixo" | "neutro";

function computeRoasTier(roas: number | null): RoasTier {
  if (roas == null) return "neutro";
  if (roas >= 3) return "alto";
  if (roas >= 1.5) return "medio";
  return "baixo";
}

export type AdContext = {
  tier: RoasTier;
  avgRoas: number | null;
  roasVsAvg: number | null;
  maxRoas: number;
  barPct: number;
  shareInv: number | null;
  shareFat: number | null;
  cpm: number | null;
  avgCtr: number | null;
  avgFrequency: number | null;
  avgHookRate: number | null;
};

function avg(values: number[]): number | null {
  if (values.length === 0) return null;
  return values.reduce((s, v) => s + v, 0) / values.length;
}

export function useAdContext<T extends MetaAd | GoogleAd>(
  ad: T,
  allAds: T[],
): AdContext {
  return useMemo<AdContext>(() => {
    const adsComRoas = allAds.filter((a) => a.roas != null && a.roas > 0);
    const avgRoas = avg(adsComRoas.map((a) => a.roas as number));
    const roasVsAvg = avgRoas && ad.roas ? ad.roas / avgRoas : null;
    const maxRoas =
      adsComRoas.length > 0 ? Math.max(...adsComRoas.map((a) => a.roas as number)) : 0;
    const barPct = maxRoas > 0 && ad.roas ? (ad.roas / maxRoas) * 100 : 0;

    const totalInv = allAds.reduce((s, a) => s + (a.investimento ?? 0), 0);
    const totalFat = allAds.reduce((s, a) => s + (a.faturamento ?? 0), 0);
    const shareInv = totalInv > 0 && ad.investimento ? (ad.investimento / totalInv) * 100 : null;
    const shareFat = totalFat > 0 && ad.faturamento ? (ad.faturamento / totalFat) * 100 : null;

    const cpm =
      ad.impressoes && ad.investimento && ad.impressoes > 0
        ? (ad.investimento / ad.impressoes) * 1000
        : null;

    const ctrValues = allAds
      .map((a) => (a as { ctr?: number | null }).ctr)
      .filter((v): v is number => typeof v === "number");
    const freqValues = allAds
      .map((a) => (a as { frequency?: number | null }).frequency)
      .filter((v): v is number => typeof v === "number");
    const hookValues = allAds
      .map((a) => (a as { hook_rate?: number | null }).hook_rate)
      .filter((v): v is number => typeof v === "number");

    return {
      tier: computeRoasTier(ad.roas),
      avgRoas,
      roasVsAvg,
      maxRoas,
      barPct,
      shareInv,
      shareFat,
      cpm,
      avgCtr: avg(ctrValues),
      avgFrequency: avg(freqValues),
      avgHookRate: avg(hookValues),
    };
  }, [ad, allAds]);
}
