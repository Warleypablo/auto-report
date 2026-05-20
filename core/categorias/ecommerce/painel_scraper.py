from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

import pandas as pd
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from utils.logger import get_logger  # type: ignore
from core.periodo import Periodo  # type: ignore
from core.cred_manager import load_oauth  # type: ignore
from core.status import set_status  # type: ignore

from utils.formatting import _fmt_brl, _fmt_percent, _to_float_br, _fmt_roas, _fmt_int, _DEF_DASH, _MONTH_PT
from utils.retry import execute_with_retries

import re

log = get_logger(__name__)

__all__ = ["parse_sheet_id", "coletar_metricas"]

# ---------------------------------------------------------------------------
# Helpers Google Sheets
# ---------------------------------------------------------------------------

def _build_sheets_service():
    """Client Sheets autenticado com a credencial OAuth (Sheets/Drive)."""
    return build(
        "sheets",
        "v4",
        credentials=load_oauth(),
        cache_discovery=False,
    )

# ---------------------------------------------------------------------------
# Regex – extrai o *spreadsheetId* da URL
# ---------------------------------------------------------------------------

_RE_SHEET_ID = re.compile(r"/d/([a-zA-Z0-9-_]+)")


def parse_sheet_id(url: str) -> str:
    m = _RE_SHEET_ID.search(url)
    if not m:
        raise ValueError(f"URL de planilha inválida: {url}")
    return m.group(1)

# ---------------------------------------------------------------------------
# Download DataFrame com fallback de aba
# ---------------------------------------------------------------------------

def _fetch_dataframe(spreadsheet_id: str, tab_name: str = "Acompanhamento Geral") -> pd.DataFrame:
    import time
    service = _build_sheets_service()
    max_retries = 5
    delay = 2
    for attempt in range(max_retries):
        try:
            resp = execute_with_retries(
                lambda: service.spreadsheets().values().get(
                    spreadsheetId=spreadsheet_id,
                    range=tab_name
                ).execute(),
                logger=log,
                context=f"sheets.values().get ({spreadsheet_id}, {tab_name})"
            )
            break
        except HttpError as exc:
            if exc.resp.status == 400 and "Unable to parse range" in str(exc):
                raise  # propaga para _try_tab lidar
            elif exc.resp.status == 503:
                log.warning(f"Sheets API 503 (rate limit) – tentativa {attempt+1}/{max_retries}. Aguarde {delay}s...")
                time.sleep(delay)
                delay *= 2
                continue
            else:
                raise
    else:
        raise RuntimeError(f"Sheets API 503 – excedido número máximo de tentativas ({max_retries})")

    values: List[List[str]] = resp.get("values", [])
    if not values:
        raise RuntimeError("Planilha vazia ou aba sem dados.")

    header, *rows = values
    n_cols = len(header)
    rows = [r[:n_cols] + [""] * max(0, n_cols - len(r)) for r in rows]
    return pd.DataFrame(rows, columns=header)

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

    # Prioridade 1: aba com nome exato do ano (e.g. "2026")
    for tab in all_tabs:
        if tab.strip() == year_str:
            candidates.append(tab)
            break

    # Prioridade 2: abas contendo o ano no nome (e.g. "Acompanhamento Geral 2026")
    for tab in all_tabs:
        if year_str in tab and tab not in candidates:
            candidates.append(tab)

    # Prioridade 3: aba padrão (se existir e ainda não foi adicionada)
    if default_tab not in candidates:
        if default_tab in all_tabs:
            candidates.append(default_tab)

    # Fallback: se nenhuma candidata, usa a primeira aba disponível
    if not candidates and all_tabs:
        candidates.append(all_tabs[0])

    if not candidates:
        candidates = [default_tab]

    return candidates

# ---------------------------------------------------------------------------
# Dataclass resultado (placeholders)
# ---------------------------------------------------------------------------

