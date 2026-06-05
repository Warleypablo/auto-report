"""Wraps core report generation and returns the report URL.

Called in a background thread by the gestor API. Replicates the data steps of
report_generator.processar_cliente(), gera o report em PDF (Playwright), sobe
para o Drive do cliente e devolve a URL do PDF.

O report é SEMPRE PDF — não há geração de Google Slides nem fallback. Se o PDF
falhar, o erro propaga e o job é marcado como ERRO (com o motivo).
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
    data_inicio: str | None = None,
    data_fim: str | None = None,
    today: "date | None" = None,
):
    """Resolve (periodo_ref, periodo_comp) a partir dos dados do trigger.

    - SEMANAL: se ``data_inicio`` e ``data_fim`` vierem, usa esse período livre
      (precedência); o comparativo é o período de MESMA DURAÇÃO imediatamente
      anterior. Senão, a semana útil seg–sex de ``semana_inicio`` (qualquer dia
      serve) ou a semana vigente, com comparativo = semana anterior.
    - MENSAL: mês selecionado (via âncora no dia 15 do mês seguinte); comparativo
      = mês anterior. (Comportamento original preservado.)
    """
    from core import periodo as P  # type: ignore

    freq = frequencia.upper()
    if freq == "SEMANAL":
        if data_inicio and data_fim:
            ini = date.fromisoformat(data_inicio)
            fim = date.fromisoformat(data_fim)
            ref = P.Periodo(inicio=ini, fim=fim, fim_plus_1=fim + timedelta(days=1))
            # Comparativo: mesma duração, imediatamente antes do início.
            diff = (fim - ini).days
            comp_fim = ini - timedelta(days=1)
            comp_ini = comp_fim - timedelta(days=diff)
            comp = P.Periodo(
                inicio=comp_ini, fim=comp_fim, fim_plus_1=comp_fim + timedelta(days=1)
            )
            return ref, comp
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


def _core_cliente_from_db(db_cliente):
    """Monta um ``core.leitura_central.Cliente`` a partir de um registro de
    ``public.clientes`` (o modelo do banco).

    Fallback para clientes que existem só no banco — cadastrados via sistema
    (POST /clientes) ou importados do ClickUp — e portanto não têm linha na
    Planilha Central. ``extras={}`` faz ``set_status`` virar no-op (não há célula
    de STATUS na planilha para esse cliente). Campos ausentes viram "" porque o
    ``__post_init__`` do core.Cliente chama ``.strip()`` (None quebraria).
    """
    from core.leitura_central import Cliente as CoreCliente  # type: ignore

    cat = getattr(db_cliente.categoria, "value", db_cliente.categoria)
    return CoreCliente(
        nome=db_cliente.nome,
        categoria=str(cat or ""),
        painel_url=db_cliente.painel_url or "",
        pasta_url=db_cliente.pasta_url or "",
        id_google_ads=db_cliente.id_google_ads or "",
        id_meta_ads=db_cliente.id_meta_ads or "",
        id_ga4=db_cliente.id_ga4 or "",
        extras={},
    )


def _resolver_cliente(slug: str, nome_cliente: str, core_settings, session_factory=None):
    """Resolve o ``core.Cliente`` usado na geração do report.

    Tenta primeiro a Planilha Central (por nome); se o cliente não estiver lá,
    cai para o registro do banco (``public.clientes``) — caso de cliente
    cadastrado via sistema. Os IDs de mídia/categoria/pasta vêm do banco, que já
    contém esses campos.

    Raises:
        ValueError: se o cliente não existe nem na planilha nem no banco.
    """
    from core.leitura_central import fetch_clientes  # type: ignore

    clientes = fetch_clientes(
        atualizar=False,
        only=nome_cliente,
        sheet_url=core_settings.CENTRAL_SHEET_URL,
        tab_name=core_settings.CENTRAL_TAB_NAME,
    )
    if clientes:
        return clientes[0]

    if session_factory is None:
        from db import SessionLocal  # type: ignore

        session_factory = SessionLocal
    from sqlalchemy import select

    from models.cliente import Cliente as ClienteDB  # type: ignore

    with session_factory() as session:
        db_cli = session.scalar(select(ClienteDB).where(ClienteDB.slug == slug))
    if db_cli is None:
        raise ValueError(
            f"Cliente '{nome_cliente}' (slug={slug!r}) não encontrado "
            "na Planilha Central nem no banco"
        )
    return _core_cliente_from_db(db_cli)


def gerar_slides(slug: str, nome_cliente: str, mes: str, frequencia: str = "MENSAL", semana_inicio: str | None = None, data_inicio: str | None = None, data_fim: str | None = None) -> str:
    """Gera o report em PDF para um cliente e devolve a URL do Drive.

    (Nome mantido como ``gerar_slides`` por compatibilidade com o chamador; o
    comportamento é PDF-only.)

    Args:
        slug: DB slug (used only for error messages here)
        nome_cliente: Client name as it appears in the Central Sheet
        mes: Reference month in YYYY-MM format
        frequencia: "MENSAL" or "SEMANAL"

    Returns:
        URL do Drive do PDF gerado.

    Raises:
        ValueError: if client is not found in the Central Sheet
        RuntimeError: se a geração/upload do PDF não devolver URL
        Exception: propagated from core (API errors, Drive errors, etc.)
    """
    from config import settings as core_settings  # type: ignore
    from core import (  # type: ignore
        basic_placeholders,
        template_manager,
    )
    from core.categorias import get_handler  # type: ignore
    from core.status import set_status  # type: ignore

    # Planilha Central como fonte primária; fallback para o banco quando o cliente
    # só existe lá (cadastrado via sistema / importado do ClickUp).
    cliente = _resolver_cliente(slug, nome_cliente, core_settings)
    FREQ = frequencia.upper()

    periodo_ref, periodo_comp = _resolver_periodo_ref(
        mes, FREQ, semana_inicio, data_inicio=data_inicio, data_fim=data_fim
    )

    dados = basic_placeholders.montar_placeholders_basicos(cliente, periodo_ref, FREQ=FREQ)
    dados.update(
        basic_placeholders.montar_placeholders_basicos(cliente, periodo_comp, FREQ=FREQ, sufixo="_comp")
    )

    handler = get_handler(cliente.categoria)
    dados.update(handler.coletar_dados(cliente, periodo_ref, periodo_comp))

    # Análise narrativa por IA (não bloqueia o report — None se falhar/sem key).
    try:
        from core import ai_insights
        from app_settings import get_settings as _get_settings
        _contexto_ia = {
            "cliente": cliente.nome,
            "categoria": cliente.categoria,
            "freq": "Semanal" if FREQ == "SEMANAL" else "Mensal",
            "periodo": f"{periodo_ref.inicio:%d/%m} a {periodo_ref.fim:%d/%m/%Y}",
        }
        _texto_ia = ai_insights.gerar_analise(
            dados, _contexto_ia, api_key=_get_settings().anthropic_api_key
        )
        if _texto_ia:
            dados["{{ai_analise}}"] = _texto_ia
    except Exception:
        _log.exception("Falha ao injetar análise de IA para %s", cliente.nome)

    # ── Report SEMPRE em PDF. Sem Google Slides, sem fallback. ──────────────
    # Se a geração do PDF falhar, o erro PROPAGA (o job vira ERRO visível com o
    # motivo, via handler do chamador) em vez de cair calado no Slides.
    _log.info("[PDF] gerando report PDF p/ %s", cliente.nome)
    folder_id = template_manager._dest_folder(
        cliente,
        template_manager._parse_id(cliente.pasta_url, "folder"),
        freq=FREQ,
    )
    pdf_url = _gerar_e_subir_pdf(cliente, dados, periodo_ref, folder_id)
    if not pdf_url:
        raise RuntimeError(
            f"Geração de PDF retornou vazio para {cliente.nome} "
            "(upload ao Drive não devolveu URL)"
        )
    set_status(cliente, "GERADO ✅")
    _log.info("[PDF] sucesso p/ %s → %s", cliente.nome, pdf_url)
    return pdf_url


def _gerar_e_subir_pdf(cliente, dados: dict, periodo_ref, folder_id: str) -> str | None:
    """Gera PDF via Playwright e sobe para o Drive na pasta informada.

    Retorna a URL pública do Drive ou None em caso de falha.
    """
    from googleapiclient.http import MediaIoBaseUpload
    from core import pdf_generator as _pdf_gen
    from core.cred_manager import load_oauth

    from googleapiclient.discovery import build as _build
    drive_svc = _build("drive", "v3", credentials=load_oauth(), cache_discovery=False)

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
