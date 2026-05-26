"""Compute o 'destaque do mês' para a splash do cliente.

Toda a heurística é pura — opera sobre a lista de dicts retornada por
`build_timeline` (services/metricas.py). Sem I/O.
"""
from __future__ import annotations

NOMES_MES = [
    "Janeiro", "Fevereiro", "Março", "Abril", "Maio", "Junho",
    "Julho", "Agosto", "Setembro", "Outubro", "Novembro", "Dezembro",
]


def _mes_pt(mes_yyyymm: str) -> str:
    """'2026-05' -> 'Maio'."""
    try:
        return NOMES_MES[int(mes_yyyymm[5:7]) - 1]
    except (ValueError, IndexError):
        return mes_yyyymm


def compute_highlight(timeline: list[dict]) -> dict | None:
    """Calcula o highlight do último ponto da timeline.

    timeline: lista ordenada cronologicamente (antigo → recente), mesmo
    formato que `build_timeline` retorna.

    Retorna dict com keys: type, metric, value, period_months, message
    ou None se nada relevante.
    """
    if not timeline or len(timeline) < 6:
        return None

    janela = timeline[-12:]
    atual = timeline[-1]
    mes_label = _mes_pt(atual["mes"])

    roas_values = [r["roas"] for r in janela if r["roas"] is not None]
    if (
        atual["roas"] is not None
        and roas_values
        and atual["roas"] == max(roas_values)
        and len(roas_values) >= 6
        and roas_values.count(atual["roas"]) == 1
    ):
        return {
            "type": "best_roas_window",
            "metric": "roas",
            "value": atual["roas"],
            "period_months": len(janela),
            "message": f"{mes_label} foi seu melhor mês em ROAS dos últimos {len(janela)} meses.",
        }

    fat_values = [r["faturamento"] for r in janela if r["faturamento"] is not None]
    if (
        atual["faturamento"] is not None
        and fat_values
        and atual["faturamento"] == max(fat_values)
        and len(fat_values) >= 6
        and fat_values.count(atual["faturamento"]) == 1
    ):
        return {
            "type": "best_revenue_window",
            "metric": "faturamento",
            "value": atual["faturamento"],
            "period_months": len(janela),
            "message": f"{mes_label} foi seu melhor mês em faturamento dos últimos {len(janela)} meses.",
        }

    fat_var = atual.get("faturamento_var_pct")
    if fat_var is not None and fat_var >= 15.0:
        return {
            "type": "growth_vs_prev",
            "metric": "faturamento",
            "value": fat_var,
            "period_months": 1,
            "message": f"+{fat_var:.0f}% em faturamento vs. mês anterior.",
        }

    return None