@dataclass
class _Metricas:
    faturamento_semana: Optional[float] = None
    faturamento_mes: Optional[float] = None
    investimento_semana: Optional[float] = None
    investimento_mes: Optional[float] = None
    pedidos_semana: Optional[int] = None
    sessoes_semana: Optional[int] = None
    roas: Optional[float] = None
    taxa_conversao: Optional[float] = None  # decimal (0.034)
    ticket_medio: Optional[float] = None
    custo_por_sessao: Optional[float] = None
    meta_fat: Optional[float] = None
    meta_invest: Optional[float] = None
    meta_per_fat: Optional[float] = None  # decimal
    meta_per_inv: Optional[float] = None  # decimal
    cpa_semana: Optional[float] = None #Novo

    def as_placeholders(self, sufixo: str="") -> Dict[str, str]:
        """Converte as métricas em valores de placeholder prontos para Slides."""
        return {
            f"{{{{fat_sem{sufixo}}}}}":    _fmt_brl(self.faturamento_semana),
            f"{{{{fat_mes{sufixo}}}}}":    _fmt_brl(self.faturamento_mes),
            f"{{{{inv_sem{sufixo}}}}}":    _fmt_brl(self.investimento_semana),
            f"{{{{inv_mes{sufixo}}}}}":    _fmt_brl(self.investimento_mes),
            f"{{{{vendas{sufixo}}}}}":     _fmt_int(self.pedidos_semana),
            f"{{{{roas{sufixo}}}}}":       _fmt_roas(self.roas) if self.roas is not None else _DEF_DASH,
            f"{{{{taxa_conv{sufixo}}}}}":  _fmt_percent(self.taxa_conversao),
            f"{{{{tck_med{sufixo}}}}}":    _fmt_brl(self.ticket_medio, 2),
            f"{{{{cps{sufixo}}}}}":        _fmt_brl(self.custo_por_sessao, 2),
            f"{{{{meta_fat{sufixo}}}}}":   _fmt_brl(self.meta_fat),
            f"{{{{meta_inv{sufixo}}}}}":   _fmt_brl(self.meta_invest),
            f"{{{{per_meta_fat{sufixo}}}}}":_fmt_percent(self.meta_per_fat),
            f"{{{{per_meta_inv{sufixo}}}}}":_fmt_percent(self.meta_per_inv),
            f"{{{{cpa{sufixo}}}}}":        _fmt_brl(self.cpa_semana, 2) if self.cpa_semana is not None else _DEF_DASH,
        }

# ---------------------------------------------------------------------------
# Processamento de uma aba individual
# ---------------------------------------------------------------------------

