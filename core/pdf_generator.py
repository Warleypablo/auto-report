"""
core/pdf_generator.py

Geração de PDF via Playwright + Jinja2.
"""
from __future__ import annotations

import base64
import re
import urllib.request
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

_TEMPLATES_DIR = Path(__file__).parent / "templates"
_jinja_env: Environment | None = None

_TEMPLATE_MAP: dict[str, str] = {
    "E-commerce":    "ecommerce.html",
    "Lead Com Site": "lead_com_site.html",
    "Lead Sem Site": "lead_sem_site.html",
}

# Valores que o handler usa como "sem dado"
_EMPTY_VALUES = {"", "—", "-", "__NO_IMAGE__", "0", "0,00", "R$ 0,00"}


def _get_env() -> Environment:
    global _jinja_env
    if _jinja_env is None:
        env = Environment(
            loader=FileSystemLoader(str(_TEMPLATES_DIR)),
            autoescape=select_autoescape(["html"]),
        )
        env.filters["delta_class"] = delta_class
        _jinja_env = env
    return _jinja_env


def _extract_number(v: str) -> float | None:
    """Extrai valor numérico de string PT-BR formatada.
    'R$ 23.575,00' → 23575.0 | 'R$ 180.000' → 180000.0
    '106,74' → 106.74 | '+51,7%' → 51.7 | '-' → None
    """
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s or s in _EMPTY_VALUES:
        return None
    s = re.sub(r"[R$\s%↑↓+]", "", s).strip()
    if not s or s in {"-", "–", "—"}:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        parts = s.split(".")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            s = s.replace(".", "")
    try:
        return float(s)
    except ValueError:
        return None


def _fetch_image_b64(url: str, timeout: int = 6) -> str:
    """Busca imagem remota e retorna data URI base64 para embutir no HTML.
    Retorna string vazia se falhar (URL expirada, sem acesso, etc.).
    """
    if not url or url in _EMPTY_VALUES or not url.startswith("http"):
        return ""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read()
            ct = resp.headers.get_content_type() or "image/jpeg"
            return f"data:{ct};base64,{base64.b64encode(data).decode()}"
    except Exception:
        return ""


def normalizar_dados(dados: dict[str, str]) -> dict[str, Any]:
    """
    Converte placeholders do handler em contexto Jinja2.
    {"{{PERIODO_INICIO}}": "26/05"} → {"periodo_inicio": "26/05"}
    Adiciona variante _n com valor numérico.
    Lowercaseia todas as chaves.
    """
    result: dict[str, Any] = {}
    for k, v in dados.items():
        clean = re.sub(r"[{}]", "", k).strip().lower()
        # Normaliza "-" (vazio do handler) para "—"
        valor = "—" if v in {"-", "__NO_IMAGE__"} else v
        result[clean] = valor
        num = _extract_number(valor)
        if num is not None:
            result[clean + "_n"] = num
    return result


def selecionar_template(categoria: str) -> str:
    """Retorna nome do arquivo de template para a categoria."""
    name = _TEMPLATE_MAP.get(categoria)
    if name is None:
        raise ValueError(f"Categoria sem template PDF: {categoria!r}")
    return name


def delta_class(valor: str) -> str:
    """Retorna 'up', 'down' ou 'neutral' para uso como classe CSS."""
    s = str(valor).strip()
    if not s or s in {"—", "-"}:
        return "neutral"
    if s.startswith("-") or s.startswith("↓"):
        return "down"
    if s.startswith("+") or s.startswith("↑"):
        try:
            num_str = re.sub(r"[↑↓+%\s]", "", s).replace(",", ".")
            return "up" if float(num_str) > 0 else "down"
        except ValueError:
            return "up"
    return "neutral"


def renderizar_html(categoria: str, ctx: dict[str, Any]) -> str:
    """Renderiza template Jinja2 da categoria com o contexto fornecido."""
    env = _get_env()
    template = env.get_template(selecionar_template(categoria))
    return template.render(**ctx)


def html_para_pdf(html: str) -> bytes:
    """Renderiza HTML em headless Chromium e exporta PDF A4.

    Fonte Inter embutida (base64) e sem deps de CDN → set_content não espera rede.
    """
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        # channel="chromium": usa o Chromium "cheio" (new-headless), que é
        # instalado por `playwright install chromium`. Sem isso, o launch headless
        # padrão procura o chrome-headless-shell (download à parte) e quebra em
        # produção com "Executable doesn't exist at .../chrome-headless-shell".
        browser = p.chromium.launch(channel="chromium")
        page = browser.new_page()
        # wait_until="load": sem recursos de rede (fonte embutida, sem Chart.js CDN)
        page.set_content(html, wait_until="load")
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()
    return pdf_bytes


