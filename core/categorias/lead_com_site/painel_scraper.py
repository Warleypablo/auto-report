from __future__ import annotations

"""Coletor de métricas de geração de leads.

Este módulo replica a lógica do *painel_scraper* original, porém ajustado
para campanhas de geração de *leads* em vez de e‑commerce.

Principais mudanças em relação à versão anterior:
• **Sessões não são mais capturadas** da planilha; o valor deve ser
  fornecido externamente como argumento ``sessoes_semana``.
• Removida a coluna *SESSÕES* das validações e das conversões numéricas.
• O placeholder ``{{sessao}}`` deixa de ser produzido – a sessão será
  empacotada por outra etapa do pipeline.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional

import re

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.logger import get_logger  # type: ignore
from core.periodo import Periodo  # type: ignore
from core.cred_manager import load_oauth  # type: ignore
from core.status import set_status  # type: ignore
from utils.formatting import (
    _fmt_brl,
    _fmt_int,
    _fmt_percent,
    _to_float_br,
    _DEF_DASH,
    _MONTH_PT,
)
from utils.retry import execute_with_retries

log = get_logger(__name__)

__all__ = ["parse_sheet_id", "coletar_metricas_leads"]

# ---------------------------------------------------------------------------
# Sheets helpers
# ---------------------------------------------------------------------------

def _build_sheets_service():
    """Instância autenticada da API Google Sheets."""
    return build(
        "sheets",
        "v4",
        credentials=load_oauth(),
        cache_discovery=False,
    )


_RE_SHEET_ID = re.compile(r"/d/([a-zA-Z0-9-_]+)")


def parse_sheet_id(url: str) -> str:  # noqa: D401
    """Extrai *spreadsheetId* da URL ou lança ``ValueError``."""
    m = _RE_SHEET_ID.search(url)
    if not m:
        raise ValueError(f"URL de planilha inválida: {url}")
    return m.group(1)


# ---------------------------------------------------------------------------
# DataFrame loader com fallback de aba
# ---------------------------------------------------------------------------

def _fetch_dataframe(spreadsheet_id: str, tab_name: str = "Acompanhamento Geral") -> pd.DataFrame:  # noqa: D401,E501
    """Baixa tabela da planilha; se a aba não existir usa a primeira disponível."""
    import time
    service = _build_sheets_service()
    max_retries = 5
    delay = 2.0
    last_exc = None
    for attempt in range(max_retries):
        try:
            resp = execute_with_retries(
                lambda: service.spreadsheets()
                    .values()
                    .get(spreadsheetId=spreadsheet_id, range=tab_name)
                    .execute(),
                logger=log,
                context=f"sheets.values().get ({spreadsheet_id}, {tab_name})"
            )
            values: List[List[str]] = resp.get("values", [])
            if not values:
                raise RuntimeError("Planilha vazia ou aba sem dados.")
            header, *rows = values
            n_cols = len(header)
            rows = [r[:n_cols] + [""] * max(0, n_cols - len(r)) for r in rows]
            return pd.DataFrame(rows, columns=header)
        except HttpError as exc:
            last_exc = exc
            if exc.resp.status == 400 and "Unable to parse range" in str(exc):
                raise  # propaga para _try_tab lidar
            elif exc.resp.status == 503:
                log.warning(
                    "Sheets API 503 (rate limit) na tentativa %d/%d. Aguardando %.1fs...",
                    attempt + 1, max_retries, delay,
                )
                time.sleep(delay)
                delay *= 2
            else:
                break
        except Exception as exc:
            last_exc = exc
            break
    raise last_exc if last_exc else RuntimeError("Falha ao coletar dados da planilha.")


# ---------------------------------------------------------------------------
# Descoberta de abas candidatas por ano
# ---------------------------------------------------------------------------

def _get_candidate_tabs(sheet_id: str, default_tab: str, target_year: int) -> List[str]:
    """Retorna lista ordenada de abas a tentar, priorizando o ano do período."""
    year_str = str(target_year)
    candidates: List[str] = []

    try:
        service = _build_sheets_service()
        meta = execute_with_retries(
            lambda: service.spreadsheets().get(
                spreadsheetId=sheet_id,
                fields="sheets.properties.title"
            ).execute(),
            logger=log,
            context=f"sheets.get ({sheet_id}, list tabs)"
        )
        all_tabs = [s["properties"]["title"] for s in meta.get("sheets", [])]
    except Exception as exc:
        log.warning("Falha ao listar abas (%s): %s", sheet_id, exc)
        return [default_tab]

    for tab in all_tabs:
        if tab.strip() == year_str:
            candidates.append(tab)
            break

    for tab in all_tabs:
        if year_str in tab and tab not in candidates:
            candidates.append(tab)

    if default_tab not in candidates:
        if default_tab in all_tabs:
            candidates.append(default_tab)

    if not candidates and all_tabs:
        candidates.append(all_tabs[0])

    if not candidates:
        candidates = [default_tab]

    return candidates


# ---------------------------------------------------------------------------
# Dataclass de retorno
# ---------------------------------------------------------------------------


@dataclass
class _MetricasLead:
    """Estrutura interna para armazenar métricas já tipadas."""

    lead_semana: Optional[int] = None
    lead_mes: Optional[int] = None
    investimento_semana: Optional[float] = None
    investimento_mes: Optional[float] = None
    sessoes_semana: Optional[int] = None
    cpl_semana: Optional[float] = None
    cps_semana: Optional[float] = None
    lps_semana: Optional[float] = None  # Leads por sessão
    meta_lead: Optional[int] = None
    meta_invest: Optional[float] = None
    meta_per_lead: Optional[float] = None  # decimal (0‑1)
    meta_per_inv: Optional[float] = None   # decimal (0‑1)

    def as_placeholders(self, sufixo: str = "") -> Dict[str, str]:  # noqa: D401
        return {
            f"{{{{lead_sem{sufixo}}}}}": _fmt_int(self.lead_semana),
            f"{{{{lead_mes{sufixo}}}}}": _fmt_int(self.lead_mes),
            f"{{{{inv_sem{sufixo}}}}}": _fmt_brl(self.investimento_semana),
            f"{{{{inv_mes{sufixo}}}}}": _fmt_brl(self.investimento_mes),
            f"{{{{cpl{sufixo}}}}}": _fmt_brl(self.cpl_semana, 2) if self.cpl_semana is not None else _DEF_DASH,
            f"{{{{cps{sufixo}}}}}": _fmt_brl(self.cps_semana, 2) if self.cps_semana is not None else _DEF_DASH,
            f"{{{{lps{sufixo}}}}}": _fmt_percent(self.lps_semana) if self.lps_semana is not None else _DEF_DASH,
            f"{{{{meta_lead{sufixo}}}}}": _fmt_int(self.meta_lead),
            f"{{{{meta_inv{sufixo}}}}}": _fmt_brl(self.meta_invest),
            f"{{{{per_meta_lead{sufixo}}}}}": _fmt_percent(self.meta_per_lead),
            f"{{{{per_meta_inv{sufixo}}}}}": _fmt_percent(self.meta_per_inv),
        }


# ---------------------------------------------------------------------------
# Processamento de uma aba individual
# ---------------------------------------------------------------------------

def _try_tab(sheet_id: str, aba: str, cliente, periodo: Periodo,
             sessoes_semana: Optional[int]) -> Optional[_MetricasLead]:
    """Tenta extrair métricas de uma aba. Retorna None se sem dados semanais."""
    try:
        df = _fetch_dataframe(sheet_id, aba)
    except Exception as exc:
        log.warning("Falha ao buscar aba '%s' (%s): %s", aba, cliente.nome, exc)
        return None

    required_cols = {"DATA", "VALOR INVESTIDO", "LEADS"}
    missing = required_cols - set(df.columns)
    if missing:
        log.warning("Aba '%s' sem colunas obrigatórias: %s (%s)", aba, ', '.join(missing), cliente.nome)
        return None

    df["DATA_TXT"] = df["DATA"].astype(str).str.strip().str.upper()
    log.info("Amostra DATA bruta (%s, aba='%s'): %s", cliente.nome, aba,
             df["DATA_TXT"].head(5).tolist())

    df["DATA"] = (
        pd.to_datetime(df["DATA"].astype(str).str.strip(),
                       format="%d/%m/%Y", dayfirst=True, errors="coerce")
        .dt.normalize()
        .dt.date
    )

    log.info("Datas parseadas (%s, aba='%s'): %d/%d válidas",
             cliente.nome, aba, df["DATA"].notna().sum(), len(df))

    numeric_cols = ["VALOR INVESTIDO", "LEADS", "META INVESTIMENTO", "META LEADS"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(_to_float_br)

    def _sum(s: pd.Series) -> Optional[float]:
        s_non_null = s.dropna()
        return None if s_non_null.empty else float(s_non_null.sum())

    def _first_non_null(s: pd.Series) -> Optional[float]:
        s_non_null = s.dropna()
        return None if s_non_null.empty else float(s_non_null.iloc[0])

    inicio, fim = periodo.inicio, periodo.fim
    linhas_validas = df["DATA"].notna()
    semana = df[linhas_validas & df["DATA"].between(inicio, fim, inclusive="both")]

    log.info("Filtro semanal (%s, aba='%s'): periodo=%s→%s | semana=%d",
             cliente.nome, aba, inicio, fim, len(semana))

    # Fallback de ano: se não achou dados, verifica se a planilha usa outro ano
    year_offset = 0
    if semana.empty and linhas_validas.any():
        datas_na_planilha = df.loc[linhas_validas, "DATA"]
        ano_planilha = datas_na_planilha.iloc[-1].year
        if ano_planilha != periodo.fim.year:
            year_offset = ano_planilha - periodo.fim.year
            inicio = inicio.replace(year=inicio.year + year_offset)
            fim = fim.replace(year=fim.year + year_offset)
            semana = df[linhas_validas & df["DATA"].between(inicio, fim, inclusive="both")]
            log.info("Fallback de ano (%s): ajuste %d→%d | semana=%d",
                     cliente.nome, periodo.fim.year, ano_planilha, len(semana))

    if semana.empty:
        return None

    nome_mes = _MONTH_PT[periodo.fim.month]
    linha_mes = df[df["DATA"].isna() & (df["DATA_TXT"] == nome_mes)]

    if not linha_mes.empty:
        lead_mes = _first_non_null(linha_mes["LEADS"])
        inv_mes = _first_non_null(linha_mes["VALOR INVESTIDO"])
        meta_lead = _first_non_null(linha_mes.get("META LEADS", pd.Series(dtype=float)))
        meta_inv = _first_non_null(linha_mes.get("META INVESTIMENTO", pd.Series(dtype=float)))
    else:
        mes_inicio = periodo.inicio.replace(day=1, year=periodo.inicio.year + year_offset)
        mes = df[df["DATA"].between(mes_inicio, fim)]
        lead_mes = _sum(mes["LEADS"])
        inv_mes = _sum(mes["VALOR INVESTIDO"])
        meta_lead = _first_non_null(mes.get("META LEADS", pd.Series(dtype=float)))
        meta_inv = _first_non_null(mes.get("META INVESTIMENTO", pd.Series(dtype=float)))

    lead_semana = _sum(semana["LEADS"])
    inv_semana = _sum(semana["VALOR INVESTIDO"])

    sessoes_semana_val = sessoes_semana
    cpl_semana = None if not inv_semana or not lead_semana else inv_semana / lead_semana
    cps_semana = None if not inv_semana or not sessoes_semana_val else inv_semana / sessoes_semana_val
    lps_semana = None if not lead_semana or not sessoes_semana_val else lead_semana / sessoes_semana_val

    meta_per_lead = None if not lead_mes or not meta_lead else lead_mes / meta_lead
    meta_per_inv = None if not inv_mes or not meta_inv else inv_mes / meta_inv

    return _MetricasLead(
        lead_semana=int(lead_semana) if lead_semana is not None else None,
        lead_mes=int(lead_mes) if lead_mes is not None else None,
        investimento_semana=inv_semana,
        investimento_mes=inv_mes,
        sessoes_semana=int(sessoes_semana_val) if sessoes_semana_val is not None else None,
        cpl_semana=cpl_semana,
        cps_semana=cps_semana,
        lps_semana=lps_semana,
        meta_lead=int(meta_lead) if meta_lead is not None else None,
        meta_invest=meta_inv,
        meta_per_lead=meta_per_lead,
        meta_per_inv=meta_per_inv,
    )


# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def coletar_metricas_leads(  # noqa: D401
    cliente,
    periodo: Periodo,
    sessoes_semana: Optional[int],
    sufixo: str = "",
    aba: str = "Acompanhamento Geral",
) -> Dict[str, str]:
    """Retorna placeholders de métricas de leads para o período solicitado.

    Tenta múltiplas abas automaticamente, priorizando abas cujo nome
    contenha o ano do período.
    """
    try:
        sheet_id = parse_sheet_id(cliente.painel_url)
    except ValueError as exc:
        log.error("URL Painel inválida (%s): %s", cliente.nome, exc)
        set_status(cliente, "PAINEL URL INVÁLIDA")
        return {}

    candidates = _get_candidate_tabs(sheet_id, aba, periodo.fim.year)
    log.info("Abas candidatas (%s): %s", cliente.nome, candidates)

    for tab in candidates:
        met = _try_tab(sheet_id, tab, cliente, periodo, sessoes_semana)
        if met is not None:
            log.info("Dados encontrados na aba '%s' (%s)", tab, cliente.nome)
            return met.as_placeholders(sufixo)

    log.warning(
        "Nenhuma aba com dados para %s→%s (%s). Abas tentadas: %s",
        periodo.inicio, periodo.fim, cliente.nome, candidates,
    )
    return _MetricasLead().as_placeholders(sufixo)
