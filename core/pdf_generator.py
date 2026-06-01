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


def normalizar_dados(dados: dict[str, str]) -> dict[str, Any]:
    """
    Converte placeholders do handler em contexto Jinja2.
    {"{{fat_sem}}": "R$ 100,00"} → {"fat_sem": "R$ 100,00"}
    """
    return {re.sub(r"[{}]", "", k).strip(): v for k, v in dados.items()}


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
