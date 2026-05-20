from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import Any

logger = logging.getLogger(__name__)

_EMPTY_VALUES_LOWER = {"", "-", "n/a", "—"}
_STRIPPABLE = ("R$", "%", "x")


def parse_pt_br(valor: Any) -> Decimal | None:
    """Converte strings PT-BR (R$, %, x, etc.) para Decimal.

    Retorna None para valores vazios/ausentes. Levanta ValueError para strings
    sintaticamente inválidas.
    """
    if valor is None:
        return None
    if isinstance(valor, bool):
        raise ValueError("bool não é numérico")
    if isinstance(valor, Decimal):
        return valor
    if isinstance(valor, (int, float)):
        return Decimal(str(valor))
    if not isinstance(valor, str):
        raise ValueError(f"Tipo não suportado: {type(valor).__name__}")

    s = valor.strip()
    if s.lower() in _EMPTY_VALUES_LOWER:
        return None

    sinal = ""
    if s.startswith("+"):
        s = s[1:]
    elif s.startswith("-"):
        sinal = "-"
        s = s[1:]

    for marker in _STRIPPABLE:
        s = s.replace(marker, "")

    s = s.strip()
    if not s:
        return None

    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(".", "")

    try:
        return Decimal(sinal + s)
    except InvalidOperation as exc:
        raise ValueError(f"Não foi possível converter {valor!r} para Decimal") from exc


def parse_metric(nome: str, valor: Any) -> Decimal | None:
    """Versão tolerante: loga warning e devolve None em erro."""
    try:
        return parse_pt_br(valor)
    except ValueError as exc:
        logger.warning("falha_parse_metric", extra={"metric": nome, "valor": valor, "erro": str(exc)})
        return None


# mapping de chave-placeholder → (campo_destino, fonte_opcional)
# fonte=None significa campo de destaque na tabela snapshots
# fonte="meta"/"google"/"ga4"/"painel" vai para metricas_detalhadas[fonte]
_MAPA_HANDLER = {
    # Destaque (colunas tipadas)
    "{{fat_sem}}": ("faturamento", None),
    "{{inv_sem}}": ("investimento", None),
    "{{roas}}": ("roas", None),
    "{{cpa}}": ("cpa", None),
    "{{vendas}}": ("vendas", None),
    "{{leads}}": ("leads", None),
    # Variações
    "{{fat_sem_var}}": ("faturamento_var_pct", None),
    "{{roas_var}}": ("roas_var_pct", None),
    # Meta
    "{{fat_face}}": ("faturamento", "meta"),
    "{{inv_face}}": ("investimento", "meta"),
    "{{roas_face}}": ("roas", "meta"),
    "{{cpa_face}}": ("cpa", "meta"),
    "{{vendas_face}}": ("vendas", "meta"),
    # Google
    "{{fat_goog}}": ("faturamento", "google"),
    "{{inv_goog}}": ("investimento", "google"),
    "{{roas_goog}}": ("roas", "google"),
    "{{cpa_goog}}": ("cpa", "google"),
    "{{vendas_goog}}": ("vendas", "google"),
    # GA4
    "{{ses_ga}}": ("sessoes", "ga4"),
    "{{ses_eng_ga}}": ("sessoes_engajadas", "ga4"),
    "{{taxa_eng_ga}}": ("taxa_engajamento", "ga4"),
}

_INTEGER_CAMPOS = {"vendas", "leads", "sessoes", "sessoes_engajadas"}


def map_handler_dados(dados: dict[str, str]) -> dict:
    """Converte dict do handler (placeholders PT-BR) em dict tipado para Snapshot."""
    resultado: dict = {"metricas_detalhadas": {}, "raw_dados": dict(dados)}

    for chave, valor in dados.items():
        mapping = _MAPA_HANDLER.get(chave)
        if mapping is None:
            continue
        campo, fonte = mapping
        parsed = parse_metric(chave, valor)
        if parsed is None:
            continue
        if campo in _INTEGER_CAMPOS:
            parsed = int(parsed)
        if fonte is None:
            resultado[campo] = parsed
        else:
            resultado["metricas_detalhadas"].setdefault(fonte, {})[campo] = parsed

    return resultado