def _extrair_ads(ctx: dict, prefixo: str, max_n: int = 3) -> list[dict]:
    """Extrai lista de ads REAIS do contexto normalizado.

    Ignora slots de preenchimento (nome = "—" ou vazio).
    Pré-busca imagens como base64 para evitar expiração de URLs.
    """
    def _val(i: int, key: str) -> str:
        v = ctx.get(f"{key}_{prefixo}{i}", "—")
        return "—" if v in {"—", "-", ""} else v

    # 1) Seleciona slots com ad real (sem buscar imagem ainda)
    ads = []
    for i in range(1, 21):
        if len(ads) >= max_n:
            break
        nome = ctx.get(f"nome_{prefixo}{i}", "")
        if not nome or nome == "—":
            continue  # slot vazio de preenchimento
        ads.append({
            "pos": i, "nome": nome,
            "img_url": ctx.get(f"img_{prefixo}{i}", ""),
            "roas": _val(i, "roas"), "conv": _val(i, "conv"),
            "fat": _val(i, "fat"),   "cpa": _val(i, "cpa"),
            "lead": _val(i, "lead"), "cpl": _val(i, "cpl"),
            "inv": _val(i, "inv"),   "ctr": _val(i, "ctr"),
            "imp": _val(i, "imp"),
        })

    # 2) Busca thumbnails em paralelo (não serializa N round-trips de rede)
    urls = [a["img_url"] for a in ads if a["img_url"] and a["img_url"] != "—"]
    if urls:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=min(6, len(urls))) as ex:
            b64_map = dict(zip(urls, ex.map(_fetch_image_b64, urls)))
    else:
        b64_map = {}
    for a in ads:
        a["img"] = b64_map.get(a["img_url"], "")
        del a["img_url"]
    return ads


def _detectar_plataformas(ctx: dict, ads_meta: list, ads_google: list) -> dict:
    """Detecta quais plataformas têm dados reais para decidir quais páginas renderizar.

    Reconhece chaves de E-commerce (fat_face, ses_ga, vendas) e de Lead
    (lead_face, ses, lead_sem) — o dict é unificado.
    """
    def tem(*chaves: str) -> bool:
        return any(ctx.get(k, "—") not in {"—", "", None, "0"} for k in chaves)

    return {
        "has_meta":      tem("fat_face", "roas_face", "inv_face", "lead_face", "cpl_face"),
        "has_google":    tem("fat_goog", "roas_goog", "inv_goog", "lead_goog", "cpl_goog"),
        "has_ga4":       tem("ses_ga", "ses_eng_ga", "taxa_eng_ga", "ses", "user_ga"),
        "has_painel":    tem("fat_sem", "vendas", "roas", "tck_med", "lead_sem", "cpl"),
        "has_criativos": len(ads_meta) > 0,
    }


def gerar_pdf(
    categoria: str,
    dados: dict[str, str],
    dados_diarios: dict[str, list[float]] | None = None,
) -> bytes:
    """
    Ponto de entrada: dados do handler → PDF bytes.

    Parameters
    ----------
    categoria : str
        "E-commerce" | "Lead Com Site" | "Lead Sem Site"
    dados : dict
        Dict de placeholders retornado por handler.coletar_dados().
        Chaves com ou sem {{ }}.
    dados_diarios : dict | None
        Opcional. {"meta_ads": [seg, ter, qua, qui, sex], "google_ads": [...]}
    """
    ctx = normalizar_dados(dados)
    if dados_diarios:
        ctx["dados_diarios"] = dados_diarios
    ads_meta   = _extrair_ads(ctx, prefixo="adf", max_n=3)
    ads_google = _extrair_ads(ctx, prefixo="adg", max_n=3)
    ctx["ads_meta"]   = ads_meta
    ctx["ads_google"] = ads_google
    ctx.update(_detectar_plataformas(ctx, ads_meta, ads_google))
    return html_para_pdf(renderizar_html(categoria, ctx))


def salvar_pdf(
    pdf_bytes: bytes,
    nome_cliente: str,
    ano: int,
    mes: int,
    semana: int,
) -> Path:
    """
    Salva PDF em reports/{cliente}/{ano}/{mes:02d}/Report_Sem{N}_{cliente}.pdf
    Retorna o Path do arquivo criado.
    """
    safe = re.sub(r"[^a-zA-Z0-9_\-]", "_", nome_cliente).strip("_")
    pasta = Path("reports") / safe / str(ano) / f"{mes:02d}"
    pasta.mkdir(parents=True, exist_ok=True)
    caminho = pasta / f"Report_Sem{semana:02d}_{safe}.pdf"
    caminho.write_bytes(pdf_bytes)
    return caminho
