"""
core/pdf_generator.py

Geração de PDF via Playwright + Jinja2.
Substitui Google Slides como output do report_generator.
"""
from __future__ import annotations

import re
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
    '106,74' → 106.74 | '+51,7%' → 51.7
    """
    if not isinstance(v, str):
        return None
    s = v.strip()
    if not s or s == "—":
        return None
    # Remove prefixos/sufixos não numéricos
    s = re.sub(r"[R$\s%↑↓+]", "", s).strip()
    if not s or s == "-":
        return None
    if "," in s:
        # PT-BR: ponto = milhar, vírgula = decimal → "23.575,00" → 23575.0
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        # PT-BR sem vírgula: "180.000" → todos os pontos são milhares
        parts = s.split(".")
        if len(parts) > 1 and all(len(p) == 3 for p in parts[1:]):
            # todos os grupos após o primeiro têm 3 dígitos → são separadores de milhar
            s = s.replace(".", "")
        # else: ponto decimal normal (ex: "3.14") — mantém como está
    try:
        return float(s)
    except ValueError:
        return None


def normalizar_dados(dados: dict[str, str]) -> dict[str, Any]:
    """
    Converte placeholders do handler em contexto Jinja2.
    {"{{PERIODO_INICIO}}": "26/05"} → {"periodo_inicio": "26/05"}
    Também adiciona variante _n com valor numérico (ex: fat_face_n = 23575.0).
    Lowercaseia todas as chaves.
    """
    result: dict[str, Any] = {}
    for k, v in dados.items():
        clean = re.sub(r"[{}]", "", k).strip().lower()
        result[clean] = v
        num = _extract_number(v)
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
    if not s or s == "—":
        return "neutral"
    if s.startswith("-") or s.startswith("↓"):
        return "down"
    if s.startswith("+") or s.startswith("↑"):
        try:
            num_str = re.sub(r"[↑↓+%,\s]", "", s).replace(",", ".")
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
    """Renderiza HTML em headless Chromium e exporta PDF A4."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        try:
            page.wait_for_function(
                "typeof chartsReady === 'function' && chartsReady()",
                timeout=10_000,
            )
        except Exception:
            pass  # sem gráficos ou timeout — continua
        pdf_bytes = page.pdf(
            format="A4",
            print_background=True,
            margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},
        )
        browser.close()
    return pdf_bytes


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
    ctx["ads_meta"] = _extrair_ads(ctx, prefixo="adf", max_n=5)
    ctx["ads_google"] = _extrair_ads(ctx, prefixo="adg", max_n=5)
    return html_para_pdf(renderizar_html(categoria, ctx))


def _extrair_ads(ctx: dict, prefixo: str, max_n: int = 5) -> list[dict]:
    """Extrai lista de ads do contexto normalizado.
    prefixo='adf' usa nome_adf1, img_adf1, roas_adf1, etc.
    prefixo='adg' usa nome_adg1, roas_adg1, etc.
    """
    ads = []
    for i in range(1, 21):
        if len(ads) >= max_n:
            break
        nome = ctx.get(f"nome_{prefixo}{i}", "")
        if not nome or nome == "—":
            continue
        ads.append({
            "pos":  i,
            "nome": nome,
            "img":  ctx.get(f"img_{prefixo}{i}", ""),
            "roas": ctx.get(f"roas_{prefixo}{i}", "—"),
            "conv": ctx.get(f"conv_{prefixo}{i}", "—"),
            "fat":  ctx.get(f"fat_{prefixo}{i}", "—"),
            "inv":  ctx.get(f"inv_{prefixo}{i}", "—"),
            "cpa":  ctx.get(f"cpa_{prefixo}{i}", "—"),
            "ctr":  ctx.get(f"ctr_{prefixo}{i}", "—"),
        })
    return ads


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
