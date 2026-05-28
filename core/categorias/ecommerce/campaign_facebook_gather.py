# core/campaign_facebook_gather.py
"""
Coleta métricas dos *TOP N* anúncios (nível **ad**) do Meta Ads,
ordenados por número de compras/conversões.

Agora também devolve a **miniatura (thumbnail)** do criativo de cada anúncio
para que o slide possa exibir visualmente os criativos vencedores.

Alteração 2025‑06‑18
-------------------
* **Correção de supercontagem**: limita a **UMA** janela de atribuição
  ("7d_click") e passa a filtrar compras pelo tipo canônico
  ``omni_purchase``.
* Remove ``action_breakdowns=action_type`` para evitar duplicar eventos.
* Função ``_extract_purchase_metrics`` atualizada para aplicar o filtro.
"""

from __future__ import annotations

import json
from typing import Dict, List, Optional
from collections import Counter, defaultdict

import requests

from config.settings import ACCESS_TOKEN_META_SYSTEM
from utils.logger import get_logger
from core.periodo import Periodo
from core.status import set_status
from utils.formatting import _fmt_brl, _fmt_int, _fmt_roas

log = get_logger(__name__)

###############################################################################
# Configurações
###############################################################################
META_API_VERSION = "v23.0"        # estável ~fev‑2026
TIMEOUT          = 30             # seg. para requests
_TOP_N           = 20             # anúncios a devolver (top 5 no template, restantes em raw_dados)
_BATCH_SIZE      = 50             # máx. IDs por chamada no endpoint /?ids=
_DEF_DASH        = "-"

# Contamos apenas o tipo de compra "canônico". Evita duplicidades.
PURCHASE_TYPES = {"omni_purchase", "purchase"}  # cobre contas antigas

_ATTR_WINDOW = ["7d_click"]  # janela única, sem view

# -----------------------------------------------------------------------------
# Auxiliares numéricos e de parsing
# -----------------------------------------------------------------------------

def _calc_cpa(cost: Optional[float], conv: Optional[int]) -> Optional[float]:
    return None if not cost or not conv else cost / conv


def _calc_roas(value: Optional[float], cost: Optional[float]) -> Optional[float]:
    return None if not cost or not value else value / cost


def _extract_purchase_metrics(actions, action_values):
    conv_counter = Counter()
    fat_counter  = defaultdict(float)

    for a in actions or []:
        if a.get("action_type") in PURCHASE_TYPES and "value" in a:
            try:
                conv_counter[a["action_type"]] += int(float(a["value"]))
            except (ValueError, TypeError):
                pass

    for a in action_values or []:
        if a.get("action_type") in PURCHASE_TYPES and "value" in a:
            try:
                fat_counter[a["action_type"]] += float(a["value"])
            except (ValueError, TypeError):
                pass

    conv = conv_counter.get("omni_purchase") or conv_counter.get("purchase", 0)
    fat  = fat_counter.get("omni_purchase")  or fat_counter.get("purchase",  0.0)
    return conv, fat

def _video_3s_views_from_row(row: dict) -> Optional[int]:
    """Extrai contagem de 3-second video plays do row da Meta Insights API.

    Tenta na ordem: `video_3_sec_watched_actions` (campo dedicado) e
    `actions[action_type=video_view]` (fallback clássico). Retorna `None`
    quando nenhuma das chaves está presente — sinal de que o anúncio não
    é em vídeo (estático/imagem), distinguindo de "zero views".
    """
    primary = row.get("video_3_sec_watched_actions")
    if primary:
        total = 0
        for item in primary:
            if isinstance(item, dict) and "value" in item:
                try:
                    total += int(float(item["value"]))
                except (TypeError, ValueError):
                    continue
        return total

    actions = row.get("actions")
    if actions and isinstance(actions, list):
        total = 0
        found = False
        for item in actions:
            if not isinstance(item, dict):
                continue
            if item.get("action_type") == "video_view":
                found = True
                try:
                    total += int(float(item.get("value", 0)))
                except (TypeError, ValueError):
                    continue
        return total if found else None

    return None

# -----------------------------------------------------------------------------
# Consulta extra: miniatura dos criativos
# -----------------------------------------------------------------------------

