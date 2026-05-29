from __future__ import annotations
"""
Coleta métricas dos **TOP N** anúncios (nível *ad*) do Meta Ads focando **Leads**.
"""

import json
import re
from typing import Dict, List, Optional, Sequence

import requests

from config.settings import ACCESS_TOKEN_META_SYSTEM
from utils.logger import get_logger
from core.periodo import Periodo
from core.status import set_status
from utils.formatting import _fmt_brl, _fmt_int, _DEF_DASH, _fmt_percent

log = get_logger(__name__)

###############################################################################
# Configurações
###############################################################################
META_API_VERSION = "v23.0"
TIMEOUT          = 30            # seg
_TOP_N           = 20            # anúncios devolvidos (top 5 no template, restantes em raw_dados)
_BATCH_SIZE      = 50            # máx. IDs por chamada a /?ids=

_ATTR_WINDOW = ["7d_click"]      # janela de atribuição única

###############################################################################
# Regex e helpers numéricos
###############################################################################
_INT_RE  = re.compile(r"\d+")
_LEAD_RE = re.compile(r"(lead|conversation_started)", re.I)

def _calc_cpl(cost: Optional[float], leads: Optional[int]) -> Optional[float]:
    return None if not cost or not leads else cost / leads

def _calc_lpi(leads: Optional[int], impressions: Optional[int]) -> Optional[float]:
    return None if not impressions or not leads else leads / impressions

###############################################################################
# Extrator genérico de leads (mesma lógica do módulo principal)
###############################################################################
def _lead_count_from_any(obj) -> int:
    """Extrai contagem de leads de qualquer estrutura devolvida pela API."""
    if obj in (None, "", [], 0):
        return 0

    # STRING – "123" ou "123 Leads"
    if isinstance(obj, str):
        m = _INT_RE.search(obj)
        return int(m.group()) if m else 0

    # DICIONÁRIO – linha unitária já quebrada
    if isinstance(obj, dict):
        label = str(obj.get("action_type") or obj.get("indicator") or "")
        return int(float(obj.get("value", 0))) if _LEAD_RE.search(label) else 0

    # LISTA de dicts – actions / conversions / results
    if isinstance(obj, Sequence):
        total = 0
        for item in obj:
            if not isinstance(item, dict):
                continue
            label = str(item.get("action_type") or item.get("indicator") or "")
            if not _LEAD_RE.search(label):
                continue
            # Clássico: {'action_type': '...', 'value': '12'}
            if "value" in item and not isinstance(item["value"], list):
                total += int(float(item["value"]))
            # Novo formato: {'indicator': '...', 'values': [{ 'value': '12', … }]}
            elif "values" in item and item["values"]:
                total += int(float(item["values"][0].get("value", 0)))
        return total

    # Número direto ou coercível
    try:
        return int(float(obj))
    except (TypeError, ValueError):
        return 0

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

###############################################################################
# Miniaturas dos criativos
###############################################################################
def _get_creatives_thumbnail_urls(ad_ids: List[str]) -> Dict[str, str]:
    if not ad_ids:
        return {}

    thumbs: Dict[str, str] = {}
    for i in range(0, len(ad_ids), _BATCH_SIZE):
        chunk = ad_ids[i : i + _BATCH_SIZE]
        url = f"https://graph.facebook.com/{META_API_VERSION}"
        params = {
            "ids": ",".join(chunk),
            "fields": "creative{thumbnail_url}",
            "access_token": ACCESS_TOKEN_META_SYSTEM,
        }
        try:
            resp = requests.get(url, params=params, timeout=TIMEOUT)
            resp.raise_for_status()
            data: Dict[str, dict] = resp.json()
            for ad_id, ad_obj in data.items():
                thumb_url = (ad_obj.get("creative") or {}).get("thumbnail_url")
                if thumb_url:
                    thumbs[ad_id] = thumb_url
        except Exception:  # noqa: BLE001
            log.exception("Falha ao obter thumbnails Meta Ads")
    return thumbs

