"""Wraps core report generation and returns the report URL.

Called in a background thread by the gestor API. Replicates the steps of
report_generator.processar_cliente() but captures and returns presentation_id
instead of discarding it.

When PDF_REPORT_ATIVO=true, also generates a PDF, uploads it to the same
Drive folder as the Slides, and returns the Drive PDF URL instead.
"""
from __future__ import annotations

import io
import logging
import os
import sys
from datetime import date, timedelta
from pathlib import Path

_log = logging.getLogger(__name__)

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


def _resolver_periodo_ref(
    mes: str,
    frequencia: str,
    semana_inicio: str | None,
    *,
    today: "date | None" = None,
):
    """Resolve (periodo_ref, periodo_comp) a partir dos dados do trigger.

    - SEMANAL: semana útil seg–sex escolhida (``semana_inicio``, qualquer dia da
      semana serve) ou a semana vigente; comparativo = semana anterior.
    - MENSAL: mês selecionado (via âncora no dia 15 do mês seguinte); comparativo
      = mês anterior. (Comportamento original preservado.)
    """
    from core import periodo as P  # type: ignore

    freq = frequencia.upper()
    if freq == "SEMANAL":
        if semana_inicio:
            ref = P.semana_de(date.fromisoformat(semana_inicio))
        else:
            ref = P.semana_vigente(today=today)
        comp = P.semana_de(ref.inicio - timedelta(days=7))
        return ref, comp

    # MENSAL — âncora no dia 15 do mês seguinte p/ ultimo_mes_completo devolver o mês escolhido
    ano, mes_num = int(mes[:4]), int(mes[5:7])
    proximo = mes_num + 1
    ano_alvo = ano + (1 if proximo > 12 else 0)
    proximo = 1 if proximo > 12 else proximo
    ancora = date(ano_alvo, proximo, 15)
    ref = P.ultimo_mes_completo(today=ancora)
    comp = P.ultimo_mes_completo(today=ref.inicio)
    return ref, comp


def gerar_slides(slug: str, nome_cliente: str, mes: str, frequencia: str = "MENSAL", semana_inicio: str | None = None) -> str:
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
        slide_filler,
        template_manager,
    )
    from core.categorias import get_handler  # type: ignore
    from core.leitura_central import fetch_clientes  # type: ignore
    from core.status import set_status  # type: ignore

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

    periodo_ref, periodo_comp = _resolver_periodo_ref(mes, FREQ, semana_inicio)

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

    slides_url = f"https://docs.google.com/presentation/d/{presentation_id}/edit"

    if os.getenv("PDF_REPORT_ATIVO", "false").lower() == "true":
        try:
            pdf_url = _gerar_e_subir_pdf(cliente, dados, periodo_ref, presentation_id)
            if pdf_url:
                return pdf_url
        except Exception:
            _log.exception("Falha ao gerar/subir PDF para %s — usando Slides", cliente.nome)

    return slides_url


def _gerar_e_subir_pdf(cliente, dados: dict, periodo_ref, presentation_id: str) -> str | None:
    """Gera PDF via Playwright e sobe para o Drive na mesma pasta do Slides.

    Retorna a URL pública do Drive ou None em caso de falha.
    """
    from googleapiclient.http import MediaIoBaseUpload
    from core import pdf_generator as _pdf_gen
    from core.cred_manager import load_oauth

    from googleapiclient.discovery import build as _build
    drive_svc = _build("drive", "v3", credentials=load_oauth(), cache_discovery=False)

    # Descobre a pasta onde o Slides foi salvo
    file_meta = drive_svc.files().get(
        fileId=presentation_id,
        fields="parents",
        supportsAllDrives=True,
    ).execute()
    folder_id = file_meta["parents"][0]

    # Gera o PDF
    pdf_bytes = _pdf_gen.gerar_pdf(cliente.categoria, dados)

    # Nome do arquivo: Report_DD.MM_NomeCliente.pdf
    data_str = periodo_ref.inicio.strftime("%d.%m")
    safe_nome = "".join(c if c.isalnum() or c in " _-" else "_" for c in cliente.nome).strip()
    filename = f"Report_{data_str}_{safe_nome}.pdf"

    # Upload para o Drive
    media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf")
    uploaded = drive_svc.files().create(
        body={"name": filename, "parents": [folder_id]},
        media_body=media,
        fields="id",
        supportsAllDrives=True,
    ).execute()

    pdf_id = uploaded["id"]
    _log.info("PDF subido ao Drive: %s → %s", filename, pdf_id)
    return f"https://drive.google.com/file/d/{pdf_id}/view"
