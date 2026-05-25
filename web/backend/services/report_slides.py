"""Wraps core report generation and returns the Google Slides URL.

Called in a background thread by the gestor API. Replicates the steps of
report_generator.processar_cliente() but captures and returns presentation_id
instead of discarding it.
"""
from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

# Garante que a raiz do projeto vem PRIMEIRO no sys.path, mesmo que já esteja
# em outra posição. Necessário para que 'from config import settings' resolva
# para o nosso pacote local e não para um eventual pacote 'config' externo
# instalado em site-packages.
_ROOT = Path(__file__).resolve().parents[3]
_ROOT_STR = str(_ROOT)
if _ROOT_STR in sys.path:
    sys.path.remove(_ROOT_STR)
sys.path.insert(0, _ROOT_STR)

# Se um pacote 'config' diferente (ex: do PyPI) foi carregado primeiro,
# remove do cache para forçar o reimport apontando para o nosso.
_cached_config = sys.modules.get("config")
if _cached_config is not None and not hasattr(_cached_config, "settings"):
    del sys.modules["config"]
    sys.modules.pop("config.settings", None)


def gerar_slides(slug: str, nome_cliente: str, mes: str, frequencia: str = "MENSAL") -> str:
    """Generate Google Slides report for one client and return the Drive URL.

    Args:
        slug: DB slug (used only for error messages here)
        nome_cliente: Client name as it appears in the Central Sheet
        mes: Reference month in YYYY-MM format
        frequencia: "MENSAL" or "SEMANAL"

    Returns:
        Full URL to the created Google Slides presentation

    Raises:
        ValueError: if client is not found in the Central Sheet
        Exception: propagated from core (API errors, Drive errors, etc.)
    """
    from config import settings as core_settings  # type: ignore
    from core import (  # type: ignore
        basic_placeholders,
        periodo as periodo_mod,
        slide_filler,
        template_manager,
    )
    from core.categorias import get_handler  # type: ignore
    from core.leitura_central import fetch_clientes  # type: ignore
    from core.status import set_status  # type: ignore

    # Convert "YYYY-MM" to a `today` in the NEXT month so periodo_referencia
    # returns the correct month. Example: mes="2026-04" → today=2026-05-15
    ano, mes_num = int(mes[:4]), int(mes[5:7])
    proximo = mes_num + 1
    ano_alvo = ano + (1 if proximo > 12 else 0)
    proximo = 1 if proximo > 12 else proximo
    today = date(ano_alvo, proximo, 15)

    clientes = fetch_clientes(
        atualizar=False,
        only=nome_cliente,
        sheet_url=core_settings.CENTRAL_SHEET_URL,
        tab_name=core_settings.CENTRAL_TAB_NAME,
    )
    if not clientes:
        raise ValueError(
            f"Cliente '{nome_cliente}' (slug={slug!r}) não encontrado na Planilha Central"
        )

    cliente = clientes[0]
    FREQ = frequencia.upper()

    periodo_ref = periodo_mod.periodo_referencia(today=today, frequencia=FREQ)
    periodo_comp = periodo_mod.periodo_referencia(today=periodo_ref.inicio, frequencia=FREQ)

    dados = basic_placeholders.montar_placeholders_basicos(cliente, periodo_ref, FREQ=FREQ)
    dados.update(
        basic_placeholders.montar_placeholders_basicos(cliente, periodo_comp, FREQ=FREQ, sufixo="_comp")
    )

    handler = get_handler(cliente.categoria)
    dados.update(handler.coletar_dados(cliente, periodo_ref, periodo_comp))

    presentation_id = template_manager.criar_copia(
        cliente, periodo_ref, template_id=handler.template_id, FREQ=FREQ
    )
    slide_filler.preencher(presentation_id, dados, handler._SLIDES.meta_ads)
    handler.pos_processar(presentation_id, dados)
    set_status(cliente, "GERADO ✅")

    return f"https://docs.google.com/presentation/d/{presentation_id}/edit"
