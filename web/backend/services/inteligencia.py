from __future__ import annotations

import re
from typing import Any

_BRAND_RE = re.compile(r'\[inst\]|\[brand\]|\[marc\]', re.IGNORECASE)


def detectar_roas_brand_inflado(breakdown: dict) -> dict | None:
    google_ads = breakdown.get("google_ads") or []
    brand = [ad for ad in google_ads if _BRAND_RE.search(ad.get("nome") or "")]
    if not brand:
        return None
    pior = max(brand, key=lambda ad: ad.get("roas") or 0)
    if not pior.get("roas") or pior["roas"] <= 50:
        return None
    outras = [ad for ad in google_ads if ad not in brand]
    fat = sum(ad.get("faturamento") or 0 for ad in outras)
    inv = sum(ad.get("investimento") or 0 for ad in outras)
    roas_sem_brand = round(fat / inv, 2) if inv > 0 else None
    return {
        "tipo": "roas_brand_inflado",
        "severidade": "atencao",
        "titulo": "ROAS inflado por campanha brand",
        "metrica_principal": f"{pior['roas']:.2f}×",
        "contexto": {
            "campanha": pior["nome"],
            "investimento": pior.get("investimento"),
            "faturamento": pior.get("faturamento"),
            "roas_sem_brand": roas_sem_brand,
        },
    }


def detectar_roas_queda(snap_atual, snap_anterior) -> dict | None:
    if snap_anterior is None or snap_anterior.roas is None:
        return None
    if snap_atual is None or snap_atual.roas is None:
        return None
    roas_ant = float(snap_anterior.roas)
    roas_atu = float(snap_atual.roas)
    if roas_ant == 0:
        return None
    queda = (roas_ant - roas_atu) / roas_ant
    if queda < 0.20:
        return None
    return {
        "tipo": "roas_queda",
        "severidade": "critico",
        "titulo": f"ROAS caiu {queda * 100:.0f}% vs. mês anterior",
        "metrica_principal": f"{roas_atu:.2f}×",
        "contexto": {
            "roas_atual": round(roas_atu, 2),
            "roas_anterior": round(roas_ant, 2),
            "queda_pct": round(queda * 100, 1),
        },
    }


def detectar_faturamento_queda(snap_atual, snap_anterior) -> dict | None:
    if snap_anterior is None or snap_anterior.faturamento is None:
        return None
    if snap_atual is None or snap_atual.faturamento is None:
        return None
    fat_ant = float(snap_anterior.faturamento)
    fat_atu = float(snap_atual.faturamento)
    if fat_ant == 0:
        return None
    queda = (fat_ant - fat_atu) / fat_ant
    if queda < 0.25:
        return None
    return {
        "tipo": "faturamento_queda",
        "severidade": "critico",
        "titulo": f"Faturamento caiu {queda * 100:.0f}% vs. mês anterior",
        "metrica_principal": f"R${fat_atu:,.0f}",
        "contexto": {
            "faturamento_atual": round(fat_atu, 2),
            "faturamento_anterior": round(fat_ant, 2),
            "queda_pct": round(queda * 100, 1),
        },
    }


def detectar_roas_abaixo_limiar(snap_atual) -> dict | None:
    if snap_atual is None or snap_atual.roas is None:
        return None
    roas = float(snap_atual.roas)
    if roas >= 1.5:
        return None
    return {
        "tipo": "roas_abaixo_limiar",
        "severidade": "critico",
        "titulo": "ROAS abaixo do mínimo (< 1,5×)",
        "metrica_principal": f"{roas:.2f}×",
        "contexto": {"roas": round(roas, 2)},
    }


def detectar_oportunidade_escala(snap_atual, media_investimento_carteira: float | None) -> dict | None:
    if snap_atual is None or snap_atual.roas is None or snap_atual.investimento is None:
        return None
    if media_investimento_carteira is None or media_investimento_carteira == 0:
        return None
    roas = float(snap_atual.roas)
    inv = float(snap_atual.investimento)
    if roas <= 5.0:
        return None
    if inv >= media_investimento_carteira * 0.5:
        return None
    return {
        "tipo": "oportunidade_escala",
        "severidade": "oportunidade",
        "titulo": "Alta eficiência com baixo investimento",
        "metrica_principal": f"{roas:.2f}×",
        "contexto": {
            "roas": round(roas, 2),
            "investimento": round(inv, 2),
            "media_carteira": round(media_investimento_carteira, 2),
        },
    }


def detectar_investimento_parado(snap_atual) -> dict | None:
    if snap_atual is not None and snap_atual.investimento is not None and float(snap_atual.investimento) > 0:
        return None
    return {
        "tipo": "investimento_parado",
        "severidade": "atencao",
        "titulo": "Sem investimento registrado",
        "metrica_principal": "R$0",
        "contexto": {},
    }


def rodar_detectores(
    snap_atual,
    snap_anterior,
    breakdown: dict,
    media_investimento_carteira: float | None,
) -> list[dict[str, Any]]:
    candidatos = [
        detectar_roas_brand_inflado(breakdown),
        detectar_roas_queda(snap_atual, snap_anterior),
        detectar_faturamento_queda(snap_atual, snap_anterior),
        detectar_roas_abaixo_limiar(snap_atual),
        detectar_oportunidade_escala(snap_atual, media_investimento_carteira),
        detectar_investimento_parado(snap_atual),
    ]
    return [s for s in candidatos if s is not None]