def _get_creatives_thumbnail_urls(ad_ids: List[str]) -> Dict[str, str]:
    """Busca a URL da miniatura (thumbnail) de cada ad creative.

    Utiliza o endpoint de *Ad* com nested field ``creative{thumbnail_url}``.
    É feita em lote via parâmetro **ids** para reduzir round‑trips.
    """
    if not ad_ids:
        return {}

    thumbs: Dict[str, str] = {}
    # Quebra em lotes para evitar URLs gigantes (~2 KB)
    for i in range(0, len(ad_ids), _BATCH_SIZE):
        chunk = ad_ids[i : i + _BATCH_SIZE]
        ids_param = ",".join(chunk)
        url = f"https://graph.facebook.com/{META_API_VERSION}"
        params = {
            "ids": ids_param,
            "fields": "creative{thumbnail_url}",
            "access_token": ACCESS_TOKEN_META_SYSTEM,
        }
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data: Dict[str, dict] = resp.json()
            for ad_id, ad_obj in data.items():
                creative = ad_obj.get("creative") or {}
                thumb_url = creative.get("thumbnail_url")
                if thumb_url:
                    thumbs[ad_id] = thumb_url
        except Exception as exc:  # noqa: BLE001
            log.exception("Falha ao obter thumbnails Meta Ads: %s", exc)
    return thumbs

# -----------------------------------------------------------------------------
# Função principal
# -----------------------------------------------------------------------------