###############################################################################
# Helper de placeholders vazios
###############################################################################
def _adf_placeholders_vazios(top_n: int) -> Dict[str, str]:
    """Placeholders "vazios" (—) p/ a tabela de Anúncios em Destaque.

    Devolvido quando não há dados de anúncios (período sem entrega, conta sem
    ID Meta, erro na API, etc.) para o template NUNCA exibir placeholders crus.
    """
    ph: Dict[str, str] = {}
    for rank in range(1, top_n + 1):
        ph.update({
            f"{{{{nome_adf{rank}}}}}": "-",
            f"{{{{img_adf{rank}}}}}":  "__NO_IMAGE__",
            f"{{{{lead_adf{rank}}}}}": "-",
            f"{{{{cpl_adf{rank}}}}}":  "-",
            f"{{{{inv_adf{rank}}}}}":  "-",
            f"{{{{lpi_adf{rank}}}}}":  "-",
            f"{{{{imp_adf{rank}}}}}":  "-",
            f"{{{{ctr_adf{rank}}}}}":  "-",
            f"{{{{freq_adf{rank}}}}}": "-",
            f"{{{{hook_adf{rank}}}}}": "-",
        })
    return ph


###############################################################################
# Função principal
###############################################################################
def coletar_metricas_anuncios_meta(
    cliente,
    periodo: Periodo,
    top_n: int = _TOP_N,
) -> Dict[str, str]:
    """Coleta e ranqueia anúncios por leads, devolvendo placeholders."""

    # ─── Validações básicas ────────────────────────────────────────────
    if not (periodo.inicio and periodo.fim):
        log.error("Periodo inválido para %s (ads meta)", cliente.nome)
        set_status(cliente, "ERRO DATA ADS")
        return _adf_placeholders_vazios(top_n)

    ad_account_id = cliente.id_meta_ads
    if not ad_account_id:
        log.warning("Cliente %s sem ID Meta Ads", cliente.nome)
        set_status(cliente, "SEM META ID")
        return _adf_placeholders_vazios(top_n)

    # ─── Parâmetros da chamada ─────────────────────────────────────────
    acct_path = f"act_{ad_account_id.lstrip('act_')}"
    url       = f"https://graph.facebook.com/{META_API_VERSION}/{acct_path}/insights"

    params = {
        "level": "ad",
        "time_range": json.dumps(
            {
                "since": periodo.inicio.strftime("%Y-%m-%d"),
                "until": periodo.fim.strftime("%Y-%m-%d"),
            },
            separators=(",", ":"),
        ),
        "time_increment": "all_days",
        # agora inclui results + conversions para não perder formatos novos
        "fields": (
            "ad_id,ad_name,spend,impressions,results,actions,conversions,"
            "clicks,reach,video_3_sec_watched_actions"
        ),
        "action_attribution_windows": json.dumps(_ATTR_WINDOW, separators=(",", ":")),
        "action_report_time": "conversion",
        "limit": 5000,
        "access_token": ACCESS_TOKEN_META_SYSTEM,
    }

    # ─── Chamada à API ────────────────────────────────────────────────
    try:
        resp = requests.get(url, params=params, timeout=TIMEOUT)
        resp.raise_for_status()
        rows: List[dict] = resp.json().get("data", [])
    except requests.HTTPError as exc:
        log.error("HTTP Meta Ads (%s): %s", cliente.nome, exc.response.text)
        set_status(cliente, "ERRO API ADS")
        return _adf_placeholders_vazios(top_n)
    except Exception as exc:  # noqa: BLE001
        log.exception("Falha Meta Ads (%s): %s", cliente.nome, exc)
        set_status(cliente, "ERRO API ADS")
        return _adf_placeholders_vazios(top_n)

    if not rows:
        log.info("Meta Ads devolveu lista vazia para %s", cliente.nome)
        set_status(cliente, "SEM DADOS ADS")
        return _adf_placeholders_vazios(top_n)

    # ─── Processamento & agregação ────────────────────────────────────
    ads: List[dict] = []
    for row in rows:
        leads = (
            _lead_count_from_any(row.get("results")) or
            _lead_count_from_any(row.get("conversions")) or
            _lead_count_from_any(row.get("actions"))
        )
        ads.append({
            "ad_name":  row.get("ad_name") or _DEF_DASH,
            "ad_id":    row.get("ad_id"),
            "spend":    float(row.get("spend", 0.0)),
            "lead":     leads,
            "imp":      int(row.get("impressions") or 0),
            "clicks":   int(row.get("clicks") or 0),
            "reach":    int(row.get("reach") or 0),
            "video_3s": _video_3s_views_from_row(row),
        })

    # Filtra anúncios com leads > 0
    ads_validos = [ad for ad in ads if ad["lead"] > 0]
    ads_validos.sort(key=lambda x: x["lead"], reverse=True)
    ads_top = ads_validos[:top_n]

    # ─── Thumbnails ────────────────────────────────────────────────────
    thumb_urls = _get_creatives_thumbnail_urls([ad["ad_id"] for ad in ads_top if ad["ad_id"]])
    for ad in ads_top:
        ad["thumb"] = thumb_urls.get(ad["ad_id"], _DEF_DASH)

    # ─── Placeholders ─────────────────────────────────────────────────
    placeholders: Dict[str, str] = {}
    # Preenche os placeholders dos anúncios válidos
    for rank, ad in enumerate(ads_top, start=1):
        cpl = _calc_cpl(ad["spend"], ad["lead"])
        lpi = _calc_lpi(ad["lead"], ad["imp"])
        ctr = (ad["clicks"] / ad["imp"] * 100) if ad["imp"] > 0 else None
        frequency = (ad["imp"] / ad["reach"]) if ad["reach"] > 0 else None
        hook_rate = None
        if ad["video_3s"] is not None and ad["imp"] > 0:
            hook_rate = ad["video_3s"] / ad["imp"] * 100
        placeholders.update({
            f"{{{{nome_adf{rank}}}}}": ad["ad_name"],
            f"{{{{img_adf{rank}}}}}":  ad["thumb"],
            f"{{{{lead_adf{rank}}}}}": _fmt_int(ad["lead"]),
            f"{{{{cpl_adf{rank}}}}}":  _fmt_brl(cpl, 2) if cpl is not None else _DEF_DASH,
            f"{{{{inv_adf{rank}}}}}":  _fmt_brl(ad["spend"], 2),
            f"{{{{lpi_adf{rank}}}}}":  _fmt_percent(lpi) if lpi is not None else _DEF_DASH,
            f"{{{{imp_adf{rank}}}}}":  _fmt_int(ad["imp"]),
            f"{{{{ctr_adf{rank}}}}}":  f"{ctr:.2f}".replace(".", ",") if ctr is not None else _DEF_DASH,
            f"{{{{freq_adf{rank}}}}}": f"{frequency:.2f}".replace(".", ",") if frequency is not None else _DEF_DASH,
            f"{{{{hook_adf{rank}}}}}": f"{hook_rate:.2f}".replace(".", ",") if hook_rate is not None else _DEF_DASH,
        })

    # Preenche os placeholders restantes com "" e sinalizador de imagem
    for rank in range(len(ads_top) + 1, top_n + 1):
        placeholders.update({
            f"{{{{nome_adf{rank}}}}}": "-",
            f"{{{{img_adf{rank}}}}}":  "__NO_IMAGE__",
            f"{{{{lead_adf{rank}}}}}": "-",
            f"{{{{cpl_adf{rank}}}}}":  "-",
            f"{{{{inv_adf{rank}}}}}":  "-",
            f"{{{{lpi_adf{rank}}}}}":  "-",
            f"{{{{imp_adf{rank}}}}}":  "-",
            f"{{{{ctr_adf{rank}}}}}":  "-",
            f"{{{{freq_adf{rank}}}}}": "-",
            f"{{{{hook_adf{rank}}}}}": "-",
        })

    return placeholders