def _try_tab(sheet_id: str, aba: str, cliente, periodo: Periodo) -> Optional[_Metricas]:
    """Tenta extrair métricas de uma aba específica.

    Retorna ``_Metricas`` se encontrou dados semanais, ou ``None`` para
    sinalizar que a próxima aba deve ser tentada.
    """
    # 1) Baixa DataFrame
    try:
        df = _fetch_dataframe(sheet_id, aba)
    except Exception as exc:
        log.warning("Falha ao buscar aba '%s' (%s): %s", aba, cliente.nome, exc)
        return None

    # 2) Validação de colunas mínimas
    required_cols = {"DATA", "VALOR INVESTIDO", "FATURAMENTO", "PEDIDOS", "SESSÕES"}
    missing = required_cols - set(df.columns)
    if missing:
        log.warning("Aba '%s' sem colunas obrigatórias: %s (%s)", aba, ', '.join(missing), cliente.nome)
        return None

    # 3) Prepara coluna de texto original e parseia datas
    df["DATA_TXT"] = df["DATA"].astype(str).str.strip().str.upper()

    _raw_sample = df["DATA_TXT"].head(5).tolist()
    log.info("Amostra DATA bruta (%s, aba='%s'): %s", cliente.nome, aba, _raw_sample)

    df["DATA"] = (
        pd.to_datetime(df["DATA"].astype(str).str.strip(),
                       format="%d/%m/%Y",
                       dayfirst=True,
                       errors="coerce")
        .dt.normalize()
        .dt.date
    )

    _datas_validas = df["DATA"].notna().sum()
    log.info("Datas parseadas (%s, aba='%s'): %d/%d válidas",
             cliente.nome, aba, _datas_validas, len(df))

    # 4) Conversões de valores numéricos
    numeric_cols = [
        "VALOR INVESTIDO", "FATURAMENTO", "PEDIDOS", "SESSÕES",
        "TAXA DE CONVERSÃO", "TICKET MÉDIO", "META INVESTIMENTO", "META FATURAMENTO",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = df[col].apply(_to_float_br)

    # Helpers
    def _sum(s: pd.Series) -> Optional[float]:
        s_non_null = s.dropna()
        return None if s_non_null.empty else float(s_non_null.sum())

    def _first_non_null(s: pd.Series) -> Optional[float]:
        s_non_null = s.dropna()
        return None if s_non_null.empty else float(s_non_null.iloc[0])

    # 5) Segmentação semanal
    inicio_periodo = periodo.inicio
    fim_periodo = periodo.fim

    linhas_validas = df["DATA"].notna()
    semana = df[linhas_validas & df["DATA"].between(inicio_periodo, fim_periodo, inclusive="both")]

    log.info(
        "Filtro semanal (%s, aba='%s'): periodo=%s→%s | linhas_validas=%d | semana=%d",
        cliente.nome, aba, inicio_periodo, fim_periodo,
        linhas_validas.sum(), len(semana),
    )

    # Fallback de ano: se não achou dados, verifica se a planilha usa outro ano
    year_offset = 0
    if semana.empty and linhas_validas.any():
        datas_na_planilha = df.loc[linhas_validas, "DATA"]
        ano_planilha = datas_na_planilha.iloc[-1].year  # último registro
        if ano_planilha != periodo.fim.year:
            year_offset = ano_planilha - periodo.fim.year
            inicio_ajustado = inicio_periodo.replace(year=inicio_periodo.year + year_offset)
            fim_ajustado = fim_periodo.replace(year=fim_periodo.year + year_offset)
            semana = df[linhas_validas & df["DATA"].between(inicio_ajustado, fim_ajustado, inclusive="both")]
            log.info(
                "Fallback de ano (%s): ajuste %d→%d | semana=%d",
                cliente.nome, periodo.fim.year, ano_planilha, len(semana),
            )
            inicio_periodo = inicio_ajustado
            fim_periodo = fim_ajustado

    # Se não encontrou dados semanais mesmo com fallback, sinaliza próxima aba
    if semana.empty:
        return None

    # 6) Segmentação mensal (linha-síntese)
    nome_mes = _MONTH_PT[periodo.fim.month]
    linha_mes = df[df["DATA"].isna() & (df["DATA_TXT"] == nome_mes)]

    if not linha_mes.empty:
        fat_mes = _first_non_null(linha_mes["FATURAMENTO"])
        inv_mes = _first_non_null(linha_mes["VALOR INVESTIDO"])
        meta_fat = _first_non_null(linha_mes.get("META FATURAMENTO", pd.Series(dtype=float)))
        meta_inv = _first_non_null(linha_mes.get("META INVESTIMENTO", pd.Series(dtype=float)))
    else:
        mes_inicio = periodo.inicio.replace(day=1, year=periodo.inicio.year + year_offset)
        mes = df[df["DATA"].between(mes_inicio, fim_periodo)]
        fat_mes = _sum(mes["FATURAMENTO"])
        inv_mes = _sum(mes["VALOR INVESTIDO"])
        meta_fat = _first_non_null(mes.get("META FATURAMENTO", pd.Series(dtype=float)))
        meta_inv = _first_non_null(mes.get("META INVESTIMENTO", pd.Series(dtype=float)))

    # 7) Agregações da semana
    fat_semana = _sum(semana["FATURAMENTO"])
    inv_semana = _sum(semana["VALOR INVESTIDO"])
    pedidos_semana = _sum(semana["PEDIDOS"])
    sessoes_semana = _sum(semana["SESSÕES"])

    cpa_semana = (
        None if (inv_semana is None or pedidos_semana is None or pedidos_semana == 0)
        else inv_semana / pedidos_semana)

    roas_semana = (
        None if (inv_semana is None or inv_semana == 0 or fat_semana is None)
        else fat_semana / inv_semana)

    taxa_conv = (
        None if (sessoes_semana is None or sessoes_semana == 0 or pedidos_semana is None)
        else pedidos_semana / sessoes_semana)

    ticket_medio = (
        None if (pedidos_semana is None or pedidos_semana == 0 or fat_semana is None)
        else fat_semana / pedidos_semana)

    custo_por_sessao = (
        None if (sessoes_semana is None or sessoes_semana == 0 or inv_semana is None)
        else inv_semana / sessoes_semana)

    # 8) Percentuais de meta
    meta_per_fat = (
        None if (fat_mes is None or fat_mes == 0 or meta_fat is None)
        else fat_mes / meta_fat)

    meta_per_inv = (
        None if (inv_mes is None or inv_mes == 0 or meta_inv is None)
        else inv_mes / meta_inv)

    return _Metricas(
        faturamento_semana=fat_semana,
        faturamento_mes=fat_mes,
        investimento_semana=inv_semana,
        investimento_mes=inv_mes,
        pedidos_semana=int(pedidos_semana) if pedidos_semana is not None else None,
        sessoes_semana=int(sessoes_semana) if sessoes_semana is not None else None,
        roas=roas_semana,
        taxa_conversao=taxa_conv,
        ticket_medio=ticket_medio,
        custo_por_sessao=custo_por_sessao,
        meta_fat=meta_fat,
        meta_invest=meta_inv,
        meta_per_fat=meta_per_fat,
        meta_per_inv=meta_per_inv,
        cpa_semana=cpa_semana,
    )

# ---------------------------------------------------------------------------
# Função principal
# ---------------------------------------------------------------------------

def coletar_metricas(cliente, periodo: Periodo, sufixo: str = "", aba: str = "Acompanhamento Geral") -> Dict[str, str]:
    """Baixa métricas do Painel de Controle e devolve placeholders prontos.

    Tenta múltiplas abas automaticamente, priorizando abas cujo nome
    contenha o ano do período (ex.: "2026", "Acompanhamento Geral 2026").

    * **Semana**: intervalo fechado [periodo.inicio, periodo.fim].
    * **Mês**: utiliza a linha‑síntese (JANEIRO…)
      – se ausente, soma do dia 1 até periodo.fim como fallback.
    """
    # 1) Valida URL
    try:
        sheet_id = parse_sheet_id(cliente.painel_url)
    except ValueError as exc:
        log.error("URL Painel inválida (%s): %s", cliente.nome, exc)
        set_status(cliente, "PAINEL URL INVÁLIDA")
        return {}

    # 2) Descobre abas candidatas (prioriza ano do período)
    candidates = _get_candidate_tabs(sheet_id, aba, periodo.fim.year)
    log.info("Abas candidatas (%s): %s", cliente.nome, candidates)

    # 3) Tenta cada aba até encontrar dados para o período
    for tab in candidates:
        met = _try_tab(sheet_id, tab, cliente, periodo)
        if met is not None:
            log.info("Dados encontrados na aba '%s' (%s)", tab, cliente.nome)
            return met.as_placeholders(sufixo)

    # Nenhuma aba tinha dados para o período
    log.warning(
        "Nenhuma aba com dados para %s→%s (%s). Abas tentadas: %s",
        periodo.inicio, periodo.fim, cliente.nome, candidates,
    )
    return _Metricas().as_placeholders(sufixo)
