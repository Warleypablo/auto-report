from services.cliente_highlight import compute_highlight


def _row(mes: str, fat: float | None = None, roas: float | None = None,
         fat_var: float | None = None):
    return {
        "mes": mes,
        "faturamento": fat,
        "roas": roas,
        "investimento": None,
        "cpa": None,
        "leads": None,
        "vendas": None,
        "faturamento_var_pct": fat_var,
        "roas_var_pct": None,
        "periodo_inicio": "",
        "periodo_fim": "",
    }


def test_returns_none_when_timeline_empty():
    assert compute_highlight([]) is None


def test_returns_none_when_less_than_six_months():
    tl = [_row(f"2026-0{m}", roas=3.0) for m in range(1, 6)]
    assert compute_highlight(tl) is None


def test_best_roas_window_when_last_is_max_in_12m():
    # 12 meses, último com ROAS maior
    tl = [_row(f"2025-{m:02d}", roas=2.0) for m in range(6, 13)] + \
         [_row(f"2026-{m:02d}", roas=2.5) for m in range(1, 5)] + \
         [_row("2026-05", roas=4.2)]
    h = compute_highlight(tl)
    assert h is not None
    assert h["type"] == "best_roas_window"
    assert h["metric"] == "roas"
    assert h["value"] == 4.2
    assert h["period_months"] == 12
    assert "ROAS" in h["message"]


def test_best_revenue_when_roas_not_best_but_revenue_is():
    # Último mês com ROAS médio mas maior faturamento
    tl = [_row(f"2025-{m:02d}", fat=1000.0, roas=4.0) for m in range(6, 13)] + \
         [_row(f"2026-{m:02d}", fat=1500.0, roas=4.0) for m in range(1, 5)] + \
         [_row("2026-05", fat=2000.0, roas=3.5)]
    h = compute_highlight(tl)
    assert h is not None
    assert h["type"] == "best_revenue_window"
    assert h["metric"] == "faturamento"
    assert h["value"] == 2000.0


def test_growth_vs_prev_when_no_window_best():
    # ROAS e faturamento estáveis exceto crescimento de 20% no último
    tl = [_row(f"2025-{m:02d}", fat=2000.0, roas=4.0) for m in range(6, 13)] + \
         [_row(f"2026-{m:02d}", fat=2000.0, roas=4.0) for m in range(1, 5)] + \
         [_row("2026-05", fat=1700.0, roas=4.0, fat_var=20.0)]
    h = compute_highlight(tl)
    assert h is not None
    assert h["type"] == "growth_vs_prev"
    assert h["value"] == 20.0


def test_returns_none_when_nothing_remarkable():
    tl = [_row(f"2025-{m:02d}", fat=2000.0, roas=4.0) for m in range(6, 13)] + \
         [_row(f"2026-{m:02d}", fat=2000.0, roas=4.0) for m in range(1, 6)]
    assert compute_highlight(tl) is None