def coletar_metricas_anuncios_meta(
    cliente,
    periodo: Periodo,
    top_n: int = _TOP_N,
) -> Dict[str, str]:
    """
    Faz a chamada ao endpoint **/{act_id}/insights** no nível *ad*,
    agrega métricas de purchase e devolve os *N* anúncios com mais conversões
    — agora incluindo a URL da miniatura do criativo.
    """

    # --------------------------------------------------------------------- #
    # Validações de entrada                                                 #
    # --------------------------------------------------------------------- #
    if not periodo.inicio or not periodo.fim:
        log.error("Periodo inválido para %s (ads meta)", cliente.nome)
        set_status(cliente, "ERRO DATA ADS")
        return {}

    # ad_account_id: Optional[str] = getattr(cliente, "id_meta_ads", None)
    ad_account_id = cliente.id_meta_ads
    if not ad_account_id:
        log.warning("Cliente %s sem ID Meta Ads", cliente.nome)
        set_status(cliente, "SEM META ID")
        return {}

    # --------------------------------------------------------------------- #
    # Monta parâmetros da requisição                                        #
    # --------------------------------------------------------------------- #
    acct_path = f"act_{ad_account_id.lstrip('act_')}"   # garante único act_
    url       = f"https://graph.facebook.com/{META_API_VERSION}/{acct_path}/insights"

    time_range_json = json.dumps(
        {
            "since": periodo.inicio.strftime("%Y-%m-%d"),
            "until": periodo.fim.strftime("%Y-%m-%d"),
        },
        separators=(",", ":"),
    )

    params = {
        "level": "ad",
        "time_range": time_range_json,
        "time_increment": "all_days",
        "fields": (
            "ad_id,ad_name,spend,impressions,"
            "actions,action_values,"
            "clicks,reach,video_3_sec_watched_actions"
        ),
        # ► BUGFIX · só 7d_click
        "action_attribution_windows": json.dumps(_ATTR_WINDOW, separators=(",", ":")),
        # usar CONVERSION para contabilizar quando o evento acontece
        "action_report_time": "conversion",
        "limit": 5000,
        "access_token": ACCESS_TOKEN_META_SYSTEM,
    }

    # --------------------------------------------------------------------- #
    # Chamada à API                                                         #
    # --------------------------------------------------------------------- #
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        rows: List[dict] = resp.json().get("data", [])
    except requests.HTTPError as exc:
        err = exc.response.text if exc.response else str(exc)
        log.error("HTTP Meta Ads (%s): %s", cliente.nome, err)
        set_status(cliente, "ERRO API ADS")
        return {}
    except Exception as exc:  # noqa: BLE001
        log.exception("Falha Meta Ads (%s): %s", cliente.nome, exc)
        set_status(cliente, "ERRO API ADS")
        return {}

    if not rows:
        log.info("Meta Ads devolveu lista vazia para %s", cliente.nome)
        set_status(cliente, "SEM DADOS ADS")
        return {}

    # --------------------------------------------------------------------- #
    # Processa linha‑a‑linha e agrega métricas                              #
    # --------------------------------------------------------------------- #
    ads: List[dict] = []
    ad_ids: List[str] = []
    for row in rows:
        spend = float(row.get("spend", 0.0))
        conv, fat = _extract_purchase_metrics(
            row.get("actions") or [],
            row.get("action_values") or [],
        )
        ad_id = row.get("ad_id")
        ads.append({
            "ad_name":  row.get("ad_name") or _DEF_DASH,
            "ad_id":    ad_id,
            "spend":    spend,
            "conv":     conv,
            "fat":      fat,
            "imp":      int(row.get("impressions") or 0),
            "clicks":   int(row.get("clicks") or 0),
            "reach":    int(row.get("reach") or 0),
            "video_3s": _video_3s_views_from_row(row),
        })
        if ad_id:
            ad_ids.append(ad_id)

    # Ordena por conversões desc ------------------------------------------ #
    ads.sort(key=lambda x: x["conv"], reverse=True)
    # Filtra anúncios com conversão > 0
    ads_nonzero = [ad for ad in ads if ad["conv"] and ad["conv"] > 0]
    ads_top = ads_nonzero[:top_n]

    # Busca thumbnails dos criativos apenas para anúncios válidos
    thumb_urls = _get_creatives_thumbnail_urls([ad["ad_id"] for ad in ads_top if ad["ad_id"]])

    for ad in ads_top:
        ad["thumb"] = thumb_urls.get(ad["ad_id"], _DEF_DASH)

    # Geração dos placeholders
    placeholders: Dict[str, str] = {}
    rank = 1
    for ad in ads_top:
        cpa  = _calc_cpa(ad["spend"], ad["conv"])
        roas = _calc_roas(ad["fat"], ad["spend"])
        ctr = (ad["clicks"] / ad["imp"] * 100) if ad["imp"] > 0 else None
        frequency = (ad["imp"] / ad["reach"]) if ad["reach"] > 0 else None
        hook_rate = None
        if ad["video_3s"] is not None and ad["imp"] > 0:
            hook_rate = ad["video_3s"] / ad["imp"] * 100

        placeholders.update({
            f"{{{{nome_adf{rank}}}}}": ad["ad_name"],
            f"{{{{img_adf{rank}}}}}":  ad["thumb"],
            f"{{{{conv_adf{rank}}}}}": _fmt_int(ad["conv"]),
            f"{{{{cpa_adf{rank}}}}}":  _fmt_brl(cpa, 2)  if cpa  is not None else _DEF_DASH,
            f"{{{{inv_adf{rank}}}}}":  _fmt_brl(ad["spend"], 2),
            f"{{{{roas_adf{rank}}}}}": _fmt_roas(roas)   if roas is not None else _DEF_DASH,
            f"{{{{fat_adf{rank}}}}}":  _fmt_brl(ad["fat"], 2),
            f"{{{{imp_adf{rank}}}}}":  _fmt_int(ad["imp"]),
            f"{{{{ctr_adf{rank}}}}}":  f"{ctr:.2f}".replace(".", ",") if ctr is not None else _DEF_DASH,
            f"{{{{freq_adf{rank}}}}}": f"{frequency:.2f}".replace(".", ",") if frequency is not None else _DEF_DASH,
            f"{{{{hook_adf{rank}}}}}": f"{hook_rate:.2f}".replace(".", ",") if hook_rate is not None else _DEF_DASH,
        })
        rank += 1

    # Preenche até top_n para evitar erros no template
    while rank <= top_n:
        placeholders.update({
            f"{{{{nome_adf{rank}}}}}": "-",
            f"{{{{img_adf{rank}}}}}":  "__NO_IMAGE__",
            f"{{{{conv_adf{rank}}}}}": "-",
            f"{{{{cpa_adf{rank}}}}}":  "-",
            f"{{{{inv_adf{rank}}}}}":  "-",
            f"{{{{roas_adf{rank}}}}}": "-",
            f"{{{{fat_adf{rank}}}}}":  "-",
            f"{{{{imp_adf{rank}}}}}":  "-",
            f"{{{{ctr_adf{rank}}}}}":  "-",
            f"{{{{freq_adf{rank}}}}}": "-",
            f"{{{{hook_adf{rank}}}}}": "-",
        })
        rank += 1

    return placeholders